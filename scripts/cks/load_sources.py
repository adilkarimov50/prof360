from __future__ import annotations

import glob
import os
from pathlib import Path

import pandas as pd

from .districts import detect_district_id, file_hint_district, norm_key
from .geo_normalize import parse_address, registration_scope_from_address
from .iin_utils import normalize_iin
from .paths import ADM_XLSX, CKS_DIR, DEAD_XLSX, PROF_DIR

RATING_PREFIXES = (
    "Рейтинг",
    "Сводная статистика",
    "Сводный отчет",
    "Незанятые (скрытая",
    "Сведения о незанятых лицах в возрасте",
)


def category_slug(filename: str) -> str:
    base = Path(filename).stem
    return norm_key(base)[:80].lower().replace(" ", "_")


def is_person_file(path: Path) -> bool:
    name = path.name
    if name.startswith("~$"):
        return False
    for p in RATING_PREFIXES:
        if name.startswith(p):
            return False
    return True


def load_cks_person_rows() -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(CKS_DIR.glob("*.xlsx")):
        if not is_person_file(path):
            continue
        df = pd.read_excel(path)
        if "ИИН" not in df.columns:
            continue
        slug = category_slug(path.name)
        hint = file_hint_district(path.name)
        is_unemployed = "статистика неработающего" in path.name.lower()

        for _, r in df.iterrows():
            iin = normalize_iin(r.get("ИИН"))
            if not iin:
                continue
            fio = str(r.get("ФИО") or "").strip()
            addr = str(r.get("Адрес") or "").strip()
            raj = str(r.get("Район") or "").strip() if "Район" in df.columns else ""
            parsed = parse_address(addr)
            did = detect_district_id(raj) if raj else parsed.get("district_id")
            if not did and hint:
                did = hint
            if not did:
                did = parsed.get("district_id")
            scope = registration_scope_from_address(addr, raj or did)
            if scope == "oblast" and not did:
                scope = "unresolved"
            rows.append(
                {
                    "iin": iin,
                    "fio": fio,
                    "source_file": path.name,
                    "category": slug,
                    "district_id": did or "",
                    "okrug": parsed.get("okrug") or "",
                    "settlement": parsed.get("settlement") or "",
                    "registration_scope": scope,
                    "address": addr,
                    "has_np_in_source": not is_unemployed,
                    "reason": str(r.get("Причина") or "") if "Причина" in df.columns else "",
                    "categories_extra": str(r.get("Категории") or "") if "Категории" in df.columns else "",
                }
            )
    return pd.DataFrame(rows)


def load_deceased() -> pd.DataFrame:
    if not DEAD_XLSX.exists():
        return pd.DataFrame(columns=["iin", "death_dt"])
    d1 = pd.read_excel(DEAD_XLSX, sheet_name="Умершие 1", usecols=["DeathDt", "IIN"])
    d1 = d1.rename(columns={"DeathDt": "death_dt"})
    d2 = pd.read_excel(DEAD_XLSX, sheet_name="Умершие 2", header=None, usecols=[2, 3, 6])
    d2.columns = ["DtReg", "death_dt", "IIN"]
    d2 = d2[["death_dt", "IIN"]].rename(columns={"IIN": "iin_raw"})
    d1["iin_raw"] = d1["IIN"]
    all_d = pd.concat([d1[["death_dt", "iin_raw"]], d2], ignore_index=True)
    all_d["iin"] = all_d["iin_raw"].map(normalize_iin)
    all_d = all_d[all_d["iin"] != ""]
    all_d["death_dt"] = pd.to_datetime(all_d["death_dt"], errors="coerce")
    all_d = all_d.sort_values("death_dt").drop_duplicates(subset="iin", keep="last")
    return all_d[["iin", "death_dt"]]


def load_prof_dela() -> pd.DataFrame:
    files = ["205_21.05.2026.xls", "206_21.05.2026.xls", "301_21.05.2026.xls", "УДО_21.05.2026.xls"]
    rows = []
    for fn in files:
        p = PROF_DIR / fn
        if not p.exists():
            continue
        df = pd.read_excel(p)
        oc = [c for c in df.columns if str(c).startswith("Область")][0]
        rc = [c for c in df.columns if str(c).startswith("Район")][0]
        nc = [c for c in df.columns if str(c).startswith("Населенный пункт")][0]
        for _, r in df.iterrows():
            iin = normalize_iin(r.get("ИИН"))
            if not iin:
                continue
            rows.append(
                {
                    "iin": iin,
                    "source": fn,
                    "oblast": str(r.get(oc) or ""),
                    "district_text": str(r.get(rc) or ""),
                    "settlement": str(r.get(nc) or ""),
                    "district_id": detect_district_id(str(r.get(rc) or "")) or "",
                }
            )
    return pd.DataFrame(rows)


def load_adm() -> pd.DataFrame:
    if not ADM_XLSX.exists():
        return pd.DataFrame()
    a = pd.read_excel(ADM_XLSX, sheet_name=0, header=1)
    a = a[a["№"].notna()]
    col_iin = "24. ИИН"
    rows = []
    for _, r in a.iterrows():
        iin = normalize_iin(r.get(col_iin))
        if not iin:
            continue
        ob = str(r.get("22. Место жительства Область") or "")
        raj = str(r.get("22. Место жительства Район") or "")
        np_ = str(r.get("22. Место жительства Насел.пункт") or "")
        scope = "oblast"
        ok = norm_key(ob)
        if "АЛМАТЫ" in ok and "ОБЛ" not in ok and "ОБЛАСТ" not in ok:
            scope = "almaty_city"
        elif ok and "АЛМАТИНСК" not in ok and "АЛМАТЫ ОБЛ" not in ok:
            scope = "other_region"
        rows.append(
            {
                "iin": iin,
                "oblast_residence": ob,
                "district_text": raj,
                "settlement": np_,
                "district_id": detect_district_id(raj) or "",
                "registration_scope": scope,
                "article": str(r.get("5. Статья") or ""),
            }
        )
    return pd.DataFrame(rows)


def list_cks_files() -> list[Path]:
    return [p for p in sorted(CKS_DIR.glob("*.xlsx")) if is_person_file(p)]
