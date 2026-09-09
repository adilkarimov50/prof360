/* Общие компоненты паспорта: шапка, подвал, диаграммы, форматирование. */

const KRIM = window.KRIM_DATA || {};
const PASSPORTS = KRIM.passports || [];
const GEO = KRIM.geo || {};
const DISTRICTS = KRIM.districts || {};

const SITE = {
  repo: 'https://github.com/adilkarimov50/krim-passport',
  pages: 'https://adilkarimov50.github.io/krim-passport/',
};

function passportStatus(p) {
  return p?.passport_status === 'full' ? 'full' : (p?.passport_status === 'profile_only' ? 'profile_only' : 'full');
}

function isProfileOnly(p) {
  return passportStatus(p) === 'profile_only';
}

function passportStatusBadge(p) {
  return isProfileOnly(p)
    ? '<span class="badge badge--profile">обзор</span>'
    : '<span class="badge badge--full">полный паспорт</span>';
}

function localityProfileHtml(p) {
  const lp = p?.locality_profile;
  if (!lp) return '<div class="callout"><p>Социально-экономический профиль уточняется.</p></div>';
  const pop = lp.population || {};
  const ethnic = (lp.ethnic_composition || []).slice(0, 3)
    .map((e) => `${esc(e.group)} ${String(e.share_pct).replace('.', ',')}%`).join(' · ');
  const economy = (lp.economy?.primary_activity || []).join(', ') || '—';
  const migrants = pop.internal_migrants_note || '—';
  const prevention = (lp.prevention_factors || []).map((f) => `
    <div class="card card-warn" style="margin-bottom:10px;padding:14px 16px">
      <strong>${esc(f.factor)}</strong>
      <span class="badge badge--risk badge--risk-${f.risk || 'medium'}" style="margin-left:8px">${esc(f.risk || 'medium')}</span>
      <p style="margin:8px 0 0;font-size:14px;color:var(--muted)">${esc(f.implication || '')}</p>
    </div>`).join('');
  const highlights = (lp.highlights || []).map((h) => `<li><span>${esc(h)}</span></li>`).join('');
  const sources = (lp.sources || []).map((s) =>
    `<li><a href="${esc(s.url || '#')}" target="_blank" rel="noopener">${esc(s.title)}</a> · ${esc(s.as_of || '')}</li>`).join('');
  function lpKpi(v, l, n) {
    return `<div class="card kpi" style="padding:14px 16px;margin:0;box-shadow:none"><b style="font-size:22px">${v}</b><span style="font-size:12px;color:var(--muted)">${esc(l)}</span>${n ? `<div class="note" style="font-size:11px;margin-top:4px;color:var(--muted)">${esc(n)}</div>` : ''}</div>`;
  }
  return `
    <div class="grid grid--4" style="margin-bottom:16px">
      ${lpKpi(fmt(pop.total), 'Население', pop.year ? `оценка ${pop.year}` : '')}
      ${lpKpi(pop.local_permanent ? fmt(pop.local_permanent) : '—', 'Местные (оценка)')}
      ${lpKpi(lp.economy?.sme_registered ? fmt(lp.economy.sme_registered) : '—', 'Субъекты МСП')}
      ${lpKpi(lp.settlement_type === 'city' ? 'город' : 'село', 'Тип НП')}
    </div>
    <div class="grid grid--2">
      <div class="card">
        <div class="card__title">Национальный состав (топ-3)</div>
        <p style="margin:0">${ethnic || '—'}</p>
        <p style="margin:12px 0 0;font-size:14px;color:var(--muted)"><b>Миграция:</b> ${esc(migrants)}</p>
      </div>
      <div class="card">
        <div class="card__title">Экономика и занятость</div>
        <p style="margin:0">${esc(economy)}</p>
        <p style="margin:12px 0 0;font-size:14px;color:var(--muted)">${esc(lp.economy?.industry_services_note || '')}</p>
      </div>
    </div>
    ${(lp.social_features || []).length ? `<div class="card" style="margin-top:16px"><div class="card__title">Особенности</div><p style="margin:0">${(lp.social_features || []).map((s) => esc(s)).join(' · ')}</p></div>` : ''}
    ${highlights ? `<div class="card" style="margin-top:16px"><div class="card__title">Ключевые особенности</div><ul class="list-check">${highlights}</ul></div>` : ''}
    ${prevention ? `<div style="margin-top:16px"><div class="card__title" style="margin-bottom:10px">Факторы профилактики</div>${prevention}</div>` : ''}
    ${sources ? `<div class="card" style="margin-top:16px"><div class="card__title">Источники</div><ul style="margin:0;padding-left:18px;font-size:14px">${sources}</ul></div>` : ''}`;
}

