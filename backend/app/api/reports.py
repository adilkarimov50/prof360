"""Генерация и выгрузка документов (требует право экспорта; пишет аудит + водяной знак)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.db import get_db
from app.core.deps import abac_district_filter, client_ip, get_current_user, require_export
from app.core.rbac import allow_pii
from app.models.person import AdminCase, Person
from app.models.user import User
from app.reports import adm_blocks, adm_blocks_report, generator, karasai_reality_report, spravka, spravka_health
from app.schemas import ReportRequest

router = APIRouter(prefix="/reports", tags=["reports"])

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/generate")
def generate(data: ReportRequest, request: Request,
             user: User = Depends(require_export), db: Session = Depends(get_db)):
    export_id = uuid.uuid4().hex[:12]
    allow_pii_flag = allow_pii(user)

    if data.kind == "person":
        person = db.get(Person, int(data.target)) if data.target else None
        if not person:
            raise HTTPException(status_code=404, detail="Лицо не найдено")
        abac = abac_district_filter(user)
        if abac and person.district != abac:
            raise HTTPException(status_code=403, detail="Нет доступа (ABAC)")
        content = generator.person_report_docx(db, person, user.full_name, export_id, allow_pii_flag)
        media, ext = _DOCX, "docx"
        fname = f"spravka_person_{person.id}_{export_id}.{ext}"

    elif data.kind == "district":
        district = data.target or abac_district_filter(user) or "Алматинская область"
        content = generator.district_report_docx(db, district, user.full_name, export_id)
        media, ext = _DOCX, "docx"
        fname = f"spravka_district_{export_id}.{ext}"

    elif data.kind == "escalation":
        content = generator.escalation_report_xlsx(db, user.full_name, export_id)
        media, ext = _XLSX, "xlsx"
        fname = f"escalation_{export_id}.{ext}"

    elif data.kind == "admin_violations":
        df = data.district or abac_district_filter(user)
        abac = abac_district_filter(user)
        if abac and df != abac:
            raise HTTPException(status_code=403, detail="Нет доступа к данному району (ABAC)")
        content = generator.proceedings_violations_xlsx(db, df, user.full_name, export_id)
        media, ext = _XLSX, "xlsx"
        fname = f"admin_violations_{export_id}.{ext}"

    elif data.kind in ("representation", "protest", "appeal", "requirement"):
        # Акты прокурорского реагирования (Приказ ГП РК №32) — по конкретному лицу
        person = db.get(Person, int(data.target)) if data.target else None
        if not person:
            raise HTTPException(status_code=404, detail="Лицо не найдено")
        abac = abac_district_filter(user)
        if abac and person.district != abac:
            raise HTTPException(status_code=403, detail="Нет доступа (ABAC)")
        case = None
        if data.case_id:
            case = db.get(AdminCase, data.case_id)
            if case and case.person_id != person.id:
                raise HTTPException(status_code=400, detail="Материал не относится к лицу")
        if data.kind == "representation":
            content = generator.representation_docx(db, person, user.full_name, export_id)
        elif data.kind == "protest":
            content = generator.protest_docx(db, person, case, user.full_name, export_id)
        elif data.kind == "appeal":
            content = generator.appeal_motion_docx(db, person, case, user.full_name, export_id)
        else:
            content = generator.requirement_docx(db, person, user.full_name, export_id)
        media, ext = _DOCX, "docx"
        fname = f"{data.kind}_{person.id}_{export_id}.{ext}"

    elif data.kind in ("spravka_police", "spravka_mio", "spravka_complex", "spravka_health"):
        # Комплексная аналитическая справка (полиция / МИО / здравоохранение / общая). ABAC по району.
        df = data.district or abac_district_filter(user)
        abac = abac_district_filter(user)
        if abac and df != abac:
            raise HTTPException(status_code=403, detail="Нет доступа к данному району (ABAC)")
        if data.kind == "spravka_police":
            content = spravka.spravka_police_docx(db, df, user.full_name, export_id)
        elif data.kind == "spravka_mio":
            content = spravka.spravka_mio_docx(db, df, user.full_name, export_id)
        elif data.kind == "spravka_health":
            content = spravka_health.spravka_health_docx(db, df, user.full_name, export_id)
        else:
            content = spravka.spravka_complex_docx(db, df, user.full_name, export_id)
        media, ext = _DOCX, "docx"
        fname = f"{data.kind}_{export_id}.{ext}"

    elif data.kind == "adm_blocks":
        # Разделение адм. практики: составы против личности и общества vs дорожная безопасность
        try:
            content = adm_blocks_report.adm_blocks_docx(user.full_name, export_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Выгрузка формы 1-АД недоступна")
        media, ext = _DOCX, "docx"
        fname = f"adm_blocks_chundzha_{export_id}.{ext}"

    elif data.kind == "karasai_reality":
        try:
            content = karasai_reality_report.karasai_reality_docx(user.full_name, export_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        media, ext = _DOCX, "docx"
        fname = f"karasai_reality_{export_id}.{ext}"
    else:
        raise HTTPException(status_code=400, detail="Неизвестный тип отчёта")

    log_action(db, action="export", user=user, ip=client_ip(request),
               export_id=export_id, entity_type="report",
               details={"kind": data.kind, "target": data.target, "file": fname})

    return StreamingResponse(
        iter([content]), media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"',
                 "X-Export-Id": export_id},
    )


@router.get("/adm-blocks")
def adm_blocks_analytics(user: User = Depends(get_current_user)) -> dict:
    """Аналитика адм. практики с. Чунджа с разделением на блоки (для экрана системы)."""
    try:
        return adm_blocks.build_analysis()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Выгрузка формы 1-АД недоступна")


@router.get("/karasai-analysis")
def karasai_analysis(user: User = Depends(get_current_user)) -> dict:
    """Сопоставление реальной картины: Каскелен и Иргели."""
    from app.analytics.karasai_crosscheck import build_analysis

    try:
        return build_analysis()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Данные Карасайского района не загружены")
