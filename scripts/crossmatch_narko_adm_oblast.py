"""Сверка областной административной практики по опьянению с диспансерным учётом.

Источники:
  F00-99.xlsx                  — диспансерный учёт F00-F99, Алматинская область, на 08.09.2026
  АДМ ПРОФ СЕМБЫТ алк.xlsx     — форма 1-АД, протоколы по области, 01.01.2026-11.06.2026

ИИН в выгрузке учёта маскирован в первых шести знаках, но эти знаки совпадают
с датой рождения (YYMMDD), которая приведена отдельной колонкой. Это позволяет
восстановить ИИН и сверить два учёта. На выход подаются только агрегаты.
"""

import sys

import pandas as pd

REF = pd.Timestamp("2026-09-08")


def load_registry() -> pd.DataFrame:
    raw = pd.read_excel("F00-99.xlsx", sheet_name="spis_pac_sostoit", header=None)
    rows = []
    for _, r in raw.iterrows():
        if pd.isna(r[6]) or pd.isna(r[2]):
            continue
        masked = str(r[2]).strip()
        if not masked.startswith("******"):
            continue
        birth = pd.to_datetime(r[3], errors="coerce", dayfirst=True)
        if pd.isna(birth):
            continue
        iin = birth.strftime("%y%m%d") + masked[6:]
        if len(iin) != 12 or not iin.isdigit():
            continue
        rows.append({"iin": iin, "code": str(r[6]).strip().upper(), "sex": str(r[5]).strip()})
    d = pd.DataFrame(rows).drop_duplicates(subset="iin")
    d["block"] = d["code"].str.slice(0, 3)
    return d


def load_adm() -> pd.DataFrame:
    a = pd.read_excel("АДМ ПРОФ СЕМБЫТ алк.xlsx", sheet_name=0, header=1)
    a = a[a["№"].notna()].copy()
    a["iin"] = (
        a["24. ИИН"].astype(str)
        .str.replace(r"[^0-9]", "", regex=True)
        .str.zfill(12)
    )
    a = a[a["iin"].str.len() == 12]
    a = a[a["iin"] != "0" * 12]
    a["art"] = a["9. Квалификация"].astype(str).str.strip()
    a["district"] = (
        a["2. Район совершения правонарушения"].astype(str)
        .str.replace(r"_x000D_|\n", "", regex=True).str.strip()
    )
    return a


def main() -> None:
    reg = load_registry()
    adm = load_adm()

    alco = set(reg[reg["block"] == "F10"]["iin"])
    narco = set(reg[reg["block"].isin([f"F1{i}" for i in range(1, 10)])]["iin"])
    any_f = set(reg["iin"])

    print(f"учёт F00-F99: {len(reg)} уникальных лиц "
          f"(F10 алкоголь {len(alco)}, F11-F19 наркотики {len(narco)})")
    print(f"административная практика: {len(adm)} протоколов, "
          f"{adm['iin'].nunique()} уникальных лиц, период 01.01-11.06.2026")

    # --- ст. 440: появление в общественном месте в состоянии опьянения ---
    a440 = adm[adm["art"].str.startswith("ст.440 ")]
    persons440 = set(a440["iin"])
    print(f"\n=== Статья 440 КоАП (опьянение в общественном месте) ===")
    print(f"протоколов: {len(a440)}, уникальных лиц: {len(persons440)}")
    ov_a = persons440 & alco
    ov_n = persons440 & narco
    ov_any = persons440 & any_f
    print(f"  состоят на алкогольном учёте (F10): {len(ov_a)} "
          f"({len(ov_a) / len(persons440) * 100:.1f}%)")
    print(f"  состоят на наркологическом учёте (F11-F19): {len(ov_n)}")
    print(f"  состоят на любом психиатрическом учёте (F00-F99): {len(ov_any)} "
          f"({len(ov_any) / len(persons440) * 100:.1f}%)")
    print(f"  НЕ состоят ни на каком учёте: {len(persons440 - any_f)} "
          f"({len(persons440 - any_f) / len(persons440) * 100:.1f}%)")

    # --- повторность: целевая группа для контроля трезвости ---
    cnt = a440.groupby("iin").size()
    print(f"\n-- повторность по ст. 440 за 5,5 месяца --")
    for k in (1, 2, 3):
        n = (cnt == k).sum() if k < 3 else (cnt >= 3).sum()
        label = f"{k} протокол" if k < 3 else "3 и более"
        print(f"  {label}: {n} лиц")
    rep = set(cnt[cnt >= 2].index)
    print(f"  привлекались 2 и более раз: {len(rep)} лиц "
          f"({len(rep) / len(persons440) * 100:.1f}%), "
          f"на них {int(cnt[cnt >= 2].sum())} протоколов "
          f"({cnt[cnt >= 2].sum() / len(a440) * 100:.1f}% всех)")
    print(f"  из повторных состоят на учёте F10: {len(rep & alco)} "
          f"({len(rep & alco) / len(rep) * 100:.1f}%)")

    # --- ст. 461: потребление наркотиков без назначения врача ---
    a461 = adm[adm["art"].str.startswith("ст.461")]
    p461 = set(a461["iin"])
    if p461:
        print(f"\n=== Статья 461 КоАП (потребление наркотических средств) ===")
        print(f"протоколов: {len(a461)}, уникальных лиц: {len(p461)}")
        print(f"  состоят на наркологическом учёте (F11-F19): {len(p461 & narco)} "
              f"({len(p461 & narco) / len(p461) * 100:.1f}%)")
        print(f"  состоят на любом учёте F00-F99: {len(p461 & any_f)}")
        print(f"  НЕ состоят ни на каком учёте: {len(p461 - any_f)} "
              f"({len(p461 - any_f) / len(p461) * 100:.1f}%)")

    # --- по районам ---
    print(f"\n-- статья 440 по районам: протоколы и охват учётом --")
    out = []
    for dist, g in a440.groupby("district"):
        p = set(g["iin"])
        out.append({
            "район": dist,
            "протоколов": len(g),
            "лиц": len(p),
            "на учёте F10": len(p & alco),
            "% на учёте": round(len(p & alco) / len(p) * 100, 1),
            "повторных лиц": int((g.groupby("iin").size() >= 2).sum()),
        })
    t = pd.DataFrame(out).sort_values("протоколов", ascending=False)
    print(t.to_string(index=False))

    # --- структура статей ---
    print(f"\n-- структура протоколов по статьям --")
    for art, n in adm["art"].value_counts().head(12).items():
        p = set(adm[adm["art"] == art]["iin"])
        print(f"  {art:<16} {n:5d} протоколов, {len(p):5d} лиц, "
              f"на учёте F00-F99: {len(p & any_f)}")


if __name__ == "__main__":
    sys.exit(main())
