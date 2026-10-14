import pytest

from app.graph.engine import compute_impact, compute_metrics


def _tests(impact, prediction):
    return {t["name"] for t in impact["tests"] if t["prediction"] == prediction}


def test_db_failure_propagates_through_startup(sample_graph):
    impact = compute_impact(sample_graph, "db_unavailable", "database:sqlite")
    assert impact["summary"]["routes_definite"] == 6
    assert "app:shoplite.main.app" in {a["id"] for a in impact["affected"] if a["certainty"] == "definite"}
    assert _tests(impact, "pass") == {"test_compute_total_without_discount", "test_discount_codes",
                                      "test_quantity_must_be_positive", "test_worker_delivers_events"}
    assert len(_tests(impact, "fail")) == 8


def test_paths_end_at_the_failing_component(sample_graph):
    impact = compute_impact(sample_graph, "db_unavailable", "database:sqlite")
    for a in impact["affected"]:
        assert a["path"][0] == a["id"] and a["path"][-1] == "database:sqlite"
        assert a["distance"] == len(a["path"]) - 1


def test_handled_errors_make_paths_uncertain(sample_graph):
    impact = compute_impact(sample_graph, "worker_unavailable", "worker:shoplite.worker.NotificationWorker")
    assert _tests(impact, "fail") == {"test_worker_delivers_events"}
    assert "test_create_order" in _tests(impact, "may_fail")
    t = next(t for t in impact["tests"] if t["name"] == "test_create_order")
    assert t["handled_at"]["handles"] == ["WorkerUnavailable"]
    # start() is a launcher, not a seed, so app startup is not predicted to fail
    assert "app:shoplite.main.app" not in {a["id"] for a in impact["affected"]}


def test_reraising_handlers_do_not_count_as_guards(sample_graph):
    impact = compute_impact(sample_graph, "external_api_unavailable", "external:SHIPPING_API_URL")
    assert {"test_create_order", "test_shipping_quote", "test_get_order"} <= _tests(impact, "fail")
    assert "test_list_products" in _tests(impact, "pass")


def test_env_var_with_default_is_uncertain(sample_graph):
    impact = compute_impact(sample_graph, "missing_env_var", "env:DATABASE_PATH")
    assert impact["summary"]["definite"] == 0 and impact["summary"]["possible"] > 0


def test_scenario_target_validation(sample_graph):
    with pytest.raises(ValueError, match="needs a database"):
        compute_impact(sample_graph, "db_unavailable", "env:SHIPPING_API_URL")
    with pytest.raises(ValueError, match="not in the analysed graph"):
        compute_impact(sample_graph, "db_unavailable", "database:nope")
    with pytest.raises(ValueError, match="Unsupported"):
        compute_impact(sample_graph, "meteor_strike", "database:sqlite")


def test_metrics_are_deterministic_and_bounded(sample_graph):
    m1, m2 = compute_metrics(sample_graph), compute_metrics(sample_graph)
    assert m1 == m2
    assert all(0 <= v["criticality"] <= 100 for v in m1.values())
    assert m1["func:shoplite.db.get_connection"]["criticality"] > m1["func:shoplite.services.pricing.apply_discount"]["criticality"]
    assert m1["database:sqlite"]["routes_depending"] == 6
