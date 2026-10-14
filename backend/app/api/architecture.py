"""Architecture graph, component details, findings, scenarios and analytics."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.evidence import source_excerpt
from app.api.deps import get_project, require_run
from app.db import get_db
from app.graph.engine import PROPAGATING, SCENARIOS, neighbourhood
from app.models import AIInteraction, Experiment, Finding, Prediction
from app.schemas import FindingPatch
from app.services.analysis import load_graph
from app.services.serialize import finding_out

router = APIRouter(prefix="/api", tags=["architecture"])


@router.get("/projects/{project_id}/architecture")
def architecture(project_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    run = require_run(db, p)
    comps, edges, _ = load_graph(db, run.id)
    return {
        "run_id": run.id,
        "components": comps,
        "edges": [{k: e[k] for k in ("id", "source", "target", "type", "classification", "evidence")} for e in edges],
        "propagating_edge_types": sorted(PROPAGATING),
        "summary": run.summary,
    }


@router.get("/projects/{project_id}/components/{component_id:path}")
def component_detail(project_id: str, component_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    run = require_run(db, p)
    comps, edges, g = load_graph(db, run.id)
    comp = next((c for c in comps if c["id"] == component_id), None)
    if not comp:
        raise HTTPException(404, detail={"code": "component_not_found", "message": f"Component '{component_id}' not found"})
    strip = lambda e: {k: e[k] for k in ("id", "source", "target", "type", "classification", "evidence")}
    hood = neighbourhood(g, component_id)
    findings = db.scalars(select(Finding).where(Finding.run_id == run.id, Finding.component_id == component_id)).all()
    excerpt = source_excerpt(Path(p.source_path), comp.get("file"), comp.get("line")) \
        if comp["type"] in ("function", "class", "route", "app", "worker") else None
    return {
        **comp,
        "outgoing": [strip(e) for e in edges if e["source"] == component_id],
        "incoming": [strip(e) for e in edges if e["target"] == component_id],
        "upstream": hood["upstream"],
        "downstream": hood["downstream"],
        "findings": [finding_out(f) for f in findings],
        "source_excerpt": excerpt,
    }


@router.get("/projects/{project_id}/findings")
def findings(project_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    if not p.latest_run_id:
        return []
    rows = db.scalars(select(Finding).where(Finding.run_id == p.latest_run_id)).all()
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    return sorted([finding_out(f) for f in rows], key=lambda f: (order.get(f["severity"], 9), f["title"]))


@router.patch("/findings/{finding_id}")
def update_finding(finding_id: str, body: FindingPatch, db: Session = Depends(get_db)):
    f = db.get(Finding, finding_id)
    if not f:
        raise HTTPException(404, detail={"code": "finding_not_found", "message": "Finding not found"})
    f.review_status = body.review_status
    db.commit()
    return finding_out(f)


@router.get("/projects/{project_id}/scenarios")
def scenarios(project_id: str, db: Session = Depends(get_db)):
    """Supported failure scenarios and the discovered components each can target."""
    p = get_project(db, project_id)
    run = require_run(db, p)
    comps, _, _ = load_graph(db, run.id)
    out = []
    for key, spec in SCENARIOS.items():
        targets = [{"id": c["id"], "name": c["name"], "type": c["type"], "criticality": c["metrics"].get("criticality"),
                    "dependents": c["metrics"].get("dependents")}
                   for c in comps if c["type"] in spec["target_types"]]
        out.append({"id": key, "label": spec["label"], "fault": spec["fault"], "target_types": spec["target_types"],
                    "targets": sorted(targets, key=lambda t: -(t["criticality"] or 0)), "supported": bool(targets)})
    return out


@router.get("/projects/{project_id}/analytics")
def analytics(project_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    run = require_run(db, p)
    comps, edges, _ = load_graph(db, run.id)
    exps = db.scalars(select(Experiment).where(Experiment.project_id == p.id)).all()
    preds = db.scalars(select(Prediction).where(Prediction.project_id == p.id)).all()
    fnds = db.scalars(select(Finding).where(Finding.run_id == run.id)).all()
    ai = db.scalars(select(AIInteraction).where(AIInteraction.project_id == p.id)).all()
    non_test = [c for c in comps if c["type"] not in ("test", "module")]
    centrality = sorted(non_test, key=lambda c: -c["metrics"].get("criticality", 0))[:10]
    outcome_counts: dict[str, int] = {}
    for e in exps:
        outcome_counts[e.status] = outcome_counts.get(e.status, 0) + 1
    severity_counts: dict[str, int] = {}
    for f in fnds:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
    latest_pred = max(preds, key=lambda x: x.created_at) if preds else None
    return {
        "component_counts": run.summary.get("component_counts", {}),
        "edge_counts": run.summary.get("edge_counts", {}),
        "edge_classification": run.summary.get("edge_classification", {}),
        "coverage": run.summary.get("coverage", {}),
        "scan": run.summary.get("scan", {}),
        "frameworks": run.summary.get("frameworks", []),
        "dependencies": run.summary.get("dependencies", []),
        "centrality": [{"id": c["id"], "name": c["name"], "type": c["type"], **c["metrics"]} for c in centrality],
        "experiments": {"total": len(exps), "by_status": outcome_counts},
        "predictions": {"total": len(preds),
                        "latest": {"id": latest_pred.id, "scenario": latest_pred.scenario, "target": latest_pred.target_id,
                                   "summary": latest_pred.impact.get("summary")} if latest_pred else None},
        "findings": {"total": len(fnds), "by_severity": severity_counts,
                     "open": sum(1 for f in fnds if f.review_status == "open"),
                     "recent": [finding_out(f) for f in sorted(fnds, key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f.severity, 3)))[:5]]},
        "ai": {"requests": len(ai), "ok": sum(1 for a in ai if a.status == "ok"), "errors": sum(1 for a in ai if a.status != "ok")},
    }
