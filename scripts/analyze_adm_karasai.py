"""Сводка административной практики и профучёта по Карасайскому району.

Карасайское УП ДП Алматинской области — код УП/РОП 1906214, КАТО района 195200000.
"""

import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
BASE = Path("Карасайский район")
UP_KARASAI = "1906214"
KATO_KARASAI = "195200000"


def load(name: str) -> pd.DataFrame:
    d = pd.read_excel(BASE / name, sheet_name="data", header=1).dropna(how="all")
    d["up"] = d["УП / РОП"].astype(str).str.replace(r"\.0$", "", regex=True)
    d["kato"] = d["Район"].astype(str).str.replace(r"\.0$", "", regex=True)
    d.loc[d["Район"].isna(), "kato"] = ""
    d["dt"] = pd.to_datetime(d["Дата постановки на учёт"], errors="coerce")
    d["нп"] = d["Населенный пункт"].fillna("").astype(str).str.upper().str.strip()
    return d


def block(d: pd.DataFrame, category: str, label: str) -> None:
    s = d[
        d["Категория лица"].astype(str).str.contains(category, na=False)
        & (d["dt"].dt.year == 2026)
        & (d["up"] == UP_KARASAI)
    ]
    no_addr = int((s["нп"] == "").sum())
    print(f"\n{label} — Карасайское УП, 2026 год: {len(s)}")
    print(f"  населённый пункт не заполнен: {no_addr} ({no_addr / max(len(s), 1):.0%})")
    print(f"  из заполненных — КАТО Карасайского р-на: {(s['kato'] == KATO_KARASAI).sum()}")
    top = s[s["нп"] != ""]["нп"].value_counts().head(8)
    if len(top):
        print("  населённые пункты:", ", ".join(f"{k} {v}" for k, v in top.items()))


d = load("защитка.xlsx")
print("=" * 72)
print(f"Файл защитка.xlsx — строк {len(d)}; Карасайское УП — {(d['up'] == UP_KARASAI).sum()}")
block(d, "ЗАЩИТНОЕ ПРЕДПИСАНИЕ", "Защитные предписания (ст. 60 ЗРК)")
block(d, "ОСОБЫЕ ТРЕБОВАНИЯ", "Особые требования к поведению (ст. 61 ЗРК)")
block(d, "ОФИЦИАЛЬНОЕ ПРЕДОСТЕРЕЖЕНИЕ", "Официальные предостережения (ст. 51 ЗРК)")

d2 = load("особое треб.xlsx")
print("\n" + "=" * 72)
print(f"Файл особое треб.xlsx — строк {len(d2)}; Карасайское УП — {(d2['up'] == UP_KARASAI).sum()}")
block(d2, "ОСОБЫЕ ТРЕБОВАНИЯ", "Особые требования к поведению (ст. 61 ЗРК)")
