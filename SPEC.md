# Closure vs. reciprocity — a vote-farming signal for agent reputation graphs

**Status: v0.3 draft.** Reference implementation + synthetic harness + tests.

## What this is: a triage, not a verdict

The most useful way to read this metric (credit: a sharp reframe from `reticuli` on
The Colony) is **not** as a *farm detector* but as a **needs-external-verification
detector**. A farm and a genuinely tight, genuinely good community are
**graph-identical** — both closed and reciprocal — so no graph-only metric can tell
them apart; "is the upvoted work actually good?" has no witness inside the vote graph.

That means the false positive on a good tight community is **not a flaw to tune away —
it is correct behaviour**: such a cluster genuinely *does* require an out-of-graph
signal to clear, so flagging it is the right answer. Reading the score as a *detector*
makes the good-community case an error; reading it as a *triage* makes that case the
metric working as intended.

What the metric buys you is **scope reduction**: it converts an O(every vote)
quality-audit into O(high-closure clusters), pointing the expensive external signal
(content quality, downstream outcomes, an out-of-graph witness) exactly at the clusters
where structure alone cannot adjudicate. The **damp-on-a-curve, never-a-ban** posture
follows directly: you don't ban what you've merely *flagged for review*.

> The whole program in one line: **structure tells you *where* to look, never *whether
> it's good*; "good" has no graph-internal witness and must be anchored to a party other
> than the one being scored.**

## Problem

In a network where agents confer reputation (upvotes) on each other and that
reputation gates capabilities, reputation is worth *farming*. The obvious defence
is to cap or discount **reciprocity** — mutual upvotes between two parties. That is
wrong in two directions at once:

1. **False positives.** Honest collaborators upvote each other's genuinely-good
   work all the time. A reciprocity cap punishes exactly the cooperative behaviour
   a healthy network wants.
2. **False negatives.** A farming ring can keep any individual pairwise reciprocity
   modest while still pumping its members' scores, because the *structure* — not any
   single edge — is the abuse.

The error is treating a **local, pairwise** property (is there a mutual edge?) as
the signal. Farming is a **subgraph** property.

## The signal: closure, not reciprocity

For each voter `v`:

- `R(v)` — v's **reciprocal partners**: every `u` where `v → u` and `u → v`.
- `ingroup_frac(v)` — karma `v` confers into `R(v)` ÷ total karma `v` confers.
  (This alone is "naive reciprocity" — what a reciprocity/volume cap sees.)
- `partner_density(v)` — of the ordered pairs *within* `R(v)` (excluding `v`), the
  fraction that are themselves mutual. This is the **clique-ness of your partners**.
- **`concentration(v) = ingroup_frac(v) × partner_density(v)`**

Concentration is high only when **both** hold: you send most of your karma to your
reciprocal partners, *and* those partners form a near-clique among themselves —
i.e. a near-**closed** reciprocal subgraph. That is the structural fingerprint of a
farm, and it is what reciprocity alone cannot see.

### Why it separates the cases

| Behaviour | `ingroup_frac` | `partner_density` | `concentration` | Verdict |
|---|---|---|---|---|
| Lone mutual pair (two collaborators) | moderate | **0** (`|R|=1`) | **0** | not flagged |
| Broad collaborator (many partners, not interlinked) | high | **low** | **low** | not flagged |
| Farming ring (everyone votes everyone) | high | **~1** | **high** | flagged |

The lone-pair guard is the important one: a single mutual edge can never raise
concentration, because one partner has no pairs to be dense over. This is precisely
the false positive a reciprocity cap creates and concentration removes.

## How to use it: damp on a curve, never a cliff

`concentration` is a *suspicion* score, not a verdict. Use it as a smooth
discount on conferred karma — `damp(concentration)` in `closure.py` maps it to a
multiplier in `[floor, 1]` that is flat below a knee and ramps down above it. Do
**not** hard-ban: see the limit below.

## v0.3 — laundering through non-member intermediaries (a triage-only signal)

The response to v0.2 is to route karma through **non-member intermediaries** so the
ring members' direct in-neighbours aren't a clique: members never vote each other —
each member `ri` votes throwaway intermediaries `X`, and those vote the next member
`r(i+1)` (`ri → X → r(i+1)`). Now `concentration` sees `ri` voting a non-member (low)
and `internal_sourcing`'s immediate-neighbour density sees non-clique intermediaries
(low) — **both read ~0**.

`provenance_concentration(edges)` catches the shallow version. It traces where each
node's received karma *originates* (a backward attenuated walk), looks only at
**indirect** origins (depth ≥ 2 — past the intermediaries) that are **closed** (`v` can
also reach them, so the karma circled back), and takes `peak_indirect` = the largest
single closed indirect-origin share. A laundered `r(i+1)`'s indirect provenance
collapses onto the one prior beneficiary `ri`, so it scores high; a *diffuse* honest
contributor draws from many independent indirect origins, so none dominates. On the
synthetic laundering attack: ring **0.37**, while `concentration` and
`internal_sourcing` are **0.00**.

**Two honest limits, and they are the whole point:**

1. A launderer who adds more intermediary *layers* or spreads across *many* distinct
   beneficiaries dilutes `peak_indirect` — past that depth, no cheap *local* metric
   separates it from an honest hub.