const STAFF_KEY = 'krim-staff';

const INTERNAL_PAGE_NAMES = new Set([
  'karasai_analysis.html',
  'karasai_spravka.html',
  'registry_crossmatch.html',
]);

/** Режим сотрудника: ?staff=1 сохраняется в localStorage; ?staff=0 сбрасывает. */
function isStaffView() {
  try {
    const q = new URLSearchParams(location.search);
    if (q.get('staff') === '1') {
      localStorage.setItem(STAFF_KEY, '1');
      return true;
    }
    if (q.get('staff') === '0') {
      localStorage.removeItem(STAFF_KEY);
      return false;
    }
    return localStorage.getItem(STAFF_KEY) === '1';
  } catch (e) {
    return new URLSearchParams(location.search).get('staff') === '1';
  }
}

function isInternalHref(href) {
  if (!href) return false;
  const raw = String(href).split('#')[0].split('?')[0];
  const name = raw.replace(/^(\.\.\/)+/, '').split('/').pop();
  if (INTERNAL_PAGE_NAMES.has(name)) return true;
  return /spravka_sverka|karasai_(analysis|spravka)|registry_crossmatch/i.test(raw);
}

function isInternalPageFile() {
  const path = location.pathname.replace(/\\/g, '/');
  const file = path.split('/').pop() || '';
  if (INTERNAL_PAGE_NAMES.has(file)) return true;
  return path.includes('/spravka_sverka_profueta/');
}

/** Сторонним посетителям закрываем служебные HTML-страницы. */
function guardInternalPage() {
  if (isStaffView() || !isInternalPageFile()) return;
  location.replace(`${sitePrefix()}index.html`);
}

/** Убираем из текста ссылки на справки, репозиторий и внутренние файлы. */
function sanitizePublicText(text) {
  if (text === null || text === undefined || isStaffView()) return text;
  return String(text)
    .replace(/справк[аи][^«»]*«Сверка профучёта[^»]*»/gi, 'материалы сверки реестров')
    .replace(/см\.\s*справку[^.;]*/gi, 'сверить реестры ОВД и медучёта')
    .replace(/\(passports\/maps\)/gi, 'на сайте')
    .replace(/\bdigitize\.py\b/gi, 'система оцифровки')
    .replace(/github\.com[^\s)«»]*/gi, '')
    .replace(/spravka_sverka[^\s)«»]*/gi, '')
    .replace(/karasai_[^\s)«»]*/gi, '')
    .replace(/registry_crossmatch[^\s)«»]*/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function publicDataLink(link) {
  if (!link || isStaffView() || isInternalHref(link.href)) return null;
  return link;
}

function applyPublicView() {
  if (isStaffView()) return;
  document.documentElement?.classList?.add('public-view');
  document.querySelectorAll('.staff-only').forEach((el) => el.remove());
  document.querySelectorAll('a[href]').forEach((a) => {
    if (isInternalHref(a.getAttribute('href'))) a.remove();
  });
}

