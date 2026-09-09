(function () {
  const cat = window.LEGAL_CATALOG;
  if (!cat) return;

  const grid = document.getElementById('legal-grid');
  const status = document.getElementById('legal-status');
  const qInput = document.getElementById('legal-q');
  const sidebar = document.getElementById('legal-sidebar');
  const kpi = document.getElementById('legal-kpi');

  let typeFilter = 'all';

  function esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmtBytes(n) {
    if (!n) return '';
    if (n < 1024) return n + ' Б';
    if (n < 1024 * 1024) return (n / 1024).toFixed(0) + ' КБ';
    return (n / (1024 * 1024)).toFixed(1) + ' МБ';
  }

  function badgeClass(actType) {
    if (actType === 'кодекс') return 'legal-badge legal-badge--code';
    if (actType === 'приказ') return 'legal-badge legal-badge--order';
    return 'legal-badge legal-badge--law';
  }

  function actById(id) {
    return cat.acts.find((a) => a.doc_id === id);
  }

  function renderKpi() {
    if (!kpi) return;
    const codes = cat.acts.filter((a) => a.act_type === 'кодекс').length;
    const laws = cat.acts.filter((a) => a.act_type === 'закон' || a.act_type === 'конституционный закон').length;
    const orders = cat.acts.filter((a) => a.act_type === 'приказ').length;
    kpi.innerHTML = `
      <div class="legal-kpi__cell"><b>${cat.count}</b><span>актов в библиотеке</span></div>
      <div class="legal-kpi__cell"><b>${codes}</b><span>кодексов</span></div>
      <div class="legal-kpi__cell"><b>${laws}</b><span>законов</span></div>
      <div class="legal-kpi__cell"><b>${orders}</b><span>приказов</span></div>`;
  }

  function renderSidebar() {
    if (!sidebar) return;
    const links = [
      ['all', 'Все акты'],
      ['кодекс', 'Кодексы'],
      ['закон', 'Законы'],
      ['приказ', 'Приказы'],
      ...cat.bundles.map((b) => ['bundle:' + b.id, b.title]),
    ];
    sidebar.innerHTML = `
      <div class="legal-sidebar__title">Разделы</div>
      <a class="legal-sidebar__link legal-sidebar__link--back" href="profilaktika_navigator.html">← Механизмы профилактики</a>
      ${links.map(([key, label]) =>
        `<a href="#" class="legal-sidebar__link" data-filter="${esc(key)}">${esc(label)}</a>`).join('')}
    `;
    sidebar.querySelectorAll('[data-filter]').forEach((a) => {
      a.addEventListener('click', (e) => {
        e.preventDefault();
        typeFilter = a.dataset.filter;
        sidebar.querySelectorAll('[data-filter]').forEach((x) => x.classList.toggle('is-active', x === a));
        renderGrid();
      });
    });
    const first = sidebar.querySelector('[data-filter="all"]');
    if (first) first.classList.add('is-active');
  }

  function cardHtml(act, extra) {
    const warn = act.superseded_by
      ? `<span class="legal-badge legal-badge--warn">утратил силу</span>` : '';
    const articles = extra?.key_articles?.length
      ? `<p class="legal-card__articles">Ключевые нормы: ${extra.key_articles.map((x) => `<code>${esc(x)}</code>`).join(' ')}</p>` : '';
    const note = extra?.note || '';
    const prefix = (typeof sitePrefix === 'function') ? sitePrefix() : '';
    return `
      <article class="legal-card" data-doc-id="${esc(act.doc_id)}">
        <div class="legal-card__head">
          <h3 class="legal-card__title">${esc(act.title)}</h3>
          <div class="legal-card__meta">
            <span class="${badgeClass(act.act_type)}">${esc(act.act_type)}</span>
            <span class="legal-badge">№ ${esc(act.number)}</span>
            ${warn}
            <span class="legal-badge">${fmtBytes(act.bytes)}</span>
          </div>
        </div>
        ${note ? `<p class="legal-card__note">${esc(note)}</p>` : ''}
        ${articles}
        <div class="legal-actions">
          ${act.has_txt !== false ? `
          <a class="legal-btn legal-btn--primary" href="legal_read.html?id=${encodeURIComponent(act.doc_id)}">Читать</a>
          <a class="legal-btn" href="${prefix}${esc(act.txt_url)}" download="${esc(act.doc_id)}.txt">Скачать TXT</a>` : ''}
          <a class="legal-btn ${act.has_txt === false ? 'legal-btn--primary' : 'legal-btn--ghost'}" href="${esc(act.adilet_url)}" target="_blank" rel="noopener">Adilet ↗</a>
        </div>
      </article>`;
  }

  function filteredActs() {
    const q = (qInput?.value || '').trim().toLowerCase();
    let list = cat.acts.slice();

    if (typeFilter.startsWith('bundle:')) {
      const bid = typeFilter.slice(7);
      const bundle = cat.bundles.find((b) => b.id === bid);
      const ids = new Set((bundle?.acts || []).map((a) => a.doc_id));
      list = list.filter((a) => ids.has(a.doc_id));
    } else if (typeFilter === 'закон') {
      list = list.filter((a) => a.act_type === 'закон' || a.act_type === 'конституционный закон');
    } else if (typeFilter !== 'all') {
      list = list.filter((a) => a.act_type === typeFilter);
    }

    if (q) {
      list = list.filter((a) =>
        (a.title + ' ' + a.number + ' ' + a.act_type + ' ' + a.doc_id).toLowerCase().includes(q));
    }
    return list;
  }

  function renderGrid() {
    const list = filteredActs();
    if (status) status.textContent = `Показано: ${list.length} из ${cat.count} · обновлено ${cat.updated}`;

    if (!grid) return;

    if (typeFilter.startsWith('bundle:')) {
      const bid = typeFilter.slice(7);
      const bundle = cat.bundles.find((b) => b.id === bid);
      const extraMap = Object.fromEntries((bundle?.acts || []).map((a) => [a.doc_id, a]));
      grid.innerHTML = list.map((a) => cardHtml(a, extraMap[a.doc_id])).join('');
      return;
    }

    if (typeFilter === 'all' && !(qInput?.value || '').trim()) {
      const groups = [
        ['Кодексы', cat.acts.filter((a) => a.act_type === 'кодекс')],
        ['Законы и конституционные законы', cat.acts.filter((a) => a.act_type === 'закон' || a.act_type === 'конституционный закон')],
        ['Приказы и подзаконные акты', cat.acts.filter((a) => a.act_type === 'приказ')],
      ];
      grid.innerHTML = groups.filter((g) => g[1].length).map(([title, acts]) => `
        <h2 class="legal-section-title">${esc(title)}</h2>
        <div class="legal-grid">${acts.map((a) => cardHtml(a)).join('')}</div>`).join('');
      return;
    }

    grid.innerHTML = `<div class="legal-grid">${list.map((a) => cardHtml(a)).join('')}</div>`;
  }

  renderKpi();
  renderSidebar();
  renderGrid();

  qInput?.addEventListener('input', renderGrid);

  document.querySelectorAll('.legal-filter').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.legal-filter').forEach((b) => b.setAttribute('aria-pressed', 'false'));
      btn.setAttribute('aria-pressed', 'true');
      typeFilter = btn.dataset.type || 'all';
      sidebar?.querySelectorAll('[data-filter]').forEach((x) => {
        x.classList.toggle('is-active', x.dataset.filter === typeFilter);
      });
      renderGrid();
    });
  });
})();
