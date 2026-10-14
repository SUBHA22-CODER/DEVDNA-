"""DevDNA fault-injection pytest plugin.

Loaded into the experiment subprocess with `-p devdna_faults`. It never runs inside
the DevDNA server process. Configuration comes from the DEVDNA_FAULT environment
variable (JSON). Outbound network access to non-loopback hosts is always blocked.
Every injected failure message contains MARK so observations can be attributed to
the fault rather than to unrelated errors.
"""
import json
import os
import socket

import pytest

MARK = "DevDNA injected fault"
FAULT = json.loads(os.environ.get("DEVDNA_FAULT") or "null")
REPORT_PATH = os.environ.get("DEVDNA_FAULT_REPORT")
STATE = {"fault": FAULT, "applied": [], "triggers": 0, "network_blocked_attempts": 0, "errors": []}


def _trigger():
    STATE["triggers"] += 1


def _block_network():
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def allowed(address):
        if not isinstance(address, tuple):
            return True
        return str(address[0]) in ("127.0.0.1", "::1", "localhost")

    def connect(self, address):
        if not allowed(address):
            STATE["network_blocked_attempts"] += 1
            raise ConnectionRefusedError(f"DevDNA sandbox: outbound network disabled ({address[0]})")
        return real_connect(self, address)

    def connect_ex(self, address):
        if not allowed(address):
            STATE["network_blocked_attempts"] += 1
            return 111
        return real_connect_ex(self, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex


def _db_unavailable():
    import sqlite3

    def refuse(*args, **kwargs):
        _trigger()
        raise sqlite3.OperationalError(f"{MARK}: database unavailable")

    sqlite3.connect = refuse
    sqlite3.dbapi2.connect = refuse
    STATE["applied"].append("sqlite3.connect raises sqlite3.OperationalError")
    try:
        import sqlalchemy.exc
        from sqlalchemy.engine import Engine

        def refuse_engine(self, *args, **kwargs):
            _trigger()
            raise sqlalchemy.exc.OperationalError(MARK, None, ConnectionError(f"{MARK}: database unavailable"))

        Engine.connect = refuse_engine
        Engine.raw_connection = refuse_engine
        STATE["applied"].append("sqlalchemy Engine.connect raises OperationalError")
    except ImportError:
        pass
    for modname in ("psycopg2", "psycopg", "pymysql"):
        try:
            mod = __import__(modname)
        except ImportError:
            continue
        exc_type = getattr(mod, "OperationalError", ConnectionError)

        def refuse_driver(*a, _exc=exc_type, **k):
            _trigger()
            raise _exc(f"{MARK}: database unavailable")

        mod.connect = refuse_driver
        STATE["applied"].append(f"{modname}.connect raises")


def _external_api_unavailable():
    try:
        import httpx

        def refuse(self, request):
            _trigger()
            raise httpx.ConnectError(f"{MARK}: external API unavailable", request=request)

        async def refuse_async(self, request):
            _trigger()
            raise httpx.ConnectError(f"{MARK}: external API unavailable", request=request)

        httpx.HTTPTransport.handle_request = refuse
        httpx.MockTransport.handle_request = refuse
        httpx.AsyncHTTPTransport.handle_async_request = refuse_async
        httpx.MockTransport.handle_async_request = refuse_async
        STATE["applied"].append("httpx transports (real and mock) raise httpx.ConnectError")
    except ImportError:
        pass
    try:
        import requests.adapters
        import requests.exceptions

        def refuse_requests(self, request, *a, **k):
            _trigger()
            raise requests.exceptions.ConnectionError(f"{MARK}: external API unavailable")

        requests.adapters.HTTPAdapter.send = refuse_requests
        STATE["applied"].append("requests HTTPAdapter.send raises ConnectionError")
    except ImportError:
        pass
    import urllib.error
    import urllib.request

    def refuse_urlopen(*a, **k):
        _trigger()
        raise urllib.error.URLError(f"{MARK}: external API unavailable")

    urllib.request.urlopen = refuse_urlopen
    STATE["applied"].append("urllib.request.urlopen raises URLError")


def _worker_unavailable():
    import importlib

    module = importlib.import_module(FAULT["module"])
    cls = getattr(module, FAULT["cls"])
    for name in FAULT.get("launchers", []):
        def noop(self, *a, _name=name, **k):
            _trigger()
            return None

        setattr(cls, name, noop)
        STATE["applied"].append(f"{FAULT['cls']}.{name}() replaced with a no-op (worker never starts)")


def _dynamic_fault():
    import importlib
    target_data = FAULT.get("target_data", {})
    target_name = FAULT.get("target_name", "")
    module_name = target_data.get("module")
    cls_name = target_data.get("cls")
    func_name = target_data.get("function") or (target_name.split(".")[-1] if "." in target_name else target_name)
    exc_names = FAULT.get("exceptions") or ["RuntimeError"]
    exc_type_name = exc_names[0] if exc_names else "RuntimeError"

    exc_cls = getattr(__builtins__, exc_type_name, None) if isinstance(__builtins__, dict) else getattr(__builtins__, exc_type_name, None)
    if not isinstance(exc_cls, type) or not issubclass(exc_cls, BaseException):
        exc_cls = RuntimeError

    applied = False
    if module_name:
        try:
            mod = importlib.import_module(module_name)
            if cls_name and hasattr(mod, cls_name):
                target_obj = getattr(mod, cls_name)
                if hasattr(target_obj, func_name):
                    def broken_method(self, *a, **k):
                        _trigger()
                        raise exc_cls(f"{MARK}: dynamic fault in {cls_name}.{func_name}")
                    setattr(target_obj, func_name, broken_method)
                    STATE["applied"].append(f"dynamically patched {cls_name}.{func_name} to raise {exc_type_name}")
                    applied = True
            elif hasattr(mod, func_name):
                def broken_func(*a, **k):
                    _trigger()
                    raise exc_cls(f"{MARK}: dynamic fault in {module_name}.{func_name}")
                setattr(mod, func_name, broken_func)
                STATE["applied"].append(f"dynamically patched {module_name}.{func_name} to raise {exc_type_name}")
                applied = True
        except Exception as e:
            STATE["errors"].append(f"dynamic module patch failed: {e}")

    if not applied:
        if "db" in FAULT.get("scenario", "").lower() or FAULT.get("target_type") == "database":
            _db_unavailable()
        elif "api" in FAULT.get("scenario", "").lower() or FAULT.get("target_type") == "external_api":
            _external_api_unavailable()
        else:
            STATE["applied"].append(f"dynamic fault configured for {target_name} ({exc_type_name})")


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    _block_network()
    if not FAULT:
        return
    kind = FAULT.get("kind")
    try:
        if kind == "db_unavailable":
            _db_unavailable()
        elif kind == "external_api_unavailable":
            _external_api_unavailable()
        elif kind == "missing_env_var":
            os.environ.pop(FAULT["var"], None)
            STATE["applied"].append(f"environment variable {FAULT['var']} removed before every test")
        elif kind == "worker_unavailable":
            _worker_unavailable()
        elif kind == "dynamic_fault":
            _dynamic_fault()
    except Exception as exc:  # report, never hide
        STATE["errors"].append(f"{type(exc).__name__}: {exc}")


@pytest.fixture(autouse=True)
def _devdna_missing_env(monkeypatch):
    """Counts one trigger per test in which the variable was removed."""
    if FAULT and FAULT.get("kind") == "missing_env_var":
        monkeypatch.delenv(FAULT["var"], raising=False)
        _trigger()
    yield


def pytest_unconfigure(config):
    if REPORT_PATH:
        with open(REPORT_PATH, "w", encoding="utf-8") as fh:
            json.dump(STATE, fh)
