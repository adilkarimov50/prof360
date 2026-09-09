"""Сопоставление «реальной картины» Каскелен / Иргели по материалам папки «Карасайский район».

Читает passports/data/karasai/bundle.json и паспорта kaskelen.json / irgeli.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.analytics.karasai_legal import legal_assessment

ROOT = Path(__file__).resolve().parents[3]
BUNDLE_PATH = ROOT / "passports" / "data" / "karasai" / "bundle.json"
PASSPORT_DIR = ROOT / "passports" / "data"

# Профучёт ОВД из паспортов _итог (раздел 11 — если не оцифрован, fallback)
REGISTRY_OVD = {"kaskelen": 87, "irgeli": 16}
REGISTRY_MINORS = {"kaskelen": 12, "irgeli": 10}

# Hotspots из паспорта (раздел 7 / 16)
PASSPORT_HOTSPOTS = {
    "kaskelen": {"abylay": 46, "asyl_arman": None},
    "irgeli": {"altyn_orda": 88, "asyl_arman": 46, "aport": None},
}

INFRA = {
    "kaskelen": {"cameras": 226, "cameras_needed": 300, "streets_lit": 124, "streets_unlit": 299, "theft_unsolved_pct": 44.8},
    "irgeli": {"cameras": 37, "cameras_needed": None, "streets_lit": 27, "streets_unlit": 107, "theft_unsolved_pct": 51.7},
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle(path: Path | None = None) -> dict:
    p = path or BUNDLE_PATH
    if not p.exists():
        raise FileNotFoundError(f"Нет bundle: {p}. Запустите passports/scripts/ingest_karasai.py")
    return _load_json(p)


def load_passport(locality: str) -> dict:
    return _load_json(PASSPORT_DIR / f"{locality}.json")


def _admin_count(passport: dict, needle: str) -> int | None:
    for row in passport.get("admin_practice", []):
        if needle in row.get("indicator", ""):
            return row.get("count")
    return None


def _pct_diff(a: float | int | None, b: float | int | None) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return round((b - a) / a * 100, 1)


def _flagged(pct: float | None, threshold: float = 10.0) -> bool:
    return pct is not None and abs(pct) > threshold


def population_reality(bundle: dict) -> list[dict]:
    gaps: list[dict] = []
    pop_alt = bundle.get("population_alternatives", {})

    for loc, label, passport_pop, alt_key in (
        ("kaskelen", "г. Каскелен", 87023, "kaskelen"),
        ("irgeli", "Иргелинский с.о.", 63152, "irgeli_passport"),
    ):
        alts = pop_alt.get(alt_key) if alt_key != "irgeli_passport" else [pop_alt.get("irgeli_passport")]
        if loc == "irgeli":
            alts = [pop_alt.get("irgeli_passport"), pop_alt.get("irgeli_gov_kz_2025")]
        crimes = bundle["passport_kpis"][loc]["crimes_current"]
        rates = []
        for p in alts:
            if p and crimes:
                rates.append({"population": p, "rate": round(crimes / p * 10000, 1)})
        if loc == "irgeli" and len(rates) >= 2:
            gap_pct = _pct_diff(rates[0]["rate"], rates[1]["rate"])
            gaps.append({
                "kind": "population",
                "locality": loc,
                "label": label,
                "metric": "Уровень на 10 тыс.",
                "passport_value": rates[0]["rate"],
                "alt_value": rates[1]["rate"],
                "passport_source": f"паспорт ({rates[0]['population']:,} чел.)".replace(",", " "),
                "alt_source": f"gov.kz ({rates[1]['population']:,} чел.)".replace(",", " "),
                "delta_pct": gap_pct,
                "flagged": True,
                "note": f"При {rates[1]['population']:,} реальный уровень {rates[1]['rate']}, а не {rates[0]['rate']}".replace(",", " "),
            })
        elif loc == "kaskelen" and len(rates) >= 2:
            gaps.append({
                "kind": "population",
                "locality": loc,
                "label": label,
                "metric": "База численности",
                "passport_value": rates[0]["population"],
                "alt_value": rates[-1]["population"],
                "passport_source": "перепись 2022",
                "alt_source": "справка акимата",
                "delta_pct": _pct_diff(rates[0]["population"], rates[-1]["population"]),
                "flagged": True,
                "note": "Три цифры без единой базы — уровень 63,7–110 на 10 тыс. не определён",
            })
    return gaps


def crime_triangulation(bundle: dict, passports: dict[str, dict]) -> list[dict]:
    gaps: list[dict] = []
    erdr = bundle["erdr"]
    hs_erdr = erdr.get("hotspots_erdr", {})

    for loc, label in (("kaskelen", "г. Каскелен"), ("irgeli", "Иргелинский с.о.")):
        kpis = bundle["passport_kpis"][loc]
        passport_crimes = kpis["crimes_current"]
        erdr_key = "kaskelen" if loc == "kaskelen" else "irgeli"
        erdr_cnt = erdr.get(erdr_key) if loc == "kaskelen" else sum(
            v for k, v in erdr.get("by_class", {}).items() if k == "irgeli"
        )
        delta = _pct_diff(passport_crimes, erdr_cnt)
        gaps.append({
            "kind": "crime_erdr",
            "locality": loc,
            "label": label,
            "metric": "Уголовные правонарушения",
            "passport_value": passport_crimes,
            "alt_value": erdr_cnt,
            "passport_source": "кримпаспорт _итог",
            "alt_source": "выгрузка ЕРДР",
            "delta_pct": delta,
            "flagged": _flagged(delta),
            "note": f"{'+' if (erdr_cnt or 0) > (passport_crimes or 0) else ''}{(erdr_cnt or 0) - (passport_crimes or 0)} записей",
        })

    # Hotspots triangulation (Иргели)
    for key, passport_val in (("altyn_orda", 88), ("asyl_arman", 46)):
        erdr_val = hs_erdr.get(key, 0)
        delta = _pct_diff(passport_val, erdr_val)
        gaps.append({
            "kind": "hotspot",
            "locality": "irgeli",
            "label": f"Иргели · {key.replace('_', ' ').title()}",
            "metric": "Факты по объекту",
            "passport_value": passport_val,
            "alt_value": erdr_val,
            "passport_source": "раздел 7 паспорта",
            "alt_source": "ЕРДР (геопривязка)",
            "delta_pct": delta,
            "flagged": _flagged(delta),
            "note": "Зависит от методики: зарегистрированные факты vs адрес в ЕРДР vs микрозоны",
        })

    return gaps


def admin_reality(bundle: dict, passports: dict[str, dict]) -> list[dict]:
    gaps: list[dict] = []
    admin = bundle["admin"]

    for loc, label in (("kaskelen", "г. Каскелен"), ("irgeli", "Иргелинский с.о.")):
        pp = passports[loc]
        for art, needle in (("440", "440"), ("442", "442"), ("73", "73")):
            passport_cnt = _admin_count(pp, f"ст.{needle}")
            raw_key = f"{loc}_key"
            admin_cnt = admin.get(raw_key, {}).get(f"ст.{art}")
            district_cnt = admin.get("district_key", {}).get(f"ст.{art}")
            delta = _pct_diff(passport_cnt, admin_cnt)
            gaps.append({
                "kind": "admin_geo",
                "locality": loc,
                "label": label,
                "metric": f"ст.{art} КоАП",
                "passport_value": passport_cnt,
                "alt_value": admin_cnt,
                "passport_source": "паспорт (районная агрегация)" if passport_cnt and admin_cnt and passport_cnt > admin_cnt * 3 else "паспорт",
                "alt_source": "1-АД (геофильтр НП)",
                "district_value": district_cnt,
                "delta_pct": delta,
                "flagged": _flagged(delta) or (passport_cnt and admin_cnt and passport_cnt > admin_cnt * 3),
                "note": "Паспорт использует свод по району; 1-АД по полю «место» занижает город" if loc == "kaskelen" and art == "440" else "",
            })
    return gaps


def registry_gap(bundle: dict, passports: dict[str, dict]) -> list[dict]:
    gaps: list[dict] = []
    narco = bundle["narcology"]
    psych = bundle["psychiatry"]

    for loc, label in (("kaskelen", "г. Каскелен"), ("irgeli", "Иргелинский с.о.")):
        pp = passports[loc]
        ovd_alcohol = REGISTRY_OVD[loc]
        narco_cnt = narco.get(loc, 0)
        psych_cnt = psych.get(loc, 0)
        st440 = _admin_count(pp, "440")
        st442 = _admin_count(pp, "442")
        minors = REGISTRY_MINORS[loc]

        gaps.append({
            "kind": "registry",
            "locality": loc,
            "label": label,
            "metric": "Профучёт алкоголь (ОВД) vs наркология F10",
            "passport_value": ovd_alcohol,
            "alt_value": narco.get("f10_alcohol") if loc == "kaskelen" else narco_cnt,
            "passport_source": "профучёт ОВД",
            "alt_source": "наркологический учёт",
            "delta_pct": _pct_diff(ovd_alcohol, narco_cnt),
            "flagged": ovd_alcohol < (narco_cnt or 0) * 0.5,
            "note": f"{ovd_alcohol} на учёте ОВД при {narco_cnt} в наркологии и {st440} ст.440",
        })
        gaps.append({
            "kind": "registry",
            "locality": loc,
            "label": label,
            "metric": "Профучёт ОВД vs психиатрия",
            "passport_value": ovd_alcohol + minors,
            "alt_value": psych_cnt,
            "passport_source": "профучёт ОВД (сумма категорий)",
            "alt_source": "психиатрический учёт",
            "delta_pct": _pct_diff(ovd_alcohol + minors, psych_cnt),
            "flagged": (ovd_alcohol + minors) < (psych_cnt or 0) * 0.2,
            "note": "Медучёт и полицейский профучёт не синхронизированы (ст.59, приказ №814)",
        })
        if st442 and minors:
            gaps.append({
                "kind": "minors",
                "locality": loc,
                "label": label,
                "metric": "ст.442 vs несовершеннолетние на учёте",
                "passport_value": st442,
                "alt_value": minors,
                "passport_source": "адм. практика",
                "alt_source": "профучёт ОВД",
                "delta_pct": _pct_diff(minors, st442),
                "flagged": st442 > minors * 10,
                "note": f"{st442} фактов ст.442 при {minors} несовершеннолетних на учёте",
            })
    return gaps


def commission_execution(bundle: dict, passports: dict[str, dict]) -> list[dict]:
    gaps: list[dict] = []
    for loc, label in (("kaskelen", "г. Каскелен"), ("irgeli", "Иргелинский с.о.")):
        pp = passports[loc]
        kpi = pp.get("kpi_execution", [])
        filled = sum(1 for k in kpi if k.get("value"))
        total = len(kpi)
        gaps.append({
            "kind": "commission_kpi",
            "locality": loc,
            "label": label,
            "metric": "KPI исполнения (раздел паспорта)",
            "passport_value": filled,
            "alt_value": total,
            "passport_source": "таблицы KPI _итог",
            "alt_source": "требование ст.41–43 Закона",
            "delta_pct": None,
            "flagged": filled == 0 and total > 0,
            "note": f"Заполнено {filled} из {total} показателей KPI",
        })

    for sess in bundle.get("commission", []):
        gaps.append({
            "kind": "commission_kpi",
            "locality": "kaskelen",
            "label": f"Комиссия {sess.get('id', '')}",
            "metric": "Поручения с KPI",
            "passport_value": sess.get("assignments_count", 0),
            "alt_value": 0 if not sess.get("execution_generic") else 1,
            "passport_source": sess.get("file", ""),
            "alt_source": "ответы исполнителей",
            "delta_pct": None,
            "flagged": sess.get("assignments_count", 0) > 0,
            "note": "Отчёты шаблонные; нет количественных KPI (камеры, семьи, акты)",
            "topics": sess.get("topics", {}),
        })
    return gaps


def infrastructure_gaps(passports: dict[str, dict]) -> list[dict]:
    gaps: list[dict] = []
    for loc, label in (("kaskelen", "г. Каскелен"), ("irgeli", "Иргелинский с.о.")):
        inf = INFRA[loc]
        other = INFRA["kaskelen" if loc == "irgeli" else "irgeli"]
        gaps.append({
            "kind": "infrastructure",
            "locality": loc,
            "label": label,
            "metric": "Видеокамеры",
            "passport_value": inf["cameras"],
            "alt_value": other["cameras"],
            "passport_source": "паспорт _итог",
            "alt_source": f"сравнение с {'Каскеленом' if loc == 'irgeli' else 'Иргели'}",
            "delta_pct": _pct_diff(other["cameras"], inf["cameras"]) if loc == "irgeli" else None,
            "flagged": loc == "irgeli" and inf["cameras"] < 50,
            "note": f"{inf['theft_unsolved_pct']}% краж не раскрыто; {inf['streets_unlit']} ул. без освещения",
        })
    return gaps


def prevention_funnel(bundle: dict, passports: dict[str, dict]) -> dict:
    """Воронка: медучёт → ОВД → адм. материалы."""
    funnel: dict[str, list[dict]] = {}
    for loc in ("kaskelen", "irgeli"):
        pp = passports[loc]
        funnel[loc] = [
            {"stage": "Наркология", "count": bundle["narcology"].get(loc, 0)},
            {"stage": "Психиатрия", "count": bundle["psychiatry"].get(loc, 0)},
            {"stage": "Профучёт ОВД (алкоголь)", "count": REGISTRY_OVD[loc]},
            {"stage": "ст.440 КоАП", "count": _admin_count(pp, "440") or 0},
            {"stage": "ст.442 КоАП", "count": _admin_count(pp, "442") or 0},
        ]
    return funnel


def build_analysis(bundle_path: Path | None = None) -> dict[str, Any]:
    bundle = load_bundle(bundle_path)
    passports = {loc: load_passport(loc) for loc in ("kaskelen", "irgeli")}

    raw_gaps: list[dict] = []
    raw_gaps.extend(population_reality(bundle))
    raw_gaps.extend(crime_triangulation(bundle, passports))
    raw_gaps.extend(admin_reality(bundle, passports))
    raw_gaps.extend(registry_gap(bundle, passports))
    raw_gaps.extend(commission_execution(bundle, passports))
    raw_gaps.extend(infrastructure_gaps(passports))

    gaps = legal_assessment(raw_gaps)
    flagged = [g for g in gaps if g.get("flagged")]

    return {
        "meta": {
            **bundle.get("meta", {}),
            "localities": ["kaskelen", "irgeli"],
        },
        "summary": {
            "total_gaps": len(gaps),
            "flagged_gaps": len(flagged),
            "kaskelen_crimes": bundle["passport_kpis"]["kaskelen"]["crimes_current"],
            "irgeli_crimes": bundle["passport_kpis"]["irgeli"]["crimes_current"],
            "erdr_total": bundle["erdr"]["total"],
            "admin_total": bundle["admin"]["total"],
            "narcology_total": bundle["narcology"]["total"],
            "psychiatry_total": bundle["psychiatry"]["total"],
        },
        "kpi_strip": {
            "kaskelen": {
                "passport_crimes": bundle["passport_kpis"]["kaskelen"]["crimes_current"],
                "erdr": bundle["erdr"].get("kaskelen"),
                "admin_1ad": bundle["admin"]["by_class"].get("kaskelen"),
                "narcology": bundle["narcology"].get("kaskelen"),
                "psychiatry": bundle["psychiatry"].get("kaskelen"),
            },
            "irgeli": {
                "passport_crimes": bundle["passport_kpis"]["irgeli"]["crimes_current"],
                "erdr": bundle["erdr"]["by_class"].get("irgeli"),
                "admin_1ad": bundle["admin"]["by_class"].get("irgeli"),
                "narcology": bundle["narcology"].get("irgeli"),
                "psychiatry": bundle["psychiatry"].get("irgeli"),
            },
        },
        "gaps": gaps,
        "funnel": prevention_funnel(bundle, passports),
        "commission": bundle.get("commission", []),
        "erdr_highlights": {
            "fraud_190": bundle["erdr"].get("fraud_190"),
            "theft_188": bundle["erdr"].get("theft_188"),
            "hotspots": bundle["erdr"].get("hotspots_erdr"),
        },
        "conclusions": {
            "kaskelen": (
                "Рост +27,3% driven by мошенничество; 89,3% совершивших не работают; "
                "834 ст.442 при 12 несовершеннолетних на учёте; KPI комиссии не заполнены."
            ),
            "irgeli": (
                "При 43,1 тыс. — уровень ~51 на 10 тыс.; дневной поток рынка 80–90 тыс. не учтён; "
                "51,7% краж не раскрыто при 37 камерах; 16 алкозлоупотребляющих при 284 алкообъектах."
            ),
            "systemic": (
                "Цепочка «выявление → профучёт → индивидуальная мера → контроль → KPI» "
                "разорвана на стыке ОВД ↔ медучреждения ↔ акимат."
            ),
        },
    }
