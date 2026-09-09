/* Титульная страница: выбор паспорта и сопоставление населённых пунктов. */

mountSiteChrome('index');

if (!PASSPORTS.length) {
  document.getElementById('picker').innerHTML = '<div class="card" style="padding:20px"><p style="margin:0">Данные паспортов не загрузились. Обновите страницу.</p></div>';
} else {
const totalPop = PASSPORTS.reduce((sum, p) => sum + (p.summary.population || 0), 0);
const FULL_PASSPORTS = PASSPORTS.filter((p) => !isProfileOnly(p));
const totalCrimes = FULL_PASSPORTS.reduce((sum, p) => sum + (p.summary.crimes?.current || 0), 0);

document.getElementById('hero-count').textContent = `${PASSPORTS.length} ${PASSPORTS.length === 1 ? 'населённый пункт' : PASSPORTS.length < 5 ? 'населённых пункта' : 'населённых пунктов'}`;
document.getElementById('hero-pop').textContent = `${fmt(totalPop)} жителей`;
document.getElementById('hero-crimes').textContent = FULL_PASSPORTS.length
  ? `${fmt(totalCrimes)} уголовных (3 полных паспорта)`
  : 'кримпаспорта уточняются';

/* Карточки выбора паспорта */
const MAP_LINKS = { kaskelen: 'kaskelen_map.html', irgeli: 'irgeli_map.html', chundzha: 'chundzha_map.html' };
document.getElementById('picker').innerHTML = PASSPORTS.map((p) => {
  const c = p.summary.crimes || {};
  const mapLink = MAP_LINKS[p.id];
  const lp = p.locality_profile || {};
  const economy = (lp.economy?.primary_activity || []).slice(0, 2).join(', ') || '—';
  return `
  <div class="pcard" style="display:flex;flex-direction:column">
    <a href="passport.html?id=${p.id}" style="flex:1;display:block;text-decoration:none;color:inherit">
    <div class="pcard__top">
      <div class="pcard__kicker">${esc(p.summary.district || p.district)} ${passportStatusBadge(p)}</div>
      <h3>${esc(p.name)}</h3>
      <p>${esc((lp.highlights || [])[0] || p.summary.description)}</p>
    </div>
    <div class="pcard__grid">
      <div class="pcard__cell">
        <b>${fmt(p.summary.population)}</b>
        <span>населения</span>
      </div>
      <div class="pcard__cell">
        <b>${isProfileOnly(p) ? economy : fmt(c.current)}</b>
        <span>${isProfileOnly(p) ? 'основная занятость' : `правонарушений ${deltaBadge(c.delta_pct ?? null)}`}</span>
      </div>
      <div class="pcard__cell">
        <b>${isProfileOnly(p) ? (lp.settlement_type === 'city' ? 'город' : 'село') : String(p.summary.rate_per_10k ?? '—').replace('.', ',')}</b>
        <span>${isProfileOnly(p) ? 'тип НП' : 'на 10 тыс. нас.'}</span>
      </div>
    </div>
    <div class="pcard__foot"><span>${isProfileOnly(p) ? 'Открыть профиль' : 'Открыть паспорт'}</span><span class="arrow">→</span></div>
    </a>
    ${mapLink ? `<a href="${mapLink}" style="display:block;margin:0;padding:10px 16px;background:var(--up);color:#fff;text-decoration:none;font-size:13px;font-weight:600;text-align:center">
      Карта + маршруты патрулирования →</a>` : ''}
  </div>`;
}).join('');

function renderLocalityCards(filter) {
  const list = PASSPORTS.filter((p) => {
    if (filter === 'city') return p.locality_profile?.settlement_type === 'city';
    if (filter === 'village') return p.locality_profile?.settlement_type === 'village';
    return true;
  });
  const groups = (DISTRICTS.districts || []).length ? DISTRICTS.districts : [{ id: 'all', title: 'Все', localities: list.map((p) => p.id) }];
  return groups.map((g) => {
    const items = list.filter((p) => !g.localities || g.localities.includes(p.id));
    if (!items.length) return '';
    return `<div class="locality-group"><h3 class="locality-group__title">${esc(g.title)}</h3>
      <div class="grid grid--3">${items.map((p) => {
        const lp = p.locality_profile || {};
        const ethnic = (lp.ethnic_composition || []).slice(0, 3).map((e) => `${e.group} ${e.share_pct}%`).join(', ');
        return `<div class="card locality-card">
          <div class="locality-card__head">${passportStatusBadge(p)} <strong>${esc(p.name)}</strong></div>
          <p style="margin:8px 0;font-size:14px;color:var(--muted)">${esc((lp.highlights || [])[0] || p.summary.description)}</p>
          <div class="stat-row"><span class="stat-row__label">Население</span><span class="stat-row__value">${fmt(lp.population?.total || p.summary.population)}</span></div>
          <div class="stat-row"><span class="stat-row__label">Этнос (топ-3)</span><span class="stat-row__value">${esc(ethnic || '—')}</span></div>
          <div class="stat-row"><span class="stat-row__label">Миграция</span><span class="stat-row__value">${esc(lp.population?.internal_migrants_note || '—')}</span></div>
          <div class="stat-row"><span class="stat-row__label">Экономика</span><span class="stat-row__value">${esc((lp.economy?.primary_activity || []).join(', ') || '—')}</span></div>
          <p style="margin:12px 0 0"><a class="tag" href="passport.html?id=${p.id}" style="padding:8px 14px;text-decoration:none;font-size:13px">Подробнее →</a></p>
        </div>`;
      }).join('')}</div></div>`;
  }).join('');
}

const localityEl = document.getElementById('locality-profiles');
if (localityEl) {
  let locFilter = 'all';
  const draw = () => { localityEl.innerHTML = renderLocalityCards(locFilter); };
  draw();
  document.querySelectorAll('[data-loc-filter]').forEach((btn) => {
    btn.addEventListener('click', () => {
      locFilter = btn.dataset.locFilter;
      document.querySelectorAll('[data-loc-filter]').forEach((b) => b.classList.toggle('active', b === btn));
      draw();
    });
  });
}

/* Сравнительная таблица */
function adminTotal(p) {
  if (Array.isArray(p.admin_practice)) {
    return p.admin_practice.find((r) => r.indicator.startsWith('Всего'))?.count;
  }
  return p.admin_practice?.total;
}

function registryTotal(p) {
  if (!Array.isArray(p.registry)) return '—';
  return fmt(p.registry.reduce((sum, r) => sum + (r.count || 0), 0));
}

const CRIME_INDICATOR_ALIASES = {
  'Против половой неприкосновенности': ['Половые преступления'],
  'Кражи': ['Кражи (ст.188)', 'Кражи и мелкие хищения (ст.188)'],
  'Мошенничества': ['Мошенничества (ст.190)'],
  'Средней тяжести': ['Средней тяжести'],
  'Телесные повреждения': ['Телесные повреждения'],
  'Убийства (ст.99)': ['Убийства (ст.99)'],
};

function kpiCard(value, label, note = '', badge = '') {
  return `<div class="card kpi" style="padding:14px 16px;margin:0;box-shadow:none">
    <b style="font-size:22px">${value} ${badge}</b>
    <span style="font-size:12px;color:var(--muted)">${esc(label)}</span>
    ${note ? `<div class="note" style="font-size:11px;margin-top:4px;color:var(--muted)">${esc(note)}</div>` : ''}
  </div>`;
}

function findCrimeRow(p, name) {
  const names = [name, ...(CRIME_INDICATOR_ALIASES[name] || [])];
  const fromStructure = p.crime_structure?.find((r) => names.includes(r.indicator));
  if (fromStructure) return fromStructure;
  return p.crime_severity?.find((r) => r.category === name) || null;
}

function crimeValue(p, name) {
  const row = findCrimeRow(p, name);
  if (!row) return '—';
  const cur = row.current ?? row.value;
  const prev = row.previous;
  if (cur !== undefined && cur !== null && prev !== undefined && prev !== null) {
    const pair = { current: Number(cur), previous: Number(prev), delta_pct: row.delta_pct };
    const delta = deltaFromPair(pair) ?? (typeof row.delta === 'string'
      ? Number(String(row.delta).replace(/[^\d,.-−]/g, '').replace(',', '.').replace('−', '-'))
      : null);
    return `${fmt(Number(cur))} <span style="color:var(--muted)">/ ${fmt(Number(prev))}</span> ${deltaBadge(delta)}`;
  }
  if (cur !== undefined && cur !== null) return fmt(Number(String(cur).replace(/\s/g, '')) || String(cur));
  return fmt(row.value);
}

const COMPARE_ROWS = [
  ['Численность населения', (p) => fmt(p.summary.population), false],
  ['Уровень преступности на 10 тыс. населения', (p) => String(p.summary.rate_per_10k).replace('.', ','), false],
  ...['Всего зарегистрировано', 'Особо тяжкие', 'Тяжкие', 'Средней тяжести', 'Кражи', 'Мошенничества',
    'Телесные повреждения', 'Семейно-бытовые преступления', 'Против половой неприкосновенности',
    'В состоянии алкогольного опьянения', 'Убийства (ст.99)'].map((name) => [name, (p) => crimeValue(p, name), true]),
  ['Всего административных правонарушений', (p) => fmt(adminTotal(p)), false],
  ['ст.440 КоАП — распитие и появление в пьяном виде', (p) => {
    const row = Array.isArray(p.admin_practice)
      ? p.admin_practice.find((r) => /440/.test(r.indicator))
      : null;
    return row ? fmt(row.count) : '—';
  }, false],
  ['ст.442 КоАП — несовершеннолетние ночью', (p) => {
    const row = Array.isArray(p.admin_practice)
      ? p.admin_practice.find((r) => /442/.test(r.indicator))
      : null;
    return row ? fmt(row.count) : '—';
  }, false],
  ['ст.73 КоАП — семейно-бытовая сфера', (p) => {
    const row = Array.isArray(p.admin_practice)
      ? p.admin_practice.find((r) => /73/.test(r.indicator))
      : null;
    return row ? fmt(row.count) : '—';
  }, false],
  ['Лиц на профилактическом учёте', registryTotal, false],
];

function passportSocioRows(p) {
  if (Array.isArray(p.socio) && p.socio.length) return p.socio;
  if (!Array.isArray(p.socio_extended)) return [];
  return p.socio_extended.flatMap((block) => (block.rows || []).map((r) => ({
    indicator: r.indicator,
    value: r.comment ? `${r.value} · ${r.comment}` : r.value,
  })));
}

function passportNarrative(p) {
  if (p.characteristic) return p.characteristic;
  const block = (p.narrative_blocks || []).find((b) => /криминолог/i.test(b.title || ''));
  return block?.text || (p.narrative_blocks || [])[0]?.text || p.summary?.description || '';
}

setHtml('dash-kpi', PASSPORTS.map((p) => {
  if (isProfileOnly(p)) {
    return `<div class="card" style="opacity:.92">
      <div class="card__title">${esc(p.name)} ${passportStatusBadge(p)}</div>
      <p style="margin:0;color:var(--muted);font-size:14px">Полный кримпаспорт готовится. Доступен обзорный профиль.</p>
      <p style="margin:14px 0 0"><a class="tag" href="passport.html?id=${p.id}" style="padding:8px 14px;text-decoration:none;font-size:13px">Открыть профиль →</a></p>
    </div>`;
  }
  const c = p.summary.crimes;
  const adm = adminTotal(p);
  return `<div class="card">
    <div class="card__title">${esc(p.name)} ${passportStatusBadge(p)}</div>
    <div class="grid grid--2" style="gap:10px">
      ${kpiCard(fmt(p.summary.population), 'Население')}
      ${kpiCard(fmt(c.current), 'Уголовных', `АППГ ${fmt(c.previous)}`, deltaBadge(c.delta_pct ?? null))}
      ${kpiCard(String(p.summary.rate_per_10k).replace('.', ','), 'На 10 тыс.')}
      ${kpiCard(fmt(adm), 'Адм. правонарушений')}
    </div>
    <p style="margin:14px 0 0"><a class="tag" href="passport.html?id=${p.id}" style="padding:8px 14px;text-decoration:none;font-size:13px">Открыть паспорт →</a></p>
  </div>`;
}).join(''));

setHtml('dash-crime', FULL_PASSPORTS.map((p) => {
  const rows = (p.crime_structure || []).filter((r) => r.current != null && !/^всего/i.test(r.indicator));
  if (!rows.length) return `<div class="card"><div class="card__title">${esc(p.name)}</div><p style="margin:0;color:var(--muted)">Нет данных</p></div>`;
  return `<div class="card card--flush" style="padding:16px 18px">
    <div class="card__title">${esc(p.name)}</div>
    ${barsChart(rows)}
  </div>`;
}).join(''));

setHtml('dash-admin', PASSPORTS.map((p) => {
  if (!Array.isArray(p.admin_practice)) {
    return `<div class="card"><div class="card__title">${esc(p.name)}</div><p style="margin:0;color:var(--muted)">${fmt(p.admin_practice?.total || 0)} за период</p></div>`;
  }
  const rest = p.admin_practice.filter((r) => !r.indicator.startsWith('Всего'));
  return `<div class="card card--flush" style="padding:16px 18px">
    <div class="card__title">${esc(p.name)} · ${fmt(adminTotal(p))} всего</div>
    ${simpleBars(rest.map((r) => ({ label: r.indicator.replace(/^ст\./, 'ст.'), value: r.count })))}
  </div>`;
}).join(''));

setHtml('dash-socio', PASSPORTS.map((p) => {
  const rows = passportSocioRows(p);
  if (!rows.length) {
    return `<div class="card"><div class="card__title">${esc(p.name)}</div><p style="margin:0;color:var(--muted)">Данные уточняются в паспорте.</p></div>`;
  }
  return `<div class="card card--flush" style="padding:16px 18px">
    <div class="card__title">${esc(p.name)}</div>
    ${rows.slice(0, 8).map((r) => `
      <div class="stat-row">
        <span class="stat-row__label">${esc(r.indicator)}</span>
        <span class="stat-row__value">${esc(r.value)}</span>
      </div>`).join('')}
  </div>`;
}).join(''));

setHtml('dash-narrative', PASSPORTS.map((p) => {
  const text = passportNarrative(p);
  const extra = (p.narrative_blocks || []).slice(1, 3).map((b) => `
    <div style="margin-top:12px;padding-top:12px;border-top:1px dashed var(--line)">
      <b style="font-size:13px;display:block;margin-bottom:4px">${esc(b.title)}</b>
      <p style="margin:0;font-size:14px;color:var(--muted);line-height:1.45">${esc(String(b.text).slice(0, 280))}${b.text.length > 280 ? '…' : ''}</p>
    </div>`).join('');
  return `<div class="card">
    <div class="card__title">${esc(p.name)}</div>
    <p style="margin:0;font-size:14.5px;line-height:1.5;color:var(--muted)">${esc(String(text).slice(0, 420))}${text.length > 420 ? '…' : ''}</p>
    ${extra}
    <p style="margin:14px 0 0"><a class="tag" href="passport.html?id=${p.id}" style="padding:8px 14px;text-decoration:none;font-size:13px">Все разделы →</a></p>
  </div>`;
}).join(''));

setHtml('compare', `
  <thead><tr><th>Показатель</th>${PASSPORTS.map((p) => `<th class="num">${esc(p.name)}</th>`).join('')}</tr></thead>
  <tbody>${COMPARE_ROWS.map(([label, render, crimeRow]) => `
    <tr>
      <td>${esc(label)}</td>
      ${PASSPORTS.map((p) => `<td class="num">${isProfileOnly(p) && crimeRow ? '<span style="color:var(--muted)">—</span>' : render(p)}</td>`).join('')}
    </tr>`).join('')}
  </tbody>`);

/* Точки концентрации по каждому паспорту */
setHtml('hotspots', PASSPORTS.map((p) => {
  const spots = passportHotspots(p);
  return `
  <div class="card">
    <div class="card__title">${esc(p.name)}</div>
    ${spots.map((s, i) => `
      <div class="hotspot" style="padding:13px 0;border-bottom:${i < spots.length - 1 ? '1px dashed var(--line)' : '0'}">
        <div class="hotspot__rank">${i + 1}</div>
        <div class="hotspot__body">
          <h4>${esc(s.object)}</h4>
          <p>${esc(s.types)}</p>
        </div>
        <div class="hotspot__count">${hotspotCountHtml(s.count)}</div>
      </div>`).join('')}
  </div>`;
}).join(''));
}

applyPublicView();
