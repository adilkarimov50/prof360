/* Страница паспорта: 18 разделов, навигация со слежением за прокруткой. */

let active = currentId();

/* ---------- Конструкторы блоков ---------- */

function kpiCard(value, label, note = '', badge = '') {
  return `
    <div class="card kpi">
      <b>${value} ${badge}</b>
      <span>${esc(label)}</span>
      ${note ? `<div class="note">${esc(note)}</div>` : ''}
    </div>`;
}

function statRows(rows, keyField, valueField) {
  const list = Array.isArray(rows) ? rows : [];
  return list.map((row) => `
    <div class="stat-row">
      <span class="stat-row__label">${esc(row[keyField])}</span>
      <span class="stat-row__value">${esc(row[valueField]) || '—'}</span>
    </div>`).join('') || '<p style="margin:0;color:var(--muted);font-size:14.5px">Данные не заполнены.</p>';
}

function passportCharacteristicText(p) {
  if (p.characteristic) return p.characteristic;
  const block = (p.narrative_blocks || []).find((b) => /криминолог/i.test(b.title || ''));
  if (block?.text) return block.text;
  const first = (p.narrative_blocks || [])[0];
  return first?.text || p.summary?.description || '—';
}

function narrativeBlockHtml(p, titleRe) {
  const block = (p.narrative_blocks || []).find((b) => titleRe.test(b.title || ''));
  if (!block?.text) return '';
  return `<div class="callout"><p>${esc(block.text)}</p></div>`;
}

function socioBlock(p) {
  if (Array.isArray(p.socio) && p.socio.length) {
    return `<div class="card">${statRows(p.socio, 'indicator', 'value')}</div>`;
  }
  if (!Array.isArray(p.socio_extended) || !p.socio_extended.length) {
    return '<div class="callout"><p>Данные акимата и центра занятости не заполнены в паспорте.</p></div>';
  }
  return p.socio_extended.map((block) => {
    const rows = (block.rows || []).map((r) => ({
      indicator: r.indicator,
      value: r.comment ? `${r.value} · ${r.comment}` : r.value,
    }));
    const title = block.table === 'employment' ? 'Занятость и предпринимательство'
      : block.table === 'education' ? 'Образование'
        : block.table || 'Показатели';
    return `<div class="card" style="margin-bottom:12px">
      <div class="card__title">${esc(title)}</div>
      ${statRows(rows, 'indicator', 'value')}
    </div>`;
  }).join('');
}

function dynamicsCards(rows) {
  return rows.map((row) => {
    if (row.current === undefined || row.current === null) {
      return `<div class="card">
          <div class="card__title">${esc(row.indicator)}</div>
          <p style="margin:0;color:var(--muted);font-size:14.5px">${esc(row.raw)}</p>
        </div>`;
    }
    const prev = row.previous !== undefined && row.previous !== null
      ? `АППГ — ${fmt(row.previous)}` : '';
    return kpiCard(fmt(row.current), row.indicator, prev, deltaBadge(deltaFromPair(row)));
  }).join('');
}

