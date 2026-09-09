/* Ежеквартальные акты надзора для МВК — отдельная страница */
(function initQuarterlyPage() {
  'use strict';

  document.getElementById('chrome-top').innerHTML = renderTopbar('navigator');
  document.getElementById('chrome-bottom').innerHTML = renderFooter();

  const QUARTER = window.QUARTERLY_NADZOR || { blocks: [] };
  const KEY_Q = 'profilaktika-quarterly-v1';
  const LAW245 = 'https://adilet.zan.kz/rus/docs/Z2500000245';
  const TAG_LABELS = {
    силовой: 'Правоохранительные',
    социальный: 'Социальный блок',
    местный: 'Местный уровень',
  };

  let stateQ = {};
  try { stateQ = JSON.parse(localStorage.getItem(KEY_Q) || '{}'); } catch (e) { stateQ = {}; }

  const blocksEl = document.getElementById('nav-quarterly-blocks');
  const sidebar = document.getElementById('nav-q-sidebar');
  const kpiEl = document.getElementById('nav-q-kpi');

  function saveQ() {
    try { localStorage.setItem(KEY_Q, JSON.stringify(stateQ)); } catch (e) { /* ignore */ }
  }

  function navEsc(s) {
    return String(s ?? '').replace(/[&<>"]/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
    ));
  }

  function linkifyLaw(text) {
    const safe = navEsc(sanitizePublicText(text));
    return safe.replace(
      /(ст\.\s*\d+(?:\s*[-–]\s*\d+)?(?:\s*п\.?\s*\d+)?(?:\s*пп\.?\s*\d+)?(?:\s*ЗРК)?)/gi,
      (match) => {
        const num = match.match(/\d+/);
        const href = num ? `${LAW245}#z${num[0]}` : LAW245;
        return `<a class="nav-law" href="${href}" target="_blank" rel="noopener noreferrer">${match}</a>`;
      },
    );
  }

  function quarterProgress(block) {
    const done = block.acts.filter((_, i) => stateQ[`${block.id}:${i}`]).length;
    return { done, total: block.acts.length, pct: block.acts.length ? Math.round((done / block.acts.length) * 100) : 0 };
  }

  function totals() {
    const totalActs = (QUARTER.blocks || []).reduce((a, b) => a + b.acts.length, 0);
    const doneActs = Object.keys(stateQ).filter((k) => stateQ[k]).length;
    const pct = totalActs ? Math.round((doneActs / totalActs) * 100) : 0;
    return { totalActs, doneActs, pct, blocks: (QUARTER.blocks || []).length };
  }

  function renderKpi() {
    const t = totals();
    if (!kpiEl) return;
    kpiEl.innerHTML = `
      <div class="nav-kpi__cell"><b>${t.blocks}</b><span>Блоков</span></div>
      <div class="nav-kpi__cell"><b>${t.totalActs}</b><span>Актов надзора</span></div>
      <div class="nav-kpi__cell"><b>${t.doneActs}</b><span>Отмечено</span></div>
      <div class="nav-kpi__cell"><b>${t.pct}%</b><span>Готовность</span></div>`;
  }

  function renderSidebar() {
    if (!sidebar) return;
    sidebar.innerHTML = `<a class="nav-sidebar__link nav-sidebar__link--back" href="profilaktika_navigator.html">← 12 субъектов ЗРК</a>
      <a class="nav-sidebar__link nav-sidebar__link--back" href="prokuror_zakon.html">⚖ Работа с законами</a>
      <div class="nav-sidebar__title">Блоки МВК</div>`
      + (QUARTER.blocks || []).map((block) => {
        const { done, total, pct } = quarterProgress(block);
        const short = block.title.replace(/^[^·]+·\s*/, '');
        return `<a class="nav-sidebar__link" href="#qblock-${block.id}" data-jump="${block.id}">
          <span class="nav-sidebar__mini"><i style="width:${pct}%"></i></span>
          <span>${navEsc(short.length > 30 ? `${short.slice(0, 28)}…` : short)}<br>
          <small style="font-weight:500;color:var(--muted)">${done}/${total}</small></span>
        </a>`;
      }).join('');
  }

  function renderQuarterly() {
    const leadEl = document.getElementById('nav-quarterly-lead');
    const timingEl = document.getElementById('nav-quarterly-timing');
    const statusElQ = document.getElementById('nav-quarterly-status');
    if (!blocksEl || !(QUARTER.blocks || []).length) {
      if (blocksEl) {
        blocksEl.innerHTML = '<div class="nav-empty">Данные не загружены. Проверьте файл navigator_quarterly_data.js.</div>';
      }
      return;
    }

    if (leadEl) leadEl.textContent = QUARTER.lead || '';

    const ordersEl = document.getElementById('nav-quarterly-orders');
    if (ordersEl && QUARTER.orders_index?.length) {
      ordersEl.innerHTML = `<h3 class="nav-quarterly__orders-title">Подзаконные акты (для ссылок в актах надзора)</h3><ul class="nav-orders-index">${
        QUARTER.orders_index.map((o) => `<li><strong>${navEsc(o.label)}</strong> — ${navEsc(o.about)}</li>`).join('')
      }</ul>`;
    }

    if (timingEl && QUARTER.timing?.length) {
      timingEl.innerHTML = `<h3 class="nav-quarterly__orders-title">Когда что готовить</h3><div class="nav-quarterly__timing-grid">${
        QUARTER.timing.map(([q, period, note]) => `
        <div class="nav-qtime"><b>${navEsc(q)}</b><span>${navEsc(period)}</span><small>${navEsc(note)}</small></div>`).join('')
      }</div>`;
    }

    const openIds = new Set(
      [...blocksEl.querySelectorAll('details.nav-qblock[open]')].map((el) => el.id.replace('qblock-', '')),
    );

    const t = totals();
    if (statusElQ) {
      statusElQ.innerHTML = `<span>Ежеквартальный пакет: <b>${t.doneActs}</b> из ${t.totalActs} пунктов подготовлено</span>
        <div class="nav-status__bar"><i style="width:${t.pct}%"></i></div>`;
    }

    const glossaryEl = document.getElementById('nav-quarterly-glossary');
    if (glossaryEl && QUARTER.soc_glossary?.length) {
      glossaryEl.innerHTML = `<div class="nav-glossary">
        <h3 class="nav-glossary__title">Словарь для соцблока</h3>
        <dl class="nav-glossary__list">${
          QUARTER.soc_glossary.map((item) => `
          <div class="nav-glossary__item">
            <dt>${navEsc(item.term)}</dt>
            <dd>${linkifyLaw(item.about)}</dd>
          </div>`).join('')
        }</dl>
      </div>`;
    } else if (glossaryEl) {
      glossaryEl.innerHTML = '';
    }

    blocksEl.innerHTML = QUARTER.blocks.map((block) => {
      const { done, total, pct } = quarterProgress(block);
      const tagLabel = TAG_LABELS[block.tag] || block.tag;
      const actsHtml = block.acts.map((act, i) => {
        const k = `${block.id}:${i}`;
        const on = !!stateQ[k];
        return `<details class="nav-qact${on ? ' is-done' : ''}" id="qact-${k}">
          <summary>
            <input type="checkbox" class="nav-qact__chk" data-qk="${k}"${on ? ' checked' : ''} aria-label="Выполнено" onclick="event.stopPropagation()">
            <span class="nav-qact__title">${navEsc(act.title)}</span>
            <span class="nav-qact__norm">${linkifyLaw(act.norm)}</span>
          </summary>
          <div class="nav-qact__body">
            <div class="nav-qfield"><h5>Зачем прокурору</h5><p>${linkifyLaw(act.purpose)}</p></div>
            <div class="nav-qfield"><h5>Что запросить / проверить</h5><p>${linkifyLaw(act.request)}</p></div>
            <div class="nav-qfield"><h5>Как проверить</h5><p>${linkifyLaw(act.verify)}</p></div>
            ${(act.orders || []).length ? `<div class="nav-qfield nav-qfield--orders"><h5>Приказы / подзаконные акты</h5><ul>${act.orders.map((o) => `<li>${linkifyLaw(o)}</li>`).join('')}</ul></div>` : ''}
            <div class="nav-callout nav-callout--sig"><strong>Признак нарушения:</strong> ${linkifyLaw(act.signal)}</div>
            <div class="nav-callout nav-callout--react"><strong>Что сделать на комиссии и как реагировать:</strong> ${linkifyLaw(act.react)}</div>
          </div>
        </details>`;
      }).join('');

      return `<details class="nav-qblock" id="qblock-${block.id}"${openIds.has(block.id) || (!openIds.size && block.id === QUARTER.blocks[0]?.id) ? ' open' : ''}>
        <summary>
          <h3>${navEsc(block.title)} <span class="nav-tag nav-tag--${block.tag}">${navEsc(tagLabel)}</span></h3>
          <p class="nav-qblock__organs">${navEsc(block.organs)}</p>
          <div class="nav-org__progress">Подготовлено ${done} из ${total}
            <div class="nav-org__track"><i style="width:${pct}%"></i></div>
          </div>
        </summary>
        <div class="nav-qblock__body">
          <div class="nav-qfield nav-qfield--why"><h4>Зачем этот блок на МВК</h4><p>${linkifyLaw(block.why)}</p></div>
          <div class="nav-callout nav-callout--gap"><strong>Формулировка для повестки:</strong> ${linkifyLaw(block.commission)}</div>
          <h4>Акты надзора (ежеквартально)</h4>
          <div class="nav-qacts">${actsHtml}</div>
        </div>
      </details>`;
    }).join('');

    renderKpi();
    renderSidebar();
  }

  function updateQuarterProgress() {
    renderQuarterly();
  }

  blocksEl?.addEventListener('change', (e) => {
    const cb = e.target.closest('.nav-qact__chk');
    if (!cb) return;
    stateQ[cb.dataset.qk] = cb.checked;
    cb.closest('.nav-qact')?.classList.toggle('is-done', cb.checked);
    saveQ();
    updateQuarterProgress();
  });

  document.getElementById('nav-q-open-all')?.addEventListener('click', () => {
    document.querySelectorAll('details.nav-qblock, details.nav-qact').forEach((d) => { d.open = true; });
  });
  document.getElementById('nav-q-close-all')?.addEventListener('click', () => {
    document.querySelectorAll('details.nav-qblock, details.nav-qact').forEach((d) => { d.open = false; });
  });
  document.getElementById('nav-q-reset')?.addEventListener('click', () => {
    if (!confirm('Снять отметки ежеквартального пакета?')) return;
    stateQ = {};
    saveQ();
    updateQuarterProgress();
  });
  document.getElementById('nav-q-export')?.addEventListener('click', () => {
    const rows = [['Блок', 'Органы', 'Акт надзора', 'Норма', 'Приказы', 'Зачем', 'Комиссия и реагирование', 'Отметка']];
    (QUARTER.blocks || []).forEach((block) => block.acts.forEach((act, i) => {
      rows.push([
        block.title, block.organs, act.title, act.norm,
        (act.orders || []).join('; '), act.purpose, act.react,
        stateQ[`${block.id}:${i}`] ? 'готово' : '',
      ]);
    }));
    const csv = `\uFEFF${rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\r\n')}`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'akt_nadzora_mvk_kvartal.csv';
    a.click();
    URL.revokeObjectURL(url);
  });
  document.getElementById('nav-q-print')?.addEventListener('click', () => {
    document.querySelectorAll('details.nav-qblock, details.nav-qact').forEach((d) => { d.open = true; });
    window.print();
  });

  sidebar?.addEventListener('click', (e) => {
    const link = e.target.closest('[data-jump]');
    if (!link) return;
    e.preventDefault();
    const id = link.dataset.jump;
    const el = document.getElementById(`qblock-${id}`);
    if (el) {
      el.open = true;
      scrollToElement(el);
      sidebar.querySelectorAll('.nav-sidebar__link').forEach((a) => a.classList.remove('is-active'));
      link.classList.add('is-active');
    }
  });

  renderQuarterly();

  if (location.hash.startsWith('#qblock-')) {
    setTimeout(() => {
      const el = document.querySelector(location.hash);
      if (el) {
        el.open = true;
        scrollToElement(el);
      }
    }, 100);
  }
}());
