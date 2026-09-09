"""Нормативное ядро: поиск, карточка нормы, редакция на дату, перечень актов."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db
from app.core.deps import get_current_user
from app.legal.codes_registry import CODES_BY_DOC_ID
from app.legal.document_cache import catalog as legal_catalog
from app.legal.document_cache import docx_path, ensure_cached, get_plain_text, safe_filename
from app.legal.search import hybrid_search, norm_on_date
from app.legal.topics import INGEST_PRIORITY, TOPICS
from app.models.entitlements import Entitlement, EntitlementIcdLink, IcdCode
from app.models.legal import LegalAct, LegalNorm
from app.models.user import User
from app.schemas import NormOut

router = APIRouter(prefix="/legal", tags=["legal"])


def _to_out(n: LegalNorm) -> NormOut:
    return NormOut(
        id=n.id, act=n.act.title, act_number=n.act.number, article=n.article,
        point=n.point, title=n.title, text_ru=n.text_ru, status=n.status,
        edition_start=n.edition_start, category=n.category, subject=n.subject,
        measure=n.measure, source_url=n.source_url,
    )


def _doc_id_for_act(act: LegalAct) -> str | None:
    if act.source_url:
        m = __import__("re").search(r"/docs/([^/]+)", act.source_url)
        if m:
            return m.group(1)
    for code in CODES_BY_DOC_ID.values():
        if code.get("number") == act.number:
            return code["doc_id"]
    return None


@router.get("/acts")
def list_acts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acts = db.query(LegalAct).order_by(LegalAct.hierarchy_level).all()
    return [
        {"id": a.id, "title": a.title, "type": a.act_type, "number": a.number,
         "adopt_date": a.adopt_date, "norms_count": len(a.norms), "source_url": a.source_url,
         "doc_id": _doc_id_for_act(a)}
        for a in acts
    ]


@router.get("/documents")
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return legal_catalog(db)


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if doc_id not in CODES_BY_DOC_ID:
        raise HTTPException(status_code=404, detail="Документ не в реестре")
    items = legal_catalog(db)
    row = next((x for x in items if x["doc_id"] == doc_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return row


@router.get("/documents/{doc_id}/text")
def document_text(doc_id: str, user: User = Depends(get_current_user)):
    if doc_id not in CODES_BY_DOC_ID:
        raise HTTPException(status_code=404, detail="Документ не в реестре")
    try:
        text = get_plain_text(doc_id, fetch_if_missing=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Не удалось загрузить с adilet: {exc}") from exc
    code = CODES_BY_DOC_ID[doc_id]
    return {
        "doc_id": doc_id,
        "title": code["title"],
        "number": code.get("number"),
        "act_type": code.get("act_type"),
        "adilet_url": f"https://adilet.zan.kz/rus/docs/{doc_id}",
        "text": text,
    }


@router.get("/documents/{doc_id}/download")
def document_download(doc_id: str, user: User = Depends(get_current_user)):
    if doc_id not in CODES_BY_DOC_ID:
        raise HTTPException(status_code=404, detail="Документ не в реестре")
    try:
        ensure_cached(doc_id, force=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Не удалось скачать: {exc}") from exc
    path = docx_path(doc_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe_filename(doc_id),
    )


@router.get("/documents/{doc_id}/download.txt")
def document_download_txt(doc_id: str, user: User = Depends(get_current_user)):
    if doc_id not in CODES_BY_DOC_ID:
        raise HTTPException(status_code=404, detail="Документ не в реестре")
    try:
        text = get_plain_text(doc_id, fetch_if_missing=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PlainTextResponse(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename(doc_id).replace(".docx", ".txt")}"'},
    )


@router.get("/acts/{act_id}/norms", response_model=list[NormOut])
def act_norms(act_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    act = db.get(LegalAct, act_id)
    if not act:
        raise HTTPException(status_code=404, detail="Акт не найден")
    norms = (
        db.query(LegalNorm)
        .filter(LegalNorm.act_id == act_id)
        .order_by(LegalNorm.article, LegalNorm.point)
        .limit(500)
        .all()
    )
    return [_to_out(n) for n in norms]


@router.get("/search", response_model=list[NormOut])
def search(q: str = Query(..., min_length=2), user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    results = hybrid_search(db, q, limit=10)
    return [_to_out(r["norm"]) for r in results]


@router.get("/version-on-date", response_model=NormOut)
def version_on_date(article: str, on: date, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    norm = norm_on_date(db, article, on)
    if not norm:
        raise HTTPException(status_code=404, detail="Норма не найдена")
    return _to_out(norm)


@router.get("/norms/{norm_id}", response_model=NormOut)
def get_norm(norm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    norm = db.get(LegalNorm, norm_id)
    if not norm:
        raise HTTPException(status_code=404, detail="Норма не найдена")
    return _to_out(norm)


@router.get("/topics")
def list_topics(user: User = Depends(get_current_user)):
    return TOPICS


@router.get("/ingest-priority")
def ingest_priority(user: User = Depends(get_current_user)):
    return {"doc_ids": INGEST_PRIORITY}


@router.get("/icd-codes")
def list_icd_codes(
    q: str | None = None,
    chapter: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(IcdCode).order_by(IcdCode.code)
    if chapter:
        query = query.filter(IcdCode.chapter == chapter)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(IcdCode.code.ilike(like) | IcdCode.title_ru.ilike(like))
    rows = query.limit(200).all()
    return [
        {"code": r.code, "title_ru": r.title_ru, "chapter": r.chapter,
         "prevention_note": r.prevention_note}
        for r in rows
    ]


@router.get("/icd-codes/{code}")
def get_icd_code(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = (
        db.query(IcdCode)
        .options(joinedload(IcdCode.links).joinedload(EntitlementIcdLink.entitlement))
        .filter(IcdCode.code == code)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Код МКБ не найден")
    entitlements = []
    for link in row.links:
        e = link.entitlement
        entitlements.append({
            "id": e.id, "title": e.title, "category": e.category,
            "legal_act": e.legal_act, "legal_article": e.legal_article,
            "adilet_url": e.adilet_url, "administering_body": e.administering_body,
        })
    return {
        "code": row.code, "title_ru": row.title_ru, "chapter": row.chapter,
        "prevention_note": row.prevention_note, "entitlements": entitlements,
    }


@router.get("/entitlements")
def list_entitlements(
    category: str | None = None,
    q: str | None = None,
    icd: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Entitlement).order_by(Entitlement.category, Entitlement.title)
    if category:
        query = query.filter(Entitlement.category == category)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            Entitlement.title.ilike(like)
            | Entitlement.beneficiary.ilike(like)
            | Entitlement.condition_text.ilike(like)
        )
    if icd:
        query = query.join(EntitlementIcdLink).filter(EntitlementIcdLink.icd_code == icd)
    rows = query.limit(100).all()
    return [
        {
            "id": e.id, "slug": e.slug, "title": e.title, "category": e.category,
            "beneficiary": e.beneficiary, "condition_text": e.condition_text,
            "amount_note": e.amount_note, "administering_body": e.administering_body,
            "legal_act": e.legal_act, "legal_article": e.legal_article,
            "adilet_url": e.adilet_url, "prevention_relevance": e.prevention_relevance,
        }
        for e in rows
    ]


@router.get("/entitlements/{entitlement_id}")
def get_entitlement(entitlement_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    e = (
        db.query(Entitlement)
        .options(joinedload(Entitlement.icd_links).joinedload(EntitlementIcdLink.icd))
        .filter(Entitlement.id == entitlement_id)
        .first()
    )
    if not e:
        raise HTTPException(status_code=404, detail="Мера поддержки не найдена")
    return {
        "id": e.id, "slug": e.slug, "title": e.title, "category": e.category,
        "beneficiary": e.beneficiary, "condition_text": e.condition_text,
        "amount_note": e.amount_note, "administering_body": e.administering_body,
        "legal_act": e.legal_act, "legal_article": e.legal_article,
        "adilet_doc_id": e.adilet_doc_id, "adilet_url": e.adilet_url,
        "prevention_relevance": e.prevention_relevance,
        "icd_codes": [
            {"code": l.icd.code, "title_ru": l.icd.title_ru, "note": l.note}
            for l in e.icd_links
        ],
    }
