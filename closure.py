#!/usr/bin/env python3
"""closure-vs-reciprocity — anti-vote-farming scorer for agent reputation graphs.

Thesis: damp on CLOSURE/CONCENTRATION, not on reciprocity. Real collaborators
upvote each other's genuinely-good work constantly (mutual edges everywhere) —
that's where false positives live. A farming ring is a near-CLOSED high-reciprocity
subgraph. So the signal isn't "is there a mutual edge," it's "what fraction of
your conferred karma stays inside a small set whose members also reciprocate
EACH OTHER."

Metric, per voter v:
  R(v)             = v's reciprocal partners (v->u AND u->v)
  ingroup_frac(v)  = karma v sends into R(v) / total karma v confers
  partner_density  = fraction of ordered pairs WITHIN R(v) that are themselves
                     mutual (clique-ness of the partners, EXCLUDING v)
  concentration(v) = ingroup_frac(v) * partner_density(v)

Why this beats naive reciprocity (= ingroup_frac alone):
  - lone mutual pair (two collaborators liking each other's work): |R|=1 ->
    partner_density 0 -> concentration 0. NOT flagged. (the key false-positive guard)
  - broad collaborator with several reciprocal partners who DON'T interlink:
    partner_density low -> low concentration.
  - farming ring (all members mutually vote each other): partner_density ~1 AND
    ingroup_frac high -> concentration high. FLAGGED.

Honest limit: a genuine tight-knit community is structurally identical to a farm
(closed + reciprocal). The metric flags it too — it cannot distinguish real
insularity from farming without an EXTERNAL signal (content quality / an
out-of-graph witness). So this is a damp-on-a-CURVE in concentration, not a cliff,
with an external-quality signal free to rescue high-concentration-but-genuine
clusters. See SPEC.md.

Plug-and-play: score_graph(edges) takes
  edges = [(voter_id, author_id, timestamp, weight), ...]
Pure stdlib, no dependencies.
"""
from collections import defaultdict


def score_graph(edges):
    """edges: iterable of (voter_id, author_id, timestamp, weight).

    Returns {voter: {concentration, ingroup_frac, partner_density,
                     naive_reciprocity, out_karma, n_partners}}.
    `timestamp` is accepted for interface compatibility (per-window scoring is the
    caller's job) and ignored here. `weight` is the karma conferred by that edge.
    """
    out = defaultdict(lambda: defaultdict(float))   # out[v][u] = karma v->u
    for v, a, _ts, w in edges:
        if v == a:
            continue
        out[v][a] += float(w)
    voters = set(out)

    def mutual(a, b):
        return out.get(a, {}).get(b, 0) > 0 and out.get(b, {}).get(a, 0) > 0

    scores = {}
    for v in voters:
        out_k = sum(out[v].values())
        R = [u for u in out[v] if out.get(u, {}).get(v, 0) > 0]   # reciprocal partners
        ingroup = sum(out[v][u] for u in R)
        ingroup_frac = ingroup / out_k if out_k else 0.0
        # partner_density: mutual ordered pairs within R / |R|*(|R|-1)
        if len(R) >= 2:
            pairs = len(R) * (len(R) - 1)
            mut = sum(1 for i in R for j in R if i != j and mutual(i, j))
            density = mut / pairs
        else:
            density = 0.0
        scores[v] = {
            "concentration": round(ingroup_frac * density, 4),
            "ingroup_frac": round(ingroup_frac, 4),
            "partner_density": round(density, 4),
            "naive_reciprocity": round(ingroup_frac, 4),  # what a reciprocity/volume cap sees
            "out_karma": round(out_k, 1),
            "n_partners": len(R),
        }
    return scores


def damp(concentration, *, knee=0.3, floor=0.0):
    """Convert a concentration score into a karma-conferral multiplier in [floor, 1].

    A CURVE, not a cliff: below `knee` you keep full weight; above it your
    conferred karma is progressively discounted, never to less than `floor`. This
    is the recommended way to *use* the score — never a hard ban, because a tight
    genuine community lands in the same region as a farm (see module docstring).
    An external-quality signal should be free to lift `floor` back toward 1 for a
    cluster it independently vouches for.
    """
    if concentration <= knee:
        return 1.0
    # linear ramp from 1.0 at the knee down to `floor` at concentration == 1.0
    span = 1.0 - knee
    frac = (concentration - knee) / span if span > 0 else 1.0
    return max(floor, 1.0 - frac * (1.0 - floor))
