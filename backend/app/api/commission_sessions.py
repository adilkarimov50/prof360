"""API заседаний МВК: импорт документов, поручения, исполнение, эффективность."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.commission import effectiveness as eff_module
from app.commission import session_ingestor
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.rbac import require_capability
from app.models.commission_session import CommissionAssignment, CommissionExecution, CommissionSession
from app.models.user import User

router = APIRouter(prefix="/commission-sessions", tags=["commission-sessions"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    id: int
    session_number: str
    session_date: str | None = None
    session_type: str
    quarter: int | None = None
    year: int | None = None
    title: str | None = None
    chairman: str | None = None
    effectiveness_score: float | None = None
    assignments_count: int = 0
    executions_count: int = 0
    grade: str | None = None
    goals_achieved: str | None = None

    model_config = {"from_attributes": True}


class AssignmentOut(BaseModel):
    id: int
    point_number: str
    text: str
    responsible_organs: str | None = None
    deadline: str | None = None
    topic: str | None = None
    priority: str | None = None
    executions_count: int = 0
    completion_rate: float | None = None

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    id: int
    organ_name: str
    organ_type: str | None = None
    execution_status: str
    quality_score: float | None = None
    ai_assessment: str | None = None
    issues: list | None = None
    source_file: str | None = None

    model_config = {"from_attributes": True}


class IngestRequest(BaseModel):
    folder_path: str
    session_number: str | None = None
    session_date: str | None = None
    session_type: str = "ordinary"
    force: bool = False


class ExecutionUpdateRequest(BaseModel):
    execution_status: str | None = None
    quality_score: float | None = None
    ai_assessment: str | None = None


class AssignmentCreateRequest(BaseModel):
    point_number: str
    text: str
    responsible_organs: str | None = None
    deadline: str | None = None
    topic: str | None = None
    priority: str | None = None


class SessionCreateRequest(BaseModel):
    session_number: str
    session_date: str | None = None
    session_type: str = "ordinary"
    quarter: int | None = None
    year: int | None = None
    title: str | None = None
    chairman: str | None = None
    location: str | None = None


class ExecutionCreateRequest(BaseModel):
    organ_name: str
    organ_type: str | None = None
    response_text: str | None = None
    execution_status: str = "unknown"
    quality_score: float | None = None
    ai_assessment: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_out(s: CommissionSession) -> SessionOut:
    ai = (s.analysis_json or {}).get("ai_analysis", {})
    return SessionOut(
        id=s.id,
        session_number=s.session_number,
        session_date=s.session_date.isoformat() if s.session_date else None,
        session_type=s.session_type,
        quarter=s.quarter,
        year=s.year,
        title=s.title,
        chairman=s.chairman,
        effectiveness_score=s.effectiveness_score,
        assignments_count=len(s.assignments),
        executions_count=sum(len(a.executions) for a in s.assignments),
        grade=ai.get("overall_grade"),
        goals_achieved=ai.get("goals_achieved"),
    )


def _assignment_out(a: CommissionAssignment) -> AssignmentOut:
    comp = eff_module._assignment_completion_rate(a)
    return AssignmentOut(
        id=a.id,
        point_number=a.point_number,
        text=a.text,
        responsible_organs=a.responsible_organs,
        deadline=a.deadline,
        topic=a.topic,
        priority=a.priority,
        executions_count=len(a.executions),
        completion_rate=comp.get("rate"),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[SessionOut])
def list_sessions(
    year: int | None = Query(None),
    quarter: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(CommissionSession).order_by(
        CommissionSession.year.desc(),
        CommissionSession.session_date.desc(),
    )
    if year:
        q = q.filter(CommissionSession.year == year)
    if quarter:
        q = q.filter(CommissionSession.quarter == quarter)
    return [_session_out(s) for s in q.limit(100).all()]


@router.get("/cross-report")
def cross_report(
    year: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Сводный отчёт по всем сессиям: динамика, рейтинг органов."""
    return eff_module.get_cross_session_report(db, year=year)


