# Bibliography & Sources

The conceptual scaffolding for this artifact lives in the following texts, in rough order of immediacy:

## Primary sources for *Agentworld*

- **Bratton, Benjamin.** (2026, forthcoming). *Agentworld* research brief, Antikythera. The brief in dialogue with which this artifact was constructed. ~12–15 scenarios for a society of 800B agents and 8B humans.
- **Bratton, Benjamin.** (2026). Telegram correspondence with Marek Poliks, April 21, 2026. The genesis of the *fractal multiplication of folded surfaces* hypothesis.
- **Antikythera.** (2026). *Agentworld R&D Unit*, San Francisco 2026. Project description: ["100:1: A Parasociety of a Trillion Minds"](https://antikythera.org/research).
- **Poliks, Marek & Trillo, Roberto Alonso.** (2025). *Exocapitalism*. The framing that the smooth/striated dial misnames the variable. *Lift* (capital's drift through layers of abstraction), *drag* (the labor of producing legibility), and the rejection of last-mile-as-real are the conceptual basis of `engine/exo/`.
- **Poliks, Marek & Trillo, Roberto Alonso.** (2025). Interview with 邊界_RG (Biānjiè Research Group). The most direct articulation of the exo position on Coasean bargaining: the agent layer as anxiety dampener.
- **Poliks, Marek.** (2026, draft). *What is Exocapitalism?* The Catalyst (General Catalyst × Spike Art Magazine), prompt from Dean Kissick. The McDonald's-as-real-estate, university-as-hedge-fund examples.

## Coasean / smooth attractor

- **Krier, Séb.** (2025). *Coasean Bargaining at Scale: Decentralisation, coordination, and co-existence with AGI.* AI Policy Perspectives, September 29, 2025. The most direct articulation of what I call the "smooth attractor." [Link](https://www.aipolicyperspectives.com/p/coasean-bargaining-at-scale).
- **Coase, Ronald H.** (1960). *The Problem of Social Cost.* Journal of Law and Economics 3:1–44. The origin.
- **Coase, Ronald H.** (1937). *The Nature of the Firm.* Economica 4(16):386–405. The other origin: why firms exist when transaction costs are non-zero. Implicitly, why they may dissolve when transaction costs are near-zero.
- **Hayek, Friedrich A.** (1945). *The Use of Knowledge in Society.* American Economic Review 35(4):519–530. The decentralized-knowledge argument that Krier extends to agents.
- **Ostrom, Elinor.** (1990). *Governing the Commons: The Evolution of Institutions for Collective Action.* Cambridge University Press. The empirical companion to Coase.
- **Greenwald, Bruce & Stiglitz, Joseph.** (1986). *Externalities in Economies with Imperfect Information and Incomplete Markets.* Quarterly Journal of Economics 101(2):229–264. The foundational result Krier builds on.

## Striated / Baroque attractor

- **Deleuze, Gilles & Guattari, Félix.** (1980). *Mille Plateaux*, especially Chapter 14: *1440: Le Lisse et le Strié* (The Smooth and the Striated). The conceptual home of the variable.
- **Deleuze, Gilles.** (1988). *Le Pli: Leibniz et le Baroque.* Translated as *The Fold: Leibniz and the Baroque.* The image of fractal multiplication of folds.
- **Mandelbrot, Benoit.** (1982). *The Fractal Geometry of Nature.* Freeman. For the underlying mathematics of unbounded surface area in folded geometries.

## Multi-agent economic infrastructure

- **Tomašev, Nenad et al.** (2025). *Virtual Agent Economy.* arXiv:2509.10147. The "virtual agent economy" framing that Krier and others build on. Co-authored by Julian Jacobs (DeepMind / Oxford Martin AIGI). Cross-listed under "Sandbox economies" below: its two-axis taxonomy (emergent ↔ intentional, permeable ↔ impermeable) is orthogonal to this artifact's smooth ↔ striated axis and forms the basis of the `cross_stack_permeability` parameter introduced in `docs/plans/hadfield_jacobs_robustness.md` (W1c).
- **Leibo, Joel Z. et al.** (2025). *A patchwork polychrome quilt: Modelling societal and technological progress.* arXiv:2505.05197. The "muddle through" framing of socio-technical evolution.
- **Capability-Priced Micro-Markets (CPMM).** (2026). arXiv:2603.16899. Framework for HTTP 402 / agent payment infrastructure.
- **ClawCoin.** (2026). arXiv:2604.19026. Compute-cost-indexed cryptocurrency for A2A settlement.
- **SoK: Blockchain Agent-to-Agent Payments.** (2026). arXiv:2604.03733. Survey of A2A payment infrastructure.
- **Mastercard Agent Pay**, **Stripe Agentic Commerce**, **Google Cloud AP2 protocol** — production infrastructure shipping in late 2025 / early 2026.

## Regulatory infrastructure and registration regimes

- **Hadfield, Gillian K.** (Winter 2026). *Regulatory Markets: The Future of AI Governance.* Jurimetrics. Government-licensed private regulators competing on audit quality. The construct the Matryoshka middle layer is *not*: see `docs/concepts/matryoshkan_alignment.md` "What this model is not." Operationalized as the `regulator_reject` filter (W1a in `docs/plans/hadfield_jacobs_robustness.md`).
- **Hadfield, Gillian K.** (May 2025). *Normative infrastructure for AI alignment.* Interview, AIhub. Alignment as participation in evolving community norms rather than preference-matching at static distance. The reason `align_reject` is a load-bearing misspecification in the current engine; replaced by norm-participation under `NormsConfig.enabled` (W1b).
- **Hadfield, Gillian K.** (February 2026). *Legal Infrastructure for Transformative AI Governance.* arXiv:2602.01474. Registration regimes for autonomous agents as the precondition for everything else. The absence the artifact must name as a conditioning assumption; addressed by W2a (`RegistrationConfig`, persistent `agent_id`).

## Sandbox economies

- **Tomašev, Nenad et al. / Jacobs, Julian.** (2025). *Virtual Agent Economy.* arXiv:2509.10147. See primary entry under "Multi-agent economic infrastructure." The two-axis sandbox taxonomy is what `cross_stack_permeability` (W1c) and `mission_economy` (W2b) bring into the artifact's parameter space.
- **Jacobs, Julian.** *Predicting AI's Impact on Jobs.* Oxford Martin AIGI. Labor-displacement work that motivates the explicit human-side labor-market split (W2c).

## Alignment and Matryoshka layers

- **Levin, Michael.** (2019). *The Computational Boundary of a "Self": Developmental Bioelectricity Drives Multicellularity and Scale-Free Cognition.* Frontiers in Psychology 10:2688. Where Krier's "scale-free cognition" / Matryoshka image comes from.
- **Levin, Michael & Lyon, Benjamin.** (2024). *Cognitive glue.* OSF preprint. The "cognitive glue" framing of bottom-up coordination.
- **Williams, Dan.** *Why do people believe true things?* Conspicuous Cognition. The institutional framing of alignment-as-governance.
- **Constitution Maker.** (2023). arXiv:2310.15428. Extracting natural-language principles from preference data.
- **Inverse Constitutional AI.** (2024). arXiv:2406.06560. Compressing preferences into interpretable principles.

## Planetary computation / Antikythera background

- **Bratton, Benjamin H.** (2015). *The Stack: On Software and Sovereignty.* MIT Press. The foundational text. The Earth/Cloud/City/Address/Interface/User stack from which "Hemispherical Stacks" derive.
- **Bratton, Benjamin H.** (2021). *The Revenge of the Real: Politics for a Post-Pandemic World.* Verso.
- **Antikythera.** (2024–2026). *Speculative Philosophy of Planetary Computation*, [spoc.antikythera.org](https://spoc.antikythera.org). The methodology. Particularly the "recursive simulations" track.
- **Bratton, Benjamin & Agüera y Arcas, Blaise.** (2022). *The Model Is the Message.* Noema Magazine.
- **Agüera y Arcas, Blaise.** (2025). *What is Intelligence?* MIT Press / Antikythera. The first book in the Antikythera/MIT Press series.

## Empire, world-system, extraction

- **Wallerstein, Immanuel.** (1974). *The Modern World-System I.* Academic Press. The world-system tradition the imperial-tract topology draws on: capital and polity are not coextensive; core / semi-periphery / periphery persist over centuries.
- **Arrighi, Giovanni.** (1994). *The Long Twentieth Century.* Verso. Hegemonic cycles as long-run capital pooling — "attractor strength" rotating between named centers (Genoa, Amsterdam, London, New York).
- **Mitchell, Timothy.** (2011). *Carbon Democracy.* Verso. The geological / energy basis of imperial tract structure.
- **Davis, Mike.** (2001). *Late Victorian Holocausts.* Verso. The empirical record of extraction-without-polity-coverage.
- **Mbembe, Achille.** (2003). *Necropolitics.* Public Culture 15(1):11–40. The "passive production / retrospective consumption of violence" framing the imperial violence-floor borrows from.
- **Pistor, Katharina.** (2019). *The Code of Capital.* Princeton University Press. How legal infrastructure pools high-layer capital across polity boundaries.
- **Galeano, Eduardo.** (1971). *Las venas abiertas de América Latina.* The popular formulation of meatspace-as-extraction-pipeline.

## Political economy of AI

- **Acemoglu, Daron & Robinson, James.** *Why Not a Political Coase Theorem?* MIT working paper. The political-economy critique of Coasean clearance Krier engages with.
- **Maskin, Eric.** *Introduction to Mechanism Design and Implementation.* Harvard. For the mechanism-design machinery underneath Coasean clearance.
- **Bowman, Sam.** *Democracy is the Solution to Vetocracy.* On NIMBYism and the diffuse-cost problem.
- **Schmitt, Carl.** (1922). *Politische Theologie.* Where the "framework guarantor" question gets sharp.

## Companion theoretical resources

- **Walker, Sara & Cronin, Lee.** *Assembly Theory.* The framing of evolution as combinatorial assembly that Antikythera's allopoiesis discussion builds on.
- **James C. Scott.** (1998). *Seeing Like a State.* For the limits of central observation that agent-mediated bottom-up coordination addresses.
- **Marx, Karl.** (1867). *Das Kapital* Vol. I. *"Free association of producers"* — the formulation Smoothworld may, with sufficient deliberation, be approximating.

---

A note on dates: this is April 2026, and many of the most relevant papers (the agent-payment-protocol literature in particular) are extremely recent. Citations with arXiv IDs in the 2603–2606 range are from this year. The bibliography is *as of writing*; the field is moving in months.
