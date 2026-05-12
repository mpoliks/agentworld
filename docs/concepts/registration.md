# Registration — Persistent Agent Identity

> *"The infrastructure of registration is the precondition for everything else."* — paraphrase of Gillian K. Hadfield, *Legal Infrastructure for Transformative AI Governance* (arXiv:2602.01474, Feb 2026)

Status: **landed 2026-05.** `RegistrationConfig` is in `engine/core/topology.py`, persistent `agent_id` / `registered` fields are on `Population`, and the registration regime couples to the W1a regulator gate via `registration_floor`. Default-off so canonical baselines stay bit-identical; opt-in scenarios are still to be authored (see "What is still not modeled" below for the parts that remain stubbed even after W2a).

---

## What is missing

Every transaction in the α-engine is between two anonymous prototype draws from `Population`. Prototypes carry `sector`, `stack`, `firm_id`, `alignment`, `autonomy`, `capability`, and `wealth`. They do *not* carry a stable identifier across steps. There is no `agent_id` field, no `registered` mask, no audit trail. Two transactions in consecutive steps that "look like" they involve the same agent are, in the model, drawn from the same population class but not bound to the same actor.

This means the engine cannot represent:

- a regulator that flags a specific agent and bars it from subsequent transactions,
- an audit trail that survives one step,
- identity laundering through firm formation and dissolution,
- multi-jurisdiction registration arbitrage (registering under the laxest regulator, transacting under the strictest),
- reputation that accrues to an individual rather than a sector / stack / firm class.

Hadfield's argument is that without these, every higher-level governance design (regulatory markets, normative competence, mission-economy coordination) runs on infrastructure that does not exist.

## What the planned implementation does

W2a in `docs/plans/hadfield_jacobs_robustness.md` adds:

- `agent_id: np.int64` on `Population`, stable across steps, monotonic on prototype creation.
- `registered: np.ndarray[bool]` mask, set by `RegistrationConfig` policy.
- A per-step `registration_cost` charged against wealth for registered agents — analog of compliance overhead.
- A `registration_floor`: unregistered agents face an additional rejection probability at the regulator layer (`regulator_reject`, introduced in W1a). This is the lever by which the registration regime *does work* — unregistered actors can still trade, but they pay a regulatory-rejection premium and a reputation discount.

Three scenarios bracket the axis:

- **registration_strict** — `registration_cost` set so 80%+ of agents register; `registration_floor` is large enough that unregistered trade is largely shut out at the regulator layer. The Hadfield ideal.
- **registration_lax** — `registration_cost` low, `registration_floor` low. Most agents register but the regulator layer barely reads the bit. The current artifact's implicit position.
- **registration_collapse** — `regulator_capture` rises endogenously when registered-agent share drops below a threshold; captured regulators forge audit trails; the registration signal degrades to noise. The failure mode Hadfield's *Legal Infrastructure* paper is most worried about.

## What is now modeled after the S1–S3 stretch goals

Three of the four W2a omissions landed as scenario-default-off levers in the registration stretch round:

- **Audit-trail tampering (S1).** `RegulatorConfig.audit_tampering_rate` is the per-step probability that an unregistered agent's `registered` bit is forged to True in the regulator's view, scaled by `regulator_capture[stack]`. With both knobs at 1.0 the `registration_floor` is fully defeated and unregistered agents trade as if registered. Surfaced on `StepMetrics.forged_registration_share` for the dashboard.
- **Identity laundering through firm formation (S2).** `InstitutionConfig.laundering_enabled` couples firm dissolution to identity re-issue: every member of a dissolved firm gets a fresh monotonic `agent_id` and a fresh draw on the `registered` bit per `RegistrationConfig.initial_registered_share`. `RegulatorConfig.laundering_detection_rate` flips a fraction of the redrawn bits back to False — the regulator catches some but not all attempts. Bit-identity contract is preserved when the flag is off.
- **Multi-jurisdiction registration arbitrage (S3).** `RegistrationConfig.arbitrage_enabled` populates `Population.registration_stack` at world build by picking the stack with the lowest effective regulator rejection rate (`strength × audit_quality × (1 − capture)`). The regulator-gate floor on each agent then reads its registration stack's effective strength — agents who escaped to a lax stack see a proportionally smaller floor.

## What is still not modeled after the S1–S3 stretch

- **Reputation accrual to individuals.** `agent_id` is an identifier, not a reputation accumulator. A reputation-tracked engine variant is a candidate v3 extension after the identity machinery is stable.

These omissions are the conditioning assumptions a reader in the Hadfield orbit should hold while reading any registration-regime result the engine produces post-stretch.

---

## References

- Hadfield, G. K. (February 2026). *Legal Infrastructure for Transformative AI Governance.* arXiv:2602.01474.
- Hadfield, G. K. (May 2025). *Normative infrastructure for AI alignment.* AIhub interview.
- `docs/plans/hadfield_jacobs_robustness.md` — W2a workstream.
- `docs/concepts/matryoshkan_alignment.md` — "What this model is not", third paragraph.