function integratedBlock(intg, passportId) {
  if (!intg) return '';
  const connRows = (intg.connections || []).map((c) => `
    <div class="card" style="margin-bottom:12px">
      <div class="card__title">${esc(c.title)}</div>
      <p style="margin:0 0 8px;font-size:14.5px;color:var(--muted)">${esc(c.conclusion)}</p>
    </div>`).join('');
  const shareRows = (intg.locality_compare || []).map((r, i) => `
    <div class="stat-row">
      <span class="stat-row__label">${esc(isStaffView() ? r.source : `Реестр ${i + 1}`)}</span>
      <span class="stat-row__value">${fmt(r.count)} · ${esc(r.share)}</span>
    </div>`).join('');
  const funnel = (intg.funnel || []).map((s) => kpiCard(fmt(s.count), s.stage)).join('');
  const cs = intg.crossmatch_summary || {};
  return `
    <div class="callout" style="margin-bottom:16px"><p>${esc(intg.summary)}</p></div>
    <div class="grid grid--2" style="margin-bottom:16px">
      <div class="card">
        <div class="card__title">Доли от районного числа</div>
        ${shareRows || '<p style="margin:0;color:var(--muted)">—</p>'}
      </div>
      <div class="card">
        <div class="card__title">Воронка профилактики</div>
        <div class="grid grid--2">${funnel}</div>
      </div>
    </div>
    <div class="grid grid--4" style="margin-bottom:16px">
      ${kpiCard(fmt(cs.unique_persons), 'Лиц в сверке')}
      ${kpiCard(fmt(cs.match_all_three), 'ОВД+мед+УД', 'полное пересечение')}
      ${kpiCard(fmt(cs.gap_med_no_police), 'Мед без ОВД')}
      ${kpiCard(fmt(cs.gap_crime_no_police), 'УД без ОВД')}
    </div>
    <div class="card" style="margin-bottom:16px">
      <div class="card__title">Скрытые логические связи</div>
      ${connRows}
    </div>
    <div class="grid grid--2">
      <div class="card">
        <div class="card__title">Выявленные проблемы</div>
        <ul class="list-check">${(intg.problems || []).map((t) => `<li><span>${esc(t)}</span></li>`).join('')}</ul>
      </div>
      <div class="card">
        <div class="card__title">Рекомендации</div>
        <ul class="list-check">${(intg.recommendations || []).map((t) => `<li><span>${esc(t)}</span></li>`).join('')}</ul>
      </div>
    </div>
    <p style="margin:16px 0 0;display:flex;gap:10px;flex-wrap:wrap">
      ${isStaffView() ? `<a class="tag" href="${passportId === 'kaskelen' ? 'kaskelen_map.html' : 'irgeli_map.html'}" style="padding:9px 15px;text-decoration:none;font-size:13.5px;background:var(--up);color:#fff">
        Карта + сверка профучёта →</a>` : `<a class="tag" href="${passportId === 'kaskelen' ? 'kaskelen_map.html' : 'irgeli_map.html'}" style="padding:9px 15px;text-decoration:none;font-size:13.5px;background:var(--up);color:#fff">
        Карта объектов →</a>`}
    </p>`;
}

function measuresBlock(measures) {
  const fields = [
    ['object', 'Объект'],
    ['executors', 'Исполнители'],
    ['term', 'Срок'],
    ['criterion', 'Критерий оценки'],
  ];
  return measures.map((m) => `
    <article class="measure" open-state="0">
      <button class="measure__btn" type="button">
        <span class="measure__no">${m.number}</span>
        <span class="measure__ttl">${esc(m.title)}</span>
        <span class="measure__caret">▾</span>
      </button>
      <div class="measure__body">
        <dl style="margin:0">
          ${fields.filter(([key]) => m[key]).map(([key, label]) => `
            <div class="measure__row"><dt>${label}</dt><dd>${esc(m[key])}</dd></div>`).join('')}
        </dl>
        ${m.rationale ? `<div class="measure__why"><b>Основание:</b> ${esc(m.rationale)}</div>` : ''}
      </div>
    </article>`).join('');
}

/* ---------- Разделы ---------- */