@router.post("/ingest")
def ingest_documents(
    req: IngestRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    """Загрузить папку документов МВК и создать заседания/поручения/исполнения."""
    result = session_ingestor.ingest_folder(
        db,
        folder_path=req.folder_path,
        session_number=req.session_number or "auto",
        session_date_str=req.session_date,
        session_type=req.session_type,
        force=req.force,
    )
    return result


@router.post("/{session_id}/assess")
def assess_executions(
    session_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    """Запустить AI-оценку качества исполнения поручений заседания."""
    background_tasks.add_task(_run_assess, session_id)
    return {"status": "started", "session_id": session_id}


def _run_assess(session_id: int) -> None:
    from app.core.db import SessionLocal
    db = SessionLocal()
    try:
        session_ingestor.assess_session_executions(db, session_id)
    finally:
        db.close()


@router.post("/{session_id}/analyze")
def analyze_session(
    session_id: int,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    """AI-заключение об эффективности заседания МВК."""
    session = db.query(CommissionSession).filter(CommissionSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Заседание не найдено")
    return eff_module.ai_effectiveness_report(db, session)


@router.get("/{session_id}", response_model=dict)
def get_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(CommissionSession).filter(CommissionSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Заседание не найдено")

    assignments = [_assignment_out(a) for a in session.assignments]
    matrix = eff_module._organ_execution_matrix(session)
    underperformers = eff_module._underperforming_organs(matrix)

    basic = eff_module.compute_session_effectiveness(db, session)

    return {
        **_session_out(session).model_dump(),
        "agenda_raw": session.agenda_raw,
        "assignments": [a.model_dump() for a in assignments],
        "matrix": matrix,
        "underperforming_organs": underperformers,
        "assignment_breakdown": basic.get("assignment_breakdown", []),
        "ai_analysis": (session.analysis_json or {}).get("ai_analysis"),
    }


@router.get("/{session_id}/assignments/{assignment_id}/executions")
def get_executions(
    session_id: int,
    assignment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assignment = db.query(CommissionAssignment).filter(
        CommissionAssignment.id == assignment_id,
        CommissionAssignment.session_id == session_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Поручение не найдено")
    return [
        ExecutionOut.model_validate(e).model_dump()
        for e in assignment.executions
    ]


@router.patch("/{session_id}/assignments/{assignment_id}/executions/{exec_id}")
def update_execution(
    session_id: int,
    assignment_id: int,
    exec_id: int,
    body: ExecutionUpdateRequest,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    """Ручная корректура оценки исполнения."""
    ex = db.query(CommissionExecution).filter(
        CommissionExecution.id == exec_id,
        CommissionExecution.assignment_id == assignment_id,
    ).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if body.execution_status is not None:
        ex.execution_status = body.execution_status
    if body.quality_score is not None:
        ex.quality_score = body.quality_score
    if body.ai_assessment is not None:
        ex.ai_assessment = body.ai_assessment
    ex.analyzed_at = datetime.utcnow()
    db.commit()
    return ExecutionOut.model_validate(ex).model_dump()


@router.post("/", response_model=SessionOut)
def create_session(
    body: SessionCreateRequest,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    """Создать заседание вручную."""
    from datetime import datetime as dt
    date_obj = None
    if body.session_date:
        try:
            date_obj = dt.strptime(body.session_date, "%Y-%m-%d").date()
        except Exception:
            pass
    quarter = body.quarter or (((date_obj.month - 1) // 3 + 1) if date_obj else None)
    year = body.year or (date_obj.year if date_obj else None)
    session = CommissionSession(
        session_number=body.session_number,
        session_date=date_obj,
        session_type=body.session_type,
        quarter=quarter,
        year=year,
        title=body.title,
        chairman=body.chairman,
        location=body.location,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(session)


@router.post("/{session_id}/assignments")
def add_assignment(
    session_id: int,
    body: AssignmentCreateRequest,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    """Добавить поручение к заседанию."""
    session = db.query(CommissionSession).filter(CommissionSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Заседание не найдено")
    assignment = CommissionAssignment(
        session_id=session_id,
        point_number=body.point_number,
        text=body.text,
        responsible_organs=body.responsible_organs,
        deadline=body.deadline,
        topic=body.topic or "other",
        priority=body.priority or "medium",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return _assignment_out(assignment).model_dump()


@router.post("/{session_id}/assignments/{assignment_id}/executions")
def add_execution(
    session_id: int,
    assignment_id: int,
    body: ExecutionCreateRequest,
    user: User = Depends(require_capability("commission")),
    db: Session = Depends(get_db),
):
    """Добавить запись об исполнении поручения органом."""
    assignment = db.query(CommissionAssignment).filter(
        CommissionAssignment.id == assignment_id,
        CommissionAssignment.session_id == session_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Поручение не найдено")
    ex = CommissionExecution(
        assignment_id=assignment_id,
        organ_name=body.organ_name,
        organ_type=body.organ_type,
        response_text=body.response_text,
        execution_status=body.execution_status,
        quality_score=body.quality_score,
        ai_assessment=body.ai_assessment,
        analyzed_at=datetime.utcnow() if body.execution_status != "unknown" else None,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ExecutionOut.model_validate(ex).model_dump()


@router.delete("/{session_id}")
def delete_session(
    session_id: int,
    user: User = Depends(require_capability("admin")),
    db: Session = Depends(get_db),
):
    session = db.query(CommissionSession).filter(CommissionSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Заседание не найдено")
    db.delete(session)
    db.commit()
    return {"deleted": True, "id": session_id}
