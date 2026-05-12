# W2a stretch — registration regime extensions

Status: drafted 2026-05-12. Three deferred pieces of the Hadfield
registration story that `docs/concepts/registration.md` named as
out-of-scope when W2a landed. Each is a distinct mechanism; this
plan scopes them as three independent sub-workstreams so they can
land separately or together.

## Dependencies

W2a (`commit 3250fb6`) and W1a regulator (`commit baf77d7`).
Persistent `agent_id` and the `registered` mask are the
infrastructure these all build on.

## Why

`docs/concepts/registration.md` "What is still not modeled after
W2a" lists four omissions the smallest-credible W2a left open:

- Audit-trail tampering with cryptographic signatures.
- Identity laundering through firm formation / dissolution.
- Multi-jurisdiction registration arbitrage.
- Reputation accrual to individuals.

The fourth (reputation) is a v3 architectural decision and stays
out of this plan. The first three are each tractable as a per-step
mechanism layered on top of the existing `RegulatorConfig` /
`RegistrationConfig` levers. They are what makes the registration
regime *do work under capture* — the failure modes Hadfield's *Legal
Infrastructure for Transformative AI Governance* (arXiv:2602.01474,
Feb 2026) is most worried about.

## Three sub-workstreams

### S1 — Audit-trail tampering

The regulator gate at `engine/core/transactions.py` reads
`pop.registered` as a clean bit. In reality the regulator's ability
to detect non-registration depends on protocol design, and a
captured regulator can be coerced into forging the bit for paying
clients.

Mechanism:

- New `RegulatorConfig.audit_tampering_rate ∈ [0, 1]` — per-step
  probability that an unregistered agent's bit gets *forged to
  True* in the regulator's view, scaled by `regulator_capture[stack]`
  so capture is the load-bearing input.
- `coasean_step` evaluates the forged-view bit instead of the raw
  `pop.registered` at the regulator gate. The `registration_floor`
  bump applies against the *forged* bit, so a high-tampering high-
  capture regime lets unregistered agents trade as if registered.
- Pin `forged_registration_share` on `StepMetrics` so the dashboard
  can read how much of the regulator's effective registration mask
  is a forgery.

Test: with `audit_tampering_rate=1.0` and `regulator_capture=1.0`,
unregistered agents should experience the same gate rejection rate
as registered agents — capture completely defeats the floor.

### S2 — Identity laundering through firm formation

The dissolution / formation cycle in
`engine/core/institutions.py` doesn't re-issue `agent_id` when a
firm dissolves. A registered agent who picks up a regulator-flag
can therefore't shed it; this is unrealistic. Real-world
laundering uses firm structures as identity shells.

Mechanism:

- `InstitutionConfig.laundering_enabled: bool = False` flag (new).
- When `dissolution_step` retires a firm, the member prototypes
  whose `firm_id == retired_id` get a fresh `agent_id` issued (the
  W2a re-issue mechanism, now exposed at firm-dissolution boundary
  instead of only at population entry/exit). Their `registered`
  bit is also reset per `RegistrationConfig.initial_registered_share`,
  meaning a previously-flagged agent re-emerges as a fresh
  registered/unregistered draw.
- Optional: charge a `RegulatorConfig.laundering_detection_rate ∈
  [0, 1]` cost — fraction of laundered prototypes get their bit
  flagged back to `registered=False` at the moment of re-issue,
  modelling the regulator catching some but not all of the
  laundering attempts.

Test: with `laundering_enabled=True` and zero detection, a
prototype's `agent_id` strictly grows across firm
dissolution-formation cycles; the cumulative count of unique
agent_ids exceeds the population size.

### S3 — Multi-jurisdiction registration arbitrage

Each stack has its own regulator vendor under W1a, but agents do
not strategically choose which stack to register under. W1c
permeability is the structural surface that would allow arbitrage:
register under the laxest regulator, transact under the strictest
(via cross-stack pairs).

Mechanism:

- Two-pass approach: agents look at the per-stack regulator vendor
  arrays once at world build and pick the stack with the lowest
  effective rejection probability for *their* sector. The chosen
  stack becomes their *registration stack* (a new
  `Population.registration_stack: np.ndarray[int8]` field).
- The `registration_floor` bump at the regulator gate reads the
  registration_stack's regulator, not the trading partner's.
- Optional: charge a per-step `RegistrationConfig.foreign_registration_cost`
  for agents whose `registration_stack != stack` — the cost of
  maintaining a foreign legal entity.

Test: when one stack has strictly less stringent regulator params
than all others, with arbitrage enabled all agents register there;
with arbitrage disabled (the W2a default) registration stack
matches each agent's own stack.

## Sequencing

| # | Sub | Why this order |
| --- | --- | --- |
| 1 | S1 audit-tampering | Smallest. Single new param, single per-pair tweak. |
| 2 | S3 arbitrage | Couples to W1a regulator vendor pool. New Population field. |
| 3 | S2 laundering | Couples to institutions. Largest behavioural change. |

## Exit conditions

Each sub-workstream's exit condition:

- Default-off so canonical baselines bit-identical.
- One new scenario per sub demonstrating the lever's effect against
  the W2a `registration_strict` / `registration_lax` baseline (not
  yet authored — would land alongside this round).
- Test coverage in the existing `test_registration.py` pattern.
- A one-paragraph addition to `docs/concepts/registration.md` "What
  is still not modeled" → "What is now modeled" for each landed
  sub.

## Notes for the executor

- S1 and S3 are tractable as a single round (≈ 1 day each). S2 is
  larger because it touches institutions.py's dissolution path and
  has the most subtle bit-identity guarantee — the laundering
  re-issue can only fire when *both* `laundering_enabled` and the
  W2a flag are True, so W2a-on / laundering-off is the new
  bit-identity contract.
- Reputation accrual to individuals (the fourth omission) needs a
  per-prototype reputation accumulator that ages over time and is
  read by the regulator gate. That's a v3 architectural decision —
  out of scope here.