function buildSectionsChundzha(p) {
  const s = p.summary;
  const timeTotal = p.time_of_day.reduce((sum, r) => sum + (r.count || 0), 0);
  const nightShare = p.time_of_day
    .filter((r) => /Ночное|Вечернее/i.test(r.period))
    .reduce((sum, r) => sum + (r.count || 0), 0);

  return [
    {
      title: 'Общая характеристика',
      lead: 'Базовые сведения о населённом пункте и уровне зарегистрированной преступности.',
      html: `
        <div class="grid grid--4">
          ${kpiCard(fmt(s.population), 'Численность населения')}
          ${kpiCard(fmt(s.crimes.current), 'Зарегистрировано уголовных правонарушений',
            `АППГ — ${fmt(s.crimes.previous)}`, deltaBadge(s.crimes.delta_pct ?? null))}
          ${kpiCard(String(s.rate_per_10k).replace('.', ','), 'Уровень преступности на 10 тыс. населения')}
          ${kpiCard(fmt(p.admin_practice?.total || 0), 'Административных правонарушений', p.admin_practice?.period || '')}
        </div>
        <div class="callout" style="margin-top:16px"><p>${esc(s.description)}</p></div>`,
    },
    {
      title: 'Криминологическая характеристика',
      lead: 'Обобщённая оценка криминогенной обстановки на территории.',
      html: `<div class="callout"><p>${esc(p.characteristic)}</p></div>`,
    },
    {
      title: 'Структура преступности',
      lead: 'Распределение по видам уголовных правонарушений за отчётный период.',
      html: `<div class="card">${simpleBars(
        p.crime_structure.filter((r) => r.indicator !== 'ВСЕГО').map((r) => ({
          label: r.indicator,
          value: Number(String(r.value).replace(/\s/g, '')) || 0,
        })),
      )}</div>`,
    },
    {
      title: 'Тяжесть преступлений',
      lead: 'Сопоставление с аналогичным периодом прошлого года по категориям тяжести.',
      html: `<div class="card">${statRows(p.crime_severity, 'category', 'current')}</div>`,
    },
    {
      title: 'Портрет лица, совершившего преступление',
      lead: 'Характеристика установленных лиц, определяющая адресность профилактической работы.',
      html: `<div class="card">${statRows(p.offender_profile, 'indicator', 'value')}</div>`,
    },
    {
      title: 'Портрет потерпевшего',
      lead: 'Категории граждан, наиболее подверженные риску стать потерпевшими.',
      html: `<div class="grid grid--3">${p.victim_profile.slice(0, 9).map((r) => kpiCard(esc(r.value), r.indicator)).join('')}</div>`,
    },
    {
      title: 'Время и место совершения',
      lead: `Распределение по времени суток и объекты концентрации преступности. На вечернее и ночное время приходится ${pct((nightShare / (timeTotal || 1)) * 100)} фактов.`,
      html: `
        <div class="grid grid--2">
          <div class="card">
            <div class="card__title">Время суток</div>
            ${donutChart(p.time_of_day.map((r) => ({ label: r.period, value: r.count })))}
          </div>
          <div class="card">
            <div class="card__title">Точки концентрации преступности</div>
            ${passportHotspots(p).map((h, i, arr) => `
              <div class="hotspot" style="padding:13px 0;border-bottom:${i < arr.length - 1 ? '1px dashed var(--line)' : '0'}">
                <div class="hotspot__rank">${i + 1}</div>
                <div class="hotspot__body">
                  <h4>${esc(h.object)}</h4>
                  <p>${esc(h.types)}</p>
                  ${h.measures ? `<p style="font-size:12.5px;color:var(--muted);margin-top:4px">${esc(h.measures)}</p>` : ''}
                </div>
                <div class="hotspot__count">${hotspotCountHtml(h.count)}</div>
              </div>`).join('')}
            <p style="margin:16px 0 0;display:flex;gap:10px;flex-wrap:wrap">
              <a class="tag" href="map.html?id=${p.id}" style="padding:9px 15px;text-decoration:none;font-size:13.5px">
                Карта объектов →</a>
              ${{ chundzha: 'chundzha_map.html', kaskelen: 'kaskelen_map.html', irgeli: 'irgeli_map.html' }[p.id]
                ? `<a class="tag" href="${{ chundzha: 'chundzha_map.html', kaskelen: 'kaskelen_map.html', irgeli: 'irgeli_map.html' }[p.id]}" style="padding:9px 15px;text-decoration:none;font-size:13.5px;background:var(--up);color:#fff">
                Детальная карта + маршруты патрулирования →</a>` : ''}
            </p>
          </div>
        </div>`,
    },
    {
      title: 'Основные криминогенные факторы',
      lead: 'Факторы с количественным подтверждением по данным паспорта.',
      html: `<div class="grid grid--2">${p.factors.map((f) => `
        <div class="card">
          <div class="card__title">${esc(f.factor)} <span class="tag">${esc(f.risk)}</span></div>
          <p style="margin:0;color:var(--muted);font-size:14.5px">${esc(f.details) || '—'}</p>
        </div>`).join('')}</div>`,
    },
    {
      title: 'Причины и условия',
      lead: 'Группировка причин и условий, способствующих совершению правонарушений.',
      html: `<div class="grid grid--3">${p.causes.map((c) => `
        <div class="card">
          <div class="card__title">${esc(c.type)}</div>
          <p style="margin:0 0 12px;font-size:14.5px">${esc(c.details)}</p>
          ${c.examples ? `<div class="measure__why" style="margin:0">${esc(c.examples)}</div>` : ''}
        </div>`).join('')}</div>`,
    },
    {
      title: 'Криминогенные объекты',
      lead: 'Объекты и участки, требующие профилактического контроля.',
      html: `<div class="card">${statRows(p.criminogenic_objects, 'object', 'details')}</div>`,
    },
    {
      title: 'Административная практика',
      lead: `Форма 1-АД. За период ${esc(p.admin_practice.period)} зарегистрировано ${fmt(p.admin_practice.total)} административных правонарушений.`,
      html: `<div class="card">${simpleBars(p.admin_practice.top_articles.map((r) => ({
        label: `${r.article} — ${r.title}`,
        value: Number(String(r.count).replace(/\s/g, '')) || 0,
      })))}</div>`,
    },
    {
      title: 'Приоритетные профилактические мероприятия',
      lead: 'Мероприятия по конкретным местам, времени, способам совершения преступлений и категориям потерпевших.',
      html: measuresBlock(p.measures),
    },
    {
      title: 'Ожидаемые результаты',
      lead: 'Результаты, ожидаемые от реализации приоритетных мероприятий.',
      html: `<div class="card"><ul class="list-check">${p.expected_results
        .filter((t) => !/перечень использованных/i.test(t))
        .map((t) => `<li><span>${esc(t)}</span></li>`).join('')}</ul></div>`,
    },
  ];
}

