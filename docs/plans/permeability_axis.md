# Permeability as a first-class axis

Status: the only permeability-like parameter in the engine is `cross_stack_compat: float = 0.55` on `TopologyConfig` (`engine/core/topology.py:195`), which sets the off-diagonal of the inter-stack compatibility matrix. The exo layers (lift / drag / last-mile / differential) have no inter-layer permeability parameter at all — flow between layers is determined by the layer-specific kinetics with no exposed friction. As a consequence, every scenario in the atlas implicitly runs at "high permeability" on the exo side, and the only knob on the agent side is a single scalar.

The Tomašev et al. Virtual Agent Economy paper sets two axes — emergent vs. intentional, permeable vs. impermeable — and the agentworld concept docs add a third (smooth ↔ striated friction). Permeability is collapsed into the static `0.55`. A permeable Smoothworld and an impermeable Smoothworld are different attractors with different welfare profiles, and the artifact currently cannot exhibit one of them.

This plan promotes permeability to a first-class config block exposed to the sensitivity sweep, plumbed through both the agent-stack topology and the exo cross-layer transfers, and exercises two new scenarios at the previously absent corners of the (smooth/striated, low/high permeability) plane.

This plan stands alone. Read these inputs only:

- `engine/core/topology.py` (the `TopologyConfig` and the cross-stack compatibility matrix)
- `engine/core/transactions.py` (the inter-stack pair sampling)
- `engine/exo/world.py` (the exo step orchestration)
- `engine/exo/last_mile.py`, `engine/exo/drag.py`, `engine/exo/differential.py` (the layer transfer functions)
- `engine/exo/config.py` (where exo config currently lives)
- `engine/scenarios/__init__.py` (the scenario factory)
- `engine/sensitivity.py` (Sobol parameter list)

## Dependencies

- Plan 1 (per-component RNG split) — preferred. Cleaner attribution on permeability parameters.
- Otherwise independent.

## Why

Three concrete claims hang off this plan:

1. **Permeability is orthogonal to the friction-coefficient axis (smooth/striated).** Smooth + permeable, smooth + impermeable, striated + permeable, striated + impermeable are four different attractors, and the artifact currently exercises mostly the smooth + permeable corner.
2. **Cross-stack agent permeability and cross-exo-layer permeability are different objects** that should not be tied to a single parameter. Agent-stack permeability gates whether NATO-stack agents can transact with PRC-stack agents; exo-layer permeability gates whether value generated in the lift layer reaches the last-mile layer.
3. **The Sobol attribution is currently silent on permeability** because the parameter does not appear in the sweep. Adding it lets us check whether the artifact's conclusions are robust to permeability variation or are products of the implicit high-permeability default.

## What to do

### Task 1 — Define `PermeabilityConfig`

New file `engine/core/permeability.py` (or as a section of `engine/core/topology.py` if you prefer to keep config files flat):

```python
@dataclass
class PermeabilityConfig:
    # Agent-side: cross-stack compatibility. Replaces the existing
    # TopologyConfig.cross_stack_compat scalar.
    agent_stack: float = 0.55

    # Exo-side: how easily value migrates between layers.
    exo_lift_to_lastmile: float = 0.85
    exo_lastmile_to_drag: float = 0.50
    exo_drag_to_differential: float = 0.40

    # Convention: 1.0 = perfectly permeable, 0.0 = sealed.
```

Defaults reproduce current behavior — `agent_stack = 0.55` matches the existing `cross_stack_compat`. The exo defaults (0.85, 0.50, 0.40) are calibrated so the existing exo-engine canonical metrics reproduce within float noise; verify this empirically when landing.

### Task 2 — Plumb `agent_stack` into the topology

In `engine/core/topology.py`:

- Replace `TopologyConfig.cross_stack_compat` with a property that reads from `PermeabilityConfig.agent_stack`. Keep the old name as a deprecated alias for one round.
- The compatibility matrix construction at `topology.py:314` uses this scalar; no change needed beyond the rename.

### Task 3 — Plumb `exo_*` into the layer transfers

In `engine/exo/last_mile.py:49-100` and `engine/exo/drag.py`, `engine/exo/differential.py`: each layer's `step` function performs an internal transfer from a source layer's pool to its own pool. Multiply the transferred quantity by the corresponding permeability scalar.