function setHtml(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

const CATEGORY_COLORS = {
  hotspot: '#cf3f3f',
  street: '#d98324',
  object: '#7a4fb5',
  settlement: '#1f6fb2',
  reference: '#5d6b80',
};

const CATEGORY_LABELS = {
  hotspot: 'Точки концентрации',
  street: 'Проблемные улицы',
  object: 'Криминогенные объекты',
  settlement: 'Населённые пункты',
  reference: 'Инфраструктура',
};

const DONUT_COLORS = ['#0d1b33', '#1f6fb2', '#c8a24a', '#8b9bb4', '#7a4fb5', '#1f8a53'];

/* ---------- Форматирование ---------- */

const nf = new Intl.NumberFormat('ru-RU');

function fmt(value) {
  return value === null || value === undefined ? '—' : nf.format(value);
}

function pct(value, digits = 1) {
  return `${value.toFixed(digits).replace('.', ',').replace(/,0$/, '')}%`;
}

function esc(text) {
  return String(text ?? '').replace(/[&<>"]/g, (ch) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]
  ));
}

/** Микрозоны из паспорта: hotspots_detailed приоритетнее укрупнённых hotspots. */
function passportHotspots(p) {
  const list = (p.hotspots_detailed?.length ? p.hotspots_detailed : p.hotspots) || [];
  return [...list].sort((a, b) => (b.count ?? -1) - (a.count ?? -1));
}

function hotspotCountHtml(count) {
  if (count === null || count === undefined) {
    return '<span style="font-size:12px;color:var(--muted);font-weight:600">ожид. состав</span>';
  }
  return `${fmt(count)}<span>фактов</span>`;
}

/**
 * Плашка динамики. Для преступности рост — негативный сигнал, поэтому
 * положительное изменение окрашивается в красный.
 */
function deltaBadge(value) {
  if (value === null || value === undefined) return '';
  const kind = value > 0 ? 'up' : value < 0 ? 'down' : 'flat';
  const sign = value > 0 ? '▲ +' : value < 0 ? '▼ ' : '';
  return `<span class="delta delta--${kind}">${sign}${pct(Math.abs(value))}</span>`;
}

function deltaFromPair(row) {
  if (row.delta_pct !== undefined) return row.delta_pct;
  if (row.current && row.previous) return ((row.current - row.previous) / row.previous) * 100;
  return null;
}

/* ---------- Диаграммы ---------- */

/** Сравнительные полосы «текущий период / АППГ». */
function barsChart(rows) {
  const max = Math.max(...rows.flatMap((r) => [r.current || 0, r.previous || 0]), 1);
  const body = rows.map((row) => {
    const cur = row.current || 0;
    const prev = row.previous || 0;
    return `
      <div class="bar">
        <div class="bar__head">
          <span class="bar__name">${esc(row.indicator)}</span>
          <span class="bar__nums">${fmt(cur)} / ${fmt(prev)} ${deltaBadge(deltaFromPair(row))}</span>
        </div>
        <div class="bar__track">
          <div class="bar__prev" style="width:${(prev / max) * 100}%"></div>
          <div class="bar__fill" style="width:${(cur / max) * 100}%"></div>
        </div>
      </div>`;
  }).join('');
  return `
    <div class="legend">
      <span><i style="background:var(--navy-700)"></i>Текущий период</span>
      <span><i style="background:#c3cede"></i>Аналогичный период прошлого года</span>
    </div>
    <div class="bars">${body}</div>`;
}

/** Простые полосы одного ряда значений. */
function simpleBars(rows) {
  const max = Math.max(...rows.map((r) => r.value || 0), 1);
  return `<div class="bars">${rows.map((row) => `
    <div class="bar">
      <div class="bar__head">
        <span class="bar__name">${esc(row.label)}</span>
        <span class="bar__nums">${fmt(row.value)}</span>
      </div>
      <div class="bar__track">
        <div class="bar__fill" style="width:${(row.value / max) * 100}%;background:${row.color || 'var(--navy-700)'}"></div>
      </div>
    </div>`).join('')}</div>`;
}

/** Кольцевая диаграмма с легендой. */
function donutChart(rows) {
  const total = rows.reduce((sum, r) => sum + (r.value || 0), 0) || 1;
  const R = 62;
  const C = 2 * Math.PI * R;
  let offset = 0;

  const arcs = rows.map((row, i) => {
    const share = (row.value || 0) / total;
    const seg = `<circle r="${R}" cx="80" cy="80" fill="none"
        stroke="${DONUT_COLORS[i % DONUT_COLORS.length]}" stroke-width="26"
        stroke-dasharray="${share * C} ${C}" stroke-dashoffset="${-offset}"
        transform="rotate(-90 80 80)"></circle>`;
    offset += share * C;
    return seg;
  }).join('');

  const legend = rows.map((row, i) => `
    <div>
      <i style="background:${DONUT_COLORS[i % DONUT_COLORS.length]}"></i>
      <span>${esc(row.label)}</span>
      <b>${fmt(row.value)} · ${pct(((row.value || 0) / total) * 100)}</b>
    </div>`).join('');

  return `
    <div class="donut-wrap">
      <svg class="donut" width="160" height="160" viewBox="0 0 160 160" role="img" aria-label="Кольцевая диаграмма">
        ${arcs}
        <text x="80" y="76" text-anchor="middle" font-size="25" font-weight="700" fill="#16202f">${fmt(total)}</text>
        <text x="80" y="95" text-anchor="middle" font-size="11" fill="#5d6b80">всего</text>
      </svg>
      <div class="donut-legend">${legend}</div>
    </div>`;
}

/* ---------- Шапка и подвал ---------- */

/** Префикс ../ для страниц во вложенных папках (spravka_sverka_profueta/ и т.д.). */
function sitePrefix() {
  const parts = location.pathname.replace(/\\/g, '/').split('/').filter(Boolean);
  const fileIdx = parts.findIndex((p) => p.endsWith('.html'));
  const depth = fileIdx >= 0 ? fileIdx : parts.length;
  const rootIdx = parts.indexOf('krim-passport');
  const docsIdx = parts.indexOf('docs');
  const base = rootIdx >= 0 ? rootIdx + 1 : docsIdx >= 0 ? docsIdx + 1 : 0;
  const rel = depth - base;
  return rel > 0 ? '../'.repeat(rel) : '';
}

function renderTopbarTab(p, href, label, title, key, page, activeId) {
  const qs = activeId && (key === 'passport' || key === 'map') ? `?id=${activeId}` : '';
  const primary = key === 'index' || key === 'passport' ? ' tab--primary' : '';
  return `<a class="tab${primary}" href="${p}${href}${qs}" title="${title}"
     ${key === page ? 'aria-current="page"' : ''}>${label}</a>`;
}

function renderTopbar(page, activeId) {
  const p = sitePrefix();
  const tabs = [
    ['index.html', 'Обзор', 'Обзор разделов', 'index'],
    ['passport.html', 'Паспорт', 'Криминологический паспорт', 'passport'],
    ['map.html', 'Карта', 'Карта объектов и правонарушений', 'map'],
    ['profilaktika_navigator.html', 'Прокурору', 'Прокурору для работы · Закон № 245', 'navigator'],
    ['nauka_profilaktika.html', 'Наука', 'Наука и практика профилактики', 'library'],
  ];
  return `
  <header class="topbar">
    <div class="wrap topbar__inner">
      <a class="brand" href="${p}index.html">
        <img class="brand__emblem" src="${p}assets/img/prokuratura-emblem.png" width="36" height="36" alt="Эмблема органов прокуратуры Республики Казахстан">
        <span class="brand__text">Криминологический паспорт
          <small>9 населённых пунктов · Алматинская область и г. Алматы · 2026</small>
        </span>
      </a>
      <nav class="topbar__nav" aria-label="Разделы сайта">
        <div class="topbar__scroll">
          ${tabs.map(([href, label, title, key]) => renderTopbarTab(p, href, label, title, key, page, activeId)).join('')}
        </div>
      </nav>
    </div>
  </header>`;
}

/** Высота липкой шапки — для прокрутки к якорям на телефоне. */
function headerOffset() {
  return document.querySelector('.topbar')?.offsetHeight || 68;
}

function scrollToElement(el, behavior) {
  if (!el) return;
  const y = el.getBoundingClientRect().top + window.scrollY - headerOffset() - 10;
  window.scrollTo({ top: Math.max(0, y), behavior: behavior || 'smooth' });
}

function renderFooter() {
  const p = sitePrefix();
  const staff = isStaffView();
  return `
  <footer class="footer">
    <div class="wrap">
      <div class="footer__grid">
        <div>
          <h3>Цифровой криминологический паспорт</h3>
          <p>${staff
    ? 'Паспорта населённых пунктов оцифрованы из документов формата .docx и опубликованы в виде интерактивного издания. Исходные данные, скрипт оцифровки и исходный код страницы открыты в репозитории.'
    : 'Интерактивное издание криминологических паспортов населённых пунктов за 2026 год: сравнение показателей, карта объектов и материалы для профилактической работы.'}</p>
          ${staff ? `<p>Репозиторий: <a href="${SITE.repo}">${SITE.repo.replace('https://', '')}</a></p>` : ''}
          <p>Адрес издания: <a href="${SITE.pages}">${SITE.pages.replace('https://', '')}</a></p>
        </div>
        <div class="footer__qr">
          <img src="${p}assets/img/qr.svg" alt="QR-код для перехода к цифровому паспорту" width="148" height="148">
          <span>Наведите камеру</span>
        </div>
      </div>
      <div class="footer__legal">
        Сведения основаны на криминологических паспортах за 2026 год. Координаты объектов на карте
        получены геокодированием по OpenStreetMap и носят ориентировочный характер.
      </div>
    </div>
  </footer>`;
}

/** Единая шапка и подвал — вызывается на каждой странице. */
function mountSiteChrome(page, activeId) {
  const top = document.getElementById('chrome-top');
  if (top) top.innerHTML = renderTopbar(page, activeId);
  const bottom = document.getElementById('chrome-bottom');
  if (bottom) bottom.innerHTML = renderFooter();
}

function resolveSitePage() {
  const fromBody = document.body?.dataset?.sitePage;
  if (fromBody) return fromBody;
  const file = location.pathname.split('/').pop() || 'index.html';
  const map = {
    'index.html': 'index',
    'passport.html': 'passport',
    'map.html': 'map',
    'profilaktika_navigator.html': 'navigator',
    'prokuror_zakon.html': 'navigator',
    'legal_read.html': 'navigator',
    'mvk_kvartal.html': 'navigator',
    'nauka_profilaktika.html': 'library',
    'karasai_analysis.html': 'index',
    'karasai_spravka.html': 'index',
    'registry_crossmatch.html': 'index',
    'kaskelen_map.html': 'map',
    'irgeli_map.html': 'map',
    'chundzha_map.html': 'map',
  };
  return map[file] || 'index';
}

function resolveActiveId(page) {
  const fromBody = document.body?.dataset?.siteId;
  if (fromBody) return fromBody;
  if (page === 'passport' || page === 'map') {
    try { return currentId(); } catch (e) { return ''; }
  }
  return undefined;
}

(function bootSiteChrome() {
  guardInternalPage();
  if (!document.getElementById('chrome-top')) return;
  const page = resolveSitePage();
  mountSiteChrome(page, resolveActiveId(page));
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyPublicView);
  } else {
    applyPublicView();
  }
})();

/** Переключатель населённого пункта; при выборе меняет ?id= в адресе. */
function renderSwitch(activeId, onChange) {
  const html = `<div class="switch">${PASSPORTS.map((p) => `
      <button type="button" data-id="${p.id}" aria-pressed="${p.id === activeId}">${esc(p.name)}</button>
    `).join('')}</div>`;

  queueMicrotask(() => {
    document.querySelectorAll('.switch button').forEach((btn) => {
      btn.addEventListener('click', () => onChange(btn.dataset.id));
    });
  });
  return html;
}

function currentId() {
  const id = new URLSearchParams(location.search).get('id');
  if (!PASSPORTS.length) return id || '';
  return PASSPORTS.some((p) => p.id === id) ? id : PASSPORTS[0].id;
}

function getPassport(id) {
  return PASSPORTS.find((p) => p.id === id) || PASSPORTS[0] || null;
}
