/* Прокурору для работы — навигатор по Закону № 245-VIII */
(function initNavigator() {
  'use strict';

  document.getElementById('chrome-top').innerHTML = renderTopbar('navigator');
  document.getElementById('chrome-bottom').innerHTML = renderFooter();

  const ORGS = window.NAVIGATOR_DATA || [];
  const KEY = 'profilaktika-checks-v1';
  const LAW245 = 'https://adilet.zan.kz/rus/docs/Z2500000245';
  const TAG_LABELS = {
    силовой: 'Правоохранительные',
    социальный: 'Социальный блок',
    местный: 'Местный уровень',
  };

  let state = {};
  try { state = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { state = {}; }

  const grid = document.getElementById('nav-grid');
  const sidebar = document.getElementById('nav-sidebar');
  const statusEl = document.getElementById('nav-status');
  const kpiEl = document.getElementById('nav-kpi');
  let activeTag = 'all';
  let query = '';

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
  }

  function navEsc(s) {
    return String(s ?? '').replace(/[&<>"]/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
    ));
  }

  /** Ссылки на статьи ЗРК № 245-VIII в ИПС «Әділет». */
  function linkifyLaw(text) {
    const safe = navEsc(text);
    return safe.replace(
      /(ст\.\s*\d+(?:\s*[-–]\s*\d+)?(?:\s*п\.?\s*\d+)?(?:\s*пп\.?\s*\d+)?(?:\s*ЗРК)?)/gi,
      (match) => {
        const num = match.match(/\d+/);
        const href = num ? `${LAW245}#z${num[0]}` : LAW245;
        return `<a class="nav-law" href="${href}" target="_blank" rel="noopener noreferrer">${match}</a>`;
      },
    );
  }

  function orgProgress(d) {
    const done = d.checks.filter((c, i) => state[`${d.id}:${i}`]).length;
    const total = d.checks.length;
    const pct = total ? Math.round((done / total) * 100) : 0;
    return { done, total, pct };
  }

  function filteredItems() {
    const q = query.trim().toLowerCase();
    return ORGS.filter((d) => {
      if (activeTag !== 'all' && d.tag !== activeTag) return false;
      if (!q) return true;
      const hay = [d.org, d.center, d.acts, d.norm, d.task, d.signals, d.react, d.gap]
        .concat(d.checks.map((c) => `${c[0]} ${c[1]}`)).join(' ').toLowerCase();
      return hay.includes(q);
    });
  }

  function renderKpi(totalChecks, totalDone) {
    const pct = totalChecks ? Math.round((totalDone / totalChecks) * 100) : 0;
    kpiEl.innerHTML = `
      <div class="nav-kpi__cell"><b>${ORGS.length}</b><span>Субъектов</span></div>
      <div class="nav-kpi__cell"><b>${totalChecks}</b><span>Пунктов проверки</span></div>
      <div class="nav-kpi__cell"><b>${totalDone}</b><span>Отмечено</span></div>
      <div class="nav-kpi__cell"><b>${pct}%</b><span>Прогресс</span></div>`;
    return { totalChecks, totalDone, pct };
  }

  function renderSidebar(items) {
    sidebar.innerHTML = `<a class="nav-sidebar__link nav-sidebar__link--back" href="prokuror_zakon.html">⚖ Работа с законами</a>
      <div class="nav-sidebar__title">Субъекты ЗРК</div>`
      + items.map((d) => {
        const { done, total, pct } = orgProgress(d);
        const short = d.org.replace(/^Органы?\s+/i, '').replace(/^УТК\s+/i, '');
        return `<a class="nav-sidebar__link" href="#card-${d.id}" data-jump="${d.id}">
          <span class="nav-sidebar__mini"><i style="width:${pct}%"></i></span>
          <span>${navEsc(short.length > 28 ? `${short.slice(0, 26)}…` : short)}<br>
          <small style="font-weight:500;color:var(--muted)">${done}/${total}</small></span>
        </a>`;
      }).join('');
  }

  function renderStatus(items, totals) {
    statusEl.innerHTML = `
      <span>Показано <b>${items.length}</b> из ${ORGS.length} органов · отмечено <b>${totals.totalDone}</b> из ${totals.totalChecks}</span>
      <div class="nav-status__bar" title="Общий прогресс проверки">
        <i style="width:${totals.pct}%"></i>
      </div>`;
  }

  function renderGrid(items) {
    if (!items.length) {
      grid.innerHTML = '<div class="nav-empty">Ничего не найдено. Измените поиск или фильтр.</div>';
      return;
    }

    const openIds = new Set(
      [...grid.querySelectorAll('details.nav-org[open]')].map((el) => el.id.replace('card-', '')),
    );

    grid.innerHTML = items.map((d) => {
      const { done, total, pct } = orgProgress(d);
      const tagLabel = TAG_LABELS[d.tag] || d.tag;
      const lis = d.checks.map((c, i) => {
        const k = `${d.id}:${i}`;
        const on = !!state[k];
        return `<li class="${on ? 'done' : ''}">
          <input type="checkbox" id="chk-${k}" data-k="${k}"${on ? ' checked' : ''} aria-label="Отметить проверенным">
          <label class="txt" for="chk-${k}">${linkifyLaw(c[0])}<span class="src">${linkifyLaw(c[1])}</span></label>
        </li>`;
      }).join('');

      const isOpen = openIds.has(d.id);

      return `<details class="nav-org" id="card-${d.id}"${isOpen ? ' open' : ''}>
        <summary>
          <h3>${navEsc(d.org)} <span class="nav-tag nav-tag--${d.tag}">${navEsc(tagLabel)}</span></h3>
          <p class="nav-org__center">${navEsc(d.center)}</p>
          <p class="nav-org__acts">${navEsc(d.acts)}</p>
          <span class="nav-norm">${linkifyLaw(d.norm)}</span>
          <div class="nav-org__progress">Проверено ${done} из ${total}
            <div class="nav-org__track"><i style="width:${pct}%"></i></div>
          </div>
          <div class="nav-org__more">Открыть предмет проверки →</div>
        </summary>
        <div class="nav-org__body">
          <h4>Что делает ведомство</h4>
          <p>${linkifyLaw(d.task)}</p>
          <h4>Что проверять прокурору</h4>
          <ul class="nav-chk">${lis}</ul>
          <h4>Признаки нарушения</h4>
          <div class="nav-callout nav-callout--sig">${linkifyLaw(d.signals)}</div>
          <h4>Форма реагирования</h4>
          <div class="nav-callout nav-callout--react">${linkifyLaw(d.react)}</div>
          <h4>На что смотреть в первую очередь</h4>
          <div class="nav-callout nav-callout--gap">${linkifyLaw(d.gap)}</div>
        </div>
      </details>`;
    }).join('');
  }

  function renderNavigator() {
    if (!ORGS.length) {
      grid.innerHTML = '<div class="nav-empty">Данные навигатора не загружены. Проверьте подключение файла navigator_data.js.</div>';
      kpiEl.innerHTML = '';
      statusEl.innerHTML = '';
      sidebar.innerHTML = '';
      return;
    }
    const items = filteredItems();
    const totalChecks = ORGS.reduce((a, d) => a + d.checks.length, 0);
    const totalDone = Object.keys(state).filter((k) => state[k]).length;
    const totals = renderKpi(totalChecks, totalDone);
    renderSidebar(items);
    renderStatus(items, totals);
    renderGrid(items);
  }

  function updateCardProgress(cardId) {
    const d = ORGS.find((o) => o.id === cardId);
    const card = document.getElementById(`card-${cardId}`);
    if (!d || !card) return;
    const { done, total, pct } = orgProgress(d);
    const prog = card.querySelector('.nav-org__progress');
    if (prog) {
      prog.innerHTML = `Проверено ${done} из ${total}
        <div class="nav-org__track"><i style="width:${pct}%"></i></div>`;
    }
    const link = sidebar.querySelector(`[data-jump="${cardId}"]`);
    if (link) {
      const mini = link.querySelector('.nav-sidebar__mini i');
      if (mini) mini.style.width = `${pct}%`;
      const sm = link.querySelector('small');
      if (sm) sm.textContent = `${done}/${total}`;
    }
    const totalChecks = ORGS.reduce((a, o) => a + o.checks.length, 0);
    const totalDone = Object.keys(state).filter((k) => state[k]).length;
    const totals = { totalChecks, totalDone, pct: totalChecks ? Math.round((totalDone / totalChecks) * 100) : 0 };
    renderKpi(totalChecks, totalDone);
    renderStatus(filteredItems(), totals);
  }

  grid.addEventListener('change', (e) => {
    const cb = e.target.closest('input[type=checkbox]');
    if (!cb) return;
    state[cb.dataset.k] = cb.checked;
    cb.closest('li')?.classList.toggle('done', cb.checked);
    save();
    const cardId = cb.dataset.k.split(':')[0];
    updateCardProgress(cardId);
  });

  sidebar.addEventListener('click', (e) => {
    const link = e.target.closest('[data-jump]');
    if (!link) return;
    e.preventDefault();
    const id = link.dataset.jump;
    const el = document.getElementById(`card-${id}`);
    if (el) {
      el.open = true;
      scrollToElement(el);
      sidebar.querySelectorAll('.nav-sidebar__link').forEach((a) => a.classList.remove('is-active'));
      link.classList.add('is-active');
    }
  });

  document.getElementById('nav-q').addEventListener('input', (e) => {
    query = e.target.value;
    renderNavigator();
  });

  document.querySelectorAll('#nav-filters .nav-filter').forEach((b) => {
    b.addEventListener('click', () => {
      document.querySelectorAll('#nav-filters .nav-filter').forEach((x) => x.setAttribute('aria-pressed', 'false'));
      b.setAttribute('aria-pressed', 'true');
      activeTag = b.dataset.tag;
      renderNavigator();
    });
  });

  document.getElementById('nav-open-all').addEventListener('click', () => {
    document.querySelectorAll('details.nav-org').forEach((d) => { d.open = true; });
  });
  document.getElementById('nav-close-all').addEventListener('click', () => {
    document.querySelectorAll('details.nav-org').forEach((d) => { d.open = false; });
  });
  document.getElementById('nav-reset').addEventListener('click', () => {
    if (!confirm('Снять все отметки о проверке?')) return;
    state = {};
    save();
    renderNavigator();
  });
  document.getElementById('nav-export').addEventListener('click', () => {
    const rows = [['Орган', 'Головное ведомство', 'Норма', 'Предмет проверки', 'Основание', 'Отметка']];
    ORGS.forEach((d) => d.checks.forEach((c, i) => {
      rows.push([d.org, d.center, d.norm, c[0], c[1], state[`${d.id}:${i}`] ? 'проверено' : '']);
    }));
    const csv = `\uFEFF${rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\r\n')}`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'predmet_nadzora_profilaktika.csv';
    a.click();
    URL.revokeObjectURL(url);
  });
  document.getElementById('nav-print').addEventListener('click', () => {
    document.querySelectorAll('details.nav-org').forEach((d) => { d.open = true; });
    window.print();
  });

  renderNavigator();
}());
