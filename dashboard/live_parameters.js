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
    .pt-family-pills { display: flex; flex-wrap: wrap; gap: 6px; }
    .pt-family-pill { padding: 6px 14px; border: 1px solid var(--border); border-radius: 20px; cursor: pointer; font-family: var(--mono); font-size: 11px; color: var(--text-2); background: transparent; user-select: none; transition: background 80ms, color 80ms, border-color 80ms; }
    .pt-family-pill:hover { color: var(--text); border-color: var(--text-3); }
    .pt-family-pill.active { background: var(--accent); color: #1a1208; border-color: var(--accent); font-weight: 600; }
    .pt-family-active-desc { font-family: var(--serif); font-size: 12px; color: var(--text-2); margin-top: 10px; line-height: 1.5; font-style: italic; }

    .pt-row { display: grid; grid-template-columns: 200px 1fr 70px 110px; gap: 12px; align-items: center; padding: 10px 0; border-top: 1px solid var(--border); position: relative; }
    .pt-row:first-child { border-top: none; }
    .pt-row.tier-1 { padding-left: 10px; border-left: 3px solid var(--accent); margin-left: -10px; }
    .pt-row.tier-1 .pt-name > span:first-child { font-size: 13px; color: var(--text); font-weight: 500; }
    .pt-row.tier-2 .pt-name > span:first-child { font-size: 12px; color: var(--text-2); }
    .pt-row.coupled { padding-left: 24px; }
    .pt-row.coupled::before { content: '↳'; position: absolute; left: 6px; color: var(--text-3); font-family: var(--mono); }
    .pt-row.inert { opacity: 0.45; }

    details.pt-more { margin-top: 4px; }
    details.pt-more > summary { cursor: pointer; padding: 12px 0 8px; color: var(--text-3); font-family: var(--mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; border-top: 1px dashed var(--border); list-style: none; }
    details.pt-more > summary::-webkit-details-marker { display: none; }
    details.pt-more > summary::before { content: '▸ '; color: var(--text-3); }
    details.pt-more[open] > summary { color: var(--accent); border-top-color: var(--accent); }
    details.pt-more[open] > summary::before { content: '▾ '; color: var(--accent); }
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
    .pt-alpha-mode-btn { display: block; width: 100%; padding: 8px 12px; margin-top: 8px; background: var(--panel-2); color: var(--text-2); border: 1px solid var(--border); border-radius: 3px; cursor: pointer; font-family: var(--mono); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; transition: color 80ms, border-color 80ms, background 80ms; }
    .pt-alpha-mode-btn:hover { color: var(--text); border-color: var(--text-3); }
    .pt-alpha-mode-btn.active { background: var(--accent); color: #1a1208; border-color: var(--accent); font-weight: 600; }
    .pt-schedule-wrap { padding: 12px 0 4px; }
    .pt-schedule-svg { width: 100%; height: 110px; background: var(--panel-2); border: 1px solid var(--border); border-radius: 3px; cursor: crosshair; }
    .pt-schedule-svg .grid { stroke: var(--border); stroke-width: 1; }
    .pt-schedule-svg .curve { stroke: var(--accent); stroke-width: 2; fill: none; }
    .pt-schedule-svg .pt-point { fill: var(--accent); stroke: var(--bg); stroke-width: 2; cursor: ns-resize; }
    .pt-schedule-svg .pt-point:hover { fill: var(--text); }
    .pt-schedule-svg .axis-label { fill: var(--text-3); font-family: var(--mono); font-size: 10px; }
    .pt-schedule-hint { font-size: 11px; color: var(--text-3); margin-top: 4px; font-family: var(--sans); }
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
      alphaMode: 'constant',      // 'constant' | 'schedule'
      // Four fractional control points along the run, y ∈ [0.05, 0.95].
      // Default: flat at the α slider's value.
      alphaSchedulePoints: [
        { x: 0.0, y: 0.5 },
        { x: 1 / 3, y: 0.5 },
        { x: 2 / 3, y: 0.5 },
        { x: 1.0, y: 0.5 },
      ],
    };

    // ---- panel sections ---------------------------------------------------

    // family selector — horizontal pills, with the active family's
    // description shown as a single line below the pill row.
    const FAMILY_SHORT_LABELS = {
      alpha_baseline: 'Baseline',
      demand_intermediation: 'Demand',
      dynamic_law: 'Dynamic law',
      pigouvian: 'Pigouvian',
      emergent_strategy: 'Emergent',
      mission_economy: 'Mission',
      norms_layer: 'Norms',
    };
    const familyGroup = el('div', { class: 'pt-group' });
    familyGroup.appendChild(el('div', { class: 'pt-group-header' },
      'Scenario family',
      el('span', { class: 'pt-hint' }, 'chosen before run; sets which engine modules are active'),
    ));
    const familyPillRow = el('div', { class: 'pt-family-pills' });
    const familyActiveDesc = el('div', { class: 'pt-family-active-desc' });
    const pillByFamily = {};
    families.forEach((fam) => {
      const pill = el('button', { class: 'pt-family-pill', type: 'button' },
        FAMILY_SHORT_LABELS[fam.id] || fam.label,
      );
      pill.title = fam.label;
      if (fam.id === state.family) pill.classList.add('active');
      pill.addEventListener('click', () => {
        state.family = fam.id;
        Object.values(pillByFamily).forEach((p) => p.classList.remove('active'));
        pill.classList.add('active');
        familyActiveDesc.textContent = fam.description;
        repopulatePresets();
      });
      familyPillRow.appendChild(pill);
      pillByFamily[fam.id] = pill;
    });
    familyGroup.appendChild(familyPillRow);
    familyActiveDesc.textContent = families.find((f) => f.id === state.family).description;
    familyGroup.appendChild(familyActiveDesc);
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

    // headline metric selector — human labels for the cryptic engine names.
    const METRIC_LABELS = {
      log_exo_baroque_index: 'Exo-baroque index (log)',
      real_per_capita_welfare: 'Real welfare per capita',
      gini_wealth_change_abs: 'Wealth Gini change |Δ|',
      log_exo_baroque_authentic: 'Authentic EBI (log)',
      real_welfare_authentic_cumulative: 'Authentic welfare, cumulative',
      productive_welfare_yield: 'Productive welfare yield',
    };
    const metricGroup = el('div', { class: 'pt-group' });
    const metricHeader = el('div', { class: 'pt-group-header' });
    metricHeader.appendChild(document.createTextNode('Sensitivity metric'));
    metricHeader.appendChild(el('span', { class: 'pt-hint' }, 'drives the S1/ST badge on each slider'));
    metricGroup.appendChild(metricHeader);
    const metricSelect = el('select', { class: 'pt-metric-select' });
    sobolMetrics.forEach((m) => {
      const label = METRIC_LABELS[m] || m;
      metricSelect.appendChild(el('option', { value: m }, label));
    });
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

    // Schedule editor constants — must be initialised BEFORE the
    // parameter loop because `buildScheduleEditor` (called during the
    // α iteration) reads them. Function declarations hoist; `const`
    // declarations don't, so leaving these below the loop puts the
    // reads in the temporal dead zone and kills the loop after α.
    const SCHED_W = 380;
    const SCHED_H = 100;
    const SCHED_PAD_X = 8;
    const SCHED_PAD_Y = 10;
    const SCHED_Y_MIN = 0.05;
    const SCHED_Y_MAX = 0.95;
    let scheduleSvg = null;
    let schedulePathEl = null;
    let schedulePointEls = [];

    // parameter rows — Tier-1 rendered visibly, Tier-2 collapsed in a
    // <details> expander so the panel doesn't tower over the rest of
    // the page on first load.
    const paramGroup = el('div', { class: 'pt-group' });
    paramGroup.appendChild(el('div', { class: 'pt-group-header' },
      'Parameters · ranked by mean |ST|',
      el('span', { class: 'pt-hint' }, 'click name to expand help'),
    ));
    const tier1Host = el('div');
    const tier2Details = el('details', { class: 'pt-more' });
    const tier2Summary = el('summary', {}, 'more parameters (Tier 2 — lower sensitivity)');
    const tier2Host = el('div');
    tier2Details.appendChild(tier2Summary);
    tier2Details.appendChild(tier2Host);
    paramGroup.appendChild(tier1Host);
    paramGroup.appendChild(tier2Details);
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
      // Tier class for visual elevation: Tier-1 gets an accent
      // border-left and a heavier label; Tier-2 sits in the expander.
      row.classList.add(p.tier === 1 ? 'tier-1' : 'tier-2');
      const wrap = el('div', {});
      wrap.appendChild(row);
      wrap.appendChild(helpDrawer);
      (p.tier === 1 ? tier1Host : tier2Host).appendChild(wrap);

      // Couple rows visually for the productive-folding pair (a Tier-1
      // and a Tier-2 — the coupling glyph reads in both hosts).
      if (p.name === 'base_variance_absorption' || p.name === 'max_productive_real_share') {
        row.classList.add('coupled');
      }

      // α gets a constant/schedule mode toggle and an inline SVG curve
      // editor. The toggle is rendered as a full-width button under the
      // row so it reads as a *primary* affordance, not a footnote on
      // the slider cell. The schedule editor is built once and hidden
      // until mode flips.
      let scheduleWrap = null;
      if (p.name === 'alpha') {
        const modeBtn = el('button', { class: 'pt-alpha-mode-btn', type: 'button' },
          'Schedule α(t) over time →',
        );
        wrap.appendChild(modeBtn);
        scheduleWrap = el('div', { class: 'pt-schedule-wrap', style: 'display: none;' });
        wrap.appendChild(scheduleWrap);
        buildScheduleEditor(scheduleWrap);
        modeBtn.addEventListener('click', () => {
          if (state.alphaMode === 'constant') {
            state.alphaMode = 'schedule';
            modeBtn.classList.add('active');
            modeBtn.textContent = '← Use constant α';
            input.style.display = 'none';
            row.querySelector('.pt-bounds').style.display = 'none';
            valueCell.style.display = 'none';
            scheduleWrap.style.display = '';
            // Seed schedule with the current slider value if untouched.
            const sliderVal = state.paramValues['alpha'];
            if (state.alphaSchedulePoints.every((q) => q.y === 0.5)) {
              state.alphaSchedulePoints.forEach((q) => { q.y = sliderVal; });
              redrawSchedule();
            }
          } else {
            state.alphaMode = 'constant';
            modeBtn.classList.remove('active');
            modeBtn.textContent = 'Schedule α(t) over time →';
            input.style.display = '';
            row.querySelector('.pt-bounds').style.display = '';
            valueCell.style.display = '';
            scheduleWrap.style.display = 'none';
          }
        });
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
    const continuousChk = el('input', { type: 'checkbox' });
    continuousChk.checked = true;          // continuous-by-default for the cockpit
    const continuousLabel = el('label', { class: 'pt-toggle' },
      continuousChk,
      el('span', {}, 'Continuous'),
    );
    const runBtn = el('button', { class: '' }, 'Run');
    const cancelBtn = el('button', { class: 'ghost' }, 'Cancel');
    cancelBtn.disabled = true;
    runGroup.appendChild(el('div', {}, el('label', {}, 'Scale'), scaleSel));
    runGroup.appendChild(el('div', {}, el('label', {}, 'Steps (fixed)'), nStepsInp));
    runGroup.appendChild(el('div', {}, el('label', {}, 'Seed'), seedInp));
    runGroup.appendChild(el('div', { style: 'align-self: center;' }, continuousLabel));
    runGroup.appendChild(el('div', { class: 'pt-run-actions' }, runBtn, cancelBtn));
    // n_steps input greys out in continuous mode.
    function syncContinuousUi() {
      nStepsInp.disabled = continuousChk.checked;
      nStepsInp.style.opacity = continuousChk.checked ? '0.4' : '1';
    }
    continuousChk.addEventListener('change', syncContinuousUi);
    syncContinuousUi();
    root.appendChild(runGroup);

    // "about the bounds" expander
    const boundsHelp = el('details', { class: 'pt-bounds-help' },
      el('summary', {}, 'About the slider bounds'),
      el('p', {}, 'Each slider is clamped to the N=2048 Sobol sampling box. The S1/ST values on each row are valid only inside that box. Extending the bounds (advanced mode) strips the sensitivity anchor.'),
    );
    root.appendChild(boundsHelp);

    // ---- behaviour --------------------------------------------------------

    // ---- schedule editor (S3) --------------------------------------------
    // SVG editor with four fixed-x control points whose y is draggable in
    // [0.05, 0.95]. The output alpha_schedule is sampled by linear
    // interpolation at integer step positions when the run is launched.
    // Constants live above the parameter loop (see TDZ note up top).

    function scheduleXY(p) {
      // Map fractional (x, y) in [0,1] × [0.05,0.95] → SVG pixel coordinates.
      const xPx = SCHED_PAD_X + p.x * (SCHED_W - 2 * SCHED_PAD_X);
      const yNorm = (SCHED_Y_MAX - p.y) / (SCHED_Y_MAX - SCHED_Y_MIN);
      const yPx = SCHED_PAD_Y + yNorm * (SCHED_H - 2 * SCHED_PAD_Y);
      return { xPx, yPx };
    }

    function pixelToY(yPx) {
      const yNorm = (yPx - SCHED_PAD_Y) / (SCHED_H - 2 * SCHED_PAD_Y);
      let y = SCHED_Y_MAX - yNorm * (SCHED_Y_MAX - SCHED_Y_MIN);
      y = Math.max(SCHED_Y_MIN, Math.min(SCHED_Y_MAX, y));
      return Math.round(y * 200) / 200;  // 0.005 resolution
    }

    function buildScheduleEditor(host) {
      const NS = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('class', 'pt-schedule-svg');
      svg.setAttribute('viewBox', `0 0 ${SCHED_W} ${SCHED_H}`);
      svg.setAttribute('preserveAspectRatio', 'none');
      // grid: 4 horizontal lines at y = 0.2, 0.4, 0.6, 0.8
      [0.2, 0.4, 0.6, 0.8].forEach((yv) => {
        const { yPx } = scheduleXY({ x: 0, y: yv });
        const line = document.createElementNS(NS, 'line');
        line.setAttribute('x1', SCHED_PAD_X);
        line.setAttribute('x2', SCHED_W - SCHED_PAD_X);
        line.setAttribute('y1', yPx);
        line.setAttribute('y2', yPx);
        line.setAttribute('class', 'grid');
        svg.appendChild(line);
      });
      // axis labels (y)
      ['0.2', '0.5', '0.8'].forEach((yv) => {
        const t = document.createElementNS(NS, 'text');
        const { yPx } = scheduleXY({ x: 0, y: parseFloat(yv) });
        t.setAttribute('x', 2);
        t.setAttribute('y', yPx + 3);
        t.setAttribute('class', 'axis-label');
        t.textContent = yv;
        svg.appendChild(t);
      });
      // path
      schedulePathEl = document.createElementNS(NS, 'polyline');
      schedulePathEl.setAttribute('class', 'curve');
      svg.appendChild(schedulePathEl);
      // points
      schedulePointEls = [];
      state.alphaSchedulePoints.forEach((p, i) => {
        const c = document.createElementNS(NS, 'circle');
        c.setAttribute('r', 5);
        c.setAttribute('class', 'pt-point');
        c.dataset.index = String(i);
        svg.appendChild(c);
        schedulePointEls.push(c);
      });
      host.appendChild(svg);
      host.appendChild(el('div', { class: 'pt-schedule-hint' },
        'drag a control point vertically. y range [0.05, 0.95]. four equally spaced steps over the run.',
      ));
      scheduleSvg = svg;

      // Dragging.
      let dragging = -1;
      function svgPointFromEvent(ev) {
        const rect = svg.getBoundingClientRect();
        const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX;
        const clientY = ev.touches ? ev.touches[0].clientY : ev.clientY;
        // Translate viewBox coordinates.
        const xPx = ((clientX - rect.left) / rect.width) * SCHED_W;
        const yPx = ((clientY - rect.top) / rect.height) * SCHED_H;
        return { xPx, yPx };
      }
      svg.addEventListener('mousedown', (ev) => {
        const idx = ev.target.dataset && ev.target.dataset.index;
        if (idx == null) return;
        dragging = Number(idx);
        ev.preventDefault();
      });
      window.addEventListener('mousemove', (ev) => {
        if (dragging < 0) return;
        const { yPx } = svgPointFromEvent(ev);
        state.alphaSchedulePoints[dragging].y = pixelToY(yPx);
        redrawSchedule();
      });
      window.addEventListener('mouseup', () => { dragging = -1; });
      redrawSchedule();
    }

    function redrawSchedule() {
      if (!scheduleSvg) return;
      const pts = state.alphaSchedulePoints.map(scheduleXY);
      schedulePathEl.setAttribute('points', pts.map((p) => `${p.xPx},${p.yPx}`).join(' '));
      schedulePointEls.forEach((c, i) => {
        c.setAttribute('cx', pts[i].xPx);
        c.setAttribute('cy', pts[i].yPx);
      });
    }

    function sampleSchedule(nSteps) {
      // Linearly interpolate the 4 control points over [0, nSteps-1].
      const out = new Array(nSteps);
      const pts = state.alphaSchedulePoints;
      for (let i = 0; i < nSteps; i++) {
        const t = nSteps === 1 ? 0 : i / (nSteps - 1);
        // Find the segment.
        let j = 0;
        while (j < pts.length - 2 && t > pts[j + 1].x) j += 1;
        const a = pts[j];
        const b = pts[j + 1];
        const segT = (t - a.x) / Math.max(b.x - a.x, 1e-9);
        out[i] = a.y + (b.y - a.y) * segT;
      }
      return out;
    }

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
      const n_steps = parseInt(nStepsInp.value, 10) || 0;
      const continuous = continuousChk.checked;
      const overrides = buildOverrides();
      // In continuous mode the engine should produce steps fast and often
      // rather than slow and big — drop pairs_per_step to ~20k so each
      // step is ~10ms and the stream feels continuous.
      if (continuous) {
        overrides.pairs_per_step = 20_000;
      }
      const cfg = {
        scenario: state.scenario,
        family: state.family,
        overrides,
        n_steps,
        scale: scaleSel.value,
        seed: parseInt(seedInp.value, 10),
        continuous,
        // K=1500 lets the deck.gl canvas feel full without forcing
        // ghost-particle interpolation. Wire cost ≈ 80 bytes × K per step.
        pair_sample_k: 1500,
        // Cockpit Pass 2: persistent cast of 150 prototypes the live
        // canvas follows from step 0. Wire cost ≈ 150 × 80 bytes per
        // step; negligible at 10 steps/sec.
        cast_size: 150,
      };
      if (state.alphaMode === 'schedule' && n_steps > 0 && !continuous) {
        cfg.alpha_schedule = sampleSchedule(n_steps);
        // Drop the per-step `alpha` override since the schedule takes precedence.
        delete cfg.overrides.alpha;
      }
      return cfg;
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
      familyPillRow.querySelectorAll('.pt-family-pill').forEach((p) => { p.disabled = running; });
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
