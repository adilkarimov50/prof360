#!/usr/bin/env python3
"""Дашборды ЦКС: публичные агрегаты + оперативный слой по лицам."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.cks.iin_utils import IIN_RE, mask_iin
from scripts.cks.paths import (
    DATA_CKS,
    DATA_DISTRICTS,
    OUT_CKS_DATA_JS,
    OUT_PRIVATE,
    OUT_PRIVATE_CSV,
    OUT_PUBLIC_DISTRICT,
    OUT_PUBLIC_OBLAST,
    PERSONS_STORE,
    PRIVATE_PERSONS,
)

DOCS_CKS = ROOT / "passports" / "docs" / "assets" / "data" / "cks"
FIO_RE = re.compile(
    r"\b[А-ЯЁA-Z][а-яёa-z]{2,}\s+[А-ЯЁA-Z][а-яёa-z]{2,}\s+[А-ЯЁA-Z][а-яёa-z]{2,}\b"
)


def sync_public_json() -> None:
    DOCS_CKS.mkdir(parents=True, exist_ok=True)
    (DOCS_CKS / "districts").mkdir(exist_ok=True)
    shutil.copy2(DATA_CKS / "oblast.json", DOCS_CKS / "oblast.json")
    if (DATA_CKS / "crossmatch.json").exists():
        cm = json.loads((DATA_CKS / "crossmatch.json").read_text(encoding="utf-8"))
        for key in (
            "dead_in_active_lists_sample",
            "multi_category_sample",
            "other_region_sample",
            "adm_other_region_sample",
        ):
            cm.pop(key, None)
        (DOCS_CKS / "crossmatch.json").write_text(
            json.dumps(cm, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if (DATA_CKS / "person_shards_index.json").exists():
        shutil.copy2(DATA_CKS / "person_shards_index.json", DOCS_CKS / "person_shards_index.json")
    vp = DATA_CKS / "violations_public.json"
    if vp.exists():
        shutil.copy2(vp, DOCS_CKS / "violations_public.json")
    for p in DATA_DISTRICTS.glob("*.json"):
        shutil.copy2(p, DOCS_CKS / "districts" / p.name)


def load_oblast() -> dict:
    return json.loads((DATA_CKS / "oblast.json").read_text(encoding="utf-8"))


def assert_no_pii_in_public(blob: str) -> None:
    if IIN_RE.search(blob):
        raise SystemExit("PII guard: найден 12-значный ИИН в публичном HTML/JSON ЦКС")
    if '"fio"' in blob.lower():
        raise SystemExit("PII guard: поле fio в публичном HTML/JSON ЦКС")


def render_oblast_html(oblast: dict) -> str:
    data_json = json.dumps(oblast, ensure_ascii=False)
    cards = "".join(
        f"""<a class="card link-card" href="cks_district.html?d={d['id']}">
        <strong>{d['title']}</strong>
        <span class="muted">{d['persons']:,} лиц · {d['rows']:,} записей</span></a>""".replace(",", " ")
        for d in oblast.get("districts", [])
    )
    cross = oblast.get("crossmatch", {})
    cross_rows = "".join(
        f"<tr><td>{k}</td><td class='num'>{v:,}</td></tr>".replace(",", " ")
        for k, v in sorted(cross.items(), key=lambda x: -x[1] if isinstance(x[1], int) else 0)
    )
    cat_rows = "".join(
        f"<tr><td>{c['label']}</td><td class='num'>{c['persons']:,}</td></tr>".replace(",", " ")
        for c in oblast.get("top_categories", [])[:20]
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ЦКС · социальный мониторинг · Алматинская область</title>
<link rel="stylesheet" href="assets/css/app.css?v=20260918">
</head>
<body data-site-page="cks">
<div id="chrome-top"></div>
<main class="wrap">
<section class="hero" style="margin-top:16px">
  <div class="hero__eyebrow">Центр комплексной поддержки · 2026</div>
  <h1>Социальный мониторинг по данным ЦКС</h1>
  <p>Обзор по Алматинской области: категории социального риска, районы и города.
     Персональные данные — только в служебном файле <code>passports/private/cks_operativ.html</code>.</p>
</section>
<div class="kpi grid grid--4" style="margin:24px 0">
  <div class="card kpi"><b>{oblast['totals']['persons']:,}</b><span>уникальных лиц</span></div>
  <div class="card kpi"><b>{oblast['totals']['rows']:,}</b><span>записей (категории)</span></div>
  <div class="card kpi"><b>{len(oblast.get('districts',[]))}</b><span>районов / городов</span></div>
  <div class="card kpi"><b>{cross.get('other_region_persons',0):,}</b><span>иногородний scope</span></div>
</div>
<h2 class="section__title">Карточки районов и городов</h2>
<div class="grid grid--3">{cards}</div>
<h2 style="margin-top:32px">Сверки (агрегаты)</h2>
<table class="table"><thead><tr><th>Показатель</th><th class="num">Значение</th></tr></thead><tbody>{cross_rows}</tbody></table>
<h2 style="margin-top:32px">Топ категорий</h2>
<table class="table"><thead><tr><th>Категория</th><th class="num">Лиц</th></tr></thead><tbody>{cat_rows}</tbody></table>
</main>
<div id="chrome-bottom"></div>
<script src="assets/js/data.js"></script>
<script src="assets/js/ui.js"></script>
<script>
mountSiteChrome('cks');
</script>
<script id="cks-oblast" type="application/json">{data_json}</script>
</body>
</html>"""


