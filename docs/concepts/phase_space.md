# Phase Space — From Scenario Atlas to Basin Map

The 15 scenarios are useful because they have names. They can be discussed:
Coasean Paradise, Slop Market, Baroque Cathedral, Hemispherical Schism. But
named scenarios are also dangerous because they can become theatrical. A serious
model needs to ask whether those scenarios are isolated anecdotes or visible
points on a larger surface.

`engine/sensitivity.py` is that check. It sweeps two parameters:

- `alpha`: the smooth/striated control variable.
- `agent_capability_mean`: the mean capability of the agent layer, with human
  capability held lower by a fixed offset.

Each grid point runs the same core world model and is classified by terminal
metrics:

- **smooth**: EBI below 2 and legibility above 0.5.
- **mixed**: no clean attractor dominates.
- **striated**: EBI above 10 but below 100.
- **baroque**: EBI above 100 with still-material welfare.
- **slop**: EBI above 100 with very weak per-capita welfare.

This produces a basin map rather than a scenario list. It lets the reader ask:
where does the system naturally go if capability improves faster than protocol
discipline? Where does it go if `alpha` rises before agents become competent?
How wide is the bad quadrant?

## First Interpretation

The basin map makes the artifact's core claim sharper:

1. Capability does not decide the direction. Capability makes the chosen
   direction more consequential.
2. Low `alpha` plus high capability produces the Krier attractor: low
   transaction cost, high legibility, direct welfare.
3. High `alpha` plus high capability produces the Bratton attractor: high
   welfare may remain possible, but nominal measurement runs far ahead of it.
4. High `alpha` plus low capability is the slop basin: intense machine activity,
   little human welfare, low legibility.

The named scenarios can therefore be treated as labeled probes into the phase
space:

- `coasean_paradise` probes the smooth/high-capability corner.
- `slop_market` probes the high-alpha/low-capability corner.
- `baroque_cathedral` probes high-alpha/high-capability folding.
- `equilibrium_drift` probes the unstable center.
- `recursive_simulation` probes path dependence: movement across the map caused
  by the map itself.

## How to Run

```bash
agentworld sweep
```

or:

```bash
PYTHONPATH=. python engine/sensitivity.py
```

The output is `outputs/sensitivity/phase_space.json`, a self-contained list of
terminal metrics for each grid point. Increase `--steps`, `--pairs`, `--humans`,
and `--agents` when producing final figures; keep defaults for fast iteration.

## Why This Matters for Bratton's Brief

Bratton's conjecture is not just that folding can happen. It is that folding may
be where the on-paper gains come from, because national accounting and protocol
owners reward the multiplication of priced surfaces. The phase-space sweep
translates that conjecture into a falsifiable form: if high `alpha` reliably
creates high EBI across a broad range of capability values, then Baroqueworld is
not a decorative scenario. It is a basin.

Krier's conjecture gets the same treatment. If low `alpha` plus high capability
reliably keeps EBI near 1 while increasing welfare, then Coasean bargaining at
scale is not wishful thinking. It is also a basin.

The political question is therefore not "which future is true?" It is: which
basin do protocol defaults, accounting rules, payment rails, and agent objective
functions make easiest to fall into?
