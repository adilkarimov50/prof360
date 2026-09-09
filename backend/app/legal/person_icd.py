"""МКБ на карточке лица и связанные меры государственной поддержки."""
from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.crypto import iin_hash
from app.models.entitlements import Entitlement, EntitlementIcdLink, IcdCode, PersonIcdCode
from app.models.person import Person

_ICD_CHAPTER = {
    "F": "F00-F99",
    "Z": "Z00-Z99",
}


def _icd_candidates(code: str) -> list[str]:
    code = (code or "").strip().upper()
    if not code:
        return []
    out = [code]
    if "." in code:
        out.append(code.split(".", 1)[0])
    return out


def ensure_icd_code(db: Session, code: str, title_hint: str | None = None) -> IcdCode | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    row = db.get(IcdCode, code)
    if row:
        return row
    parent = code.split(".", 1)[0] if "." in code else None
    parent_row = db.get(IcdCode, parent) if parent else None
    chapter = _ICD_CHAPTER.get(code[0], None)
    title = title_hint or (f"{parent_row.title_ru} ({code})" if parent_row else f"МКБ-10 {code}")
    row = IcdCode(code=code, title_ru=title[:512], chapter=chapter)
    db.add(row)
    db.flush()
    return row


def entitlements_for_codes(db: Session, codes: list[str]) -> list[Entitlement]:
    keys = {c for code in codes for c in _icd_candidates(code)}
    if not keys:
        return []
    rows = (
        db.query(Entitlement)
        .join(EntitlementIcdLink)
        .filter(EntitlementIcdLink.icd_code.in_(keys))
        .order_by(Entitlement.category, Entitlement.title)
        .all()
    )
    seen: set[int] = set()
    out: list[Entitlement] = []
    for e in rows:
        if e.id not in seen:
            seen.add(e.id)
            out.append(e)
    return out


def person_icd_rows(db: Session, person_id: int) -> list[PersonIcdCode]:
    return (
        db.query(PersonIcdCode)
        .options(joinedload(PersonIcdCode.icd))
        .filter(PersonIcdCode.person_id == person_id)
        .order_by(PersonIcdCode.source, PersonIcdCode.icd_code)
        .all()
    )


def person_support_payload(db: Session, person: Person) -> dict:
    rows = person_icd_rows(db, person.id)
    codes = [r.icd_code for r in rows]
    entitlements = entitlements_for_codes(db, codes)
    on_preventive = bool(person.preventive_records)
    gaps: list[str] = []
    narco = [r for r in rows if r.source == "narco"]
    psych = [r for r in rows if r.source == "psych"]
    if (narco or psych) and not on_preventive:
        gaps.append(
            "Медицинский учёт (нарко/псих) без записи профучёта ОВД — проверить обмен ИИН (приказ №163 ↔ №814/ДСМ-203)"
        )
    if on_preventive and not (narco or psych):
        alcohol_forms = any(
            "алког" in (p.category or "").lower() or "301" in (p.form or "")
            for p in person.preventive_records
        )
        if alcohol_forms:
            gaps.append("Профучёт ОВД (алкоголь) без кода F10/F19 в наркологии — типичный разрыв реестров")

    return {
        "person_id": person.id,
        "icd_codes": [
            {
                "code": r.icd_code,
                "title_ru": r.icd.title_ru if r.icd else r.icd_code,
                "chapter": r.icd.chapter if r.icd else None,
                "source": r.source,
                "note": r.note,
                "prevention_note": r.icd.prevention_note if r.icd else None,
            }
            for r in rows
        ],
        "entitlements": [
            {
                "id": e.id,
                "title": e.title,
                "category": e.category,
                "legal_act": e.legal_act,
                "legal_article": e.legal_article,
                "adilet_url": e.adilet_url,
                "administering_body": e.administering_body,
                "condition_text": e.condition_text,
                "prevention_relevance": e.prevention_relevance,
            }
            for e in entitlements
        ],
        "gaps": gaps,
        "subordinate_acts": [
            {"title": "Приказ МВД №163 — правила профучёта ОВД", "adilet_url": "https://adilet.zan.kz/rus/docs/V2600038111"},
            {"title": "Приказ Минздрава №814 / ДСМ-203 — мед. учёт ПАВ", "adilet_url": "https://adilet.zan.kz/rus/docs/V2000021680"},
            {"title": "Приказ МВД №1008 — координация профилактики", "adilet_url": "https://adilet.zan.kz/rus/docs/G25C0001008"},
        ] if rows or on_preventive else [],
    }


def _registry_path() -> Path | None:
    base = Path(settings.data_dir).resolve()
    candidates = [
        base / "passports" / "data" / "karasai" / "registry_crossmatch.json",
        base / "data" / "karasai" / "registry_crossmatch.json",
        Path(__file__).resolve().parents[2] / "passports" / "data" / "karasai" / "registry_crossmatch.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def import_registry_mkb(db: Session) -> dict:
    """Импорт narco_mkb / psych_mkb из registry_crossmatch.json по ИИН."""
    path = _registry_path()
    if not path:
        return {"error": "registry_crossmatch.json не найден", "linked": 0}

    data = json.loads(path.read_text(encoding="utf-8"))
    table = data.get("table") or []
    linked = 0
    persons = 0
    icd_added = 0
    skipped = 0

    for row in table:
        iin = re.sub(r"\D", "", str(row.get("iin") or ""))
        if len(iin) != 12:
            skipped += 1
            continue
        person = db.query(Person).filter(Person.iin_hash == iin_hash(iin)).first()
        if not person:
            skipped += 1
            continue
        persons += 1
        flags = row.get("flags") or ""
        for source, field in (("narco", "narco_mkb"), ("psych", "psych_mkb")):
            code = (row.get(field) or "").strip().upper()
            if not code:
                continue
            before = db.get(IcdCode, code)
            ensure_icd_code(db, code)
            if not before:
                icd_added += 1
            existing = (
                db.query(PersonIcdCode)
                .filter(
                    PersonIcdCode.person_id == person.id,
                    PersonIcdCode.icd_code == code,
                    PersonIcdCode.source == source,
                )
                .first()
            )
            if existing:
                continue
            db.add(PersonIcdCode(
                person_id=person.id,
                icd_code=code,
                source=source,
                note=flags[:500] if flags else None,
            ))
            linked += 1

    db.commit()
    return {
        "registry": str(path),
        "rows_total": len(table),
        "persons_matched": persons,
        "icd_links_added": linked,
        "icd_codes_added": icd_added,
        "skipped_no_person": skipped,
    }
