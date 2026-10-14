import io
import zipfile

from app import db as dbmod
from app.models import Component, Finding, Project


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "ok" and body["ai"]["configured"] is False and body["ai"]["model"]


def test_ai_status_without_key(client):
    r = client.get("/api/ai/status?check=true").json()
    assert r["configured"] is False and "gemma" in r["model"]


def test_sample_analysis_and_persistence(client, sample_project):
    detail = client.get(f"/api/projects/{sample_project}").json()
    assert detail["trusted"] is True and detail["latest_run"]["status"] == "completed"
    assert "source_path" not in detail
    stages = [s["stage"] for s in detail["latest_run"]["stages"]]
    assert stages[0] == "Scanning files" and "Generating findings" in stages
    db = dbmod.SessionLocal()
    try:
        p = db.get(Project, sample_project)
        assert db.query(Component).filter(Component.run_id == p.latest_run_id).count() > 50
        assert db.query(Finding).filter(Finding.project_id == sample_project).count() > 0
    finally:
        db.close()


def test_architecture_and_component_detail(client, sample_project):
    arch = client.get(f"/api/projects/{sample_project}/architecture").json()
    assert len(arch["components"]) > 50 and len(arch["edges"]) > 50
    r = client.get(f"/api/projects/{sample_project}/components/func:shoplite.db.get_connection").json()
    assert r["file"] == "shoplite/db.py"
    assert any(e["target"] == "database:sqlite" for e in r["outgoing"])
    assert "route:GET /health" in r["upstream"]
    assert "sqlite3.connect" in r["source_excerpt"]
    assert client.get(f"/api/projects/{sample_project}/components/func:nope").status_code == 404


