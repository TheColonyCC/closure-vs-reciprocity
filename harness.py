#!/usr/bin/env python3
"""Synthetic separation harness for the closure-vs-reciprocity scorer.

Generates a graph with four populations and shows that `concentration` separates
farming rings from honest behaviour where naive reciprocity does not. The numbers
this prints are the ones quoted in README.md / SPEC.md, so it doubles as a
reproducibility check (the test suite asserts the key inequalities).

Run:  python3 harness.py
"""
import random
from collections import defaultdict

from closure import score_graph


def gen_synthetic(seed=7):
    """Returns (edges, pop) where pop maps node -> population label."""
    rnd = random.Random(seed)
    edges = []
    pop = {}
    def vote(v, a, w=1):
        edges.append((v, a, 0, w))

    # 1) honest broad curators: vote widely on a shared pool of "good authors".
    authors = [f"author{i}" for i in range(200)]
    curators = [f"curator{i}" for i in range(40)]
    for c in curators:
        pop[c] = "honest_curator"
        for a in rnd.sample(authors, rnd.randint(15, 30)):     # broad out-edges
            vote(c, a)
    # genuine collaborators: lone scattered mutual pairs on real work (NOT a clique)
    for i in range(0, 20, 2):
        a, b = curators[i], curators[i + 1]
        vote(a, b); vote(b, a)                                 # the classic false-positive case
    # a "broad collaborator": 4 reciprocal partners who do NOT vote each other
    bc = "curator0"
    for p in ["curator10", "curator12", "curator14", "curator16"]:
        vote(bc, p); vote(p, bc)

    # 2) farming rings: small near-cliques, mutual votes dominate their activity
    for r in range(4):
        size = rnd.randint(4, 7)
        ring = [f"ring{r}_{j}" for j in range(size)]
        for m in ring:
            pop[m] = "farming_ring"
        for m in ring:
            for n in ring:
                if m != n:
                    vote(m, n, w=1)                            # closed clique
            for a in rnd.sample(authors, rnd.randint(0, 3)):   # a little camouflage
                vote(m, a)

    # 3) EDGE CASE — genuine tight community: dense + interlinked but NOT a farm.
    #    Structurally indistinguishable from a ring -> expect FLAGGED. Report honestly.
    comm = [f"genuinecomm_{j}" for j in range(6)]
    for m in comm:
        pop[m] = "tight_genuine_community"
    for m in comm:
        for n in comm:
            if m != n and rnd.random() < 0.8:
                vote(m, n)
        for a in rnd.sample(authors, rnd.randint(4, 10)):      # also vote outside
            vote(m, a)

    return edges, pop


def _stats(key, lst):
    xs = sorted(s[key] for s in lst)
    if not xs:
        return "n=0"
    mean = sum(xs) / len(xs)
    p50 = xs[len(xs) // 2]
    return f"n={len(xs):3d} mean={mean:.3f} p50={p50:.3f} max={xs[-1]:.3f}"


def summarize(thr=0.30, seed=7):
    """Run the demo and return a dict of the headline numbers (used by tests)."""
    edges, pop = gen_synthetic(seed)
    scores = score_graph(edges)
    by_pop = defaultdict(list)
    for v, s in scores.items():
        by_pop[pop.get(v, "author_only")].append(s)
    rings = by_pop["farming_ring"]
    tp = sum(1 for s in rings if s["concentration"] >= thr)
    return {
        "scores": scores, "by_pop": by_pop, "thr": thr,
        "ring_caught": tp, "ring_total": len(rings),
        "fp_curator": sum(1 for s in by_pop["honest_curator"] if s["concentration"] >= thr),
        "fp_community": sum(1 for s in by_pop["tight_genuine_community"] if s["concentration"] >= thr),
    }


def main():
    r = summarize()
    by_pop = r["by_pop"]
    print("=== concentration by population (the proposed metric) ===")
    for p in ["honest_curator", "tight_genuine_community", "farming_ring"]:
        print(f"  {p:24} {_stats('concentration', by_pop[p])}")
    print("\n=== naive_reciprocity (what a reciprocity/volume cap sees) — note the overlap ===")
    for p in ["honest_curator", "tight_genuine_community", "farming_ring"]:
        print(f"  {p:24} {_stats('naive_reciprocity', by_pop[p])}")

    print(f"\n=== threshold concentration >= {r['thr']} ===")
    print(f"  farming_ring caught (TP):        {r['ring_caught']}/{r['ring_total']}")
    print(f"  honest_curator flagged (FP):     {r['fp_curator']}/{len(by_pop['honest_curator'])}  <- must be ~0")
    print(f"  tight_genuine_community flagged: {r['fp_community']}/{len(by_pop['tight_genuine_community'])}  <- honest limit (see SPEC)")

    print("\n=== false-positive guards (lone pair + broad collaborator -> ~0) ===")
    for v in ["curator0", "curator2", "curator3"]:
        s = r["scores"][v]
        print(f"  {v:10} concentration={s['concentration']:.3f} naive={s['naive_reciprocity']:.3f} "
              f"partners={s['n_partners']} density={s['partner_density']:.2f}")

    print("\nNOTE: a tight genuine community is structurally identical to a farm "
          "(closed + reciprocal). The metric flags it too — damp on a CURVE in "
          "concentration, and let an EXTERNAL-quality signal rescue genuine clusters.")


if __name__ == "__main__":
    main()
