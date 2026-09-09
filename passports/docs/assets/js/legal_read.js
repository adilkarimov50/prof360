(function () {
  const cat = window.LEGAL_CATALOG;
  const params = new URLSearchParams(location.search);
  const docId = params.get('id');
  const prefix = (typeof sitePrefix === 'function') ? sitePrefix() : '';

  const titleEl = document.getElementById('legal-read-title');
  const bodyEl = document.getElementById('legal-read-body');
  const dlEl = document.getElementById('legal-read-dl');
  const adiletEl = document.getElementById('legal-read-adilet');
  const metaEl = document.getElementById('legal-read-meta');

  if (!cat || !docId) {
    if (bodyEl) bodyEl.innerHTML = '<p class="legal-read-error">Не указан документ. <a href="prokuror_zakon.html">Вернуться в библиотеку</a></p>';
    return;
  }

  const act = cat.acts.find((a) => a.doc_id === docId);
  if (!act) {
    if (bodyEl) bodyEl.innerHTML = '<p class="legal-read-error">Документ не найден в каталоге.</p>';
    return;
  }

  document.title = act.title + ' · нормативная библиотека';
  if (titleEl) titleEl.textContent = act.title;
  if (metaEl) metaEl.textContent = `${act.act_type} № ${act.number}`;
  if (dlEl) {
    dlEl.href = prefix + act.txt_url;
    dlEl.setAttribute('download', act.doc_id + '.txt');
  }
  if (adiletEl) adiletEl.href = act.adilet_url;

  fetch(prefix + act.txt_url)
    .then((r) => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.text();
    })
    .then((text) => {
      if (bodyEl) bodyEl.textContent = text;
    })
    .catch((err) => {
      if (bodyEl) {
        bodyEl.innerHTML = `<p class="legal-read-error">Не удалось загрузить текст (${esc(String(err.message))}).
          <a href="${esc(act.adilet_url)}" target="_blank" rel="noopener">Открыть на adilet.zan.kz</a></p>`;
      }
    });

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
})();
