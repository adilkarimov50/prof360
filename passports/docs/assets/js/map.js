/* Карта объектов: базовый и детальный режим (Чунджа), маршруты патрулирования. */

const PRECISION_LABELS = {
  point: 'точная привязка к объекту',
  street: 'координата участка улицы',
  area: 'центр территории',
};

let active = currentId();
let hidden = new Set();
let hiddenCrime = new Set();
let hiddenLayers = new Set(['routes']);
let selectedId = null;
let map = null;
let layer = null;
let routeLayer = null;
let resourceLayer = null;
let zoneLayer = null;
let establishmentLayer = null;
let markers = new Map();

document.getElementById('chrome-top').innerHTML = renderTopbar('map', active);
document.getElementById('chrome-bottom').innerHTML = renderFooter();

function isDetailed() {
  return GEO[active]?.mapMode === 'detailed';
}

function geoPoints() {
  const geo = GEO[active];
  if (isDetailed()) {
    return (geo.points || []).filter((p) => p.lat != null && p.lon != null);
  }
  return geo.points || [];
}

function markerIcon(point) {
  const color = isDetailed() && point.crimeCat
    ? GEO[active].crimeCategories[point.crimeCat]?.color
    : CATEGORY_COLORS[point.category];
  const size = point.count ? Math.round(26 + Math.sqrt(point.count) * 2.4) : 20;
  const label = isDetailed() ? (point.rank ?? '') : (point.count ?? '');
  return L.divIcon({
    className: '',
    html: `<div class="marker-pin${selectedId === point.id ? ' marker-pin--sel' : ''}" style="width:${size}px;height:${size}px;background:${color}">${label}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function popupHtml(point) {
  if (isDetailed()) {
    const cat = GEO[active].crimeCategories[point.crimeCat];
    return `
      <h4>${esc(point.name)}</h4>
      <div>${esc(cat?.label || point.crimes)} · <span class="pp-count">${fmt(point.count)} фактов</span></div>
      ${point.time ? `<div style="margin-top:6px"><b>Время:</b> ${esc(point.time)}</div>` : ''}
      ${point.victims ? `<div><b>Потерпевшие:</b> ${esc(point.victims)}</div>` : ''}
      <div class="pp-note">${esc(point.note)}</div>`;
  }
  return `
    <h4>${esc(point.name)}</h4>
    <div>${esc(CATEGORY_LABELS[point.category])}${
      point.count ? ` · <span class="pp-count">${fmt(point.count)} фактов</span>` : ''}</div>
    ${point.crimes ? `<div style="margin-top:6px">${esc(point.crimes)}</div>` : ''}
    <div class="pp-note">${esc(point.note)}</div>
    <div class="pp-note" style="font-style:italic">Привязка: ${PRECISION_LABELS[point.precision] || point.precision}</div>`;
}

function visiblePoints() {
  const points = geoPoints();
  if (isDetailed()) {
    return points.filter((p) => !hiddenCrime.has(p.crimeCat));
  }
  return points.filter((p) => !hidden.has(p.category));
}

function allRegistryPoints() {
  const geo = GEO[active];
  if (!isDetailed()) return visiblePoints();
  return (geo.points || []).filter((p) => !hiddenCrime.has(p.crimeCat));
}

function drawDetailCard(point) {
  const wrap = document.getElementById('detail-card');
  if (!wrap || !point) {
    if (wrap) wrap.innerHTML = '';
    return;
  }
  const cat = GEO[active].crimeCategories[point.crimeCat];
  wrap.innerHTML = `
    <div class="detail-card">
      <h3>${point.rank}. ${esc(point.name)}</h3>
      <div class="detail-row"><span>Вид</span><span>${esc(cat?.label || point.crimes)}</span></div>
      <div class="detail-row"><span>Преступлений</span><span>${fmt(point.count)}</span></div>
      <div class="detail-row"><span>Время</span><span>${esc(point.time || '—')}</span></div>
      <div class="detail-row"><span>Потерпевшие</span><span>${esc(point.victims || '—')}</span></div>
      <div class="detail-row"><span>Координаты</span><span>${point.lat != null ? `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}` : 'не локализовано'}</span></div>
      <div class="detail-measures"><b>Требуемые меры</b><p>${esc(point.measures)}</p></div>
      <div class="detail-theory">Теоретическое основание: ${esc(point.theory || '—')}</div>
    </div>`;
}

function selectPoint(point) {
  selectedId = point?.id || null;
  drawDetailCard(point);
  drawSide();
  if (point?.lat != null) {
    map.flyTo([point.lat, point.lon], 16, { duration: 0.7 });
    markers.get(point.id)?.openPopup();
  }
}

function drawRoutes() {
  if (routeLayer) routeLayer.remove();
  routeLayer = L.layerGroup();
  const routes = GEO[active].patrolRoutes || [];
  if (hiddenLayers.has('routes')) {
    routeLayer.addTo(map);
    return;
  }
  routes.forEach((route) => {
    const line = L.polyline(route.coords, {
      color: route.color,
      weight: route.type === 'auto' ? 5 : 3,
      opacity: 0.85,
      dashArray: route.type === 'foot' ? '8 6' : null,
    }).bindPopup(`<b>${esc(route.name)}</b><br>${esc(route.schedule || '')}<br><i>${route.type === 'auto' ? 'автопатруль' : 'пеший патруль'}</i>`);
    routeLayer.addLayer(line);
    (route.stops || []).forEach((stop, i) => {
      const stopMarker = L.circleMarker([stop.lat, stop.lon], {
        radius: 6,
        color: route.color,
        weight: 2,
        fillColor: '#fff',
        fillOpacity: 1,
      }).bindPopup(`<b>${esc(stop.name)}</b>${stop.time ? `<br>${esc(stop.time)}` : ''}<br><small>${esc(route.name)}</small>`);
      routeLayer.addLayer(stopMarker);
    });
    if (route.coords.length) {
      const mid = route.coords[Math.floor(route.coords.length / 2)];
      const label = L.marker(mid, {
        interactive: false,
        icon: L.divIcon({
          className: 'route-label-wrap',
          html: `<div class="route-label" style="border-color:${route.color};color:${route.color}">${esc(route.name)}</div>`,
          iconSize: [0, 0],
        }),
      });
      routeLayer.addLayer(label);
    }
  });
  routeLayer.addTo(map);
}

function drawResources() {
  if (resourceLayer) resourceLayer.remove();
  resourceLayer = L.layerGroup();
  if (hiddenLayers.has('resources')) {
    resourceLayer.addTo(map);
    return;
  }
  (GEO[active].resources || []).forEach((res) => {
    const m = L.marker([res.lat, res.lon], {
      icon: L.divIcon({
        className: '',
        html: '<div class="marker-res">●</div>',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      }),
    }).bindPopup(`<b>${esc(res.name)}</b><br>${esc(res.note)}`);
    resourceLayer.addLayer(m);
  });
  resourceLayer.addTo(map);
}

function drawZones() {
  if (zoneLayer) zoneLayer.remove();
  zoneLayer = L.layerGroup();
  if (hiddenLayers.has('zones')) {
    zoneLayer.addTo(map);
    return;
  }
  visiblePoints().forEach((point) => {
    const color = isDetailed()
      ? GEO[active].crimeCategories[point.crimeCat]?.color
      : CATEGORY_COLORS[point.category];
    zoneLayer.addLayer(L.circle([point.lat, point.lon], {
      radius: 40 + (point.count || 1) * 45,
      color,
      weight: 1,
      fillColor: color,
      fillOpacity: 0.1,
    }));
  });
  zoneLayer.addTo(map);
}

function drawEstablishments() {
  if (establishmentLayer) establishmentLayer.remove();
  establishmentLayer = L.layerGroup();
  if (!isDetailed() || hiddenLayers.has('establishments')) {
    establishmentLayer.addTo(map);
    return;
  }
  (GEO[active].establishments || []).filter((e) => e.lat != null).forEach((est) => {
    establishmentLayer.addLayer(L.marker([est.lat, est.lon], {
      icon: L.divIcon({
        className: '',
        html: '<div class="marker-est">◆</div>',
        iconSize: [16, 16],
        iconAnchor: [8, 8],
      }),
    }).bindPopup(`<b>${esc(est.name)}</b><br>${esc(est.note)}`));
  });
  establishmentLayer.addTo(map);
}

function drawMap() {
  const geo = GEO[active];
  if (!map) {
    map = L.map('map', { scrollWheelZoom: false }).setView(geo.center, geo.zoom);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; участники <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
  }
  if (layer) layer.remove();
  markers.clear();

  const points = visiblePoints();
  layer = L.layerGroup(points.map((point) => {
    const marker = L.marker([point.lat, point.lon], { icon: markerIcon(point), title: point.name })
      .bindPopup(popupHtml(point))
      .on('click', () => selectPoint(point));
    markers.set(point.id, marker);
    return marker;
  })).addTo(map);

  drawRoutes();
  if (isDetailed()) {
    drawResources();
    drawZones();
    drawEstablishments();
  }

  const bounds = [];
  points.forEach((p) => bounds.push([p.lat, p.lon]));
  (geo.patrolRoutes || []).forEach((r) => r.coords.forEach((c) => bounds.push(c)));
  if (bounds.length) {
    map.fitBounds(L.latLngBounds(bounds).pad(0.18));
  } else {
    map.setView(geo.center, geo.zoom);
  }
}

function drawFilters() {
  const geo = GEO[active];
  const filters = document.getElementById('filters');

  if (isDetailed()) {
    const cats = geo.crimeCategories;
    filters.innerHTML = Object.entries(cats).map(([key, val]) => {
      const count = (geo.points || []).filter((p) => p.crimeCat === key).reduce((s, p) => s + (p.count || 0), 0);
      return `
        <button type="button" data-crime="${key}" aria-pressed="${!hiddenCrime.has(key)}">
          <i style="background:${val.color}"></i>${esc(val.label)} · ${count}
        </button>`;
    }).join('');

    filters.innerHTML += `
      <span class="filters__sep"></span>
      <button type="button" data-layer="routes" aria-pressed="${!hiddenLayers.has('routes')}">
        <i style="background:#cf3f3f"></i>Маршруты патрулирования
      </button>
      <button type="button" data-layer="resources" aria-pressed="${!hiddenLayers.has('resources')}">
        <i style="background:#1F6B70"></i>Объекты профилактического ресурса
      </button>
      <button type="button" data-layer="zones" aria-pressed="${!hiddenLayers.has('zones')}">
        <i style="background:#B33F26"></i>Зоны концентрации
      </button>
      <button type="button" data-layer="establishments" aria-pressed="${!hiddenLayers.has('establishments')}">
        <i style="background:#7a4fb5"></i>Заведения и объекты
      </button>`;

    filters.querySelectorAll('[data-crime]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const key = btn.dataset.crime;
        if (hiddenCrime.has(key)) hiddenCrime.delete(key); else hiddenCrime.add(key);
        btn.setAttribute('aria-pressed', String(!hiddenCrime.has(key)));
        drawMap();
        drawSide();
      });
    });
  } else {
    const counts = {};
    (geo.points || []).forEach((p) => { counts[p.category] = (counts[p.category] || 0) + 1; });
    filters.innerHTML = Object.keys(counts).map((cat) => `
      <button type="button" data-cat="${cat}" aria-pressed="${!hidden.has(cat)}">
        <i style="background:${CATEGORY_COLORS[cat]}"></i>${esc(CATEGORY_LABELS[cat])} · ${counts[cat]}
      </button>`).join('');

    if ((geo.patrolRoutes || []).length) {
      filters.innerHTML += `
        <span class="filters__sep"></span>
        <button type="button" data-layer="routes" aria-pressed="${!hiddenLayers.has('routes')}">
          <i style="background:#cf3f3f"></i>Маршруты патрулирования · ${geo.patrolRoutes.length}
        </button>`;
    }

    filters.querySelectorAll('[data-cat]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const cat = btn.dataset.cat;
        if (hidden.has(cat)) hidden.delete(cat); else hidden.add(cat);
        btn.setAttribute('aria-pressed', String(!hidden.has(cat)));
        drawMap();
        drawSide();
      });
    });
  }

  filters.querySelectorAll('[data-layer]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.layer;
      if (hiddenLayers.has(key)) hiddenLayers.delete(key); else hiddenLayers.add(key);
      btn.setAttribute('aria-pressed', String(!hiddenLayers.has(key)));
      drawMap();
    });
  });
}

function drawSide() {
  const geo = GEO[active];
  const side = document.getElementById('side');

  if (isDetailed()) {
    const points = [...allRegistryPoints()].sort((a, b) => (b.count || 0) - (a.count || 0) || (a.rank || 0) - (b.rank || 0));
    side.innerHTML = points.map((point) => {
      const cat = geo.crimeCategories[point.crimeCat];
      const geoTag = point.lat != null
        ? (point.exact ? '' : '<span class="place__tag">ориентир</span>')
        : '<span class="place__tag place__tag--muted">без координат</span>';
      return `
        <button class="place${selectedId === point.id ? ' place--on' : ''}" type="button" data-id="${point.id}">
          <div class="place__top">
            <span class="place__dot" style="background:${cat?.color}">${point.rank || ''}</span>
            <span class="place__name">${esc(point.name)}</span>
            ${geoTag}
            <span class="place__count">${fmt(point.count)}</span>
          </div>
          <p class="place__meta">${esc(cat?.label || point.crimes)}</p>
        </button>`;
    }).join('') || '<div class="card">Все категории скрыты фильтром.</div>';
  } else {
    const points = [...visiblePoints()].sort((a, b) => (b.count || 0) - (a.count || 0));
    side.innerHTML = points.map((point) => `
      <button class="place" type="button" data-id="${point.id}">
        <div class="place__top">
          <span class="place__dot" style="background:${CATEGORY_COLORS[point.category]}"></span>
          <span class="place__name">${esc(point.name)}</span>
          ${point.count ? `<span class="place__count">${fmt(point.count)}</span>` : ''}
        </div>
        <p class="place__meta">${esc(point.crimes || CATEGORY_LABELS[point.category])}</p>
      </button>`).join('') || '<div class="card">Все категории скрыты фильтром.</div>';
  }

  side.querySelectorAll('.place').forEach((btn) => {
    btn.addEventListener('click', () => {
      const list = isDetailed() ? geo.points : geo.points;
      const point = list.find((p) => p.id === btn.dataset.id);
      selectPoint(point);
    });
  });

  if (isDetailed() && (geo.patrolRoutes || []).length) {
    side.innerHTML += `
      <div class="card" style="margin-top:8px">
        <div class="card__title">Маршруты патрулирования</div>
        ${geo.patrolRoutes.map((r) => `
          <div class="route-item">
            <span class="route-item__dot" style="background:${r.color}"></span>
            <div>
              <b>${esc(r.name)}</b>
              <div class="route-item__meta">${esc(r.schedule || '')} · ${r.type === 'auto' ? 'авто' : 'пеший'}</div>
            </div>
          </div>`).join('')}
      </div>`;
  }
}

function drawUnlocated() {
  const items = GEO[active].unlocated || [];
  document.getElementById('unlocated-wrap').style.display = items.length ? '' : 'none';
  document.getElementById('unlocated').innerHTML = items.map((item) => `
    <div class="card">
      <div class="card__title">${esc(item.name)}</div>
      <p style="margin:0;color:var(--muted);font-size:14.5px">${esc(item.detail)}</p>
    </div>`).join('');
}

function render(id) {
  active = id;
  hidden = new Set();
  hiddenCrime = new Set();
  hiddenLayers = new Set(['resources']);
  selectedId = null;
  history.replaceState(null, '', `?id=${id}`);
  document.getElementById('chrome-top').innerHTML = renderTopbar('map', id);
  document.getElementById('m-switch').innerHTML = renderSwitch(id, render);

  const detailWrap = document.getElementById('detail-card');
  if (detailWrap) detailWrap.innerHTML = '';

  drawFilters();
  drawMap();
  drawSide();
  drawUnlocated();
}

render(active);
