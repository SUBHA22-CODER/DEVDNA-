from app.experiments import runner
from app.experiments.runner import _scrubbed_env, choose_mode, compare


def _impact(preds):
    return {"tests": [{"name": n, "nodeid": f"tests/t.py::{n}", "junit_key": f"tests.t::{n}", "prediction": p, "path": []}
                      for n, p in preds.items()]}


def _obs(baseline, faulted, triggers=3, errors=None):
    res = lambda d: {f"tests.t::{n}": {"outcome": o, "message": "", "time": 0} for n, o in d.items()}
    return {"baseline": {"timed_out": False, "results": res(baseline), "fault_state": {}},
            "faulted": {"timed_out": False, "results": res(faulted),
                        "fault_state": {"triggers": triggers, "errors": errors or []}}}


def test_compare_confirmed():
    c = compare(_impact({"a": "fail", "b": "pass"}), _obs({"a": "passed", "b": "passed"}, {"a": "error", "b": "passed"}))
    assert c["status"] == "prediction_confirmed"
    assert c["metrics"]["accuracy"] == 1.0 and c["metrics"]["true_positive"] == 1


def test_compare_partial_and_contradicted():
    c = compare(_impact({"a": "fail", "b": "fail"}), _obs({"a": "passed", "b": "passed"}, {"a": "failed", "b": "passed"}))
    assert c["status"] == "partially_confirmed" and c["metrics"]["false_positive"] == 1
    c = compare(_impact({"a": "fail", "b": "pass"}), _obs({"a": "passed", "b": "passed"}, {"a": "passed", "b": "failed"}))
    assert c["status"] == "prediction_contradicted"


def test_compare_inconclusive_cases():
    imp = _impact({"a": "fail"})
    assert compare(imp, _obs({}, {}))["status"] == "inconclusive"  # baseline produced nothing
    assert compare(imp, _obs({"a": "passed"}, {"a": "failed"}, triggers=0))["status"] == "inconclusive"
    assert compare(imp, _obs({"a": "passed"}, {"a": "failed"}, errors=["boom"]))["status"] == "inconclusive"
    # a test failing in baseline is excluded, never counted as confirmation
    c = compare(_impact({"a": "fail"}), _obs({"a": "failed"}, {"a": "failed"}))
    assert c["status"] == "inconclusive" and c["rows"][0]["verdict"] == "excluded"


def test_uncertain_predictions_never_count_as_matches():
    c = compare(_impact({"a": "may_fail", "b": "pass"}), _obs({"a": "passed", "b": "passed"}, {"a": "passed", "b": "passed"}))
    assert c["rows"][0]["verdict"] == "uncertain_passed"
    assert c["metrics"]["true_negative"] == 1 and c["metrics"]["uncertain_passed"] == 1


def test_untrusted_projects_are_blocked_without_docker(monkeypatch):
    monkeypatch.setattr(runner, "docker_available", lambda: False)
    mode, reason = choose_mode(trusted=False)
    assert mode == "blocked" and "No code was executed" in reason
    assert choose_mode(trusted=True)[0] == "local_harness"


def test_sandbox_env_is_scrubbed(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "also-secret")
    env = _scrubbed_env(tmp_path, tmp_path, {"kind": "db_unavailable"}, tmp_path / "r.json")
    assert "GEMINI_API_KEY" not in env and "AWS_SECRET_ACCESS_KEY" not in env
    assert "super-secret" not in str(env)
    assert env["TMP"] == str(tmp_path)


def test_fault_spec_for_each_scenario(sample_graph):
    from app.graph.engine import compute_impact

    spec = runner.fault_spec(compute_impact(sample_graph, "missing_env_var", "env:SHIPPING_API_URL"))
    assert spec == {"kind": "missing_env_var", "var": "SHIPPING_API_URL"}
    spec = runner.fault_spec(compute_impact(sample_graph, "worker_unavailable", "worker:shoplite.worker.NotificationWorker"))
    assert spec["launchers"] == ["start"] and spec["cls"] == "NotificationWorker"


def test_real_db_experiment_on_sample(sample_graph):
    """Executes the sample test suite twice in the restricted harness with the DB fault injected."""
    from app.graph.engine import compute_impact
    from pathlib import Path

    SAMPLE = Path(__file__).resolve().parent.parent / "sample_project"

    impact = compute_impact(sample_graph, "db_unavailable", "database:sqlite")
    obs = runner.execute(SAMPLE, runner.fault_spec(impact), "local_harness")
    assert obs["baseline"]["counts"]["passed"] == 12, obs["baseline"]["output"][-2000:]
    assert obs["faulted"]["fault_state"]["triggers"] > 0
    assert any("sqlite3.connect" in a for a in obs["faulted"]["fault_state"]["applied"])
    c = compare(impact, obs)
    assert c["status"] == "prediction_confirmed", c
    assert all(r["fault_marker"] for r in c["rows"] if r["observed"] in ("failed", "error"))