function buildSections(p) {
  if (p.id === 'chundzha') return buildSectionsChundzha(p);
  const s = p.summary;
  const admTotal = p.admin_practice.find((r) => r.indicator.startsWith('Всего'));
  const admRest = p.admin_practice.filter((r) => !r.indicator.startsWith('Всего'));
  const registryTotal = p.registry.reduce((sum, r) => sum + (r.count || 0), 0);
  const timeTotal = p.time_of_day.reduce((sum, r) => sum + (r.count || 0), 0);
  const nightShare = p.time_of_day
    .filter((r) => /Ночное|Вечернее/i.test(r.period))
    .reduce((sum, r) => sum + (r.count || 0), 0);

  return [
    {
      title: 'Общая характеристика',
      lead: 'Базовые сведения о населённом пункте и уровне зарегистрированной преступности.',
      html: `
        <div class="grid grid--4">
          ${kpiCard(fmt(s.population), 'Численность населения')}
          ${kpiCard(fmt(s.crimes.current), 'Зарегистрировано уголовных правонарушений',
            `АППГ — ${fmt(s.crimes.previous)}`, deltaBadge(s.crimes.delta_pct ?? null))}
          ${kpiCard(String(s.rate_per_10k).replace('.', ','), 'Уровень преступности на 10 тыс. населения')}
          ${kpiCard(fmt(registryTotal), 'Лиц на профилактическом учёте')}
        </div>
        <div class="callout" style="margin-top:16px"><p>${esc(s.description)}</p></div>`,
    },
    {
      title: 'Социально-экономические показатели',
      lead: 'Сведения акимата, центра занятости населения и отдела образования, используемые для оценки криминогенного фона.',
      html: socioBlock(p),
    },
    {
      title: 'Криминологическая характеристика',
      lead: 'Обобщённая оценка криминогенной обстановки на территории.',
      html: `<div class="callout"><p>${esc(passportCharacteristicText(p))}</p></div>`,
    },
    {
      title: 'Структура преступности',
      lead: 'Сопоставление с аналогичным периодом прошлого года по основным видам уголовных правонарушений.',
      html: `<div class="card">${barsChart(p.crime_structure)}</div>`,
    },
    {
      title: 'Портрет лица, совершившего преступление',
      lead: 'Характеристика установленных лиц, определяющая адресность профилактической работы.',
      html: p.offender_profile?.length
        ? `<div class="card">${statRows(p.offender_profile, 'indicator', 'value')}</div>`
        : narrativeBlockHtml(p, /совершившего преступление/i)
          || '<div class="callout"><p>Характеристика правонарушителя приведена в криминологической характеристике.</p></div>',
    },
    {
      title: 'Портрет потерпевшего',
      lead: 'Категории граждан, наиболее подверженные риску стать потерпевшими.',
      html: p.victim_profile?.length
        ? `<div class="grid grid--3">${p.victim_profile.map((r) => kpiCard(esc(r.value), r.indicator)).join('')}</div>`
        : narrativeBlockHtml(p, /потерпевш/i)
          || '<div class="callout"><p>Характеристика потерпевших приведена в криминологической характеристике.</p></div>',
    },
    {
      title: 'Время и место совершения',
      lead: p.time_of_day?.length
        ? `Распределение по времени суток и объекты концентрации преступности. На вечернее и ночное время приходится ${pct((nightShare / (timeTotal || 1)) * 100)} фактов, распределённых по времени суток.`
        : 'Объекты концентрации преступности и сведения о времени совершения.',
      html: `
        <div class="grid grid--2">
          ${p.time_of_day?.length ? `<div class="card">
            <div class="card__title">Время суток</div>
            ${donutChart(p.time_of_day.map((r) => ({ label: r.period, value: r.count })))}
          </div>` : `<div class="card">
            <div class="card__title">Время суток</div>
            ${narrativeBlockHtml(p, /время и место/i) || '<p style="margin:0;color:var(--muted)">Данные по времени суток уточняются в паспорте.</p>'}
          </div>`}
          <div class="card">
            <div class="card__title">Точки концентрации преступности</div>
            ${passportHotspots(p).map((h, i, arr) => `
              <div class="hotspot" style="padding:13px 0;border-bottom:${i < arr.length - 1 ? '1px dashed var(--line)' : '0'}">
                <div class="hotspot__rank">${i + 1}</div>
                <div class="hotspot__body">
                  <h4>${esc(h.object)}</h4>
                  <p>${esc(h.types)}</p>
                </div>
                <div class="hotspot__count">${hotspotCountHtml(h.count)}</div>
              </div>`).join('')}
            <p style="margin:16px 0 0;display:flex;gap:10px;flex-wrap:wrap">
              <a class="tag" href="map.html?id=${p.id}" style="padding:9px 15px;text-decoration:none;font-size:13.5px">
                Карта объектов →</a>
              ${{ kaskelen: 'kaskelen_map.html', irgeli: 'irgeli_map.html', chundzha: 'chundzha_map.html' }[p.id]
                ? `<a class="tag" href="${{ kaskelen: 'kaskelen_map.html', irgeli: 'irgeli_map.html', chundzha: 'chundzha_map.html' }[p.id]}" style="padding:9px 15px;text-decoration:none;font-size:13.5px;background:var(--up);color:#fff">
                Детальная карта + маршруты →</a>` : ''}
            </p>
          </div>
        </div>`,
    },
    {
      title: 'Административная практика',
      lead: `Форма 1-АД. Всего зарегистрировано ${fmt(admTotal?.count)} административных правонарушений, из них по составам, значимым для профилактики:`,
      html: `<div class="card">${simpleBars(admRest.map((r) => ({
        label: r.indicator,
        value: r.count,
        color: /Дорожные/i.test(r.indicator) ? '#8b9bb4' : 'var(--navy-700)',
      })))}</div>`,
    },
    {
      title: 'Основные криминогенные факторы',
      lead: 'Факторы с количественным подтверждением по данным паспорта; строки без установленных фактов сохранены для последующего мониторинга.',
      html: p.factors?.length
        ? `<div class="grid grid--2">${p.factors.map((f) => `
        <div class="card">
          <div class="card__title">${esc(f.factor)}</div>
          <p style="margin:0;color:var(--muted);font-size:14.5px">${esc(f.details) || '—'}</p>
        </div>`).join('')}</div>`
        : `<div class="card">${statRows(p.criminogenic_objects, 'object', 'details')}</div>`,
    },
    {
      title: 'Причины и условия',
      lead: 'Группировка причин и условий, способствующих совершению правонарушений.',
      html: p.causes?.length
        ? `<div class="grid grid--3">${p.causes.map((c) => `
        <div class="card">
          <div class="card__title">${esc(c.type)}</div>
          <p style="margin:0 0 12px;font-size:14.5px">${esc(c.details)}</p>
          ${c.examples ? `<div class="measure__why" style="margin:0">${esc(c.examples)}</div>` : ''}
        </div>`).join('')}</div>`
        : narrativeBlockHtml(p, /семейно-бытов/i)
          || '<div class="callout"><p>Причины и условия отражены в криминогенных объектах и характеристике.</p></div>',
    },
    {
      title: 'Лица профилактического учёта',
      lead: registryTotal
        ? `Всего на профилактическом учёте состоит ${fmt(registryTotal)} лиц — это адресная база индивидуальной профилактики.`
        : 'Сведения о профилактическом учёте уточняются в актуальной редакции паспорта.',
      html: p.registry?.length
        ? `<div class="grid grid--4">${p.registry.map((r) => kpiCard(fmt(r.count), r.category)).join('')}</div>`
        : '<div class="callout"><p>Детализация профучёта будет дополнена в следующем обновлении паспорта.</p></div>',
    },
    {
      title: 'Криминогенные объекты',
      lead: 'Объекты и участки, требующие профилактического контроля.',
      html: `<div class="card">${statRows(p.criminogenic_objects, 'object', 'details')}</div>`,
    },
    {
      title: 'Семейно-бытовая преступность',
      lead: 'Показатели семейно-бытовой сферы и работа с семьями группы риска.',
      html: `<div class="grid grid--3">${dynamicsCards(p.domestic_crime || [])}</div>`,
    },
    {
      title: 'Преступления в отношении несовершеннолетних',
      lead: 'Потерпевшие несовершеннолетние, причины, условия и принятые меры.',
      html: (p.minors || []).length
        ? `
        <div class="grid grid--2">${dynamicsCards((p.minors || []).filter((r) => r.current !== undefined && r.current !== null))}</div>
        <div class="card" style="margin-top:16px">
          ${statRows((p.minors || []).filter((r) => r.current === undefined || r.current === null), 'indicator', 'raw')}
        </div>`
        : narrativeBlockHtml(p, /несовершеннолетн/i)
          || '<div class="callout"><p>Раздел уточняется в актуальной редакции паспорта.</p></div>',
    },
    {
      title: 'Скотокрадство',
      lead: 'Раздел заполняется при наличии зарегистрированных фактов.',
      html: `<div class="card">${statRows(p.cattle_theft || [], 'indicator', 'value')}</div>`,
    },
    ...(p.special?.title ? [{
      title: p.special.title,
      lead: 'Раздел, отражающий специфику территории населённого пункта.',
      html: `<div class="card">${statRows(p.special.rows || [], 'indicator', 'value')}</div>`,
    }] : []),
    {
      title: 'Приоритетные профилактические мероприятия',
      lead: 'Каждое мероприятие раскрывается объектом профилактики, исполнителями, сроком и критерием оценки. Нажмите на мероприятие, чтобы развернуть карточку.',
      html: measuresBlock(p.measures),
    },
    ...(p.integrated && isStaffView() ? [{
      title: 'Сверка профучёта и интегрированный анализ',
      lead: `Person-level сверка реестров ОВД, медучёта и ЕРДР · ${p.integrated.generated || '2026'}. Новые выводы, проблемы и рекомендации на основе 3 236 лиц.`,
      html: integratedBlock(p.integrated, p.id),
    }] : []),
    {
      title: 'Ожидаемые результаты',
      lead: 'Результаты, ожидаемые от реализации приоритетных мероприятий.',
      html: `<div class="card"><ul class="list-check">${p.expected_results
        .map((t) => `<li><span>${esc(t)}</span></li>`).join('')}</ul></div>`,
    },
  ];
}

