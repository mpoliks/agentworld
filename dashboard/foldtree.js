/* foldtree.js — d3 visualisation of the per-depth fold cascade.
 *
 * Each step adds a column whose stacked bars represent the nominal
 * contribution at depths 1..D. The width of a column scales with the
 * step's total fold-nominal; the colour shifts from accent (depth 1) to
 * red (deepest) so a Hawkes overshoot step lights up its deepest bar.
 *
 * Public API:
 *   const tree = createFoldTree(hostElement, { width, height, maxDepth });
 *   tree.reset();
 *   tree.appendStep(step, perDepthContribution);
 *   tree.resize();
 */

(function () {
  if (window.createFoldTree) return; // idempotent

  const COLORS = ['#b89a55', '#c89455', '#d2855a', '#cf705e', '#c25a5a', '#a04545', '#7d3838'];
  const PALETTE_LEN = COLORS.length;

  function colorForDepth(d, maxD) {
    if (maxD <= 0) return COLORS[0];
    const idx = Math.min(PALETTE_LEN - 1, Math.floor((d / Math.max(1, maxD)) * (PALETTE_LEN - 1)));
    return COLORS[idx];
  }

  function createFoldTree(host, opts) {
    const cfg = Object.assign({
      maxBars: 240,        // hard cap on columns; older columns are dropped
      paddingLR: 18,
      paddingTB: 18,
      labelHeight: 18,
    }, opts || {});

    const state = {
      data: [],            // [{ step, perDepth, total }]
      maxTotalSeen: 0,
      maxDepthSeen: 0,
    };

    // Build SVG inside host.
    host.innerHTML = '';
    const root = d3.select(host).append('svg')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('preserveAspectRatio', 'none')
      .attr('viewBox', '0 0 800 480');

    const g = root.append('g').attr('class', 'fold-tree-group');

    // Axis labels.
    const labelGroup = root.append('g').attr('class', 'fold-tree-labels');
    labelGroup.append('text')
      .attr('x', 10).attr('y', 16)
      .attr('fill', '#9ea2a8').attr('font-size', 11)
      .attr('font-family', 'JetBrains Mono, SF Mono, Menlo, monospace')
      .text('fold cascade · per-depth nominal · deepest = red');

    function viewBox() {
      const r = host.getBoundingClientRect();
      const w = Math.max(120, Math.floor(r.width));
      const h = Math.max(120, Math.floor(r.height));
      root.attr('viewBox', `0 0 ${w} ${h}`);
      return { w, h };
    }

    function reset() {
      state.data = [];
      state.maxTotalSeen = 0;
      state.maxDepthSeen = 0;
      g.selectAll('*').remove();
    }

    function appendStep(step, perDepth) {
      const arr = (perDepth || []).map(Number).filter((v) => Number.isFinite(v));
      const total = arr.reduce((a, b) => a + Math.max(0, b), 0);
      const rec = { step, perDepth: arr, total };
      state.data.push(rec);
      if (state.data.length > cfg.maxBars) {
        state.data.shift();
      }
      state.maxTotalSeen = Math.max(state.maxTotalSeen, total || 1);
      state.maxDepthSeen = Math.max(state.maxDepthSeen, arr.length);
      render();
    }

    function render() {
      const { w, h } = viewBox();
      const innerW = w - cfg.paddingLR * 2;
      const innerH = h - cfg.paddingTB * 2 - cfg.labelHeight;
      const n = state.data.length;
      if (n === 0) {
        g.selectAll('*').remove();
        return;
      }
      const colW = innerW / n;
      const baseX = cfg.paddingLR;
      const baseY = cfg.paddingTB + cfg.labelHeight;

      // Use log scale on totals so a Hawkes overshoot doesn't crush the
      // earlier columns to invisibility.
      const maxLog = Math.log10(1 + state.maxTotalSeen);

      // Bind columns.
      const cols = g.selectAll('g.col').data(state.data, (d) => d.step);
      const colsEnter = cols.enter().append('g').attr('class', 'col');
      const colsAll = colsEnter.merge(cols);
      cols.exit().remove();

      colsAll.attr('transform', (_, i) => `translate(${baseX + i * colW}, ${baseY + innerH})`);

      // Within each column, draw bars from bottom up: depth 1 at the bottom.
      colsAll.each(function (d) {
        const colSel = d3.select(this);
        // Each bar's height is proportional to (its contribution / sum of contributions
        // of *all* depths in *this* column), times a global scale based on log(total).
        const sum = d.perDepth.reduce((a, b) => a + Math.max(0, b), 0);
        const colTotalLog = Math.log10(1 + (d.total || 0));
        const colHeight = innerH * (maxLog > 0 ? colTotalLog / maxLog : 0);

        // Re-bind bars within this column.
        const bars = colSel.selectAll('rect.bar').data(d.perDepth);
        const barsEnter = bars.enter().append('rect').attr('class', 'bar');
        const barsAll = barsEnter.merge(bars);
        bars.exit().remove();

        let yCursor = 0;
        const maxD = state.maxDepthSeen;
        d.perDepth.forEach((c, i) => {
          const frac = sum > 0 ? Math.max(0, c) / sum : 0;
          const bH = colHeight * frac;
          barsAll.filter((_, j) => j === i)
            .attr('x', 1)
            .attr('width', Math.max(0, colW - 1.6))
            .attr('y', -(yCursor + bH))
            .attr('height', Math.max(0, bH))
            .attr('fill', colorForDepth(i + 1, maxD))
            .attr('opacity', 0.92);
          yCursor += bH;
        });
      });
    }

    return {
      reset,
      appendStep,
      resize: render,
      _state: state,
    };
  }

  window.createFoldTree = createFoldTree;
})();
