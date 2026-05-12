/*
 * dashboard/live_parameters.js — parameter terminal for the live engine (S2).
 *
 * Renders the seven scenario families as a radio group, eight Sobol-ranked
 * parameter rows as sliders (with S1/ST badges that update when the user
 * switches the headline metric), a productive-folding toggle, a scenario
 * preset selector, and the run controls. Talks to:
 *
 *   GET  /scenarios/families   — taxonomy + scenarios per family
 *   GET  /parameter_meta       — eight parameter records (label, tooltip, …)
 *   GET  /sobol_indices?metric — pinned N=2048 indices for one metric
 *   GET  /scenarios            — flat list (used for description hovers)
 *   POST /runs                 — submit { scenario, family, overrides, … }
 *
 * Public API: `window.createParameterPanel(host, { onSubmit, onCancel }) → panel`
 * with `panel.reset()`, `panel.setRunning(bool)`. `getRunConfig()` is invoked
 * by the page's run handler.
 */
(function () {
  'use strict';

  // ---- styles (scoped to the panel container) -----------------------------
  const STYLE = `
    .pt { display: flex; flex-direction: column; gap: 14px; }
    .pt-group { background: var(--panel); border: 1px solid var(--border); border-radius: 4px; padding: 12px 16px; }
    .pt-group-header { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-3); margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
    .pt-hint { font-family: var(--sans); font-size: 11px; color: var(--text-3); text-transform: none; letter-spacing: 0; font-weight: normal; }
    .pt-family-radio { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 6px 14px; }
    .pt-family-radio label { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; color: var(--text-2); cursor: pointer; padding: 4px 0; }
    .pt-family-radio input[type=radio] { margin-top: 2px; accent-color: var(--accent); }
    .pt-family-radio label.active { color: var(--text); }
    .pt-family-radio .pt-family-desc { font-family: var(--serif); font-size: 12px; line-height: 1.4; color: var(--text-3); }
    .pt-row { display: grid; grid-template-columns: 200px 1fr 70px 110px; gap: 12px; align-items: center; padding: 8px 0; border-top: 1px solid var(--border); }
    .pt-row:first-child { border-top: none; }
    .pt-row.coupled { padding-left: 16px; border-left: 2px solid var(--border); margin-left: -2px; }
    .pt-row.inert { opacity: 0.45; }
    .pt-name { font-family: var(--mono); font-size: 12px; color: var(--text); line-height: 1.3; cursor: help; }
    .pt-name .pt-sub { font-family: var(--sans); font-size: 11px; color: var(--text-3); display: block; margin-top: 2px; }
    .pt-slider-cell { display: flex; align-items: center; gap: 8px; }
    .pt-slider-cell input[type=range] { flex: 1; accent-color: var(--accent); }
    .pt-slider-cell .pt-bounds { font-family: var(--mono); font-size: 10px; color: var(--text-3); white-space: nowrap; }
    .pt-value { font-family: var(--mono); font-size: 13px; color: var(--accent); text-align: right; }
    .pt-st { font-family: var(--mono); font-size: 10px; color: var(--text-3); text-align: right; line-height: 1.3; }
    .pt-st .pt-st-s1 { color: var(--text-2); }
    .pt-help-drawer { background: var(--panel-2); border-left: 2px solid var(--accent); padding: 10px 14px; margin: 4px 0 0 0; font-family: var(--serif); font-size: 12px; line-height: 1.5; color: var(--text-2); display: none; }
    .pt-help-drawer.open { display: block; }
    .pt-run-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
    .pt-run-row > div { display: flex; flex-direction: column; gap: 4px; }
    .pt-run-row label { font-size: 10px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.08em; }
    .pt-run-row select, .pt-run-row input { font-family: var(--mono); font-size: 12px; color: var(--text); background: var(--panel); border: 1px solid var(--border); border-radius: 3px; padding: 6px 10px; }
    .pt-run-row .pt-run-actions { flex: 1; flex-direction: row; align-items: stretch; justify-content: flex-end; gap: 8px; }
    .pt-toggle { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 12px; color: var(--text); }
    .pt-toggle input { accent-color: var(--accent); }
    .pt-metric-select { font-family: var(--mono); font-size: 12px; padding: 6px 10px; background: var(--panel); color: var(--text); border: 1px solid var(--border); border-radius: 3px; }
    details.pt-bounds-help { font-family: var(--serif); font-size: 12px; color: var(--text-3); line-height: 1.5; padding: 8px 14px; background: var(--panel-2); border-radius: 3px; }
    details.pt-bounds-help summary { cursor: pointer; color: var(--text-2); font-family: var(--mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
    details.pt-bounds-help[open] summary { margin-bottom: 6px; }
    .pt-preset { width: 100%; }
  `;

  // ---- helpers ------------------------------------------------------------

  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') e.className = v;
      else if (k === 'style') e.style.cssText = v;
      else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
      else if (v != null) e.setAttribute(k, v);
    }
    for (const c of children) {
      if (c == null) continue;
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return e;
  }

  function fmt(value, decimals = 3) {
    if (!Number.isFinite(value)) return '—';
    return value.toFixed(decimals);
  }

  function inferStep(min, max) {
    const span = max - min;
    if (span <= 0.2) return 0.005;
    if (span <= 1) return 0.01;
    if (span <= 5) return 0.05;
    return 0.1;
  }

  // ---- main factory -------------------------------------------------------

  async function createParameterPanel(host, opts = {}) {
    const onSubmit = opts.onSubmit || (() => {});
    const onCancel = opts.onCancel || (() => {});

    // Inject styles once.
    if (!document.querySelector('style[data-pt]')) {
      const style = el('style', { 'data-pt': '1' });
      style.textContent = STYLE;
      document.head.appendChild(style);
    }

    host.innerHTML = '';
    const root = el('div', { class: 'pt' });
    host.appendChild(root);

    // ---- data fetch -------------------------------------------------------
    // /scenarios is best-effort — used only for preset description hovers.
    // If it fails (registration mismatch, server hiccup), the panel still
    // renders without the descriptions.
    const results = await Promise.allSettled([
      fetch('/parameter_meta').then((r) => r.json()),
      fetch('/scenarios/families').then((r) => r.json()),
      fetch('/scenarios').then((r) => r.json()),
    ]);
    if (results[0].status !== 'fulfilled' || results[1].status !== 'fulfilled') {
      host.appendChild(el('p', { style: 'color: var(--red);' },
        'parameter panel could not load — /parameter_meta or /scenarios/families failed'));
      throw new Error('panel init failed');
    }
    const paramMeta = results[0].value;
    const families = results[1].value;
    const scenarios = results[2].status === 'fulfilled' ? results[2].value : [];
    const parameters = paramMeta.parameters;
    const sobolMetrics = paramMeta.sobol_metrics;
    const scenarioByName = {};
    scenarios.forEach((s) => { scenarioByName[s.name] = s; });

    // ---- state ------------------------------------------------------------
    const state = {
      family: families[0].id,
      scenario: families[0].scenarios[0] || 'coasean_paradise',
      metric: sobolMetrics[0],
      paramValues: Object.fromEntries(parameters.map((p) => [p.name, p.default])),
      productiveFolding: false,  // gates base_variance_absorption + max_productive_real_share
      sobolByName: {},            // populated after /sobol_indices fetch
    };

    // ---- panel sections ---------------------------------------------------

    // family selector
    const familyGroup = el('div', { class: 'pt-group' });
    familyGroup.appendChild(el('div', { class: 'pt-group-header' },
      'Scenario family',
      el('span', { class: 'pt-hint' }, 'chosen before run; sets which engine modules are active'),
    ));
    const familyDescBox = el('div', { class: 'pt-family-desc' });
    const familyRadioBox = el('div', { class: 'pt-family-radio' });
    families.forEach((fam) => {
      const input = el('input', { type: 'radio', name: 'pt-family', value: fam.id });
      if (fam.id === state.family) input.checked = true;
      const label = el('label', {}, input, el('span', {}, fam.label));
      input.addEventListener('change', () => {
        state.family = fam.id;
        familyDescBox.textContent = fam.description;
        repopulatePresets();
        familyRadioBox.querySelectorAll('label').forEach((l) => l.classList.remove('active'));
        label.classList.add('active');
      });
      if (fam.id === state.family) label.classList.add('active');
      familyRadioBox.appendChild(label);
    });
    familyGroup.appendChild(familyRadioBox);
    familyDescBox.textContent = families.find((f) => f.id === state.family).description;
    familyGroup.appendChild(familyDescBox);
    root.appendChild(familyGroup);

    // scenario preset
    const presetGroup = el('div', { class: 'pt-group' });
    presetGroup.appendChild(el('div', { class: 'pt-group-header' },
      'Scenario preset',
      el('span', { class: 'pt-hint' }, 'starting point — values load into the sliders below'),
    ));
    const presetSelect = el('select', { class: 'pt-preset' });
    const presetDesc = el('p', { class: 'pt-family-desc', style: 'margin-top: 6px;' });
    presetGroup.appendChild(presetSelect);
    presetGroup.appendChild(presetDesc);
    root.appendChild(presetGroup);

    function repopulatePresets() {
      presetSelect.innerHTML = '';
      const fam = families.find((f) => f.id === state.family);
      fam.scenarios.forEach((name) => {
        if (name.endsWith('_anchored')) return;  // hide anchored variants from primary picker
        const opt = el('option', { value: name }, name);
        presetSelect.appendChild(opt);
      });
      if (fam.scenarios.length > 0) {
        state.scenario = presetSelect.value || fam.scenarios[0];
        presetSelect.value = state.scenario;
        presetDesc.textContent = (scenarioByName[state.scenario] || {}).description || '';
      }
    }
    presetSelect.addEventListener('change', () => {
      state.scenario = presetSelect.value;
      presetDesc.textContent = (scenarioByName[state.scenario] || {}).description || '';
    });
    repopulatePresets();

    // headline metric selector
    const metricGroup = el('div', { class: 'pt-group' });
    const metricHeader = el('div', { class: 'pt-group-header' });
    metricHeader.appendChild(document.createTextNode('Sensitivity metric'));
    metricHeader.appendChild(el('span', { class: 'pt-hint' }, 'drives the S1/ST badge on each slider'));
    metricGroup.appendChild(metricHeader);
    const metricSelect = el('select', { class: 'pt-metric-select' });
    sobolMetrics.forEach((m) => metricSelect.appendChild(el('option', { value: m }, m)));
    metricSelect.value = state.metric;
    metricSelect.addEventListener('change', async () => {
      state.metric = metricSelect.value;
      await refreshSobol();
      paintBadges();
    });
    metricGroup.appendChild(metricSelect);
    root.appendChild(metricGroup);

    // productive-folding toggle (gates two coupled rows)
    const pfGroup = el('div', { class: 'pt-group' });
    const pfToggle = el('input', { type: 'checkbox' });
    const pfLabel = el('label', { class: 'pt-toggle' },
      pfToggle,
      el('span', {}, 'Productive folding'),
      el('span', { class: 'pt-hint' }, 'off ⇒ base_variance_absorption = 0; max_productive_real_share inert'),
    );
    pfGroup.appendChild(pfLabel);
    pfToggle.addEventListener('change', () => {
      state.productiveFolding = pfToggle.checked;
      applyProductiveFoldingCoupling();
    });
    root.appendChild(pfGroup);

    // parameter rows
    const paramGroup = el('div', { class: 'pt-group' });
    paramGroup.appendChild(el('div', { class: 'pt-group-header' },
      'Parameters · ranked by mean |ST|',
      el('span', { class: 'pt-hint' }, 'click name to expand help'),
    ));
    const rowsHost = el('div');
    paramGroup.appendChild(rowsHost);
    root.appendChild(paramGroup);

    const rowControls = {};  // name → { input, valueCell, stCell, row, helpDrawer }

    parameters.forEach((p) => {
      const step = inferStep(p.sobol_min, p.sobol_max);
      const input = el('input', {
        type: 'range',
        min: p.sobol_min,
        max: p.sobol_max,
        step: step,
        value: state.paramValues[p.name],
      });
      const valueCell = el('div', { class: 'pt-value' }, fmt(state.paramValues[p.name]));
      const stCell = el('div', { class: 'pt-st' }, '…');
      const nameCell = el('div', { class: 'pt-name', title: p.tooltip },
        el('span', {}, p.label),
        el('span', { class: 'pt-sub' }, p.name),
      );
      const helpDrawer = el('div', { class: 'pt-help-drawer' }, p.help);
      const row = el('div', { class: 'pt-row', 'data-name': p.name },
        nameCell,
        el('div', { class: 'pt-slider-cell' },
          input,
          el('span', { class: 'pt-bounds' }, `[${p.sobol_min}, ${p.sobol_max}]`),
        ),
        valueCell,
        stCell,
      );
      const wrap = el('div', {});
      wrap.appendChild(row);
      wrap.appendChild(helpDrawer);
      rowsHost.appendChild(wrap);

      // Couple rows visually for the productive-folding pair.
      if (p.name === 'base_variance_absorption' || p.name === 'max_productive_real_share') {
        row.classList.add('coupled');
      }

      input.addEventListener('input', () => {
        const v = Number(input.value);
        state.paramValues[p.name] = v;
        const decimals = step >= 0.1 ? 2 : step >= 0.01 ? 2 : 3;
        valueCell.textContent = fmt(v, decimals);
        if (p.name === 'base_variance_absorption') {
          // Manually moving this slider above 0 implies productive folding on.
          if (v > 0 && !state.productiveFolding) {
            state.productiveFolding = true;
            pfToggle.checked = true;
          }
          applyProductiveFoldingCoupling();
        }
      });

      nameCell.addEventListener('click', () => {
        helpDrawer.classList.toggle('open');
      });

      rowControls[p.name] = { input, valueCell, stCell, row, helpDrawer, meta: p };
    });

    // run controls row
    const runGroup = el('div', { class: 'pt-group pt-run-row' });
    const scaleSel = el('select', {},
      el('option', { value: 'small' }, 'small (88K)'),
      el('option', { value: 'medium' }, 'medium (880K)'),
      el('option', { value: 'large' }, 'large (8.8M)'),
    );
    scaleSel.value = 'small';
    const nStepsInp = el('input', { type: 'number', min: '1', max: '500', value: '60' });
    const seedInp = el('input', { type: 'number', value: '0' });
    const runBtn = el('button', { class: '' }, 'Run');
    const cancelBtn = el('button', { class: 'ghost' }, 'Cancel');
    cancelBtn.disabled = true;
    runGroup.appendChild(el('div', {}, el('label', {}, 'Scale'), scaleSel));
    runGroup.appendChild(el('div', {}, el('label', {}, 'Steps'), nStepsInp));
    runGroup.appendChild(el('div', {}, el('label', {}, 'Seed'), seedInp));
    runGroup.appendChild(el('div', { class: 'pt-run-actions' }, runBtn, cancelBtn));
    root.appendChild(runGroup);

    // "about the bounds" expander
    const boundsHelp = el('details', { class: 'pt-bounds-help' },
      el('summary', {}, 'About the slider bounds'),
      el('p', {}, 'Each slider is clamped to the N=2048 Sobol sampling box. The S1/ST values on each row are valid only inside that box. Extending the bounds (advanced mode) strips the sensitivity anchor.'),
    );
    root.appendChild(boundsHelp);

    // ---- behaviour --------------------------------------------------------

    function applyProductiveFoldingCoupling() {
      const bva = rowControls['base_variance_absorption'];
      const mprs = rowControls['max_productive_real_share'];
      if (!state.productiveFolding) {
        // Force base_variance_absorption to 0 and grey out both.
        bva.input.value = 0;
        bva.valueCell.textContent = fmt(0);
        state.paramValues['base_variance_absorption'] = 0;
        bva.row.classList.add('inert');
        mprs.row.classList.add('inert');
        mprs.input.disabled = true;
      } else {
        if (Number(bva.input.value) === 0) {
          // Lift to default when toggle flips on if user hasn't already moved it.
          bva.input.value = bva.meta.default || 0.2;
          bva.valueCell.textContent = fmt(Number(bva.input.value));
          state.paramValues['base_variance_absorption'] = Number(bva.input.value);
        }
        bva.row.classList.remove('inert');
        mprs.row.classList.remove('inert');
        mprs.input.disabled = false;
      }
    }
    applyProductiveFoldingCoupling();

    async function refreshSobol() {
      const r = await fetch(`/sobol_indices?metric=${encodeURIComponent(state.metric)}`);
      if (!r.ok) {
        state.sobolByName = {};
        return;
      }
      const data = await r.json();
      const map = {};
      data.parameter_names.forEach((name, i) => {
        map[name] = { S1: data.S1[i], ST: data.ST[i] };
      });
      state.sobolByName = map;
    }

    function paintBadges() {
      parameters.forEach((p) => {
        const ctl = rowControls[p.name];
        const idx = state.sobolByName[p.name];
        if (!idx) { ctl.stCell.innerHTML = '<span class="pt-st-s1">—</span>'; return; }
        const s1 = idx.S1;
        const st = idx.ST;
        ctl.stCell.innerHTML = `<span class="pt-st-s1">S1 ${fmt(s1, 2)}</span><br>ST ${fmt(st, 2)}`;
      });
    }

    await refreshSobol();
    paintBadges();

    // ---- public API -------------------------------------------------------

    function buildOverrides() {
      // Only emit overrides for sliders the user has moved off the default,
      // *plus* anything affected by the productive-folding toggle.
      const overrides = {};
      parameters.forEach((p) => {
        let v = state.paramValues[p.name];
        if (p.name === 'base_variance_absorption' && !state.productiveFolding) v = 0;
        // Always send so the server's apply step is explicit even when the
        // slider matches the slider default (scenario defaults differ).
        overrides[p.name] = v;
      });
      return overrides;
    }

    function getRunConfig() {
      return {
        scenario: state.scenario,
        family: state.family,
        overrides: buildOverrides(),
        n_steps: parseInt(nStepsInp.value, 10) || 0,
        scale: scaleSel.value,
        seed: parseInt(seedInp.value, 10),
      };
    }

    runBtn.addEventListener('click', () => onSubmit(getRunConfig()));
    cancelBtn.addEventListener('click', () => onCancel());

    function setRunning(running) {
      runBtn.disabled = running;
      cancelBtn.disabled = !running;
      scaleSel.disabled = running;
      nStepsInp.disabled = running;
      seedInp.disabled = running;
      presetSelect.disabled = running;
      metricSelect.disabled = running;
      pfToggle.disabled = running;
      familyRadioBox.querySelectorAll('input').forEach((r) => { r.disabled = running; });
      Object.values(rowControls).forEach((ctl) => { ctl.input.disabled = running || (state.productiveFolding === false && ctl.meta.name === 'max_productive_real_share'); });
    }

    function reset() {
      // Restore param defaults; leave family/scenario alone.
      parameters.forEach((p) => {
        state.paramValues[p.name] = p.default;
        rowControls[p.name].input.value = p.default;
        rowControls[p.name].valueCell.textContent = fmt(p.default);
      });
      state.productiveFolding = false;
      pfToggle.checked = false;
      applyProductiveFoldingCoupling();
    }

    return { getRunConfig, setRunning, reset };
  }

  window.createParameterPanel = createParameterPanel;
})();
