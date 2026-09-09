/* Познавательный сборник — наука, профилактика, связь с данными */
(function initLibrary() {
  'use strict';

  document.getElementById('chrome-top').innerHTML = renderTopbar('library');
  document.getElementById('chrome-bottom').innerHTML = renderFooter();

  const DATA = window.LIBRARY_DATA || { items: [], applications: [], formula: [] };
  const TYPE_LABELS = { video: 'Ролик', book: 'Книга', article: 'Статья', quote: 'Цитата' };
  const TYPE_ICONS = { video: '▶', book: '📘', article: '📄', quote: '❝' };
  const SCIHUB_BASE = 'https://sci-hub.ru/';

  function sciHubUrl(doi) {
    const clean = String(doi || '').replace(/^https?:\/\/(dx\.)?doi\.org\//i, '').trim();
    return clean ? `${SCIHUB_BASE}${clean}` : '';
  }

  let activeType = 'all';
  let activeCollection = 'all';
  let query = '';
  const openCards = new Set();

  const grid = document.getElementById('lib-grid');
  const collectionsEl = document.getElementById('lib-collections');
  const apps = document.getElementById('lib-apps');
  const statusEl = document.getElementById('lib-status');

  function esc(s) {
    return String(s ?? '').replace(/[&<>"]/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
    ));
  }

  function itemHaystack(item) {
    return [
      item.title, item.author, item.preview, item.practice, item.doi,
      ...(item.body || []), ...(item.key_points || []), ...(item.tags || []),
    ].join(' ').toLowerCase();
  }

  function filteredItems() {
    const q = query.trim().toLowerCase();
    return (DATA.items || []).filter((item) => {
      if (activeType !== 'all' && item.type !== activeType) return false;
      if (activeCollection !== 'all' && !(item.collections || []).includes(activeCollection)) return false;
      if (!q) return true;
      return itemHaystack(item).includes(q);
    });
  }

  function renderCollections() {
    if (!collectionsEl) return;
    const cols = DATA.collections || [];
    if (!cols.length) {
      collectionsEl.innerHTML = '';
      return;
    }
    collectionsEl.innerHTML = `
      <button class="lib-collection${activeCollection === 'all' ? ' is-active' : ''}" type="button" data-collection="all" aria-pressed="${activeCollection === 'all'}">
        <span class="lib-collection__label">Все темы</span>
      </button>
      ${cols.map((c) => {
        const count = (DATA.items || []).filter((i) => (i.collections || []).includes(c.id)).length;
        return `<button class="lib-collection${activeCollection === c.id ? ' is-active' : ''}" type="button" data-collection="${c.id}" aria-pressed="${activeCollection === c.id}">
          <span class="lib-collection__label">${esc(c.label)}</span>
          <span class="lib-collection__meta">${count} · ${esc(c.lead)}</span>
        </button>`;
      }).join('')}`;
  }

  function renderLinks(item) {
    const links = [...(item.links || [])];
    if (item.doi) {
      const sh = sciHubUrl(item.doi);
      if (sh && !links.some((l) => l.url.includes('sci-hub'))) {
        links.unshift({ label: 'Sci-Hub · PDF', url: sh });
      }
      if (!links.some((l) => l.url.includes('doi.org'))) {
        links.push({ label: 'DOI', url: `https://doi.org/${item.doi.replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')}` });
      }
    }
    if (!links.length && item.url) {
      links.push({ label: 'Открыть источник', url: item.url });
    }
    return links.map((l) => `
      <a class="lib-card__link${l.label.startsWith('Sci-Hub') ? ' lib-card__link--scihub' : ''}" href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.label)} →</a>`).join('');
  }

  function renderGrid(items) {
    if (!items.length) {
      grid.innerHTML = '<div class="lib-empty">Ничего не найдено. Измените поиск или фильтр.</div>';
      return;
    }

    grid.innerHTML = items.map((item) => {
      const typeLabel = TYPE_LABELS[item.type] || item.type;
      const icon = TYPE_ICONS[item.type] || '•';
      const meta = [item.author, item.year, item.duration].filter(Boolean).join(' · ');
      const tags = (item.tags || []).map((t) => `<span class="lib-tag">${esc(t)}</span>`).join('');
      const isOpen = openCards.has(item.id);

      const bodyParas = (item.body || []).map((p) => `<p>${esc(p)}</p>`).join('');
      const keyPoints = (item.key_points || []).length
        ? `<h4 class="lib-card__h">Ключевые идеи</h4><ul class="lib-card__list">${item.key_points.map((k) => `<li>${esc(k)}</li>`).join('')}</ul>`
        : '';

      const dl = publicDataLink(item.data_link);
      const dataLink = dl
        ? `<a class="lib-card__data" href="${esc(dl.href)}">${esc(dl.label)} →</a>`
        : '';

      return `<article class="lib-card lib-card--${item.type}${isOpen ? ' is-open' : ''}" id="lib-${item.id}" data-id="${item.id}">
        <div class="lib-card__head">
          <div class="lib-card__type"><span>${icon}</span> ${esc(typeLabel)}</div>
          <h3>${esc(item.title)}</h3>
          <p class="lib-card__meta">${esc(meta)}</p>
          <div class="lib-card__tags">${tags}</div>
        </div>
        <p class="lib-card__preview">${esc(item.preview || item.summary || '')}</p>
        <div class="lib-card__expand"${isOpen ? '' : ' hidden'}>
          <div class="lib-card__body">${bodyParas}</div>
          ${keyPoints}
          <div class="lib-card__influence">
            <strong>Применение в нашей работе</strong>
            <p>${esc(item.practice || item.influence || '')}</p>
          </div>
          <div class="lib-card__foot">${renderLinks(item)}${dataLink}</div>
        </div>
        <button class="lib-card__more" type="button" data-toggle="${item.id}" aria-expanded="${isOpen}">
          ${isOpen ? 'Свернуть ↑' : 'Читать дальше ↓'}
        </button>
      </article>`;
    }).join('');
  }

  function renderStatus(items) {
    statusEl.innerHTML = `Материалов: <b>${items.length}</b> из ${(DATA.items || []).length}`;
  }

  function renderApplications() {
    const rows = (DATA.applications || []).filter((row) => isStaffView() || !isInternalHref(row.href));
    apps.innerHTML = rows.map((row) => `
      <article class="lib-app">
        <div class="lib-app__theory">${esc(row.theory)}</div>
        <h4>${esc(row.signal)}</h4>
        <p class="lib-app__data"><b>Наши данные:</b> ${esc(row.data)}</p>
        <p class="lib-app__why"><b>Почему:</b> ${esc(row.why)}</p>
        <p class="lib-app__check"><b>Что проверять:</b> ${esc(row.check)}</p>
        <a class="lib-app__link" href="${esc(row.href)}">Перейти к данным →</a>
      </article>`).join('');
  }

  function renderFormula() {
    const el = document.getElementById('lib-formula');
    if (!el) return;
    el.innerHTML = (DATA.formula || []).map((step, i) => {
      const title = typeof step === 'string' ? step : step.title;
      const hint = typeof step === 'string' ? '' : (step.hint || '');
      return `<div class="lib-formula__step">
        <div class="lib-formula__head">
          <span class="lib-formula__n">${i + 1}</span>
          <span class="lib-formula__t">${esc(title)}</span>
        </div>
        ${hint ? `<p class="lib-formula__hint">${esc(hint)}</p>` : ''}
      </div>`;
    }).join('');
  }

  function renderGridOnly(items) {
    const scrollY = window.scrollY;
    renderGrid(items);
    renderStatus(items);
    updateCollectionButtons();
    window.scrollTo({ top: scrollY, behavior: 'auto' });
  }

  function updateCollectionButtons() {
    if (!collectionsEl) return;
    collectionsEl.querySelectorAll('[data-collection]').forEach((btn) => {
      const on = btn.dataset.collection === activeCollection;
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function renderStatic() {
    renderCollections();
    renderApplications();
    renderFormula();
  }

  function renderAll() {
    renderGridOnly(filteredItems());
  }

  if (collectionsEl) {
    collectionsEl.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-collection]');
      if (!btn) return;
      activeCollection = btn.dataset.collection;
      if (activeCollection !== 'all') {
        activeType = 'article';
        document.querySelectorAll('#lib-filters .lib-filter').forEach((b) => {
          b.setAttribute('aria-pressed', b.dataset.type === activeType ? 'true' : 'false');
        });
      }
      renderAll();
    });
  }

  grid.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-toggle]');
    if (!btn) return;
    const id = btn.dataset.toggle;
    const card = document.getElementById(`lib-${id}`);
    const expand = card?.querySelector('.lib-card__expand');
    if (!card || !expand) return;

    const willOpen = expand.hidden;
    expand.hidden = !willOpen;
    card.classList.toggle('is-open', willOpen);
    btn.setAttribute('aria-expanded', willOpen);
    btn.textContent = willOpen ? 'Свернуть ↑' : 'Читать дальше ↓';
    if (willOpen) {
      openCards.add(id);
      if (window.matchMedia('(min-width: 721px)').matches) {
        scrollToElement(card, 'smooth');
      }
    } else {
      openCards.delete(id);
    }
  });

  document.getElementById('lib-q').addEventListener('input', (e) => {
    query = e.target.value;
    renderAll();
  });

  document.querySelectorAll('#lib-filters .lib-filter').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#lib-filters .lib-filter').forEach((b) => b.setAttribute('aria-pressed', 'false'));
      btn.setAttribute('aria-pressed', 'true');
      activeType = btn.dataset.type;
      renderAll();
    });
  });

  renderStatic();
  renderAll();
}());