```python
# In last_mile.py step:
incoming_from_lift = lift_pool * perm_cfg.exo_lift_to_lastmile

# In drag.py step:
incoming_from_lastmile = lastmile_pool * perm_cfg.exo_lastmile_to_drag

# In differential.py step:
incoming_from_drag = drag_pool * perm_cfg.exo_drag_to_differential
```

The remainder (the `(1 - permeability)` fraction) stays in the source layer or is recycled per the layer's existing rules — pick the conserving choice. Run the canonical exo scenarios and check accounting closes.

### Task 4 — Two new scenarios

In `engine/scenarios/__init__.py`:

```python
def low_permeability_smooth() -> WorldConfig:
    """Low cross-stack and low cross-exo-layer permeability, smooth (low-
    friction) bargaining. Tests whether the smooth attractor still produces
    a flat-hierarchy outcome when value cannot easily traverse the stack."""

def high_permeability_striated() -> WorldConfig:
    """High permeability everywhere with striated (high-friction) bargaining.
    Tests whether striation alone is enough to fold hierarchy when nothing
    is sealed."""
```

Both should be added to the dashboard's scenario picker. Suggested values:

- `low_permeability_smooth`: `agent_stack=0.10, exo_lift_to_lastmile=0.20, exo_lastmile_to_drag=0.10, exo_drag_to_differential=0.05` + the smooth-scenario topology (low alpha, low friction).
- `high_permeability_striated`: `agent_stack=0.95, exo_lift_to_lastmile=0.95, exo_lastmile_to_drag=0.90, exo_drag_to_differential=0.85` + the striated-scenario topology.

### Task 5 — Sobol parameter list

In `engine/sensitivity.py`, the parameter list passed to `saltelli.sample` currently includes ~12 parameters. Add the four permeability scalars with bounds `[0.0, 1.0]`. The sweep size N stays at 2048 (re-pin happens in plan 9).

### Task 6 — Test

`engine/tests/test_permeability.py`:

```python
def test_default_perm_reproduces_canonical():
    """Default PermeabilityConfig reproduces existing canonical metrics."""

def test_zero_agent_stack_isolates_stacks():
    """agent_stack=0 should drive cross-stack pair count to ~0."""

def test_zero_exo_lift_to_lastmile_blocks_distribution():
    """With exo_lift_to_lastmile=0, last-mile pool stays at its initial value
    forever (no inflow from lift)."""

def test_perm_conservation():
    """Total pool across all exo layers is conserved up to layer kinetics
    regardless of permeability values (within float noise)."""
```

### Task 7 — Doc

In `docs/concepts/smooth_striated.md`, add a section "Permeability is a separate axis" with a 2-D diagram (or just a 2-D ASCII matrix) showing the four attractor corners and which scenarios sit in each.

## Exit conditions

- Default `PermeabilityConfig` reproduces every existing canonical scenario within float tolerance < 1e-9.
- `low_permeability_smooth` and `high_permeability_striated` scenarios are in `engine/scenarios/__init__.py`, the dashboard's picker, and `outputs/runs/`.
- The four permeability scalars are in `engine/sensitivity.py`'s parameter vector.
- `test_permeability.py` passes.

## Acceptance test

```bash
python -m pytest engine/tests/ -x
python -m pytest engine/tests/test_permeability.py -v
python -m engine.cli run --scenario low_permeability_smooth --steps 60
python -m engine.cli run --scenario high_permeability_striated --steps 60
```

Both scenarios run to completion. Their terminal EBI / Gini / welfare values are different from the corresponding "high-permeability smooth" / "low-permeability striated" baselines (visually distinct on the dashboard).

## Notes for the executor

- Do not introduce a single "global permeability" knob. The whole point is that agent-stack permeability and exo-layer permeability decouple.
- The exo defaults (0.85, 0.50, 0.40) are placeholder. Calibrate them empirically: pick values such that the existing canonical exo scenarios reproduce within ~0.5% on EBI / human_legibility_index / fold_max_depth. If a clean reproduction is impossible at any setting (because the current code has implicit kinetics that don't compose with a multiplicative gate), document the divergence and pick the closest fit.
- The conserving choice for the `(1 - permeability)` remainder is layer-specific. For lift→last-mile, retaining the remainder in the lift layer is correct (it accumulates as un-distributed value). For last-mile→drag, retaining is also correct (drag is a sink, not a destination). Test the conservation check carefully.
- Sensitivity output names should be `perm_agent_stack`, `perm_exo_lift_lastmile`, etc. — keep them parameter-named.