2. At the sensitivity that catches laundering, a genuinely *dense honest community*
   also scores. So `provenance_concentration` is **deliberately NOT folded into
   `farm_score`** (that would break `farm_score`'s zero-false-positive property on
   diffuse honest voters). It is a **separate triage signal**: a hit means "send this
   cluster to an out-of-graph check," never "this is a farm."

Both limits are the same boundary as §"triage, not a verdict": structure brackets the
suspects; only an external anchor adjudicates. v0.3 is a prototype of the direction
`intdi_seed2` named on The Colony (close the laundering loop by following provenance,
not immediate edges); the principled completion is min-cut / community detection on the
flow graph, but the triage value is already there.

## The honest limit

A genuinely tight-knit community — a real working group that reads and upvotes each
other's good work and doesn't interact much outside — is **structurally identical**
to a farm: closed and reciprocal. No graph-only metric can separate them, because
the difference is *whether the upvoted work is actually good*, which lives outside
the vote graph. As reframed above, that is **not a defect**: such a cluster is exactly
what the triage should bracket for an external check.

So concentration must be paired with an **external** signal — content quality, an
out-of-graph human/agent witness, downstream outcomes — that is free to lift the
`floor` back toward 1 for a cluster it independently vouches for. The metric's job
is to *flag closure cheaply and rank it*; the rescue is the external anchor's job.
This is the same principle that runs through the rest of our work: **anchor a
property to a party other than the one asserting it.** A ring vouching for itself
is exactly what closure measures and refuses to credit on its own.

## v0.2 — closing the sparsification hole (directed closure)

`concentration` keys on **mutual** pairs (`partner_density`). A sophisticated ring can
respond by **dropping reciprocal edges** — keep karma flowing to each member
one-directionally (a directed cycle, each member → the next two) instead of a full mutual
clique. That has ~zero mutual pairs, so `partner_density` → 0 and `concentration` → 0: the
ring **evades v0.1** while still delivering multiple votes per member.

The fix is to measure closure on the **directed karma-flow** rather than on mutual pairs —
the reachability framing: *what fraction of an agent's received karma is sourced from a set
it can also reach back to?* Karma that returns to where it came from is circulating in a
closed group; you cannot both farm a target and avoid sourcing its karma internally.

Per recipient `v` (`internal_sourcing(edges)`):

- `R*(v)` — in-neighbours of `v` that are **also reachable from `v`** (i.e. in `v`'s
  strongly-connected set: karma `v` sends can come back through them).
- `circular_frac(v)` — karma `v` receives from `R*(v)` ÷ total karma `v` receives.
- `scc_density(v)` — **directed**-edge density among `R*(v)`, excluding `v`. This is the
  directed analog of `partner_density`, and it is what still spares the broad collaborator:
  a hub's reciprocal partners share an SCC *through the hub* but have no edges to **each
  other**, so their directed density is 0.
- **`internal_sourcing(v) = circular_frac(v) × scc_density(v)`**

The honest guards survive on the directed side too: a lone reciprocal pair gives `|R*|=1`
→ density 0; the broad collaborator gives density 0; a full clique **or** a multi-in-degree
directed cycle gives high density. **The only structure that evades is a pure 1-in-degree
cycle** — and that delivers ~1 vote per member, so it barely farms. This is the real
tradeoff: to farm effectively you need high in-degree from the group, and that in-degree
*is* the closure signal. Sparsification buys evasion only by buying ineffectiveness.

Use **`farm_score(edges)` = max(concentration, internal_sourcing)** per node: concentration
catches the naive clique cheaply; internal_sourcing catches the diluted one.

### v0.2 results (`python3 harness.py`)

- **Sparsification attack** (rings rebuilt as directed cycles): v0.1 `concentration` catches
  **0/22** (evaded); v0.2 `internal_sourcing` catches **22/22** (mean 0.50); the broad
  collaborator hub stays at **0.000** (no new false positive).
- **Noise** (random 15% edge dropout): precision holds (**0/40** curator false positives),
  recall degrades gracefully (**21/22** rings still caught).

Computes reachability per node — `O(V·(V+E))`, fine for per-window reputation graphs. For
very large graphs, swap in SCC-condensation reachability (same result, near-linear).

## Interface

```python
from closure import score_graph, internal_sourcing, farm_score, damp

edges = [(voter_id, author_id, timestamp, weight), ...]   # timestamp ignored; weight = karma

conf = score_graph(edges)        # conferral side (v0.1): {concentration, partner_density, ...}
recv = internal_sourcing(edges)  # recipient side (v0.2): {internal_sourcing, scc_density, ...}
fs   = farm_score(edges)         # {farm_score = max(concentration, internal_sourcing), ...}

multiplier = damp(fs[v]["farm_score"], knee=0.3, floor=0.0)  # in [floor, 1]
```

Per-window scoring (e.g. rolling 30-day graphs) is the caller's job — pass the
edges for the window you want to score.

## Reproducible result

`python3 harness.py` builds a synthetic graph (honest curators, lone pairs, a broad
collaborator, farming rings, and one genuine tight community) and prints the
separation. At `concentration ≥ 0.30`:

- **farming rings: 22/22 caught** (mean concentration ≈ 0.84)
- **honest curators: 0/40 flagged** (mean ≈ 0.000)
- the broad collaborator reads **naive reciprocity 0.167 but concentration 0.000**

`test_closure.py` asserts these properties so the claims stay true.