def render_district_html() -> str:
    return """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ЦКС · район</title>
<link rel="stylesheet" href="assets/css/app.css?v=20260918">
<style>
.table-wrap{max-height:420px;overflow:auto}
.link-np{cursor:pointer;color:var(--accent,#1a5c42);text-decoration:underline}
</style>
</head>
<body data-site-page="cks_district">
<div id="chrome-top"></div>
<main class="wrap" id="main"></main>
<div id="chrome-bottom"></div>
<script src="assets/js/data.js"></script>
<script src="assets/js/ui.js"></script>
<script>
mountSiteChrome('cks');
const params = new URLSearchParams(location.search);
const did = params.get('d') || 'karasai';
const np = params.get('np') || '';

function esc(s) {
  if (s == null) return '—';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}
function fmt(n) { return Number(n).toLocaleString('ru-RU'); }

fetch('assets/data/cks/districts/' + did + '.json')
  .then(r => r.json())
  .then(data => {
    const mp = data.mini_passport || {};
    const hl = (mp.highlights || []).map(h => '<li>' + esc(h) + '</li>').join('');
    let rows = (data.settlements || []).map(s => {
      const link = s.settlement && s.settlement !== '—'
        ? `<span class="link-np" data-np="${esc(s.settlement)}">${esc(s.settlement)}</span>`
        : esc(s.settlement);
      return `<tr><td>${esc(s.okrug)}</td><td>${link}</td><td class="num">${fmt(s.persons)}</td><td class="num">${fmt(s.rows)}</td></tr>`;
    }).join('');
    const cats = (data.categories || []).slice(0,15).map(c =>
      `<tr><td>${esc(c.label)}</td><td class="num">${fmt(c.persons)}</td></tr>`).join('');
    document.getElementById('main').innerHTML = `
      <section class="hero" style="margin-top:16px">
        <div class="hero__eyebrow"><a href="cks.html">← Область</a></div>
        <h1>${esc(data.title)}</h1>
        <p>Мини-кримпаспорт социального мониторинга (ЦКС). НП с &lt;50 лиц — только в таблице.</p>
      </section>
      <div class="card"><div class="card__title">Ключевые показатели</div><ul class="list-check">${hl}</ul></div>
      <h2>Населённые пункты и сельские округа</h2>
      <p class="note">Для файлов «неработающее население» НП в источнике отсутствует — строки учтены на уровне района.</p>
      <div class="table-wrap"><table class="table"><thead><tr><th>Сельский округ</th><th>Населённый пункт</th><th class="num">Лиц</th><th class="num">Записей</th></tr></thead><tbody>${rows}</tbody></table></div>
      <h2>Категории</h2>
      <table class="table"><thead><tr><th>Категория</th><th class="num">Лиц</th></tr></thead><tbody>${cats}</tbody></table>
      <div id="np-detail"></div>`;
    document.querySelectorAll('.link-np').forEach(el => {
      el.addEventListener('click', () => showNp(el.dataset.np, data));
    });
    if (np) showNp(np, data);
  });

function showNp(name, data) {
  const s = (data.settlements || []).find(x => x.settlement === name);
  const box = document.getElementById('np-detail');
  if (!s || !s.mini_passport) {
    box.innerHTML = '<div class="card"><p>Мини-паспорт НП доступен при ≥50 лиц или выберите другой пункт.</p></div>';
    return;
  }
  const mp = s.mini_passport;
  box.innerHTML = `<div class="card"><div class="card__title">Мини-паспорт: ${esc(mp.settlement)}</div>
    <p>Округ: ${esc(mp.okrug)} · Лиц: ${fmt(mp.persons)}</p>
    <p>Категории: ${(mp.top_categories||[]).map(esc).join(', ')}</p></div>`;
}
</script>
</body>
</html>"""


