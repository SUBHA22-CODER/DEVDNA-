"""Static architecture discovery for Python projects using the standard `ast` module.

Output: a list of components and edges. Every edge carries evidence
(file, line, redacted snippet) and a classification:

  confirmed - the relationship is directly visible in the source
              (e.g. `sqlite3.connect(...)`, a decorator `@router.get("/x")`).
  inferred  - the relationship relies on a heuristic (e.g. a variable's type
              guessed from its assignment, a test-client URL matched to a route).

Anything the analyzer cannot resolve is counted in `coverage.unresolved_calls`
rather than guessed. Dynamic dispatch, reflection, monkeypatching, configuration-
driven wiring and inheritance across modules are NOT modelled.
"""
from __future__ import annotations

import ast
import builtins
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from app.analyzer.ingest import scan_tree
from app.analyzer.redact import find_secrets, redact

BUILTIN_NAMES = set(dir(builtins))
HTTP_VERBS = {"get", "post", "put", "patch", "delete", "options", "head"}
ROUTE_DECORATORS = HTTP_VERBS | {"route", "api_route", "websocket"}

DB_CALLS = {
    "sqlite3.connect": "sqlite",
    "sqlalchemy.create_engine": "sqlalchemy",
    "sqlalchemy.ext.asyncio.create_async_engine": "sqlalchemy",
    "psycopg2.connect": "postgresql",
    "psycopg.connect": "postgresql",
    "asyncpg.connect": "postgresql",
    "asyncpg.create_pool": "postgresql",
    "pymysql.connect": "mysql",
    "mysql.connector.connect": "mysql",
    "pymongo.MongoClient": "mongodb",
    "motor.motor_asyncio.AsyncIOMotorClient": "mongodb",
    "redis.Redis": "redis",
    "redis.StrictRedis": "redis",
    "redis.from_url": "redis",
}
HTTP_FUNCS = {f"{lib}.{v}" for lib in ("httpx", "requests") for v in HTTP_VERBS | {"request", "stream"}}
HTTP_FUNCS |= {"urllib.request.urlopen", "urllib3.request"}
HTTP_CLIENT_CTORS = {"httpx.Client", "httpx.AsyncClient", "requests.Session", "requests.session", "aiohttp.ClientSession", "urllib3.PoolManager"}
APP_CTORS = {"fastapi.FastAPI": "fastapi", "flask.Flask": "flask"}
ROUTER_CTORS = {"fastapi.APIRouter": "fastapi", "flask.Blueprint": "flask"}
THREAD_CTORS = {"threading.Thread", "multiprocessing.Process", "concurrent.futures.ThreadPoolExecutor"}
FRAMEWORK_IMPORTS = {
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django", "sqlalchemy": "SQLAlchemy", "sqlite3": "sqlite3",
    "httpx": "httpx", "requests": "requests", "celery": "Celery", "pytest": "pytest", "pydantic": "Pydantic",
    "redis": "Redis", "pymongo": "MongoDB", "psycopg2": "PostgreSQL", "aiohttp": "aiohttp",
}
SQL_RE = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|REPLACE)\b", re.I)


# --------------------------------------------------------------------------- helpers
def dotted(node: ast.AST) -> list[str] | None:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + [node.attr] if base else None
    return None


def const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def path_template(node: ast.AST | None) -> str | None:
    """String literal or f-string -> template with {x} placeholders."""
    s = const_str(node)
    if s is not None:
        return s
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            else:
                out.append("{x}")
        return "".join(out)
    return None


def handler_names(h: ast.ExceptHandler) -> list[str]:
    if h.type is None:
        return ["*"]
    elts = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
    return [".".join(dotted(e) or ["?"]) for e in elts]


def raised_names(body: list[ast.stmt]) -> set[str]:
    out = set()
    for stmt in body:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Raise) and n.exc is not None:
                target = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
                d = dotted(target)
                if d:
                    out.add(d[-1])
    return out


def has_raise(body: list[ast.stmt]) -> bool:
    return any(isinstance(n, ast.Raise) for stmt in body for n in ast.walk(stmt))


def norm_path(p: str) -> str:
    p = p.split("?")[0]
    if not p.startswith("/"):
        p = "/" + p
    p = re.sub(r"/+", "/", p)
    return p.rstrip("/") or "/"


def paths_match(route: str, called: str) -> bool:
    a, b = norm_path(route).split("/"), norm_path(called).split("/")
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y or (x.startswith("{") and x.endswith("}")) or (y.startswith("{") and y.endswith("}")):
            continue
        return False
    return True


# --------------------------------------------------------------------------- data
@dataclass
class FuncCtx:
    id: str
    qual: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    cls: str | None = None
    local_types: dict = field(default_factory=dict)
    local_env: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)  # (Call node, tries)
    env_reads: list = field(default_factory=list)  # (var, line, has_default, tries)
    raises: set = field(default_factory=set)


