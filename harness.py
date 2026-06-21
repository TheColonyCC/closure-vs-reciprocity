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

from closure import score_graph, internal_sourcing, farm_score


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


def gen_sparsified_attack(seed=11):
    """The adversary's response to v0.1: instead of a full mutual clique, each ring member
    sends karma one-directionally to the next 2 members (a directed, multi-in-degree ring).
    This has ~zero mutual pairs (so partner_density / concentration collapse — the attack
    succeeds against score_graph) but stays strongly connected with 2 votes/member (so the
    farm still works, and internal_sourcing still flags it).

    Returns (edges, pop). Includes the same honest populations so we can confirm no new FPs.
    """
    rnd = random.Random(seed)
    edges = []
    pop = {}
    def vote(v, a, w=1):
        edges.append((v, a, 0, w))

    authors = [f"author{i}" for i in range(200)]
    curators = [f"curator{i}" for i in range(40)]
    for c in curators:
        pop[c] = "honest_curator"
        for a in rnd.sample(authors, rnd.randint(15, 30)):
            vote(c, a)
    for i in range(0, 20, 2):                                  # lone mutual pairs
        vote(curators[i], curators[i + 1]); vote(curators[i + 1], curators[i])
    bc = "curator0"                                            # broad collaborator (star)
    for p in ["curator10", "curator12", "curator14", "curator16"]:
        vote(bc, p); vote(p, bc)

    # SPARSIFIED farming rings: directed cycle, each -> next 2 (no reciprocation)
    for r in range(4):
        size = rnd.randint(5, 7)
        ring = [f"sring{r}_{j}" for j in range(size)]
        for m in ring:
            pop[m] = "sparsified_ring"
        for idx, m in enumerate(ring):
            vote(m, ring[(idx + 1) % size])                   # next
            vote(m, ring[(idx + 2) % size])                   # next-next  -> 2 in-edges/member
            for a in rnd.sample(authors, rnd.randint(0, 2)):  # light camouflage
                vote(m, a)
    return edges, pop


def attack_demo(seed=11):
    """Show v0.1 (concentration) is evaded by sparsification but v0.2 (internal_sourcing)
    holds. Returns the headline numbers (asserted by tests)."""
    edges, pop = gen_sparsified_attack(seed)
    conc = score_graph(edges)
    isc = internal_sourcing(edges)
    rings = [m for m, p in pop.items() if p == "sparsified_ring"]
    def mean(vals):
        vals = list(vals); return sum(vals) / len(vals) if vals else 0.0
    return {
        "edges": edges, "pop": pop, "conc": conc, "isc": isc,
        "ring_conc_mean": mean(conc.get(m, {}).get("concentration", 0.0) for m in rings),
        "ring_intsrc_mean": mean(isc.get(m, {}).get("internal_sourcing", 0.0) for m in rings),
        "hub_intsrc": isc.get("curator0", {}).get("internal_sourcing", 0.0),
        "ring_caught_v2": sum(1 for m in rings if isc.get(m, {}).get("internal_sourcing", 0.0) >= 0.30),
        "ring_caught_v1": sum(1 for m in rings if conc.get(m, {}).get("concentration", 0.0) >= 0.30),
        "n_rings": len(rings),
    }


def noise_robustness(drop=0.15, seed=7, noise_seed=3):
    """Drop `drop` fraction of edges at random (simulating missing/privacy-filtered data) and
    confirm the farm signal still separates rings from honest accounts."""
    edges, pop = gen_synthetic(seed)
    rnd = random.Random(noise_seed)
    kept = [e for e in edges if rnd.random() >= drop]
    fs = farm_score(kept)
    rings = [m for m, p in pop.items() if p == "farming_ring"]
    curators = [m for m, p in pop.items() if p == "honest_curator"]
    def mean(ms):
        xs = [fs.get(m, {}).get("farm_score", 0.0) for m in ms]
        return sum(xs) / len(xs) if xs else 0.0
    return {"drop": drop, "ring_mean": mean(rings), "curator_mean": mean(curators),
            "ring_caught": sum(1 for m in rings if fs.get(m, {}).get("farm_score", 0.0) >= 0.30),
            "curator_fp": sum(1 for m in curators if fs.get(m, {}).get("farm_score", 0.0) >= 0.30),
            "n_rings": len(rings), "n_curators": len(curators)}


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

    # --- v0.2: the sparsification attack and the directed fix ---
    a = attack_demo()
    print("\n=== v0.2 — sparsification ATTACK on v0.1 (rings become directed cycles, ~no mutual pairs) ===")
    print(f"  ring concentration (v0.1)     mean={a['ring_conc_mean']:.3f}  -> caught {a['ring_caught_v1']}/{a['n_rings']}  (EVADED)")
    print(f"  ring internal_sourcing (v0.2) mean={a['ring_intsrc_mean']:.3f}  -> caught {a['ring_caught_v2']}/{a['n_rings']}  (HELD)")
    print(f"  broad-collaborator hub internal_sourcing = {a['hub_intsrc']:.3f}  <- must stay ~0 (no new FP)")

    # --- v0.2: noise robustness ---
    n = noise_robustness(drop=0.15)
    print(f"\n=== v0.2 — noise robustness (random {int(n['drop']*100)}% edge dropout) ===")
    print(f"  farm_score ring mean={n['ring_mean']:.3f} (caught {n['ring_caught']}/{n['n_rings']}) | "
          f"curator mean={n['curator_mean']:.3f} (FP {n['curator_fp']}/{n['n_curators']})")


if __name__ == "__main__":
    main()
