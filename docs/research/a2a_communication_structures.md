# A2A Communication Structures — Network Models in Agent Economies

> *"Almost all economic interactions take place within a network of
> relationships."* — Matthew Jackson, *Social and Economic Networks*
> (Princeton, 2008).

Agentworld pairs agents through one of three sampling rules: well-mixed
(Bernoulli on all pairs), scale-free (Barabási-Albert preferential
attachment), or Stochastic Block Model (SBM, sectoral blocks with
intra-block density). The choice of rule predicts what kinds of clusters
appear, how concentrated trade volume becomes, and how robust the
economy is to shocks. This doc surveys the literature behind the three
rules, proposes a fourth (hyperbolic embedding), and maps the choice
to the agentic lever panel of the spatial sandbox.

---

## Why network structure matters

Two economies with identical preference distributions and identical
agents can produce different welfare outcomes purely from how the
agents are connected. Three findings from the economic-network
literature ground the agentworld lever choice.

- **Network position predicts wealth.** Jackson (2008, ch. 3) and
  Bramoullé & Galeotti (2016) survey 30+ years of evidence that an
  agent's degree, betweenness, and clustering coefficient predict its
  share of trade and its share of surplus. Two agents with identical
  preferences and identical capabilities accumulate wealth at different
  rates depending on where they sit in the graph.
- **Cluster formation is endogenous.** Hidalgo and Hausmann's *Product
  Space* (PNAS, 2009) shows that the network of products countries
  export forms a stable community structure that is not predicted by
  geography or income. The structure emerges from production
  complementarity, which in agent-economy terms is sector affinity.
- **Topology selects equilibria.** Acemoglu, Carvalho, Ozdaglar, and
  Tahbaz-Salehi (2012) show that fat-tailed network models produce
  aggregate output fluctuations that vanish under thin-tailed (e.g.
  well-mixed) models, even when the underlying shocks are identical.
  This is the agent-economy analog of the GDP-volatility result: how
  agents are connected determines whether idiosyncratic shocks
  aggregate to systemic ones.

The implication for the sandbox: the network slider is not cosmetic.
Moving from `well_mixed` to `scale_free` changes what equilibria the
engine can reach, not just the path it takes.

---

## The three canonical models, with what each predicts

### Erdős-Rényi / well-mixed

Every pair of agents has probability `p` of being connected. Random,
homogeneous, no preferential structure.

- Engine field: `network_model = "well_mixed"`
- Cluster behavior: no persistent clusters; trade volume per agent is
  approximately uniform around the mean.
- α-direction: low pressure toward folding. Surplus is distributed
  across many small pair encounters rather than concentrated.
- Realism: useful as a null. The actual a2a economy is not well-mixed.

### Barabási-Albert / scale-free

New agents attach preferentially to existing high-degree agents.
Degree distribution follows a power law with exponent ≈ 3 (Barabási &
Albert, 1999).

- Engine field: `network_model = "scale_free"`
- Cluster behavior: degree-driven hubs accumulate trade volume.
  Clustering coefficient is low (hubs connect to many low-degree
  agents) but degree variance is high.
- α-direction: high pressure toward folding. Hubs are the natural
  surplus collectors and the natural site for sub-market spawning.
  Bratton's striated attractor is the scale-free limit.
- Realism: empirical fit to financial trade networks (Boss et al.
  2004), B2B supply-chain networks (Vega-Redondo 2007), and
  agent-to-agent payment graphs in the AP2 / x402 test data (where
  available).

### Stochastic Block Model / SBM

Agents are assigned to blocks; intra-block pairs have probability `p`,
inter-block pairs have probability `q < p`. The block assignment
predicts community structure (Holland, Laskey, Leinhardt 1983;
Karrer & Newman 2011).

- Engine field: `network_model = "sbm"`, with `network_p_local`
  controlling the `p/q` ratio.
- Cluster behavior: tight communities by block; weak inter-block
  trade. The block ≈ sector mapping is the natural agentworld read.
- α-direction: intermediate. Sub-market spawning concentrates within
  blocks rather than at degree hubs. Folds tend to be nested inside
  sectors.
- Realism: good fit to sectoral trade and to ideological clustering in
  norm-space.

### Hyperbolic / Random Geometric

A fourth model worth considering: agents have positions in a hyperbolic
disk, and connection probability decays with hyperbolic distance.
Boguñá et al. (2010, *Nature Communications*) show this model recovers
both power-law degree distributions and high clustering coefficients —
two empirical features that scale-free alone misses.

- Engine field: `network_model = "hyperbolic"` (proposed, not yet in
  engine).
