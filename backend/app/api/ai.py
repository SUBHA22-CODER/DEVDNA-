"""Gemma-powered explanations. Every call requires consent and records an audit entry."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.evidence import Package, architecture_package, chat_package, experiment_package, prediction_package
from app.ai.gemma import AIError, gemma
from app.api.deps import get_project, require_run
from app.db import get_db
from app.models import AIInteraction, Experiment, Prediction, Project
from app.schemas import AIRequest, ChatIn, DynamicScenarioIn
from app.services.analysis import load_graph
from app.services.serialize import experiment_out, iso, prediction_out

router = APIRouter(prefix="/api", tags=["ai"])

PROMPTS = {
    "architecture": (
        "Explain the architecture of this Python project to a developer joining the team. Group components into "
        "layers, describe the 2-4 most important request flows step by step, list structural risks, and list unknowns "
        "that static analysis could not determine."
    ),
    "failure_analysis": (
        "Analyse the failure scenario below. The deterministic graph analysis already decided WHICH components and tests "
        "are affected; do not add or remove any. Explain the failure mechanism, the observable symptoms (exceptions, "
        "HTTP status codes) for affected routes, user impact, your assumptions, the uncertainties (especially 'possible' "
        "paths where an error is handled), recommended tests and mitigations. Set confidence to reflect evidence quality."
    ),
    "experiment_interpretation": (
        "Interpret the controlled experiment below. The comparison status was computed deterministically and must not "
        "be changed. Explain agreements, explain every mismatch or uncertain result using the failure messages and "
        "dependency paths, say what the result does and does not prove, and recommend the single most useful next test."
    ),
    "chat": (
        "Answer the developer's question about this repository using only the evidence. If the evidence is insufficient, "
        "say exactly what is missing. Write the answer in concise Markdown and list the component ids you relied on."
    ),
    "multimodal_audit": (
        "Perform a deep visual architecture audit and drift analysis. Visually inspect the provided architecture diagram "
        "or system screenshot and compare it directly against the ground-truth repository AST code evidence. Identify: "
        "1. Detected visual components that align with code, "
        "2. Architectural drift (components or links visible in the diagram but missing from code, or vice-versa), "
        "3. Failure susceptibility (unprotected remote boundaries, missing circuit breakers, single points of failure), "
        "4. Recommendations to harden resilience."
    ),
    "dynamic_scenario": (
        "Synthesize an arbitrary dynamic runtime failure scenario for DevDNA's What-If Experimentation Lab based on the user request. "
        "Determine the appropriate scenario_id, descriptive label, fault_description, target_type, suggested_target_id, "
        "the exact runtime exception class names that will be raised, failure hypotheses, and a mitigation strategy."
    ),
}


def _ai(db: Session, project: Project, kind: str, subject_id: str | None, prompt: str, pkg: Package, body: AIRequest) -> dict:
    evidence = pkg.to_dict()
    if body.preview:
        return {"preview": True, "model": gemma.model, "configured": gemma.configured, "evidence": evidence}
    if not body.consent:
        raise HTTPException(400, detail={"code": "consent_required",
                                         "message": "Confirm that the listed evidence may be sent to the Gemma API."})
    if not gemma.configured:
        raise HTTPException(503, detail={"code": "not_configured",
                                         "message": "AI is not configured. Add GEMINI_API_KEY to backend/.env and restart the backend."})
    full_prompt = f"{PROMPTS[kind]}\n\n{prompt}\n\nEVIDENCE:\n{pkg.render()}"
    record = AIInteraction(project_id=project.id, kind=kind, subject_id=subject_id, model=gemma.model, status="error",
                           evidence_refs=[i["ref"] + ": " + i["title"] for i in pkg.items])
    try:
        parsed, meta = gemma.generate(kind, full_prompt, pkg.refs)
    except AIError as exc:
        record.status = "invalid_output" if exc.code == "invalid_output" else "error"
        record.error = exc.message
        db.add(record)
        db.commit()
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message, "model": gemma.model})
    record.status, record.response, record.latency_ms = "ok", parsed.model_dump(), meta["latency_ms"]
    db.add(record)
    db.commit()
    return {"result": parsed.model_dump(), "meta": {**meta, "interaction_id": record.id}, "evidence": evidence}


@router.post("/projects/{project_id}/ai/architecture")
def explain_architecture(project_id: str, body: AIRequest, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    run = require_run(db, p)
    comps, edges, _ = load_graph(db, run.id)
    pkg = architecture_package({"name": p.name}, comps, edges, Path(p.source_path))
    return _ai(db, p, "architecture", run.id, "", pkg, body)


@router.get("/projects/{project_id}/ai/architecture/latest")
def latest_architecture(project_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    rec = db.scalars(select(AIInteraction).where(AIInteraction.project_id == p.id, AIInteraction.kind == "architecture",
                                                 AIInteraction.status == "ok", AIInteraction.subject_id == p.latest_run_id)
                     .order_by(AIInteraction.created_at.desc())).first()
    if not rec:
        return None
    return {"result": rec.response, "meta": {"model": rec.model, "generated_at": iso(rec.created_at),
                                             "latency_ms": rec.latency_ms, "interaction_id": rec.id}}


@router.post("/predictions/{prediction_id}/explain")
def explain_prediction(prediction_id: str, body: AIRequest, db: Session = Depends(get_db)):
    pred = db.get(Prediction, prediction_id)
    if not pred:
        raise HTTPException(404, detail={"code": "prediction_not_found", "message": "Prediction not found"})
    p = get_project(db, pred.project_id)
    comps, edges, _ = load_graph(db, pred.run_id)
    pkg = prediction_package(prediction_out(pred), {c["id"]: c for c in comps}, edges, Path(p.source_path))
    out = _ai(db, p, "failure_analysis", pred.id, "", pkg, body)
    if not body.preview:
        pred.ai_explanation = {"result": out["result"], "meta": out["meta"],
                               "evidence_refs": [i["ref"] + ": " + i["title"] for i in pkg.items]}
        db.commit()
    return out


@router.post("/experiments/{experiment_id}/interpret")
def interpret_experiment(experiment_id: str, body: AIRequest, db: Session = Depends(get_db)):
    exp = db.get(Experiment, experiment_id)
    if not exp:
        raise HTTPException(404, detail={"code": "experiment_not_found", "message": "Experiment not found"})
    if not exp.comparison:
        raise HTTPException(409, detail={"code": "not_executed", "message": "This experiment has no observations to interpret."})
    p = get_project(db, exp.project_id)
    pkg = experiment_package(experiment_out(exp, include_prediction=False), prediction_out(exp.prediction))
    out = _ai(db, p, "experiment_interpretation", exp.id, "", pkg, body)
    if not body.preview:
        exp.ai_interpretation = {"result": out["result"], "meta": out["meta"]}
        db.commit()
    return out


@router.post("/projects/{project_id}/ai/chat")
def chat(project_id: str, body: ChatIn, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    run = require_run(db, p)
    comps, edges, g = load_graph(db, run.id)
    pkg = chat_package(body.question, {"name": p.name}, comps, edges, Path(p.source_path), g)
    history = "\n".join(f"{m.role.upper()}: {m.content}" for m in body.history[-6:])
    prompt = (f"CONVERSATION SO FAR:\n{history}\n\n" if history else "") + f"QUESTION: {json.dumps(body.question)}"
    return _ai(db, p, "chat", None, prompt, pkg, body)


@router.get("/projects/{project_id}/ai/interactions")
def interactions(project_id: str, db: Session = Depends(get_db)):
    get_project(db, project_id)
    rows = db.scalars(select(AIInteraction).where(AIInteraction.project_id == project_id)
                      .order_by(AIInteraction.created_at.desc()).limit(50)).all()
    return [{"id": r.id, "kind": r.kind, "subject_id": r.subject_id, "model": r.model, "status": r.status,
             "error": r.error, "latency_ms": r.latency_ms, "evidence_refs": r.evidence_refs, "created_at": iso(r.created_at)}
            for r in rows]


@router.post("/projects/{project_id}/ai/multimodal-audit")
async def multimodal_audit(
    project_id: str,
    file: UploadFile = File(...),
    diagram_type: str = Form("architecture_diagram"),
    notes: str = Form(""),
    consent: bool = Form(True),
    db: Session = Depends(get_db),
):
    p = get_project(db, project_id)
    run = require_run(db, p)
    if not consent:
        raise HTTPException(400, detail={"code": "consent_required", "message": "Consent is required to send diagram image to Gemma 4."})
    if not gemma.configured:
        raise HTTPException(503, detail={"code": "not_configured", "message": "Gemma is not configured. Add GEMINI_API_KEY to backend/.env and restart."})

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, detail={"code": "file_too_large", "message": "Image must be under 10MB."})
    mime_type = file.content_type or "image/png"
    if mime_type not in ("image/png", "image/jpeg", "image/webp"):
        mime_type = "image/png"

    comps, edges, _ = load_graph(db, run.id)
    pkg = architecture_package({"name": p.name}, comps, edges, Path(p.source_path))

    prompt = (
        f"{PROMPTS['multimodal_audit']}\n\n"
        f"Diagram Type: {diagram_type}\n"
        f"User Notes: {notes or 'N/A'}\n\n"
        f"REPOSITORY EVIDENCE:\n{pkg.render()}"
    )

    record = AIInteraction(
        project_id=p.id,
        kind="multimodal_audit",
        subject_id=run.id,
        model=gemma.model,
        status="error",
        evidence_refs=[i["ref"] + ": " + i["title"] for i in pkg.items],
    )
    try:
        parsed, meta = gemma.generate_multimodal("multimodal_audit", prompt, content, mime_type, pkg.refs)
    except AIError as exc:
        record.status = "invalid_output" if exc.code == "invalid_output" else "error"
        record.error = exc.message
        db.add(record)
        db.commit()
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message, "model": gemma.model})

    record.status = "ok"
    record.response = parsed.model_dump()
    record.latency_ms = meta["latency_ms"]
    db.add(record)
    db.commit()

    return {"result": parsed.model_dump(), "meta": {**meta, "interaction_id": record.id}}


@router.get("/projects/{project_id}/ai/multimodal-audit/latest")
def latest_multimodal_audit(project_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    rec = db.scalars(
        select(AIInteraction).where(
            AIInteraction.project_id == p.id,
            AIInteraction.kind == "multimodal_audit",
            AIInteraction.status == "ok",
        ).order_by(AIInteraction.created_at.desc())
    ).first()
    if not rec:
        return None
    return {"result": rec.response, "meta": {"model": rec.model, "generated_at": iso(rec.created_at),
                                             "latency_ms": rec.latency_ms, "interaction_id": rec.id}}


@router.post("/projects/{project_id}/ai/dynamic-scenario")
def synthesize_dynamic_scenario(project_id: str, body: DynamicScenarioIn, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    run = require_run(db, p)
    comps, edges, _ = load_graph(db, run.id)
    pkg = architecture_package({"name": p.name}, comps, edges, Path(p.source_path))

    if body.preview:
        return {"preview": True, "model": gemma.model, "configured": gemma.configured, "evidence": pkg.to_dict()}
    if not body.consent:
        raise HTTPException(400, detail={"code": "consent_required", "message": "Confirm that evidence may be sent to Gemma."})
    if not gemma.configured:
        raise HTTPException(503, detail={"code": "not_configured", "message": "Gemma is not configured."})

    target_hint = f"Focus on target component: '{body.target_id}'." if body.target_id else "Select the most critical or suitable component from the evidence."
    prompt = (
        f"{PROMPTS['dynamic_scenario']}\n\n"
        f"USER SCENARIO REQUEST: {body.prompt}\n"
        f"{target_hint}\n\n"
        f"REPOSITORY EVIDENCE:\n{pkg.render()}"
    )

    record = AIInteraction(
        project_id=p.id,
        kind="dynamic_scenario",
        subject_id=run.id,
        model=gemma.model,
        status="error",
        evidence_refs=[i["ref"] + ": " + i["title"] for i in pkg.items],
    )
    try:
        parsed, meta = gemma.generate("dynamic_scenario", prompt, pkg.refs)
    except AIError as exc:
        record.status = "invalid_output" if exc.code == "invalid_output" else "error"
        record.error = exc.message
        db.add(record)
        db.commit()
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message, "model": gemma.model})

    record.status = "ok"
    record.response = parsed.model_dump()
    record.latency_ms = meta["latency_ms"]
    db.add(record)
    db.commit()

    return {"result": parsed.model_dump(), "meta": {**meta, "interaction_id": record.id}}
