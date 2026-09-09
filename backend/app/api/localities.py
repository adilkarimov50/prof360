"""API населённых пунктов — чтение JSON-паспортов из passports/data."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter(prefix="/localities", tags=["localities"])

ORDER = [
    "alatau", "konaev", "kaskelen", "talgar",
    "otegen_batyr", "irgeli", "uzynagash", "chundzha", "issyk",
]
SKIP = {"geo", "districts"}


def _data_dir() -> Path:
    base = Path(settings.data_dir).resolve()
    candidates = [base / "passports" / "data", base / "data", base]
    for c in candidates:
        if (c / "kaskelen.json").exists() or any(c.glob("*.json")):
            return c
    return base / "passports" / "data"


def _load_all() -> list[dict]:
    data_dir = _data_dir()
    files = {
        p.stem: p for p in data_dir.glob("*.json")
        if not p.stem.startswith("_") and p.stem not in SKIP
    }
    ordered = [files[n] for n in ORDER if n in files]
    ordered += [files[n] for n in sorted(files) if n not in ORDER]
    out = []
    for path in ordered:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _public_item(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "district": p.get("district") or p.get("summary", {}).get("district"),
        "passport_status": p.get("passport_status", "full"),
        "summary": p.get("summary"),
        "locality_profile": p.get("locality_profile"),
        "data_quality": p.get("data_quality"),
    }


@router.get("")
def list_localities():
    return [_public_item(p) for p in _load_all()]


@router.get("/{locality_id}")
def get_locality(locality_id: str):
    for p in _load_all():
        if p.get("id") == locality_id:
            return _public_item(p)
    raise HTTPException(status_code=404, detail="Населённый пункт не найден")
