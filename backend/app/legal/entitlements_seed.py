"""Загрузка справочников МКБ-10 и мер государственной поддержки."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.legal.codes_registry import doc_url
from app.models.entitlements import Entitlement, EntitlementIcdLink, IcdCode

_DATA = Path(__file__).resolve().parent / "data" / "reference_catalog.json"


def _load_catalog() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def seed_entitlements(db: Session) -> dict:
    """Идемпотентная загрузка МКБ и entitlements. Возвращает счётчики."""
    catalog = _load_catalog()
    icd_added = 0
    ent_added = 0
    links_added = 0

    for row in catalog.get("icd_codes", []):
        if db.get(IcdCode, row["code"]):
            continue
        db.add(IcdCode(
            code=row["code"],
            title_ru=row["title_ru"],
            chapter=row.get("chapter"),
            prevention_note=row.get("prevention_note"),
        ))
        icd_added += 1

    db.flush()

    for row in catalog.get("entitlements", []):
        existing = db.query(Entitlement).filter(Entitlement.slug == row["slug"]).first()
        doc_id = row["adilet_doc_id"]
        url = doc_url(doc_id)
        if existing:
            ent = existing
        else:
            ent = Entitlement(
                slug=row["slug"],
                title=row["title"],
                category=row["category"],
                beneficiary=row["beneficiary"],
                condition_text=row["condition_text"],
                amount_note=row.get("amount_note"),
                administering_body=row["administering_body"],
                legal_act=row["legal_act"],
                legal_article=row["legal_article"],
                adilet_doc_id=doc_id,
                adilet_url=url,
                prevention_relevance=row.get("prevention_relevance"),
            )
            db.add(ent)
            db.flush()
            ent_added += 1

        existing_codes = {l.icd_code for l in ent.icd_links}
        for code in row.get("icd_codes") or []:
            if code in existing_codes:
                continue
            if not db.get(IcdCode, code):
                continue
            db.add(EntitlementIcdLink(entitlement_id=ent.id, icd_code=code))
            links_added += 1

    db.commit()
    return {"icd_added": icd_added, "entitlements_added": ent_added, "links_added": links_added}
