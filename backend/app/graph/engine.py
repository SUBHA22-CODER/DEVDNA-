"""DevDNA Neuro-Symbolic Failure Engine (NSFE).

Combines deterministic multi-relational graph propagation (symbolic layer) with
Gemma 4 failure impact reasoning, dynamic fault synthesis, and empirical reconciliation (neural layer).

Edge direction is "source depends on target" (A --calls--> B means A needs B).
When B fails, every node that can reach B through *propagating* edges may be affected.

CRITICALITY SCORE (0-100, structural heuristic - NOT a failure probability):

    criticality = 100 * (0.5 * blast + 0.3 * betweenness_norm + 0.2 * route_share)

    blast            = non-test dependents of the node / (non-test nodes - 1)
    betweenness_norm = betweenness centrality / max betweenness in the graph
    route_share      = HTTP routes that (transitively) depend on the node / total routes
"""
from __future__ import annotations

from collections import deque

import networkx as nx

PROPAGATING = {"calls", "handled_by", "served_by", "runs_on_startup", "uses_database", "calls_http", "reads_env", "exercises"}

SCENARIOS = {
    "db_unavailable": {
        "label": "Database unavailable",
        "target_types": ["database"],
        "exceptions": {"Error", "OperationalError", "DatabaseError", "InterfaceError", "SQLAlchemyError", "OSError", "ConnectionError"},
        "fault": "Every database connection attempt raises an OperationalError.",
    },
    "external_api_unavailable": {
        "label": "External API unavailable",
        "target_types": ["external_api"],
        "exceptions": {"HTTPError", "RequestError", "ConnectError", "TransportError", "TimeoutException", "RequestException",
                       "ConnectionError", "URLError", "OSError", "Timeout"},
        "fault": "Outbound HTTP transports raise a connection error before any request is sent.",
    },
    "missing_env_var": {
        "label": "Missing environment variable",
        "target_types": ["env_var"],
        "exceptions": {"KeyError", "LookupError", "<default>"},
        "fault": "The environment variable is removed from the process before every test.",
    },
    "worker_unavailable": {
        "label": "Background worker unavailable",
        "target_types": ["worker"],
        "exceptions": set(),
        "fault": "The worker's launch methods become no-ops, so the worker never starts.",
    },
}
GENERIC_EXCEPTIONS = {"*", "Exception", "BaseException"}


def build_graph(components: list[dict], edges: list[dict]) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for c in components:
        g.add_node(c["id"], **c)
    for e in edges:
        if e["source"] in g and e["target"] in g:
            g.add_edge(e["source"], e["target"], key=e["id"], **e)
    return g


def _prop_digraph(g: nx.MultiDiGraph) -> nx.DiGraph:
    d = nx.DiGraph()
    d.add_nodes_from(g.nodes)
    for u, v, data in g.edges(data=True):
        if data["type"] in PROPAGATING:
            d.add_edge(u, v)
    return d


def compute_metrics(g: nx.MultiDiGraph) -> dict[str, dict]:
    d = _prop_digraph(g)
    non_test = [n for n in d.nodes if g.nodes[n]["type"] != "test"]
    routes = [n for n in d.nodes if g.nodes[n]["type"] == "route"]
    sub = d.subgraph(non_test)
    betweenness = nx.betweenness_centrality(sub) if len(sub) > 2 else {n: 0.0 for n in sub}
    max_b = max(betweenness.values(), default=0) or 1.0
    metrics = {}
    for n in d.nodes:
        anc = nx.ancestors(d, n)
        dependents = [a for a in anc if g.nodes[a]["type"] != "test"]
        tests = [a for a in anc if g.nodes[a]["type"] == "test"]
        route_dep = [a for a in anc if g.nodes[a]["type"] == "route"]
        blast = len(dependents) / max(1, len(non_test) - 1)
        b = betweenness.get(n, 0.0)
        route_share = len(route_dep) / len(routes) if routes else 0.0
        score = 100 * (0.5 * blast + 0.3 * (b / max_b) + 0.2 * route_share)
        metrics[n] = {
            "dependents": len(dependents),
            "dependencies": len(nx.descendants(d, n)),
            "tests_covering": len(tests),
            "routes_depending": len(route_dep),
            "in_degree": d.in_degree(n),
            "out_degree": d.out_degree(n),
            "betweenness": round(b, 4),
            "criticality": round(score, 1) if g.nodes[n]["type"] != "test" else 0.0,
        }
    return metrics