@dataclass
class ModuleInfo:
    name: str
    rel: str
    tree: ast.Module
    lines: list[str]
    is_test: bool
    functions: dict = field(default_factory=dict)  # qual -> FuncCtx
    classes: dict = field(default_factory=dict)  # name -> ClassDef
    bindings: dict = field(default_factory=dict)  # local name -> fq dotted
    instances: dict = field(default_factory=dict)  # module var -> ast.Call
    routers: dict = field(default_factory=dict)  # var -> {kind, framework, prefix, line, call}
    module_env: dict = field(default_factory=dict)  # const name -> env var
    class_attr_types: dict = field(default_factory=dict)  # cls -> {attr: (kind, value)}
    class_attr_env: dict = field(default_factory=dict)  # cls -> {attr: VAR}
    class_bases: dict = field(default_factory=dict)


class Analyzer:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.modules: dict[str, ModuleInfo] = {}
        self.components: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}
        self.parse_errors: list[dict] = []
        self.secret_hits: list[dict] = []
        self.frameworks: set[str] = set()
        self.third_party: set[str] = set()
        self.stats = {"resolved_calls": 0, "unresolved_calls": 0, "library_calls": 0, "functions": 0, "classes": 0}
        self.http_findings: list[dict] = []
        self.broad_excepts: list[dict] = []
        self.env_required: list[dict] = []

    # ------------------------------------------------------------- utilities
    def snippet(self, mod: ModuleInfo, line: int | None) -> str:
        if not line or line > len(mod.lines):
            return ""
        text, _ = redact(mod.lines[line - 1].strip())
        return text[:220]

    def ev(self, mod: ModuleInfo, line: int | None, detail: str = "", **extra) -> dict:
        return {"file": mod.rel, "line": line, "snippet": self.snippet(mod, line), "detail": detail, **extra}

    def add_component(self, cid: str, ctype: str, name: str, file: str | None = None, line: int | None = None, **data):
        if cid not in self.components:
            self.components[cid] = {"id": cid, "type": ctype, "name": name, "file": file, "line": line, "data": data}
        else:
            self.components[cid]["data"].update({k: v for k, v in data.items() if v is not None})
        return self.components[cid]

    def add_edge(self, source: str, target: str, etype: str, classification: str, evidence: dict, guard: list | None = None):
        if source == target:
            return
        eid = f"{etype}|{source}|{target}"
        e = self.edges.get(eid)
        if e is None:
            e = self.edges[eid] = {"id": eid, "source": source, "target": target, "type": etype,
                                   "classification": classification, "evidence": [], "call_sites": []}
        if classification == "confirmed":
            e["classification"] = "confirmed"
        if len(e["evidence"]) < 8:
            e["evidence"].append(evidence)
        e["call_sites"].append({"line": evidence.get("line"), "file": evidence.get("file"), "tries": guard or []})

    # ------------------------------------------------------------- pipeline
    def run(self, progress=None) -> dict:
        def step(name, frac):
            if progress:
                progress(name, frac)

        step("Scanning files", 0.05)
        tree = scan_tree(self.root)
        py_files = [f for f in tree["files"] if f.endswith(".py")]

        step("Parsing Python sources", 0.15)
        for rel in py_files:
            self._load_module(rel)

        step("Indexing symbols", 0.3)
        for mod in self.modules.values():
            self._index_module(mod)

        step("Resolving routes and application wiring", 0.45)
        self._resolve_app_wiring()

        step("Resolving calls and resource usage", 0.6)
        for mod in self.modules.values():
            if not mod.is_test:
                for fn in mod.functions.values():
                    self._analyse_function(mod, fn)

        step("Mapping tests to components", 0.75)
        self._analyse_tests()

        step("Reading dependency manifests", 0.85)
        manifests = self._read_manifests(tree["manifests"])

        routes = [c for c in self.components.values() if c["type"] == "route"]
        tested_routes = {e["target"] for e in self.edges.values() if e["type"] == "exercises"}
        total_calls = self.stats["resolved_calls"] + self.stats["unresolved_calls"]
        coverage = {
            "python_files": len(py_files),
            "parsed_files": len(self.modules),
            "parse_errors": self.parse_errors,
            "functions": self.stats["functions"],
            "classes": self.stats["classes"],
            "resolved_calls": self.stats["resolved_calls"],
            "unresolved_calls": self.stats["unresolved_calls"],
            "library_calls": self.stats["library_calls"],
            "call_resolution_rate": round(self.stats["resolved_calls"] / total_calls, 3) if total_calls else None,
            "routes": len(routes),
            "routes_with_tests": len([r for r in routes if r["id"] in tested_routes]),
            "tests": len([c for c in self.components.values() if c["type"] == "test"]),
        }
        languages = tree["languages"]
        return {
            "components": list(self.components.values()),
            "edges": [{k: v for k, v in e.items()} for e in self.edges.values()],
            "scan": {
                "file_count": tree["file_count"],
                "languages": languages,
                "analysed_languages": ["Python"] if py_files else [],
                "manifests": tree["manifests"],
                "skipped_sensitive": len(tree["skipped_sensitive"]),
                "skipped_large": tree["skipped_large"],
            },
            "frameworks": sorted(self.frameworks),
            "third_party_imports": sorted(self.third_party),
            "dependencies": manifests,
            "coverage": coverage,
            "secret_hits": self.secret_hits,
            "signals": {
                "http_calls": self.http_findings,
                "broad_excepts": self.broad_excepts,
                "env_required": self.env_required,
            },
        }

    # ------------------------------------------------------------- loading
    def _module_name(self, rel: str) -> str:
        parts = rel[:-3].split("/")
        if parts[0] == "src" and len(parts) > 1:
            parts = parts[1:]
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) or "__root__"

    def _load_module(self, rel: str):
        path = self.root / rel
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            self.parse_errors.append({"file": rel, "line": exc.lineno, "error": exc.msg})
            return
        name = self._module_name(rel)
        base = rel.split("/")[-1]
        is_test = base.startswith("test_") or base.endswith("_test.py") or base == "conftest.py"
        mod = ModuleInfo(name=name, rel=rel, tree=tree, lines=source.splitlines(), is_test=is_test)
        self.modules[name] = mod
        for hit in find_secrets(source):
            self.secret_hits.append({"file": rel, "line": hit["line"], "snippet": self.snippet(mod, hit["line"])})

    def _resolve_relative(self, mod: ModuleInfo, level: int, module: str | None) -> str:
        pkg = mod.name.split(".")
        if not mod.rel.endswith("__init__.py"):
            pkg = pkg[:-1]
        if level > 1:
            pkg = pkg[: len(pkg) - (level - 1)]
        return ".".join([p for p in pkg + ([module] if module else []) if p])

    # ------------------------------------------------------------- indexing
    def _index_module(self, mod: ModuleInfo):
        if not mod.is_test:
            self.add_component(f"module:{mod.name}", "module", mod.name, mod.rel, 1)
        for node in mod.tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        mod.bindings[a.asname] = a.name
                    else:
                        mod.bindings[a.name.split(".")[0]] = a.name.split(".")[0]
                    self._note_import(mod, a.name, node.lineno)
            elif isinstance(node, ast.ImportFrom):
                base = self._resolve_relative(mod, node.level, node.module) if node.level else (node.module or "")
                for a in node.names:
                    if a.name == "*":
                        continue
                    mod.bindings[a.asname or a.name] = f"{base}.{a.name}" if base else a.name
                self._note_import(mod, base, node.lineno)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add_function(mod, node, None)
            elif isinstance(node, ast.ClassDef):
                mod.classes[node.name] = node
                mod.class_bases[node.name] = [".".join(dotted(b) or []) for b in node.bases]
                if not mod.is_test:
                    self.stats["classes"] += 1
                    cid = f"class:{mod.name}.{node.name}"
                    self.add_component(cid, "class", node.name, mod.rel, node.lineno, module=mod.name)
                    self.add_edge(f"module:{mod.name}", cid, "contains", "confirmed", self.ev(mod, node.lineno))
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self._add_function(mod, item, node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                for t in targets:
                    if isinstance(t, ast.Name) and value is not None:
                        if isinstance(value, ast.Call):
                            mod.instances[t.id] = value
                        var = self._env_var_of(mod, value, None)
                        if var:
                            mod.module_env[t.id] = var[0]

    def _note_import(self, mod: ModuleInfo, name: str, line: int):
        top = name.split(".")[0] if name else ""
        if top in FRAMEWORK_IMPORTS:
            self.frameworks.add(FRAMEWORK_IMPORTS[top])
        if mod.is_test:
            return
        internal = self._internal_module(name)
        if internal and internal != mod.name:
            self.add_edge(f"module:{mod.name}", f"module:{internal}", "imports", "confirmed", self.ev(mod, line))
        elif not internal and top and top not in {"__future__"}:
            self.third_party.add(top)

    def _internal_module(self, name: str) -> str | None:
        parts = name.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in self.modules:
                return cand
        return None

    def _add_function(self, mod: ModuleInfo, node, cls: str | None):
        qual = f"{cls}.{node.name}" if cls else node.name
        fid = f"func:{mod.name}.{qual}"
        ctx = FuncCtx(id=fid, qual=qual, node=node, cls=cls)
        mod.functions[qual] = ctx
        if mod.is_test:
            return
        self.stats["functions"] += 1
        self.add_component(fid, "function", qual, mod.rel, node.lineno, module=mod.name,
                           is_async=isinstance(node, ast.AsyncFunctionDef), cls=cls,
                           args=[a.arg for a in node.args.args if a.arg not in ("self", "cls")])
        parent = f"class:{mod.name}.{cls}" if cls else f"module:{mod.name}"
        self.add_edge(parent, fid, "contains", "confirmed", self.ev(mod, node.lineno))
        if cls:
            self._index_self_attrs(mod, cls, node)

    def _index_self_attrs(self, mod: ModuleInfo, cls: str, node):
        types = mod.class_attr_types.setdefault(cls, {})
        envs = mod.class_attr_env.setdefault(cls, {})
        for n in ast.walk(node):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                        if isinstance(n.value, ast.Call):
                            types[t.attr] = ("call", n.value)
                        var = self._env_var_of(mod, n.value, None)
                        if var:
                            envs[t.attr] = var[0]

    # ------------------------------------------------------------- symbol resolution
    def resolve_symbol(self, fq: str, depth: int = 0):
        """fq dotted name -> (kind, value). kinds: func, class, module, instance, lib."""
        if depth > 6:
            return None
        parts = fq.split(".")
        for i in range(len(parts), 0, -1):
            modname = ".".join(parts[:i])
            if modname not in self.modules:
                continue
            mod = self.modules[modname]
            rest = parts[i:]
            if not rest:
                return ("module", modname)
            head = rest[0]
            if head in mod.classes:
                cls_fq = f"{modname}.{head}"
                if len(rest) == 1:
                    return ("class", cls_fq)
                if len(rest) == 2:
                    m = self.find_method(cls_fq, rest[1])
                    return ("func", m) if m else None
                return None
            if head in mod.functions and len(rest) == 1:
                return ("func", mod.functions[head].id)
            if head in mod.instances:
                inst = self.class_of_call(mod, mod.instances[head], None)
                if inst and inst[0] == "class":
                    if len(rest) == 1:
                        return ("instance", inst[1])
                    if len(rest) == 2:
                        m = self.find_method(inst[1], rest[1])
                        return ("func_inferred", m) if m else None
                if inst and inst[0] == "lib":
                    return ("lib_instance", inst[1])
                return None
            if head in mod.bindings:
                return self.resolve_symbol(".".join([mod.bindings[head]] + rest[1:]), depth + 1)
            return None
        return ("lib", fq)

    def find_method(self, cls_fq: str, name: str, depth: int = 0) -> str | None:
        modname, _, cls = cls_fq.rpartition(".")
        mod = self.modules.get(modname)
        if not mod or depth > 4:
            return None
        if f"{cls}.{name}" in mod.functions:
            return mod.functions[f"{cls}.{name}"].id
        for base in mod.class_bases.get(cls, []):
            r = self.resolve_name(mod, base.split("."), None)
            if r and r[0] == "class":
                m = self.find_method(r[1], name, depth + 1)
                if m:
                    return m
        return None

    def resolve_name(self, mod: ModuleInfo, parts: list[str], fn: FuncCtx | None):
        """Resolve a dotted reference used inside `mod` (and optionally function `fn`)."""
        head = parts[0]
        if fn is not None and head in fn.local_types:
            kind, val = fn.local_types[head]
            if kind == "class" and len(parts) == 2:
                m = self.find_method(val, parts[1])
                return ("func_inferred", m) if m else None
            if kind == "lib" and len(parts) >= 2:
                return ("lib_method", val, parts[-1])
            return None
        if head in mod.functions and len(parts) == 1:
            return ("func", mod.functions[head].id)
        if head in mod.classes:
            cls_fq = f"{mod.name}.{head}"
            if len(parts) == 1:
                return ("class", cls_fq)
            m = self.find_method(cls_fq, parts[1]) if len(parts) == 2 else None
            return ("func", m) if m else None
        if head in mod.instances and head not in mod.bindings:
            inst = self.class_of_call(mod, mod.instances[head], None)
            if inst and inst[0] == "class" and len(parts) == 2:
                m = self.find_method(inst[1], parts[1])
                return ("func_inferred", m) if m else None
            if inst and inst[0] == "lib" and len(parts) >= 2:
                return ("lib_method", inst[1], parts[-1])
            if inst and len(parts) == 1:
                return ("instance", inst[1])
            return None
        if head in mod.bindings:
            fq = ".".join([mod.bindings[head]] + parts[1:])
            r = self.resolve_symbol(fq)
            if r is None:
                return None
            if r[0] == "lib_instance" and len(parts) >= 2:
                return ("lib_method", r[1], parts[-1])
            return r
        return None

    def class_of_call(self, mod: ModuleInfo, call: ast.Call, fn: FuncCtx | None):
        parts = dotted(call.func)
        if not parts:
            return None
        r = self.resolve_name(mod, parts, fn)
        if r and r[0] == "class":
            return ("class", r[1])
        if r and r[0] == "lib":
            return ("lib", r[1])
        return None

    def _env_var_of(self, mod: ModuleInfo, node, fn: FuncCtx | None):
        """If `node` reads an environment variable, return (VAR, has_default)."""
        if isinstance(node, ast.Subscript):
            base = dotted(node.value)
            if base and self._is_environ(mod, base):
                key = const_str(node.slice)
                if key:
                    return (key, False)
        if isinstance(node, ast.Call):
            parts = dotted(node.func)
            if parts:
                fq = self._lib_fq(mod, parts)
                if fq in ("os.getenv", "os.environ.get") and node.args:
                    key = const_str(node.args[0])
                    if key:
                        return (key, len(node.args) > 1 or any(k.arg == "default" for k in node.keywords))
        return None

    def _is_environ(self, mod: ModuleInfo, parts: list[str]) -> bool:
        return self._lib_fq(mod, parts) == "os.environ"

    def _lib_fq(self, mod: ModuleInfo, parts: list[str]) -> str | None:
        head = parts[0]
        if head in mod.bindings and not self._internal_module(mod.bindings[head]):
            return ".".join([mod.bindings[head]] + parts[1:])
        return None

    # ------------------------------------------------------------- application wiring
    def _resolve_app_wiring(self):
        self.include_map: dict[str, dict] = {}
        self.apps: dict[str, dict] = {}
        # apps and routers
        for mod in self.modules.values():
            if mod.is_test:
                continue
            for var, call in mod.instances.items():
                r = self.class_of_call(mod, call, None)
                if not r or r[0] != "lib":
                    continue
                fq = r[1]
                if fq in APP_CTORS:
                    app_id = f"app:{mod.name}.{var}"
                    self.apps[f"{mod.name}.{var}"] = {"id": app_id}
                    mod.routers[var] = {"kind": "app", "framework": APP_CTORS[fq], "prefix": "", "line": call.lineno}
                    self.add_component(app_id, "app", f"{var} ({APP_CTORS[fq]})", mod.rel, call.lineno,
                                       framework=APP_CTORS[fq], module=mod.name)
                    self.add_edge(f"module:{mod.name}", app_id, "contains", "confirmed", self.ev(mod, call.lineno))
                    for kw in call.keywords:
                        if kw.arg == "lifespan":
                            target = self.resolve_name(mod, dotted(kw.value) or ["?"], None)
                            if target and target[0] == "func":
                                self.add_edge(app_id, target[1], "runs_on_startup", "confirmed",
                                              self.ev(mod, call.lineno, "FastAPI lifespan handler"))
                elif fq in ROUTER_CTORS:
                    prefix = ""
                    for kw in call.keywords:
                        if kw.arg in ("prefix", "url_prefix"):
                            prefix = const_str(kw.value) or ""
                    mod.routers[var] = {"kind": "router", "framework": ROUTER_CTORS[fq], "prefix": prefix, "line": call.lineno}
        # include_router / register_blueprint / on_event
        for mod in self.modules.values():
            if mod.is_test:
                continue
            for n in ast.walk(mod.tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and \
                        n.func.attr in ("include_router", "register_blueprint") and n.args:
                    owner = dotted(n.func.value)
                    inc = dotted(n.args[0])
                    if not owner or not inc:
                        continue
                    owner_fq = self._router_fq(mod, owner)
                    inc_fq = self._router_fq(mod, inc)
                    prefix = ""
                    for kw in n.keywords:
                        if kw.arg in ("prefix", "url_prefix"):
                            prefix = const_str(kw.value) or ""
                    if owner_fq and inc_fq:
                        self.include_map[inc_fq] = {"owner": owner_fq, "prefix": prefix, "ev": self.ev(mod, n.lineno, "router included")}
        # routes from decorators
        for mod in self.modules.values():
            if mod.is_test:
                continue
            for fn in mod.functions.values():
                for dec in fn.node.decorator_list:
                    self._route_from_decorator(mod, fn, dec)

    def _router_fq(self, mod: ModuleInfo, parts: list[str]) -> str | None:
        if len(parts) == 1 and parts[0] in mod.routers:
            return f"{mod.name}.{parts[0]}"
        if parts[0] in mod.bindings:
            fq = ".".join([mod.bindings[parts[0]]] + parts[1:])
            modname, _, var = fq.rpartition(".")
            if modname in self.modules and var in self.modules[modname].routers:
                return fq
            if fq in self.modules:  # e.g. `from app.routes import products` then products.router
                return None
        return None

    def _mount(self, router_fq: str) -> tuple[str, str | None, dict | None]:
        """Follow include_router chain -> (accumulated prefix, app fq, evidence)."""
        prefix, ev, seen = "", None, set()
        cur = router_fq
        while cur not in self.apps and cur in self.include_map and cur not in seen:
            seen.add(cur)
            inc = self.include_map[cur]
            prefix = inc["prefix"] + prefix
            ev = ev or inc["ev"]
            cur = inc["owner"]
        return prefix, (cur if cur in self.apps else None), ev

    def _route_from_decorator(self, mod: ModuleInfo, fn: FuncCtx, dec):
        if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
            return
        attr = dec.func.attr
        owner = dotted(dec.func.value)
        if not owner:
            return
        router_fq = self._router_fq(mod, owner)
        if attr == "on_event" and router_fq in self.apps:
            if const_str(dec.args[0] if dec.args else None) == "startup":
                self.add_edge(self.apps[router_fq]["id"], fn.id, "runs_on_startup", "confirmed",
                              self.ev(mod, dec.lineno, "startup event handler"))
            return
        if attr not in ROUTE_DECORATORS or router_fq is None:
            return
        rmod_name, _, rvar = router_fq.rpartition(".")
        router = self.modules[rmod_name].routers[rvar]
        path = const_str(dec.args[0]) if dec.args else None
        for kw in dec.keywords:
            if kw.arg == "path":
                path = const_str(kw.value)
        if path is None:
            return
        methods = [attr.upper()] if attr in HTTP_VERBS else []
        if attr in ("route", "api_route"):
            for kw in dec.keywords:
                if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    methods = [str(const_str(e)).upper() for e in kw.value.elts if const_str(e)]
            methods = methods or ["GET"]
        if attr == "websocket":
            methods = ["WS"]
        include_prefix, app_fq, inc_ev = ("", router_fq, None) if router_fq in self.apps else self._mount(router_fq)
        full = norm_path(include_prefix + router["prefix"] + path)
        for m in methods:
            rid = f"route:{m} {full}"
            self.add_component(rid, "route", f"{m} {full}", mod.rel, dec.lineno, method=m, path=full,
                               framework=router["framework"], handler=fn.id)
            self.add_edge(rid, fn.id, "handled_by", "confirmed", self.ev(mod, dec.lineno, f"@{'.'.join(owner)}.{attr} decorator"))
            if app_fq:
                cls = "confirmed" if (router_fq in self.apps or inc_ev) else "inferred"
                self.add_edge(rid, self.apps[app_fq]["id"], "served_by", cls,
                              inc_ev or self.ev(mod, dec.lineno, "route registered on application"))
            elif len(self.apps) == 1:
                only = next(iter(self.apps.values()))["id"]
                self.add_edge(rid, only, "served_by", "inferred", self.ev(mod, dec.lineno, "single application in project; router inclusion not statically resolved"))
        # FastAPI Depends(...) in the handler signature
        defaults = list(fn.node.args.defaults) + [d for d in fn.node.args.kw_defaults if d is not None]
        for d in defaults:
            if isinstance(d, ast.Call) and (dotted(d.func) or [""])[-1] == "Depends" and d.args:
                r = self.resolve_name(mod, dotted(d.args[0]) or ["?"], None)
                if r and r[0] in ("func", "func_inferred"):
                    self.add_edge(fn.id, r[1], "calls", "inferred", self.ev(mod, fn.node.lineno, "FastAPI Depends()"))

    # ------------------------------------------------------------- function bodies
    def _collect(self, mod: ModuleInfo, fn: FuncCtx):
        """Walk the function body, tracking enclosing try/except handlers for each call."""
        root = fn.node

        def walk(node, tries):
            if node is not root and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                return
            if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                handlers = [{"names": handler_names(h), "reraises": has_raise(h.body), "line": h.lineno} for h in node.handlers]
                for h in node.handlers:
                    names = handler_names(h)
                    swallow = all(isinstance(s, (ast.Pass, ast.Expr, ast.Continue)) for s in h.body)
                    if ("*" in names or "Exception" in names or "BaseException" in names) and swallow and not has_raise(h.body):
                        self.broad_excepts.append({"component": fn.id, **self.ev(mod, h.lineno)})
                for s in node.body:
                    walk(s, tries + [handlers])
                for h in node.handlers:
                    for s in h.body:
                        walk(s, tries)
                for s in node.orelse + node.finalbody:
                    walk(s, tries)
                return
            if isinstance(node, ast.Call):
                fn.calls.append((node, tries))
                var = self._env_var_of(mod, node, fn)
                if var:
                    fn.env_reads.append((var[0], node.lineno, var[1], tries))
            elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                var = self._env_var_of(mod, node, fn)
                if var:
                    fn.env_reads.append((var[0], node.lineno, var[1], tries))
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name) and node.value is not None:
                        if isinstance(node.value, ast.Call):
                            r = self.class_of_call(mod, node.value, fn)
                            if r:
                                fn.local_types[t.id] = r
                        var = self._env_var_of(mod, node.value, fn)
                        if var:
                            fn.local_env[t.id] = var[0]
            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if isinstance(item.optional_vars, ast.Name) and isinstance(item.context_expr, ast.Call):
                        r = self.class_of_call(mod, item.context_expr, fn)
                        if r:
                            fn.local_types[item.optional_vars.id] = r
            for child in ast.iter_child_nodes(node):
                walk(child, tries)

        for stmt in root.body:
            walk(stmt, [])
        fn.raises = raised_names(root.body)

    def _analyse_function(self, mod: ModuleInfo, fn: FuncCtx):
        self._collect(mod, fn)
        comp = self.components[fn.id]
        comp["data"]["raises"] = sorted(fn.raises)
        sql = []
        for call, tries in fn.calls:
            self._handle_call(mod, fn, call, tries)
            if isinstance(call.func, ast.Attribute) and call.func.attr in ("execute", "executemany", "executescript") and call.args:
                s = const_str(call.args[0])
                if s and SQL_RE.match(s):
                    sql.append({"line": call.lineno, "statement": " ".join(s.split())[:160]})
        if sql:
            comp["data"]["sql"] = sql
        for var, line, has_default, tries in fn.env_reads:
            env_id = f"env:{var}"
            self.add_component(env_id, "env_var", var, None, None)
            guard = tries + ([[{"names": ["<default>"], "reraises": False, "line": line}]] if has_default else [])
            self.add_edge(fn.id, env_id, "reads_env", "confirmed",
                          self.ev(mod, line, "has default value" if has_default else "no default: missing value raises KeyError",
                                  has_default=has_default), guard)
            if not has_default:
                self.env_required.append({"var": var, "component": fn.id, **self.ev(mod, line)})
        # worker detection: classes whose methods start threads/processes
        if fn.cls:
            for call, _ in fn.calls:
                r = self.class_of_call(mod, call, fn)
                if r and r[0] == "lib" and r[1] in THREAD_CTORS:
                    cls_fq = f"{mod.name}.{fn.cls}"
                    wid = f"worker:{cls_fq}"
                    w = self.add_component(wid, "worker", f"{fn.cls} (background worker)", mod.rel,
                                           mod.classes[fn.cls].lineno, module=mod.name, cls=fn.cls, kind=r[1])
                    launchers = set(w["data"].get("launcher_methods", [])) | {fn.qual.split(".")[-1]}
                    w["data"]["launcher_methods"] = sorted(launchers)
                    self.add_edge(f"class:{cls_fq}", wid, "runs_worker", "confirmed", self.ev(mod, call.lineno, f"starts {r[1]}"))

    def _handle_call(self, mod: ModuleInfo, fn: FuncCtx, call: ast.Call, tries):
        parts = dotted(call.func)
        res = None
        if parts:
            if parts[0] == "self" and fn.cls:
                cls_fq = f"{mod.name}.{fn.cls}"
                if len(parts) == 2:
                    m = self.find_method(cls_fq, parts[1])
                    res = ("func", m) if m else None
                elif len(parts) == 3:
                    t = mod.class_attr_types.get(fn.cls, {}).get(parts[1])
                    if t:
                        r = self.class_of_call(mod, t[1], None)
                        if r and r[0] == "class":
                            m = self.find_method(r[1], parts[2])
                            res = ("func_inferred", m) if m else None
                        elif r and r[0] == "lib":
                            res = ("lib_method", r[1], parts[2])
            else:
                res = self.resolve_name(mod, parts, fn)
        elif isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Call):
            r = self.class_of_call(mod, call.func.value, fn)
            if r and r[0] == "class":
                m = self.find_method(r[1], call.func.attr)
                res = ("func_inferred", m) if m else None
            elif r and r[0] == "lib":
                res = ("lib_method", r[1], call.func.attr)

        if res is None:
            if parts and len(parts) == 1 and parts[0] not in BUILTIN_NAMES:
                self.stats["unresolved_calls"] += 1
            return
        kind = res[0]
        ev = self.ev(mod, call.lineno)
        if kind in ("func", "func_inferred") and res[1]:
            self.stats["resolved_calls"] += 1
            self.add_edge(fn.id, res[1], "calls", "confirmed" if kind == "func" else "inferred", ev, tries)
        elif kind == "class":
            self.stats["resolved_calls"] += 1
            init = self.find_method(res[1], "__init__")
            if init:
                self.add_edge(fn.id, init, "calls", "confirmed", {**ev, "detail": "constructor call"}, tries)
        elif kind == "lib":
            self.stats["library_calls"] += 1
            self._lib_call(mod, fn, call, res[1], tries, "confirmed")
        elif kind == "lib_method":
            self.stats["library_calls"] += 1
            base, method = res[1], res[2]
            if base in HTTP_CLIENT_CTORS and method in HTTP_VERBS | {"request", "stream", "send"}:
                self._http_call(mod, fn, call, f"{base}.{method}", tries, "inferred", client_ctor=None)
            elif base in DB_CALLS and method in ("connect", "execute", "begin", "cursor"):
                pass  # already covered by the constructor call

    def _lib_call(self, mod, fn, call, fq, tries, classification):
        if fq in DB_CALLS:
            engine = DB_CALLS[fq]
            db_id = f"database:{engine}"
            self.add_component(db_id, "database", f"{engine} database", None, None, engine=engine,
                               libraries=sorted(set(self.components.get(db_id, {}).get("data", {}).get("libraries", [])) | {fq.split('.')[0]}))
            self.add_edge(fn.id, db_id, "uses_database", classification, self.ev(mod, call.lineno, f"{fq}()"), tries)
        elif fq in HTTP_FUNCS:
            self._http_call(mod, fn, call, fq, tries, classification)

    def _http_call(self, mod, fn, call, fq, tries, classification, client_ctor=None):
        label, key = self._url_hint(mod, fn, call)
        ext_id = f"external:{key}"
        self.add_component(ext_id, "external_api", label, None, None, hint=key)
        self.add_edge(fn.id, ext_id, "calls_http", classification, self.ev(mod, call.lineno, f"{fq}()"), tries)
        has_timeout = any(k.arg == "timeout" for k in call.keywords)
        client_timeout = False
        if fn.cls and isinstance(call.func, ast.Attribute):
            attr_parts = dotted(call.func.value) or []
            if len(attr_parts) == 2 and attr_parts[0] == "self":
                t = mod.class_attr_types.get(fn.cls, {}).get(attr_parts[1])
                if t and any(k.arg == "timeout" for k in t[1].keywords):
                    client_timeout = True
        self.http_findings.append({"component": fn.id, "external": ext_id, "lib": fq, "timeout": has_timeout or client_timeout,
                                   "guarded": bool(tries), **self.ev(mod, call.lineno)})

    def _url_hint(self, mod: ModuleInfo, fn: FuncCtx, call: ast.Call) -> tuple[str, str]:
        url_node = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "url"), None)
        if url_node is not None:
            for n in ast.walk(url_node):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" and fn.cls:
                    var = mod.class_attr_env.get(fn.cls, {}).get(n.attr)
                    if var:
                        return f"External API ({var})", var
                if isinstance(n, ast.Name):
                    var = fn.local_env.get(n.id) or mod.module_env.get(n.id)
                    if var:
                        return f"External API ({var})", var
                s = const_str(n)
                if s and s.startswith(("http://", "https://")):
                    host = urlparse(s).hostname or "unknown-host"
                    return f"External API ({host})", host
        return f"External HTTP service ({mod.name})", f"unresolved.{mod.name}"

    # ------------------------------------------------------------- tests
    def _analyse_tests(self):
        fixtures: dict[str, list] = {}  # name -> [(mod, FuncCtx)]
        tests: list[tuple[ModuleInfo, FuncCtx]] = []
        for mod in self.modules.values():
            if not mod.is_test:
                continue
            for qual, fn in mod.functions.items():
                name = qual.split(".")[-1]
                is_fixture = any((dotted(d.func if isinstance(d, ast.Call) else d) or [""])[-1] == "fixture"
                                 for d in fn.node.decorator_list)
                if is_fixture:
                    fixtures.setdefault(name, []).append((mod, fn))
                elif name.startswith("test") and (fn.cls is None or fn.cls.startswith("Test")):
                    tests.append((mod, fn))
        routes = [c for c in self.components.values() if c["type"] == "route"]
        cache: dict[str, list] = {}

        def targets_of(mod: ModuleInfo, fn: FuncCtx) -> list:
            if fn.id in cache:
                return cache[fn.id]
            cache[fn.id] = []
            self._collect(mod, fn)
            out = []
            for call, _ in fn.calls:
                if isinstance(call.func, ast.Attribute) and call.func.attr in HTTP_VERBS and call.args:
                    tpl = path_template(call.args[0])
                    if tpl and tpl.startswith("/"):
                        method = call.func.attr.upper()
                        for r in routes:
                            if r["data"]["method"] == method and paths_match(r["data"]["path"], tpl):
                                out.append((r["id"], "exercises", "inferred", self.ev(mod, call.lineno, f"test client {method} {tpl}")))
                        continue
                parts = dotted(call.func)
                res = self.resolve_name(mod, parts, fn) if parts else None
                if res is None and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Call):
                    r = self.class_of_call(mod, call.func.value, fn)
                    if r and r[0] == "class":
                        m = self.find_method(r[1], call.func.attr)
                        res = ("func_inferred", m) if m else None
                if res and res[0] in ("func", "func_inferred") and res[1] and res[1] in self.components:
                    out.append((res[1], "calls", "confirmed" if res[0] == "func" else "inferred", self.ev(mod, call.lineno)))
                elif res and res[0] == "class":
                    init = self.find_method(res[1], "__init__")
                    if init:
                        out.append((init, "calls", "confirmed", self.ev(mod, call.lineno, "constructor call")))
            params = [a.arg for a in fn.node.args.args if a.arg not in ("self", "cls")]
            autouse = [n for n, defs in fixtures.items() for (_, f) in defs
                       if any(isinstance(d, ast.Call) and any(k.arg == "autouse" and getattr(k.value, "value", False) for k in d.keywords)
                              for d in f.node.decorator_list)]
            for p in dict.fromkeys(params + autouse):
                for fmod, ffn in fixtures.get(p, []):
                    if ffn is fn:
                        continue
                    for tgt, et, _, ev in targets_of(fmod, ffn):
                        out.append((tgt, et, "inferred", {**ev, "detail": f"via fixture '{p}': {ev.get('detail') or 'call'}"}))
            cache[fn.id] = out
            return out

        for mod, fn in tests:
            nodeid = f"{mod.rel}::{fn.qual.replace('.', '::')}"
            classname = mod.rel[:-3].replace("/", ".") + (f".{fn.cls}" if fn.cls else "")
            tid = f"test:{nodeid}"
            self.add_component(tid, "test", fn.qual, mod.rel, fn.node.lineno, nodeid=nodeid,
                               junit_key=f"{classname}::{fn.node.name}")
            for tgt, et, cls, ev in targets_of(mod, fn):
                self.add_edge(tid, tgt, et, cls, ev)

    # ------------------------------------------------------------- manifests
    def _read_manifests(self, manifests: list[str]) -> list[dict]:
        deps = []
        for rel in manifests:
            path = self.root / rel
            name = path.name
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if name == "requirements.txt":
                for line in text.splitlines():
                    line = line.split("#")[0].strip()
                    if line and not line.startswith("-"):
                        pkg = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]
                        deps.append({"name": pkg, "spec": line[len(pkg):].strip(), "manifest": rel})
            elif name == "pyproject.toml":
                try:
                    data = tomllib.loads(text)
                except tomllib.TOMLDecodeError:
                    continue
                for line in data.get("project", {}).get("dependencies", []):
                    pkg = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]
                    deps.append({"name": pkg, "spec": line[len(pkg):].strip(), "manifest": rel})
                for pkg, spec in data.get("tool", {}).get("poetry", {}).get("dependencies", {}).items():
                    deps.append({"name": pkg, "spec": str(spec), "manifest": rel})
            elif name == "package.json":
                import json
                try:
                    data = json.loads(text)
                except ValueError:
                    continue
                for section in ("dependencies", "devDependencies"):
                    for pkg, spec in (data.get(section) or {}).items():
                        deps.append({"name": pkg, "spec": spec, "manifest": rel})
        return deps


def analyse_project(root: Path, progress=None) -> dict:
    return Analyzer(root).run(progress)
