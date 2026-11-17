(() => {
  'use strict';
  const D = window.PLANMIN_STUDENT_RESULTS;
  const $ = id => document.getElementById(id);
  const status = $('status');
  const P = D && window[D.group + '_PRODUCTS'];
  if (!D || !P || !/^G0[1-5]$/.test(D.group) ||
      D.s11_run_id !== P.S11?.run_id || D.s12_run_id !== P.S12?.run_id ||
      P.S11?.status !== 'VALIDATED' || P.S12?.status !== 'VALIDATED' ||
      D.fields.length !== 26 || D.blocks.length !== D.block_count) {
    status.textContent = 'La consulta no coincide con los modelos verificados. Solicita a Kai revisar esta distribución.';
    status.dataset.ready = 'false';
    return;
  }
  status.textContent = 'Resultados verificados de ' + $('project-name').textContent + '. Puedes consultar las cifras desde esta página.';
  status.dataset.ready = 'true';
  $('generations').textContent = `Generación S11: ${D.s11_run_id} · Generación S12: ${D.s12_run_id}`;
  const columns = new Map(D.block_columns.map((name, index) => [name, index]));
  const blocks = new Map(D.blocks.map(row => [row[0], row]));
  const positions = new Map(D.blocks.map(row => [`${row[1]}:${row[2]}:${row[3]}`, row[0]]));
  const numeric = (value, places) => value === null || value === undefined ? 'Sin estimación / no aplica' :
    new Intl.NumberFormat('es-PE', {minimumFractionDigits: places, maximumFractionDigits: places}).format(value);
  const fieldColumn = {
    'S11.B.CU': 'cu_pct_est', 'S11.B.RHO': 'density_t_m3_est',
    'S11.B.V': 'rock_volume_m3', 'S11.B.T': 'tonnage_t',
    'S11.B.H': 'cu_pct_holes', 'S11.B.MO': 'mo_pct_est',
    'S11.B.AU': 'au_gt_est', 'S12.B.ALLOC': 'allocated_moved_t',
    'S12.B.OPEX': 'total_opex_usd'
  };
  function makeCard(field, value, target) {
    const card = document.createElement('article');
    card.className = 'metric'; card.id = `campo-${field.id}`;
    card.dataset.fieldId = field.id; card.dataset.stage = field.stage;
    const label = document.createElement('span'); label.textContent = field.label;
    const strong = document.createElement('strong'); strong.textContent = numeric(value, field.places);
    const unit = document.createElement('small'); unit.textContent = field.unit;
    card.append(label, strong, unit); target.append(card);
  }
  for (const field of D.fields.filter(f => !f.block))
    makeCard(field, field.value, $(field.stage.toLowerCase() + '-summary'));
  const viewerBase = {};
  for (const stage of ['S11', 'S12']) {
    viewerBase[stage] = `VISOR_${stage}_${D.group}.html`;
    $(stage.toLowerCase() + '-3d').href = viewerBase[stage];
  }
  const blockFields = D.fields.filter(f => Boolean(f.block));
  const shardCache = new Map();
  window.PLANMIN_STUDENT_SHARDS = {};
  function loadShard(i) {
    if (shardCache.has(i)) return shardCache.get(i);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `${D.group.toLowerCase()}_student_blocks/i_${String(i).padStart(3, '0')}.js`;
      script.onload = () => {
        script.remove();
        const rows = window.PLANMIN_STUDENT_SHARDS[i];
        if (!Array.isArray(rows)) { reject(new Error('Bloques no disponibles')); return; }
        resolve(new Map(rows.map(row => [row[0], row])));
        delete window.PLANMIN_STUDENT_SHARDS[i];
      };
      script.onerror = () => { script.remove(); reject(new Error('Bloques no disponibles')); };
      document.head.append(script);
    });
    shardCache.set(i, promise);
    return promise;
  }
  function renderLocator(row) {
    const locator = $('locator'); locator.replaceChildren();
    const [i, j, k] = row.slice(1, 4);
    $('block-position').textContent = `Nivel ${k}; columna este ${i}, columna norte ${j}. Selecciona un vecino para comparar.`;
    for (let dj = 2; dj >= -2; dj--) for (let di = -2; di <= 2; di++) {
      const id = positions.get(`${i + di}:${j + dj}:${k}`);
      const button = document.createElement('button');
      button.type = 'button'; button.disabled = !id;
      button.textContent = id ? `${i + di}, ${j + dj}` : '·';
      button.title = id || 'Fuera de la malla';
      button.setAttribute('aria-label', id ? `Bloque ${id}` : 'Sin bloque');
      if (id === row[0]) button.className = 'active';
      if (id) button.addEventListener('click', () => inspect(id));
      locator.append(button);
    }
  }
  let request = 0;
  async function inspect(id) {
    const ticket = ++request;
    const indexed = blocks.get(id.toUpperCase());
    if (!indexed) { $('block-message').textContent = 'No se encontró ese bloque. Comprueba el identificador o elige una coincidencia.'; return; }
    $('block-message').textContent = 'Consultando el bloque…';
    let row = indexed;
    if (D.sharded) {
      try { row = (await loadShard(indexed[1])).get(indexed[0]); }
      catch { if (ticket === request) $('block-message').textContent = 'No se pudo cargar este bloque. Conserva la carpeta completa.'; return; }
    }
    if (ticket !== request || !row) return;
    $('block-input').value = indexed[0];
    $('block-message').textContent = `Bloque ${indexed[0]} localizado en los modelos verificados S11 y S12.`;
    for (const stage of ['S11', 'S12'])
      $(stage.toLowerCase() + '-3d').href = viewerBase[stage] + '?bloque=' + encodeURIComponent(indexed[0]);
    $('suggestions').replaceChildren();
    for (const stage of ['S11', 'S12']) $(stage.toLowerCase() + '-block').replaceChildren();
    for (const field of blockFields)
      makeCard(field, row[columns.get(fieldColumn[field.id])], $(field.stage.toLowerCase() + '-block'));
    renderLocator(indexed);
    if (location.hash.startsWith('#campo-'))
      document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
    window.PLANMIN_STUDENT_VIEW_READY = true;
  }
  $('block-search').addEventListener('click', () => inspect($('block-input').value.trim()));
  $('block-input').addEventListener('keydown', event => { if (event.key === 'Enter') inspect(event.target.value.trim()); });
  let suggestionTimer;
  $('block-input').addEventListener('input', event => {
    clearTimeout(suggestionTimer);
    const query = event.target.value.trim().toUpperCase();
    const suggestions = $('suggestions'); suggestions.replaceChildren();
    if (query.length < 5 || blocks.has(query)) return;
    suggestionTimer = setTimeout(() => {
      let found = 0;
      for (const id of blocks.keys()) {
        if (!id.includes(query)) continue;
        const button = document.createElement('button'); button.type = 'button'; button.textContent = id;
        button.addEventListener('click', () => inspect(id)); suggestions.append(button);
        if (++found === 6) break;
      }
    }, 120);
  });
  const requested = new URLSearchParams(location.search).get('bloque') || D.example_block;
  inspect(requested);
})();
