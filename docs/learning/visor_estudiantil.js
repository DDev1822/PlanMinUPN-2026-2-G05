(() => {
  'use strict';
  const group = document.documentElement.dataset.group;
  const detail = document.getElementById('block-detail');
  const labels = {
    block_id:'Identificador del bloque',
    cu_pct_est:'Cu estimado (%)', density_t_m3_est:'Densidad estimada (t/m³)',
    rock_volume_m3:'Volumen de roca (m³)', tonnage_t:'Tonelaje del bloque (t)',
    cu_pct_holes:'Sondajes usados para Cu', mo_pct_est:'Mo estimado (%)',
    au_gt_est:'Au estimado (g/t)', candidate_class:'Clase candidata',
    scenario_A_allocated_t:'A: movimiento asignado (t)',
    scenario_A_opex_usd:'A: OPEX asignado (USD)'
  };
  const friendly = new Set(Object.values(labels));
  const values = {ORE_CANDIDATE:'Mineral candidato', WASTE_CANDIDATE:'Desmonte candidato',
    UNCLASSIFIED:'Sin clasificar', NOT_ASSIGNED:'Sin clasificación profesional',
    ROCK:'Roca', AIR:'Aire', PARTIAL:'Parcial', UNASSIGNED:'Sin asignar'};
  function rename() {
    for (const th of detail.querySelectorAll('th')) {
      if (labels[th.textContent]) th.textContent = labels[th.textContent];
      else if (!friendly.has(th.textContent)) th.closest('tr')?.remove();
    }
    for (const td of detail.querySelectorAll('td'))
      if (values[td.textContent]) td.textContent = values[td.textContent];
  }
  new MutationObserver(rename).observe(detail, {childList:true, subtree:true});
  rename();
  for (const option of document.querySelectorAll('#class-filter option'))
    if (values[option.textContent]) option.textContent = values[option.textContent];
  const count = document.getElementById('drawing-count');
  const renameCount = () => {
    if (count.textContent.includes('filas en el CSV completo'))
      count.textContent = count.textContent.replace('filas en el CSV completo', 'bloques en el modelo completo');
  };
  if (count) { new MutationObserver(renameCount).observe(count, {childList:true}); renameCount(); }
  const id = new URLSearchParams(location.search).get('bloque');
  if (id && id.startsWith(group + '-')) {
    let deepLinked = false;
    const link = () => {
      if (deepLinked || !detail.querySelector('table')) return;
      deepLinked = true;
      document.getElementById('block-id').value = id;
      document.getElementById('inspect').click();
    };
    new MutationObserver(link).observe(detail, {childList:true});
    link();
  }
  window.PLANMIN_STUDENT_3D_READY = true;
})();
