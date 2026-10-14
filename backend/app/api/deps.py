from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Project


def get_project(db: Session, project_id: str) -> Project:
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, detail={"code": "project_not_found", "message": f"Project '{project_id}' not found"})
    return p


def require_run(db: Session, project: Project) -> AnalysisRun:
    if not project.latest_run_id:
        raise HTTPException(409, detail={"code": "not_analysed", "message": "This project has not been analysed yet."})
    return db.get(AnalysisRun, project.latest_run_id)
