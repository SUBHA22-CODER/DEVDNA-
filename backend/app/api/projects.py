"""Project ingestion (sample, ZIP upload, explicitly allowed local path) and analysis runs."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzer.ingest import ZipSecurityError, safe_extract_zip, scan_tree
from app.api.deps import get_project
from app.config import settings
from app.db import get_db
from app.models import AIInteraction, AnalysisRun, Experiment, Prediction, Project, ReportRecord, _id
from app.schemas import LocalProjectIn
from app.services.analysis import run_analysis
from app.services.serialize import project_out, run_out

router = APIRouter(prefix="/api", tags=["projects"])


def _start_run(db: Session, project: Project, background: BackgroundTasks) -> AnalysisRun:
    run = AnalysisRun(project_id=project.id)
    db.add(run)
    db.commit()
    background.add_task(run_analysis, run.id)
    return run


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [project_out(p, db.get(AnalysisRun, p.latest_run_id) if p.latest_run_id else None) for p in projects]


@router.post("/projects/sample", status_code=201)
def load_sample(background: BackgroundTasks, db: Session = Depends(get_db)):
    """Copy the bundled ShopLite sample into a fresh project and start analysis."""
    pid = _id()
    dest = settings.projects_dir / pid / "source"
    shutil.copytree(settings.sample_project_dir, dest, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))
    scan = scan_tree(dest)
    project = Project(id=pid, name="ShopLite (demo)", source_type="sample", source_path=str(dest), trusted=True,
                      ingest_stats={"files": scan["file_count"], "languages": scan["languages"]})
    db.add(project)
    db.commit()
    run = _start_run(db, project, background)
    return {"project": project_out(project), "run": run_out(run)}


@router.post("/projects/upload", status_code=201)
async def upload_project(background: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, detail={"code": "invalid_file", "message": "Upload a .zip archive of the repository."})
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, detail={"code": "too_large",
                                         "message": f"Upload exceeds {settings.max_upload_bytes // (1024 * 1024)} MB."})
    pid = _id()
    dest = settings.projects_dir / pid / "source"
    try:
        stats = safe_extract_zip(data, dest)
    except ZipSecurityError as exc:
        shutil.rmtree(settings.projects_dir / pid, ignore_errors=True)
        raise HTTPException(400, detail={"code": "unsafe_archive", "message": str(exc)})
    scan = scan_tree(dest)
    if not any(f.endswith(".py") for f in scan["files"]):
        shutil.rmtree(settings.projects_dir / pid, ignore_errors=True)
        raise HTTPException(422, detail={"code": "no_python", "message": "No Python source files found. DevDNA currently analyses Python projects."})
    name = Path(file.filename).stem[:200] or "Uploaded project"
    stats.pop("sensitive_files", None)  # names only were collected; do not persist them
    project = Project(id=pid, name=name, source_type="upload", source_path=str(dest), trusted=False,
                      ingest_stats={**stats, "files": scan["file_count"], "languages": scan["languages"]})
    db.add(project)
    db.commit()
    run = _start_run(db, project, background)
    return {"project": project_out(project), "run": run_out(run)}


@router.post("/projects/local", status_code=201)
def local_project(body: LocalProjectIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Analyse a folder on the server. Only allowed inside DEVDNA_ALLOWED_LOCAL_ROOTS (read-only analysis)."""
    if not settings.allowed_local_roots:
        raise HTTPException(403, detail={"code": "local_disabled",
                                         "message": "Local repository analysis is disabled. Set DEVDNA_ALLOWED_LOCAL_ROOTS in backend/.env."})
    path = Path(body.path).expanduser().resolve()
    roots = [Path(r).expanduser().resolve() for r in settings.allowed_local_roots]
    if not any(path == r or r in path.parents for r in roots):
        raise HTTPException(403, detail={"code": "path_not_allowed", "message": "That path is outside the allowed local roots."})
    if not path.is_dir():
        raise HTTPException(404, detail={"code": "not_found", "message": f"Directory not found: '{body.path}'"})
    scan = scan_tree(path)
    if not any(f.endswith(".py") for f in scan["files"]):
        raise HTTPException(422, detail={"code": "no_python", "message": "No Python source files found. DevDNA currently analyses Python projects."})
    project = Project(name=body.name or path.name, source_type="local", source_path=str(path), trusted=False,
                      ingest_stats={"files": scan["file_count"], "languages": scan["languages"]})
    db.add(project)
    db.commit()
    run = _start_run(db, project, background)
    return {"project": project_out(project), "run": run_out(run)}


@router.get("/projects/{project_id}")
def project_detail(project_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    return project_out(p, db.get(AnalysisRun, p.latest_run_id) if p.latest_run_id else None)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    if p.source_type in ("sample", "upload"):
        shutil.rmtree(settings.projects_dir / p.id, ignore_errors=True)
    for model in (Experiment, Prediction, AIInteraction, ReportRecord):
        db.query(model).filter(model.project_id == p.id).delete()
    db.delete(p)
    db.commit()


@router.post("/projects/{project_id}/analyze", status_code=202)
def analyze(project_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    p = get_project(db, project_id)
    running = db.scalars(select(AnalysisRun).where(AnalysisRun.project_id == p.id,
                                                   AnalysisRun.status.in_(["queued", "running"]))).first()
    if running:
        return run_out(running)
    return run_out(_start_run(db, p, background))


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    r = db.get(AnalysisRun, run_id)
    if not r:
        raise HTTPException(404, detail={"code": "run_not_found", "message": "Analysis run not found"})
    return run_out(r)