def neighbourhood(g: nx.MultiDiGraph, node_id: str) -> dict:
    d = _prop_digraph(g)
    return {"upstream": sorted(nx.ancestors(d, node_id)), "downstream": sorted(nx.descendants(d, node_id))}


def _seeds(g: nx.MultiDiGraph, scenario: str, target: str) -> list[str]:
    seeds = [target]
    node = g.nodes[target]
    if scenario == "worker_unavailable":
        module, cls = node["data"].get("module"), node["data"].get("cls")
        launchers = set(node["data"].get("launcher_methods", []))
        for n, data in g.nodes(data=True):
            dd = data.get("data", {})
            if data["type"] == "function" and dd.get("module") == module and dd.get("cls") == cls:
                short = data["name"].split(".")[-1]
                if short in launchers or short.startswith("_"):
                    continue
                seeds.append(n)
    return seeds


def _relevant(names: list[str], relevant: set[str]) -> bool:
    return any(n.split(".")[-1] in relevant or n in relevant for n in names)


def _edge_guard(data: dict, relevant: set[str]) -> dict | None:
    """Return the protecting handler if *every* call site is inside a relevant, non-re-raising handler."""
    sites = data.get("call_sites") or []
    if not sites:
        return None
    found = None
    for site in sites:
        site_guard = None
        for handlers in site.get("tries", []):
            for h in handlers:
                if _relevant(h["names"], relevant) and not h["reraises"]:
                    site_guard = {"file": site.get("file"), "line": h.get("line"), "handles": h["names"]}
        if site_guard is None:
            return None
        found = found or site_guard
    return found


def _bfs(g: nx.MultiDiGraph, seeds: list[str], relevant: set[str] | None):
    """Reverse BFS. If `relevant` is given, edges whose call sites handle the failure are not followed."""
    parent: dict[str, tuple[str, str] | None] = {s: None for s in seeds}
    dist = {s: 0 for s in seeds}
    q = deque(seeds)
    while q:
        cur = q.popleft()
        for src, _, key, data in g.in_edges(cur, keys=True, data=True):
            if data["type"] not in PROPAGATING or src in parent:
                continue
            if relevant is not None and _edge_guard(data, relevant):
                continue
            parent[src] = (cur, key)
            dist[src] = dist[cur] + 1
            q.append(src)
    return parent, dist


def _path(parent, node) -> list[str]:
    out = [node]
    while parent.get(out[-1]):
        out.append(parent[out[-1]][0])
    return out