/* ---------- Профиль-only режим ---------- */

function buildProfileOnlySections(p) {
  return [
    {
      title: 'Социально-экономический профиль',
      lead: 'Характеристика населённого пункта по данным БНС и официальных источников — основа для профилактики правонарушений.',
      html: localityProfileHtml(p),
    },
    {
      title: 'Криминологический паспорт',
      lead: 'Полный паспорт из 18 разделов готовится к публикации.',
      html: `<div class="callout card-warn" style="border-left:4px solid var(--gold)">
        <p style="margin:0 0 12px">Для <strong>${esc(p.name)}</strong> пока доступен обзорный профиль. Структура преступности, административная практика и мероприятия будут добавлены после оцифровки официального документа.</p>
        <p style="margin:0;font-size:14px;color:var(--muted)">Источники: ${(p.locality_profile?.sources || []).map((s) => esc(s.title)).join(', ') || 'БНС РК'}</p>
      </div>`,
    },
  ];
}

/* ---------- Отрисовка страницы ---------- */

function render(id) {
  active = id;
  const p = getPassport(id);
  const s = p.summary;
  const profileOnly = isProfileOnly(p);

  history.replaceState(null, '', `?id=${id}`);
  document.title = `${profileOnly ? 'Профиль' : 'Криминологический паспорт'} · ${p.name} · 2026`;
  document.getElementById('chrome-top').innerHTML = renderTopbar('passport', id);
  document.getElementById('chrome-bottom').innerHTML = renderFooter();

  document.getElementById('p-name').textContent = `${profileOnly ? 'Социально-экономический профиль' : 'Криминологический паспорт'} — ${p.name}`;
  document.getElementById('p-desc').textContent = s.description;
  const chips = profileOnly
    ? [
      ['chip--gold', `${fmt(s.population)} жителей`],
      ['', esc(p.district || s.district || '')],
      ['', passportStatusBadge(p).replace(/<[^>]+>/g, '')],
    ]
    : [
      ['chip--gold', `${fmt(s.crimes.current)} уголовных правонарушений`],
      ['', `${fmt(s.population)} жителей`],
      ['', s.rate_per_10k != null ? `${String(s.rate_per_10k).replace('.', ',')} на 10 тыс. населения` : ''],
      ['', esc(p.district)],
    ];
  document.getElementById('p-chips').innerHTML = chips
    .filter(([, t]) => t)
    .map(([mod, text]) => `<span class="chip ${mod}">${text}</span>`).join('');

  document.getElementById('p-switch').innerHTML = renderSwitch(id, render);

  let sections;
  try {
    sections = profileOnly ? buildProfileOnlySections(p) : buildSections(p);
    if (!profileOnly && p.locality_profile) {
      sections.unshift({
        title: 'Социально-экономический профиль',
        lead: 'Население, этнический состав, экономика и факторы, влияющие на профилактику правонарушений.',
        html: localityProfileHtml(p),
      });
    }
  } catch (err) {
    console.error(err);
    document.getElementById('sections').innerHTML = '<div class="card" style="padding:24px"><p style="margin:0">Не удалось загрузить разделы паспорта. Обновите страницу: <b>Cmd+Shift+R</b> (Mac) или <b>Ctrl+Shift+R</b> (Windows).</p></div>';
    document.getElementById('toc').innerHTML = '';
    return;
  }

  document.getElementById('sections').innerHTML = sections.map((sec, i) => `
    <section class="section" id="s${i + 1}">
      <div class="section__head">
        <div class="section__num">${String(i + 1).padStart(2, '0')}</div>
        <div class="section__title">
          <h2>${esc(sec.title)}</h2>
          <p>${sec.lead}</p>
        </div>
      </div>
      ${sec.html}
    </section>`).join('');

  document.getElementById('toc').innerHTML = sections.map((sec, i) => `
    <a href="#s${i + 1}"><span>${i + 1}</span>${esc(sec.title)}</a>`).join('');

  bindTocNav();
  bindMeasures();
  bindScrollSpy();
  if (render.lastId && render.lastId !== id) window.scrollTo({ top: 0, behavior: 'auto' });
  render.lastId = id;
}