def render_operative_html(oblast: dict) -> str:
    """Оперативный дашборд: загрузка шардов из private/data/cks/persons/."""
    meta = json.dumps(
        {
            "oblast": {k: oblast[k] for k in ("title", "totals", "district_ids") if k in oblast},
            "shard_base": "data/cks/persons/",
        },
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ЦКС · оператив · не публиковать</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f4f6f9;color:#1a2332}}
.wrap{{max-width:1200px;margin:0 auto;padding:24px}}
.warn{{background:#fff4f2;border:1px solid #e8b4ad;padding:12px 16px;border-radius:8px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#fff}}
th,td{{border-bottom:1px solid #dde3ea;padding:8px;text-align:left}}
.controls{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
input,select{{padding:8px 10px;font-size:14px}}
.scroll{{max-height:520px;overflow:auto;border:1px solid #dde3ea}}
.mono{{font-family:monospace}}
</style>
</head>
<body>
<div class="wrap">
<div class="warn"><strong>Служебно.</strong> ФИО и маскированный ИИН. Не выкладывать на GitHub Pages.</div>
<h1>ЦКС · таблицы по лицам</h1>
<div class="controls">
  <select id="district"></select>
  <input id="q" placeholder="Поиск ФИО / ИИН (4 цифры)" size="28">
  <input id="np" placeholder="Населённый пункт" size="24">
  <button id="load">Загрузить шард</button>
</div>
<div id="status"></div>
<div class="scroll"><table><thead><tr>
  <th>ФИО</th><th>ИИН</th><th>НП</th><th>Округ</th><th>Категории</th><th>Scope</th>
</tr></thead><tbody id="rows"></tbody></table></div>
</div>
<script id="cks-meta" type="application/json">{meta}</script>
<script>
const META = JSON.parse(document.getElementById('cks-meta').textContent);
let manifest = {{}};

fetch('data/cks/persons/manifest.json').then(r => r.json()).then(m => {{
  manifest = m;
  const sel = document.getElementById('district');
  Object.keys(m).sort().forEach(d => {{
    const o = document.createElement('option');
    o.value = d; o.textContent = d + ' (' + m[d].length + ' стр.)';
    sel.appendChild(o);
  }});
}});

function esc(s) {{ const d=document.createElement('div'); d.textContent=s??''; return d.innerHTML; }}

async function loadShard() {{
  const d = document.getElementById('district').value;
  const files = manifest[d] || [];
  if (!files.length) {{ document.getElementById('status').textContent = 'Нет шардов'; return; }}
  document.getElementById('status').textContent = 'Загрузка ' + files.length + ' файлов…';
  const q = document.getElementById('q').value.trim().toLowerCase();
  const npF = document.getElementById('np').value.trim().toLowerCase();
  let all = [];
  for (const f of files) {{
    const r = await fetch('data/cks/persons/' + f);
    const j = await r.json();
    all = all.concat(j.records || []);
  }}
  let filtered = all;
  if (npF) filtered = filtered.filter(r => (r.settlement||'').toLowerCase().includes(npF));
  if (q) filtered = filtered.filter(r =>
    (r.fio||'').toLowerCase().includes(q) || (r.iin_masked||'').includes(q) || (r.iin||'').endsWith(q));
  document.getElementById('rows').innerHTML = filtered.slice(0,2000).map(r => `<tr>
    <td>${{esc(r.fio)}}</td><td class="mono">${{esc(r.iin_masked || r.iin)}}</td>
    <td>${{esc(r.settlement)}}</td><td>${{esc(r.okrug)}}</td>
    <td>${{esc((r.categories||[]).join('; '))}}</td><td>${{esc(r.registration_scope)}}</td></tr>`).join('');
  document.getElementById('status').textContent = 'Показано ' + Math.min(filtered.length,2000) + ' из ' + filtered.length;
}}

document.getElementById('load').onclick = loadShard;
</script>
</body>
</html>"""


def export_full_csv() -> None:
    if not PERSONS_STORE.exists():
        return
    import pandas as pd

    df = pd.read_pickle(PERSONS_STORE)
    agg = df.groupby("iin").agg(
        fio=("fio", "first"),
        district_id=("district_id", "first"),
        settlement=("settlement_canon", "first"),
        categories=("category", lambda s: ";".join(sorted(set(s.astype(str))))),
    ).reset_index()
    OUT_PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUT_PRIVATE_CSV, index=False, encoding="utf-8-sig")
    print(f"CSV: {OUT_PRIVATE_CSV} ({len(agg)} rows)")


def write_cks_data_js(oblast: dict) -> None:
    body = json.dumps({"oblast": oblast}, ensure_ascii=False, indent=1)
    OUT_CKS_DATA_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_CKS_DATA_JS.write_text(
        "/* scripts/build_cks_dashboard.py */\nwindow.CKS_DATA = " + body + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    sync_public_json()
    oblast = load_oblast()
    write_cks_data_js(oblast)
    for path in (OUT_PUBLIC_OBLAST, OUT_PUBLIC_DISTRICT):
        if path.exists():
            assert_no_pii_in_public(path.read_text(encoding="utf-8"))

    OUT_PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PRIVATE.write_text(render_operative_html(oblast), encoding="utf-8")

    # Копия manifest рядом с operativ для fetch
    # Шарды уже в passports/private/data/cks/persons/ (build_cks_data.py)

    export_full_csv()
    print(f"Public: {OUT_PUBLIC_OBLAST}, {OUT_PUBLIC_DISTRICT}")
    print(f"Private: {OUT_PRIVATE}")


if __name__ == "__main__":
    main()