- Cluster behavior: tight local clusters plus long-range hub
  connections. The product-space of Hidalgo and Hausmann fits this
  model well.
- α-direction: high but with structure. Folds spawn at hub sites *and*
  within tight neighborhoods.
- Realism: arguably the best single-model fit to empirical agent-trade
  networks, at the cost of one more parameter (curvature).

The spatial sandbox ships with the three existing models and proposes
hyperbolic as a Week-3 add if the visual experience calls for it.

---

## How the network model interacts with the rest of the lever set

The network model is not isolated. Five known interactions:

1. **Network × capability.** Under scale-free, high-capability agents
   gravitate to hub positions through trade success (Hidalgo's product
   space mechanism). Under well-mixed, capability and degree are
   uncorrelated. The Gini at terminal state differs sharply.

2. **Network × certified fraction.** Under hyperbolic, agents close in
   the embedding share more certified terms (because they have more
   trade history to certify on). Under scale-free, hubs accumulate
   certified terms across many neighborhoods; the periphery has thin
   certification. This produces the Schoenegger
   `verifiable_semantics.md` failure mode: peripheral agents cannot
   transact with each other even when they share preferences.

3. **Network × Pigouvian tax.** Under scale-free, the Pigouvian tax
   collected at hubs dominates total revenue; recycling to humans
   via `human_wealth` produces a strong Gini compression because the
   tax is paid by the wealthiest agents. Under well-mixed, revenue is
   evenly distributed and the compression effect is smaller.

4. **Network × fold-depth cap.** Fold-depth caps bite harder in
   scale-free networks because folding sites are concentrated. The
   same cap in well-mixed barely affects EBI.

5. **Network × compute scarcity.** Under compute scarcity (see
   `compute_and_power_as_constraint.md`), scale-free networks
   distribute compute toward hubs (highest-return trades), which
   reinforces the hub concentration. Well-mixed networks distribute
   compute uniformly. SBM distributes compute by block.

These interactions matter for the spatial sandbox because moving any
one lever changes the consequences of the others. A user moving
"capability" with `network_model = "well_mixed"` sees a different
trajectory than the same move with `network_model = "scale_free"`. The
sandbox does not hide this; the rejection-mix HUD makes the difference
visible per tick.

---

## What this means for the engine

| Change | Path | Cost |
| --- | --- | --- |
| Surface `network_model` and `network_p_local` in the agentic lever panel | dashboard | 0 engine cost; UI work |
| Add `network_model = "hyperbolic"` option | `engine/core/population.py:368-383` (network adjacency builder) | ~40 lines: hyperbolic embedding generator + adjacency from distance |
| Add `network_hyperbolic_curvature` parameter | `engine/core/topology.py` | 1 line |
| Expose per-agent degree centrality in `cast_snapshot_v2` | `engine/core/world.py` snapshot assembler | ~3 lines |
| Stream the network adjacency to the dashboard at run start (for visual layout) | `engine/serve.py` SSE | new event type `adjacency_init` |

The hyperbolic option is the only net-new engine work. The other three
network models exist today. Building the hyperbolic option early
(Week 1 of the implementation plan) keeps the lever panel honest.

Surfacing degree centrality lets the force-directed layout in the
dashboard use degree as a node-size attribute, which is the cleanest
visual signal that the network model is doing something. See
`docs/research/force_directed_trade_graphs.md`.

---

## References

- Jackson, M. O. (2008). *Social and Economic Networks.* Princeton.
- Bramoullé, Y., & Galeotti, A. (2016). *Strategic Interaction and
  Networks.* American Economic Review.
- Hidalgo, C. A., & Hausmann, R. (2009). *The Building Blocks of
  Economic Complexity.* PNAS.
- Acemoglu, D., Carvalho, V. M., Ozdaglar, A., & Tahbaz-Salehi, A.
  (2012). *The Network Origins of Aggregate Fluctuations.*
  Econometrica.
- Barabási, A.-L., & Albert, R. (1999). *Emergence of scaling in
  random networks.* Science.
- Boss, M., Elsinger, H., Summer, M., & Thurner, S. (2004). *Network
  topology of the interbank market.* Quantitative Finance.
- Karrer, B., & Newman, M. E. J. (2011). *Stochastic blockmodels and
  community structure in networks.* Physical Review E.
- Boguñá, M., Papadopoulos, F., & Krioukov, D. (2010). *Sustaining the
  internet with hyperbolic mapping.* Nature Communications.
- `docs/concepts/coasean_bargaining.md` — the partner-discovery
  assumption that network model operationalizes.