def compute_impact(g: nx.MultiDiGraph, scenario: str, target: str, custom_spec: dict | None = None) -> dict:
    if target not in g:
        raise ValueError(f"Component '{target}' is not in the analysed graph")
    if custom_spec:
        spec = dict(custom_spec)
        spec.setdefault("label", scenario.replace("_", " ").title())
        spec.setdefault("fault", f"Arbitrary dynamic failure injected for '{target}'.")
        spec.setdefault("exceptions", {"Exception", "BaseException", "RuntimeError", "Error"})
        spec.setdefault("target_types", [])
    elif scenario in SCENARIOS:
        spec = SCENARIOS[scenario]
    else:
        raise ValueError(f"Unsupported scenario '{scenario}'")
    ttype = g.nodes[target]["type"]
    if spec.get("target_types") and ttype not in spec["target_types"]:
        raise ValueError(f"Scenario '{spec['label']}' needs a {' or '.join(spec['target_types'])} component, got '{ttype}'")

    seeds = _seeds(g, scenario, target)
    possible_parent, possible_dist = _bfs(g, seeds, None)
    raised = set()
    for n in possible_parent:
        raised |= set(g.nodes[n].get("data", {}).get("raises", []))
    relevant = set(spec["exceptions"]) | GENERIC_EXCEPTIONS | raised
    definite_parent, definite_dist = _bfs(g, seeds, relevant)

    affected, tests = [], []
    for n, data in g.nodes(data=True):
        if n not in possible_parent or n in seeds:
            continue
        definite = n in definite_parent
        path = _path(definite_parent if definite else possible_parent, n)
        guard = None
        if not definite:
            for a, b in zip(path, path[1:]):
                for _, _, edata in g.edges(a, data=True):
                    if edata["target"] == b and edata["type"] in PROPAGATING:
                        guard = guard or _edge_guard(edata, relevant)
        item = {
            "id": n, "type": data["type"], "name": data["name"], "file": data.get("file"), "line": data.get("line"),
            "certainty": "definite" if definite else "possible",
            "distance": (definite_dist if definite else possible_dist)[n],
            "path": path, "handled_at": guard,
        }
        if data["type"] == "test":
            tests.append({**item, "nodeid": data["data"].get("nodeid"), "junit_key": data["data"].get("junit_key"),
                          "prediction": "fail" if definite else "may_fail"})
        else:
            affected.append(item)
    for n, data in g.nodes(data=True):
        if data["type"] == "test" and n not in possible_parent:
            tests.append({"id": n, "type": "test", "name": data["name"], "file": data.get("file"), "line": data.get("line"),
                          "nodeid": data["data"].get("nodeid"), "junit_key": data["data"].get("junit_key"),
                          "prediction": "pass", "certainty": "unaffected", "path": [], "distance": None, "handled_at": None})
    affected.sort(key=lambda a: (a["certainty"] != "definite", a["distance"], a["id"]))
    tests.sort(key=lambda t: ({"fail": 0, "may_fail": 1, "pass": 2}[t["prediction"]], t["id"]))
    routes_total = sum(1 for _, d in g.nodes(data=True) if d["type"] == "route")
    affected_routes = [a for a in affected if a["type"] == "route"]
    tnode = g.nodes[target]
    custom_fault = {
        "kind": "dynamic_fault",
        "scenario": scenario,
        "target_id": target,
        "target_type": ttype,
        "target_name": tnode["name"],
        "target_data": tnode.get("data", {}),
        "exceptions": sorted(relevant),
        "fault_description": spec.get("fault", ""),
    } if (custom_spec or scenario not in SCENARIOS) else None

    return {
        "scenario": scenario,
        "scenario_label": spec["label"],
        "fault_description": spec["fault"],
        "custom_fault": custom_fault,
        "target": {"id": target, "type": ttype, "name": tnode["name"], "data": tnode.get("data", {})},
        "seeds": seeds,
        "relevant_exceptions": sorted(relevant),
        "affected": affected,
        "tests": tests,
        "summary": {
            "affected_total": len(affected),
            "definite": sum(1 for a in affected if a["certainty"] == "definite"),
            "possible": sum(1 for a in affected if a["certainty"] == "possible"),
            "routes_affected": len(affected_routes),
            "routes_definite": sum(1 for a in affected_routes if a["certainty"] == "definite"),
            "routes_total": routes_total,
            "tests_predicted_fail": sum(1 for t in tests if t["prediction"] == "fail"),
            "tests_predicted_may_fail": sum(1 for t in tests if t["prediction"] == "may_fail"),
            "tests_predicted_pass": sum(1 for t in tests if t["prediction"] == "pass"),
        },
        "method": (
            "Reverse breadth-first search over propagating edges (calls, handled_by, served_by, runs_on_startup, "
            "uses_database, calls_http, reads_env, exercises). 'definite' = reachable without crossing a call site "
            "protected by an except-handler that catches a relevant exception and does not re-raise; 'possible' = "
            "reachable only through such handled call sites."
        ),
        "limitations": [
            "Static analysis only: dynamic dispatch, reflection, monkeypatching and runtime configuration are not modelled.",
            "An error being 'handled' does not mean the caller's behaviour is unchanged; handled paths are reported as uncertain.",
            "Module-level (import-time) code is not part of the propagation graph.",
            "Test-to-route mapping matches test-client URL literals against discovered route templates.",
        ],
    }
