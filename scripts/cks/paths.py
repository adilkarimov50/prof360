from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CKS_DIR = ROOT / "социалка за область " / "ЦКС"
DEAD_DIR = ROOT / "социалка за область " / "Умершиев иНПО"
DEAD_XLSX = DEAD_DIR / "Умершие c 2015 по 2026гг.xlsx"
PROF_DIR = ROOT / "проф дела"
ADM_XLSX = ROOT / "АДМ ПРОФ СЕМБЫТ алк.xlsx"

REPORTS = ROOT / "reports"
DATA_CKS = ROOT / "passports" / "data" / "cks"
DATA_DISTRICTS = DATA_CKS / "districts"
PRIVATE_CKS = ROOT / "passports" / "private" / "data" / "cks"
PRIVATE_PERSONS = PRIVATE_CKS / "persons"

OUT_PUBLIC_OBLAST = ROOT / "passports" / "docs" / "cks.html"
OUT_PUBLIC_DISTRICT = ROOT / "passports" / "docs" / "cks_district.html"
OUT_CKS_DATA_JS = ROOT / "passports" / "docs" / "assets" / "js" / "cks_data.js"
OUT_PRIVATE = ROOT / "passports" / "private" / "cks_operativ.html"
OUT_PRIVATE_CSV = ROOT / "passports" / "private" / "cks_persons_full.csv"

PERSONS_STORE = PRIVATE_CKS / "persons_normalized.pkl"
CROSSMATCH_JSON = DATA_CKS / "crossmatch.json"
