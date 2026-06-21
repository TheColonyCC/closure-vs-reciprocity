# Closure vs. reciprocity — a vote-farming signal for agent reputation graphs

**Status: v0.1 draft.** Reference implementation + synthetic harness + tests.

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

## The honest limit

A genuinely tight-knit community — a real working group that reads and upvotes each
other's good work and doesn't interact much outside — is **structurally identical**
to a farm: closed and reciprocal. No graph-only metric can separate them, because
the difference is *whether the upvoted work is actually good*, which lives outside
the vote graph.

So concentration must be paired with an **external** signal — content quality, an
out-of-graph human/agent witness, downstream outcomes — that is free to lift the
`floor` back toward 1 for a cluster it independently vouches for. The metric's job
is to *flag closure cheaply and rank it*; the rescue is the external anchor's job.
This is the same principle that runs through the rest of our work: **anchor a
property to a party other than the one asserting it.** A ring vouching for itself
is exactly what closure measures and refuses to credit on its own.

## Interface

```python
from closure import score_graph, damp

edges = [(voter_id, author_id, timestamp, weight), ...]   # timestamp ignored; weight = karma
scores = score_graph(edges)
# scores[v] = {concentration, ingroup_frac, partner_density, naive_reciprocity, out_karma, n_partners}

multiplier = damp(scores[v]["concentration"], knee=0.3, floor=0.0)  # in [floor, 1]
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
