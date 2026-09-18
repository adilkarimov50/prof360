/* ЦКС: обзор области и карточки районов */

const CKS_LABELS = {
  dead_in_cks: 'Умершие, но числятся в списках ЦКС',
  dead_in_prof_dela: 'Умершие в выгрузке «проф дела» (ЕИРПУ)',
  dead_in_adm_protocols: 'Умершие в протоколах 1-АД',
  prof_in_cks: 'ЕИРПУ и одновременно в ЦКС',
  adm_in_cks: '1-АД и одновременно в ЦКС',
  prof_and_adm_in_cks: 'ЕИРПУ + 1-АД + ЦКС',
  persons_3plus_categories: 'Лица в 3+ категориях ЦКС',
  other_region_persons: 'Признак регистрации в другом регионе',
};

function cksEsc(s) {
  if (s == null || s === '') return '—';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function cksFmt(n) {
  return Number(n || 0).toLocaleString('ru-RU');
}

function cksDataBase() {
  const p = window.location.pathname;
  return p.includes('/docs/') || p.endsWith('/docs') ? 'assets/data/cks/' : 'assets/data/cks/';
}

async function cksLoadJson(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(path);
  return r.json();
}

function cksShowPanel(id) {
  document.querySelectorAll('.cks-panel').forEach((el) => el.classList.remove('active'));
  document.querySelectorAll('.cks-subnav [data-cks-tab]').forEach((el) => {
    el.classList.toggle('active', el.dataset.cksTab === id);
  });
  const panel = document.getElementById(`cks-panel-${id}`);
  if (panel) panel.classList.add('active');
  if (id && id.startsWith('sec-')) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function cksBindSubnav() {
  document.querySelectorAll('.cks-subnav [data-cks-tab]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      cksShowPanel(btn.dataset.cksTab);
    });
  });
}

function cksSortTable(tableId, colIdx, numeric) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.querySelector('tbody');
  const rows = [...tbody.querySelectorAll('tr')];
  const key = table.dataset.sortCol;
  const asc = table.dataset.sortAsc !== String(colIdx);
  rows.sort((a, b) => {
    const va = a.children[colIdx]?.textContent || '';
    const vb = b.children[colIdx]?.textContent || '';
    if (numeric) {
      const na = parseFloat(va.replace(/\s/g, '').replace(',', '.')) || 0;
      const nb = parseFloat(vb.replace(/\s/g, '').replace(',', '.')) || 0;
      return asc ? na - nb : nb - na;
    }
    return asc ? va.localeCompare(vb, 'ru') : vb.localeCompare(va, 'ru');
  });
  rows.forEach((r) => tbody.appendChild(r));
  table.dataset.sortCol = String(colIdx);
  table.dataset.sortAsc = asc ? String(colIdx) : '';
}

function cksDistrictCount(violations, did, key) {
  const block = violations?.[key];
  if (!block?.by_district) return 0;
  const row = block.by_district.find((x) => x.id === did);
  return row ? row.count : 0;
}

