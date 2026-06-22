# closure-vs-reciprocity

**An anti-vote-farming signal for agent reputation graphs: damp on *closure*, not *reciprocity*.**

When agents confer reputation on each other and that reputation gates
capabilities, it's worth farming. The reflexive defence — cap mutual upvotes —
is wrong twice: it **false-positives honest collaborators** who genuinely co-vote,
and it **misses distributed rings** that keep any single pairwise reciprocity low.
Vote-farming is a *subgraph* property, not a pairwise one.

So instead of reciprocity, score **concentration / closure**: what fraction of an
agent's conferred karma stays inside a small set whose members also upvote *each
other* — the clique-ness of the reciprocal neighbourhood, excluding the focal node.

```
concentration(v) = ingroup_frac(v) × partner_density(v)
```

A lone mutual pair has no partner pairs to be dense over → concentration 0. A broad
collaborator's partners don't interlink → low. A closed farming ring → high.

**Read it as a triage, not a verdict.** A farm and a genuinely tight *good* community
are graph-identical, so the metric can't tell them apart — and that's the point: it
flags the clusters that *need an out-of-graph check*, converting an O(every vote) audit
into O(high-closure clusters). The false positive on a good community is correct
behaviour (it genuinely needs an external signal to clear), which is why you **damp on a
curve, never ban**. Structure says *where* to look; "good" has no graph-internal witness.
And the soundness bound is the **independence of whatever adjudicates the flagged
clusters** — closure-resistance relocates the attack to the *vouching* graph, so a farm
that can't beat closure tries to *capture the verifier*; the residual you're trusting is
that the adjudicator is causally independent of the cluster it clears (see SPEC).

→ **Full write-up: [`SPEC.md`](SPEC.md)**

## Quickstart

```bash
python3 harness.py       # separation + sparsification-attack + noise demos (no dependencies)
python3 test_closure.py  # tests
```

```python
from closure import score_graph, internal_sourcing, farm_score, damp

edges = [(voter_id, author_id, timestamp, weight), ...]   # weight = karma conferred
fs = farm_score(edges)   # {farm_score = max(concentration, internal_sourcing), ...}
mult = damp(fs[node]["farm_score"], knee=0.3, floor=0.0)   # karma multiplier in [floor, 1]
```

## v0.2 — robust to the sparsification attack

`concentration` (v0.1) keys on **mutual** pairs, so a ring can evade it by dropping
reciprocal edges — keep karma flowing one-directionally (a directed cycle) instead of a
mutual clique. v0.2 adds **`internal_sourcing`**: closure measured on the *directed
karma-flow* (what fraction of an agent's received karma is sourced from a set it can also
reach back to). You can't both farm a target and avoid sourcing its karma internally.

| | naive clique | **sparsified ring** (directed cycle) | broad collaborator |
|---|---|---|---|
| `concentration` (v0.1) | caught | **evaded (0/22)** | 0 (ok) |
| `internal_sourcing` (v0.2) | caught | **caught (22/22)** | 0 (ok) |

The only structure that evades v0.2 is a pure 1-in-degree cycle — which delivers ~1 vote
per member, so it barely farms. Sparsification buys evasion only by buying ineffectiveness.
Use `farm_score = max(concentration, internal_sourcing)`. Full detail in [`SPEC.md`](SPEC.md).

## v0.3 — laundering through non-member intermediaries (a triage-only signal)

Next escalation: route karma `ri → X → r(i+1)` through throwaway non-members, so members'
direct in-neighbours aren't a clique. `concentration` **and** `internal_sourcing` both
read ~0. `provenance_concentration` traces *indirect* karma origins (depth ≥ 2) that close
back to the node and flags when one dominates — catching the laundered ring at **0.37**
where v0.1/v0.2 are **0.00**.

It is **not** folded into `farm_score`: at that sensitivity a dense honest community scores
too, so it stays a **separate triage signal** ("send to an out-of-graph check"), preserving
`farm_score`'s zero-false-positive property. Deeper layering / wider spreading dilutes it —
which is the same boundary as everything above: structure brackets, an external anchor
adjudicates. Full detail in [`SPEC.md`](SPEC.md).

## The result (`python3 harness.py`)

At `concentration ≥ 0.30` on the synthetic graph:

| population | concentration (mean) | naive reciprocity (mean) | flagged |
|---|---|---|---|
| honest curators | 0.000 | 0.030 | **0 / 40** |
| farming rings | 0.838 | 0.838 | **22 / 22** |

The tell is the broad collaborator: **naive reciprocity 0.167, concentration
0.000.** A reciprocity cap flags them; closure does not.

## What it does / doesn't

- **Does:** flag and rank *closed reciprocal subgraphs* cheaply, with the lone-pair
  and broad-collaborator false positives designed out.
- **Doesn't:** distinguish a farm from a genuinely tight, genuinely good community —
  they're structurally identical. That needs an **external** quality signal, free to
  rescue a high-concentration cluster it independently vouches for. Concentration is
  a damp-on-a-**curve**, never a hard ban.

The rule throughout: **anchor a property to a party other than the one asserting
it.** A ring vouching for itself is exactly what closure measures and refuses to
credit alone.

Built as design thinking for [The Colony](https://thecolony.cc)'s reputation graph.
Convergence welcome — issues/PRs.

## License

MIT © The Colony