def test_findings_and_review_status(client, sample_project):
    findings = client.get(f"/api/projects/{sample_project}/findings").json()
    rules = {f["rule"] for f in findings}
    assert {"startup_dependency", "shared_dependency", "required_env_var"} <= rules
    fid = findings[0]["id"]
    assert client.patch(f"/api/findings/{fid}", json={"review_status": "acknowledged"}).json()["review_status"] == "acknowledged"
    bad = client.patch(f"/api/findings/{fid}", json={"review_status": "deleted"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"


def test_scenarios_and_analytics(client, sample_project):
    sc = {s["id"]: s for s in client.get(f"/api/projects/{sample_project}/scenarios").json()}
    assert sc["db_unavailable"]["targets"][0]["id"] == "database:sqlite"
    a = client.get(f"/api/projects/{sample_project}/analytics").json()
    assert a["component_counts"]["route"] == 6 and a["centrality"]


def test_prediction_validation(client, sample_project):
    r = client.post(f"/api/projects/{sample_project}/predictions", json={"scenario": "db_unavailable", "target_id": "env:SHIPPING_API_URL"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_scenario"
    r = client.post(f"/api/projects/{sample_project}/predictions", json={"scenario": "nope", "target_id": "database:sqlite"})
    assert r.status_code == 422


def test_ai_requires_consent_and_key(client, sample_project):
    pred = client.post(f"/api/projects/{sample_project}/predictions",
                       json={"scenario": "db_unavailable", "target_id": "database:sqlite"}).json()
    r = client.post(f"/api/predictions/{pred['id']}/explain", json={"preview": True})
    assert r.status_code == 200 and r.json()["preview"] is True
    items = r.json()["evidence"]["items"]
    assert items and all(i["ref"].startswith("E") for i in items)
    r = client.post(f"/api/predictions/{pred['id']}/explain", json={})
    assert r.status_code == 400 and r.json()["error"]["code"] == "consent_required"
    r = client.post(f"/api/predictions/{pred['id']}/explain", json={"consent": True})
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_configured"
    r = client.post(f"/api/projects/{sample_project}/ai/chat", json={"question": "", "consent": True})
    assert r.status_code == 422


def test_experiment_requires_approval_and_runs(client, sample_project):
    pred = client.post(f"/api/projects/{sample_project}/predictions",
                       json={"scenario": "external_api_unavailable", "target_id": "external:SHIPPING_API_URL"}).json()
    r = client.post(f"/api/predictions/{pred['id']}/experiments", json={"approved": False})
    assert r.status_code == 400 and r.json()["error"]["code"] == "approval_required"
    r = client.post(f"/api/predictions/{pred['id']}/experiments", json={"approved": True})
    assert r.status_code == 202
    exp = client.get(f"/api/experiments/{r.json()['id']}").json()
    # validation short-circuits test_order_validation before the handler: an honest partial confirmation
    assert exp["status"] == "partially_confirmed", exp.get("error")
    mism = [row for row in exp["comparison"]["rows"] if row["verdict"] == "mismatch"]
    assert [m["test"] for m in mism] == ["test_order_validation"]
    assert exp["mode"] == "local_harness"

    md = client.get(f"/api/experiments/{exp['id']}/report?format=md")
    assert md.status_code == 200 and "# Experiment report" in md.text and "attachment" in md.headers["content-disposition"]
    js = client.get(f"/api/experiments/{exp['id']}/report?format=json").json()
    assert js["status"] == "partially_confirmed" and js["recommended_next_test"]
    lst = client.get(f"/api/projects/{sample_project}/experiments").json()
    assert lst and "output" not in lst[0]["observation"].get("faulted", {})


def test_project_report(client, sample_project):
    r = client.get(f"/api/projects/{sample_project}/report?format=md")
    assert r.status_code == 200 and "## Findings" in r.text and "Criticality formula" in r.text
    assert client.get(f"/api/projects/{sample_project}/report?format=json").json()["report_type"] == "devdna_project_report"
    assert client.get(f"/api/projects/{sample_project}/report?format=pdf").status_code == 422
    assert len(client.get(f"/api/projects/{sample_project}/reports").json()) >= 2


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for k, v in entries.items():
            zf.writestr(k, v)
    return buf.getvalue()


def test_upload_flow_and_blocked_experiment(client):
    data = _zip({"proj/app.py": "import sqlite3\n\ndef get():\n    return sqlite3.connect('x.db')\n",
                 "proj/.env": "GEMINI_API_KEY=should-never-be-read"})
    r = client.post("/api/projects/upload", files={"file": ("proj.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    pid = r.json()["project"]["id"]
    assert r.json()["project"]["ingest_stats"]["skipped_sensitive"] == 1
    assert client.get(f"/api/runs/{r.json()['run']['id']}").json()["status"] == "completed"
    pred = client.post(f"/api/projects/{pid}/predictions", json={"scenario": "db_unavailable", "target_id": "database:sqlite"}).json()
    exp = client.post(f"/api/predictions/{pred['id']}/experiments", json={"approved": True}).json()
    exp = client.get(f"/api/experiments/{exp['id']}").json()
    assert exp["status"] == "blocked" and "No code was executed" in exp["error"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_upload_rejections(client):
    r = client.post("/api/projects/upload", files={"file": ("x.txt", b"hi", "text/plain")})
    assert r.status_code == 400
    r = client.post("/api/projects/upload", files={"file": ("x.zip", _zip({"../../evil.py": "x"}), "application/zip")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsafe_archive"
    r = client.post("/api/projects/upload", files={"file": ("x.zip", _zip({"readme.md": "x"}), "application/zip")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_python"


def test_local_projects_disabled_by_default(client):
    r = client.post("/api/projects/local", json={"path": "C:/"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "local_disabled"


def test_unknown_project_404(client):
    r = client.get("/api/projects/doesnotexist/architecture")
    assert r.status_code == 404 and r.json()["error"]["code"] == "project_not_found"


def test_chat_evidence_includes_deterministic_dependents(client, sample_project):
    r = client.post(f"/api/projects/{sample_project}/ai/chat",
                    json={"question": "Which routes break if the shipping API is down?", "preview": True})
    items = r.json()["evidence"]["items"]
    dependents = [i for i in items if i["kind"] == "dependents" and "external:SHIPPING_API_URL" in i["title"]]
    assert dependents and "POST /api/orders" in dependents[0]["content"]


def test_multimodal_audit_and_dynamic_scenario(client, sample_project):
    # Multimodal audit validation
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    r = client.post(
        f"/api/projects/{sample_project}/ai/multimodal-audit",
        files={"file": ("diagram.png", fake_png, "image/png")},
        data={"consent": "false"},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "consent_required"

    r = client.post(
        f"/api/projects/{sample_project}/ai/multimodal-audit",
        files={"file": ("diagram.png", fake_png, "image/png")},
        data={"consent": "true"},
    )
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_configured"

    latest = client.get(f"/api/projects/{sample_project}/ai/multimodal-audit/latest")
    assert latest.status_code == 200

    # Dynamic scenario preview
    r = client.post(
        f"/api/projects/{sample_project}/ai/dynamic-scenario",
        json={"prompt": "Simulate Redis cache eviction storm", "preview": True},
    )
    assert r.status_code == 200 and r.json()["preview"] is True

    # Prediction with dynamic custom_spec and neuro-symbolic simulation
    custom_spec = {
        "label": "Custom Redis Failure",
        "fault": "Redis socket reset error on auth pipeline",
        "exceptions": ["ConnectionError", "RuntimeError"],
        "target_types": ["database"],
    }
    pred_res = client.post(
        f"/api/projects/{sample_project}/predictions",
        json={
            "scenario": "custom_redis_fault",
            "target_id": "database:sqlite",
            "custom_spec": custom_spec,
        },
    )
    assert pred_res.status_code == 201
    pred = pred_res.json()
    assert pred["scenario"] == "custom_redis_fault"
    assert "neuro_symbolic_simulation" in pred["impact"]
    sim = pred["impact"]["neuro_symbolic_simulation"]
    assert sim["cascading_risk_score"] > 0
    assert sim["blast_radius_assessment"] in ("CRITICAL", "HIGH", "MODERATE")
    assert pred["impact"]["custom_fault"]["kind"] == "dynamic_fault"