function bindTocNav() {
  const toc = document.getElementById('toc');
  if (!toc || toc.dataset.bound) return;
  toc.dataset.bound = '1';
  toc.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a) return;
    e.preventDefault();
    const target = document.querySelector(a.getAttribute('href'));
    if (!target) return;
    scrollToElement(target);
    history.replaceState(null, '', `${location.pathname}${location.search}${a.getAttribute('href')}`);
    toc.querySelectorAll('a').forEach((link) => link.classList.remove('active'));
    a.classList.add('active');
  });
}

function bindMeasures() {
  document.querySelectorAll('.measure__btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const card = btn.closest('.measure');
      card.setAttribute('open-state', card.getAttribute('open-state') === '1' ? '0' : '1');
    });
  });
}

let spy = null;

function bindScrollSpy() {
  if (spy) spy.disconnect();
  const links = new Map();
  document.querySelectorAll('#toc a').forEach((a) => links.set(a.getAttribute('href').slice(1), a));

  spy = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      links.forEach((a) => a.classList.remove('active'));
      const link = links.get(entry.target.id);
      if (link) link.classList.add('active');
    });
  }, { rootMargin: `-${headerOffset() + 8}px 0px -70% 0px` });

  document.querySelectorAll('.section[id]').forEach((sec) => spy.observe(sec));
}

render(active);
