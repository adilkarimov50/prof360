"""Связь AdminCase.article_base с LegalNorm (КоАП и др.)."""
from sqlalchemy.orm import Session

from app.models.legal import LegalAct, LegalNorm
from app.models.person import AdminCase


def link_cases_to_norms(db: Session, batch: int = 1000) -> dict:
    """Заполняет legal_norm_id у дел по совпадению article_base + КоАП."""
    koap = db.query(LegalAct).filter(LegalAct.number == "235-V").first()
    if not koap:
        return {"linked": 0, "error": "КоАП не найден в legal_acts"}

    norms = {
        n.article: n.id
        for n in db.query(LegalNorm).filter(LegalNorm.act_id == koap.id, LegalNorm.point.is_(None)).all()
        if n.article
    }
    linked = 0
    q = db.query(AdminCase).filter(
        AdminCase.article_base.is_not(None),
        AdminCase.legal_norm_id.is_(None),
    )
    for case in q.yield_per(batch):
        norm_id = norms.get(case.article_base)
        if norm_id:
            case.legal_norm_id = norm_id
            linked += 1
            if linked % batch == 0:
                db.flush()
    db.commit()
    return {"linked": linked, "koap_norms": len(norms)}