async function cksInitOblast() {
  const base = cksDataBase();
  const [oblast, violations] = await Promise.all([
    cksLoadJson(`${base}oblast.json`),
    cksLoadJson(`${base}violations_public.json`).catch(() => ({})),
  ]);
  const root = document.getElementById('cks-app');
  if (!root) return;

  const v = violations.summary || {};
  const cross = oblast.crossmatch || {};

  root.innerHTML = `
    <section class="cks-hero">
      <div class="wrap-inner">
        <div class="hero__eyebrow">Центр комплексной поддержки · Алматинская область · 2026</div>
        <h1>Социальный мониторинг (ЦКС)</h1>
        <p>Обзор по 11 районам и городам: категории риска, населённые пункты, сверки с умершими,
           уголовным контуром (ЕИРПУ) и административной практикой (1-АД).</p>
      </div>
    </section>

    <nav class="cks-subnav" aria-label="Разделы ЦКС">
      <div class="wrap cks-subnav__inner">
        <button type="button" class="active" data-cks-tab="overview">Обзор</button>
        <button type="button" data-cks-tab="districts">Районы и города</button>
        <button type="button" data-cks-tab="violations">Нарушения сверок</button>
        <button type="button" data-cks-tab="categories">Категории</button>
        <a class="cks-tab" href="index.html">← Кримпаспорт</a>
      </div>
    </nav>

    <div class="wrap">
      <div id="cks-panel-overview" class="cks-panel active">
        <div class="cks-kpi">
          <div class="card"><b>${cksFmt(oblast.totals.persons)}</b><span>уникальных лиц</span></div>
          <div class="card"><b>${cksFmt(oblast.totals.rows)}</b><span>записей в категориях</span></div>
          <div class="card"><b>11</b><span>районов / городов</span></div>
          <div class="card cks-kpi--alert"><b>${cksFmt(v.dead_in_cks || cross.dead_in_cks)}</b><span>умершие в списках ЦКС</span></div>
          <div class="card"><b>${cksFmt(v.prof_in_cks)}</b><span>ЕИРПУ ∩ ЦКС</span></div>
          <div class="card"><b>${cksFmt(v.adm_in_cks)}</b><span>1-АД ∩ ЦКС</span></div>
        </div>
        <div class="cks-callout">
          <h3>На что обратить внимание прокурору</h3>
          <p style="margin:0;font-size:14px;line-height:1.55">
            Сверка с реестром умерших (2015–2026): <strong>${cksFmt(v.dead_in_cks)}</strong> лиц остаются
            в действующих категориях ЦКС. По ЕИРПУ («проф дела»): <strong>${cksFmt(v.dead_in_prof_dela)}</strong>
            умерших при <strong>${cksFmt(v.prof_in_cks)}</strong> пересечениях с ЦКС.
            По 1-АД: <strong>${cksFmt(v.dead_in_adm_protocols)}</strong> умерших при
            <strong>${cksFmt(v.adm_in_cks)}</strong> пересечениях с соцучётом.
          </p>
        </div>
      </div>

      <div id="cks-panel-districts" class="cks-panel">
        <div class="cks-toolbar">
          <input type="search" id="cks-district-filter" placeholder="Поиск района или города…" autocomplete="off">
        </div>
        <div class="cks-district-grid" id="cks-district-grid"></div>
      </div>

      <div id="cks-panel-violations" class="cks-panel">
        <div id="cks-violations-content"></div>
      </div>

      <div id="cks-panel-categories" class="cks-panel">
        <div class="cks-toolbar">
          <input type="search" id="cks-cat-filter" placeholder="Фильтр категории…">
        </div>
        <div class="cks-table-wrap">
          <table class="tbl" id="cks-cat-table">
            <thead><tr>
              <th data-col="0">Категория</th>
              <th class="num" data-col="1">Лиц</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>`;

  const grid = document.getElementById('cks-district-grid');
  (oblast.districts || []).forEach((d) => {
    const deadN = cksDistrictCount(violations, d.id, 'dead_in_active_cks');
    const profN = cksDistrictCount(violations, d.id, 'prof_accountability');
    const admN = cksDistrictCount(violations, d.id, 'admin_accountability');
    const badges = [];
    if (deadN) badges.push(`<span class="badge badge--risk-high">умершие: ${deadN}</span>`);
    if (profN) badges.push(`<span class="badge badge--profile">ЕИРПУ: ${profN}</span>`);
    const a = document.createElement('a');
    a.className = 'cks-district-card';
    a.href = `cks_district.html?d=${encodeURIComponent(d.id)}`;
    a.dataset.title = d.title.toLowerCase();
    a.innerHTML = `
      <strong>${cksEsc(d.title)}</strong>
      <span class="meta">${cksFmt(d.persons)} лиц · ${cksFmt(d.rows)} записей</span>
      ${badges.length ? `<div class="badge-row">${badges.join('')}</div>` : ''}`;
    grid.appendChild(a);
  });

  document.getElementById('cks-district-filter')?.addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    grid.querySelectorAll('.cks-district-card').forEach((card) => {
      card.style.display = !q || card.dataset.title.includes(q) ? '' : 'none';
    });
  });

  const vEl = document.getElementById('cks-violations-content');
  const dead = violations.dead_in_active_cks || {};
  const prof = violations.prof_accountability || {};
  const adm = violations.admin_accountability || {};
  vEl.innerHTML = `
    <h2 class="cks-section-title">Умершие в действующих списках ЦКС</h2>
    <p class="note">Лица из реестра умерших (2015–2026), которые одновременно числятся в категориях ЦКС.</p>
    ${cksViolTable('cks-dead-dist', 'Район / город', dead.by_district)}
    ${cksViolTable('cks-dead-cat', 'Категория ЦКС', dead.by_category, 'label')}
    <h2 class="cks-section-title">Уголовный контур (ЕИРПУ «проф дела»)</h2>
    <p class="note">Всего пересечений с ЦКС: <strong>${cksFmt(prof.prof_dela_in_cks_total)}</strong>.
       Умершие, но остающиеся в выгрузке ЕИРПУ: <strong>${cksFmt(prof.dead_still_in_prof_dela)}</strong>.</p>
    ${cksViolTable('cks-prof-dist', 'Район', prof.by_district)}
    <h2 class="cks-section-title">Административная практика (1-АД)</h2>
    <p class="note">Пересечений с ЦКС: <strong>${cksFmt(adm.adm_protocols_in_cks_total)}</strong>.
       Умершие в протоколах: <strong>${cksFmt(adm.dead_still_in_adm)}</strong>.
       Протоколы с местом жительства в другом регионе: <strong>${cksFmt(adm.adm_other_region_protocols)}</strong>.</p>
    ${cksViolTable('cks-adm-dist', 'Район', adm.by_district)}`;

  vEl.querySelectorAll('th[data-col]').forEach((th) => {
    th.addEventListener('click', () => {
      const table = th.closest('table');
      if (table?.id) cksSortTable(table.id, +th.dataset.col, th.dataset.col !== '0');
    });
  });

  const catBody = document.querySelector('#cks-cat-table tbody');
  (oblast.top_categories || []).forEach((c) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${cksEsc(c.label)}</td><td class="num">${cksFmt(c.persons)}</td>`;
    tr.dataset.label = c.label.toLowerCase();
    catBody.appendChild(tr);
  });
  document.getElementById('cks-cat-filter')?.addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    catBody.querySelectorAll('tr').forEach((tr) => {
      tr.style.display = !q || tr.dataset.label.includes(q) ? '' : 'none';
    });
  });
  document.querySelectorAll('#cks-cat-table th[data-col]').forEach((th) => {
    th.addEventListener('click', () => cksSortTable('cks-cat-table', +th.dataset.col, th.dataset.col === '1'));
  });

  cksBindSubnav();
}

function cksViolTable(id, col1, rows, labelKey) {
  if (!rows?.length) return `<p class="note">Нет данных для отображения.</p>`;
  const body = rows.map((r) => {
    const name = labelKey ? r[labelKey] : r.title;
    return `<tr><td>${cksEsc(name)}</td><td class="num">${cksFmt(r.count)}</td></tr>`;
  }).join('');
  return `<div class="cks-table-wrap" style="margin-bottom:24px">
    <table class="tbl" id="${id}"><thead><tr>
      <th data-col="0">${cksEsc(col1)}</th><th class="num" data-col="1">Лиц</th>
    </tr></thead><tbody>${body}</tbody></table></div>`;
}

async function cksInitDistrict() {
  const params = new URLSearchParams(location.search);
  let did = params.get('d') || 'karasai';
  const npParam = params.get('np') || '';
  const root = document.getElementById('cks-district-app');
  if (!root) return;

  const base = cksDataBase();
  const oblast = await cksLoadJson(`${base}oblast.json`);
  const violations = await cksLoadJson(`${base}violations_public.json`).catch(() => ({}));

  async function renderDistrict() {
    const data = await cksLoadJson(`${base}districts/${did}.json`);
    const deadN = cksDistrictCount(violations, did, 'dead_in_active_cks');
    const profN = (violations.prof_accountability?.by_district || []).find((x) => x.id === did)?.count || 0;
    const admN = (violations.admin_accountability?.by_district || []).find((x) => x.id === did)?.count || 0;
    const mp = data.mini_passport || {};
    const hl = (mp.highlights || []).map((h) => `<li><span>${cksEsc(h)}</span></li>`).join('');

    const districtOptions = (oblast.districts || []).map((d) =>
      `<option value="${cksEsc(d.id)}" ${d.id === did ? 'selected' : ''}>${cksEsc(d.title)}</option>`).join('');

    root.innerHTML = `
      <section class="cks-hero">
        <div class="wrap-inner">
          <p class="hero__eyebrow"><a href="cks.html">← Область ЦКС</a></p>
          <h1>${cksEsc(data.title)}</h1>
          <p>Мини-кримпаспорт социального мониторинга · ${cksFmt(data.totals?.persons)} лиц</p>
        </div>
      </section>
      <nav class="cks-subnav">
        <div class="wrap cks-subnav__inner">
          <button type="button" class="active" data-cks-tab="d-overview">Показатели</button>
          <button type="button" data-cks-tab="d-settlements">Населённые пункты</button>
          <button type="button" data-cks-tab="d-violations">Сверки</button>
          <button type="button" data-cks-tab="d-categories">Категории</button>
          <div class="cks-district-switch">
            <select id="cks-district-jump" aria-label="Выбор района">${districtOptions}</select>
          </div>
        </div>
      </nav>
      <div class="wrap">
        <div id="cks-panel-d-overview" class="cks-panel active">
          <div class="cks-kpi">
            <div class="card"><b>${cksFmt(data.totals?.persons)}</b><span>лиц</span></div>
            <div class="card"><b>${cksFmt(data.totals?.rows)}</b><span>записей</span></div>
            <div class="card cks-kpi--alert"><b>${cksFmt(deadN)}</b><span>умершие в ЦКС</span></div>
            <div class="card"><b>${cksFmt(profN)}</b><span>ЕИРПУ ∩ ЦКС</span></div>
            <div class="card"><b>${cksFmt(admN)}</b><span>1-АД ∩ ЦКС</span></div>
          </div>
          <div class="card"><div class="card__title">Ключевые показатели</div><ul class="list-check">${hl}</ul></div>
        </div>
        <div id="cks-panel-d-settlements" class="cks-panel">
          <p class="note">Для выгрузок «неработающее население» НП в источнике часто отсутствует — учёт на уровне района.</p>
          <div class="cks-toolbar"><input type="search" id="cks-np-filter" placeholder="Поиск НП или округа…"></div>
          <div class="cks-table-wrap">
            <table class="tbl" id="cks-np-table">
              <thead><tr>
                <th data-col="0">Сельский округ</th>
                <th data-col="1">Населённый пункт</th>
                <th class="num" data-col="2">Лиц</th>
                <th class="num" data-col="3">Записей</th>
              </tr></thead>
              <tbody id="cks-np-body"></tbody>
            </table>
          </div>
          <div id="cks-np-detail"></div>
        </div>
        <div id="cks-panel-d-violations" class="cks-panel">
          <div class="cks-callout">
            <h3>Нарушения по району</h3>
            <p style="margin:0">Умершие в списках ЦКС: <strong>${cksFmt(deadN)}</strong> ·
            ЕИРПУ ∩ ЦКС: <strong>${cksFmt(profN)}</strong> · 1-АД ∩ ЦКС: <strong>${cksFmt(admN)}</strong></p>
          </div>
          <p class="note">Детальные списки лиц — в служебном файле <code>passports/private/cks_operativ.html</code>.</p>
        </div>
        <div id="cks-panel-d-categories" class="cks-panel">
          <div class="cks-table-wrap">
            <table class="tbl" id="cks-d-cat-table">
              <thead><tr><th>Категория</th><th class="num">Лиц</th></tr></thead>
              <tbody>${(data.categories || []).map((c) =>
                `<tr><td>${cksEsc(c.label)}</td><td class="num">${cksFmt(c.persons)}</td></tr>`).join('')}
              </tbody></table>
          </div>
        </div>
      </div>`;

    const tbody = document.getElementById('cks-np-body');
    (data.settlements || []).forEach((s) => {
      const tr = document.createElement('tr');
      const npCell = s.settlement && s.settlement !== '—'
        ? `<span class="cks-np-link" data-np="${cksEsc(s.settlement)}">${cksEsc(s.settlement)}</span>`
        : cksEsc(s.settlement);
      tr.innerHTML = `<td>${cksEsc(s.okrug)}</td><td>${npCell}</td>
        <td class="num">${cksFmt(s.persons)}</td><td class="num">${cksFmt(s.rows)}</td>`;
      tr.dataset.search = `${s.okrug} ${s.settlement}`.toLowerCase();
      tbody.appendChild(tr);
    });

    document.getElementById('cks-np-filter')?.addEventListener('input', (e) => {
      const q = e.target.value.trim().toLowerCase();
      tbody.querySelectorAll('tr').forEach((tr) => {
        tr.style.display = !q || tr.dataset.search.includes(q) ? '' : 'none';
      });
    });

    tbody.querySelectorAll('.cks-np-link').forEach((el) => {
      el.addEventListener('click', () => showNp(el.dataset.np, data));
    });

    document.getElementById('cks-district-jump')?.addEventListener('change', (e) => {
      location.href = `cks_district.html?d=${encodeURIComponent(e.target.value)}`;
    });

    document.querySelectorAll('.cks-subnav [data-cks-tab]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = btn.dataset.cksTab.replace('d-', '');
        document.querySelectorAll('.cks-panel').forEach((p) => p.classList.remove('active'));
        document.getElementById(`cks-panel-d-${tab}`)?.classList.add('active');
        document.querySelectorAll('.cks-subnav [data-cks-tab]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    if (npParam) showNp(npParam, data);
  }

  function showNp(name, data) {
    const s = (data.settlements || []).find((x) => x.settlement === name);
    const box = document.getElementById('cks-np-detail');
    if (!box) return;
    document.querySelectorAll('.cks-panel').forEach((p) => p.classList.remove('active'));
    document.getElementById('cks-panel-d-settlements')?.classList.add('active');
    document.querySelectorAll('.cks-subnav [data-cks-tab]').forEach((b) => b.classList.remove('active'));
    document.querySelector('[data-cks-tab="d-settlements"]')?.classList.add('active');
    if (!s?.mini_passport) {
      box.innerHTML = `<div class="card card-warn"><p>Мини-паспорт НП формируется при ≥50 лиц. Сейчас: ${cksFmt(s?.persons || 0)}.</p></div>`;
      return;
    }
    const mp = s.mini_passport;
    box.innerHTML = `<div class="card"><div class="card__title">${cksEsc(mp.settlement)}</div>
      <p>Округ: ${cksEsc(mp.okrug)} · Лиц: ${cksFmt(mp.persons)}</p>
      <p>Категории: ${(mp.top_categories || []).map(cksEsc).join(', ')}</p></div>`;
    box.scrollIntoView({ behavior: 'smooth' });
  }

  await renderDistrict();
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('cks-app')) cksInitOblast().catch(console.error);
  if (document.getElementById('cks-district-app')) cksInitDistrict().catch(console.error);
});
