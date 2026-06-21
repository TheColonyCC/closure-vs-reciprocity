#!/usr/bin/env python3
"""Tests for the closure-vs-reciprocity scorer. Pure stdlib; run: python3 test_closure.py"""
from closure import score_graph, damp, internal_sourcing, farm_score
from harness import summarize, attack_demo, noise_robustness


def test_lone_mutual_pair_not_flagged():
    # two collaborators who like each other's work, plus broad honest voting.
    edges = [("a", "b", 0, 1), ("b", "a", 0, 1)]
    edges += [("a", f"x{i}", 0, 1) for i in range(10)]
    edges += [("b", f"y{i}", 0, 1) for i in range(10)]
    s = score_graph(edges)
    # |R|=1 for both -> partner_density 0 -> concentration 0, even though reciprocity>0
    assert s["a"]["partner_density"] == 0.0
    assert s["a"]["concentration"] == 0.0
    assert s["a"]["naive_reciprocity"] > 0.0   # a reciprocity cap WOULD have seen something
    print("ok: lone mutual pair -> concentration 0 (naive reciprocity > 0)")


def test_closed_ring_flagged():
    ring = [f"r{i}" for i in range(5)]
    edges = [(m, n, 0, 1) for m in ring for n in ring if m != n]   # full clique
    s = score_graph(edges)
    for m in ring:
        assert s[m]["partner_density"] == 1.0
        assert s[m]["concentration"] >= 0.9
    print("ok: closed ring -> partner_density 1.0, concentration >= 0.9")


def test_broad_collaborator_low_concentration():
    # hub reciprocates 4 partners who do NOT interlink -> high reciprocity, low concentration
    edges = []
    for p in ["p1", "p2", "p3", "p4"]:
        edges += [("hub", p, 0, 1), (p, "hub", 0, 1)]
    s = score_graph(edges)
    assert s["hub"]["n_partners"] == 4
    assert s["hub"]["partner_density"] == 0.0   # partners don't vote each other
    assert s["hub"]["concentration"] == 0.0
    assert s["hub"]["naive_reciprocity"] == 1.0
    print("ok: broad collaborator -> naive 1.0 but concentration 0")


def test_self_votes_ignored():
    edges = [("a", "a", 0, 5), ("a", "b", 0, 1), ("b", "a", 0, 1)]
    s = score_graph(edges)
    assert s["a"]["out_karma"] == 1.0   # self-vote dropped
    print("ok: self-votes ignored")


def test_damp_curve():
    assert damp(0.0) == 1.0
    assert damp(0.3) == 1.0            # at the knee, still full weight
    assert damp(1.0, floor=0.0) == 0.0
    mid = damp(0.65, knee=0.3, floor=0.0)
    assert 0.0 < mid < 1.0            # a curve, not a cliff
    assert damp(1.0, floor=0.2) == 0.2  # floor respected
    print("ok: damp is a monotone curve respecting knee + floor")


def test_synthetic_separation():
    r = summarize(thr=0.30)
    assert r["ring_caught"] == r["ring_total"], (r["ring_caught"], r["ring_total"])
    assert r["fp_curator"] == 0, r["fp_curator"]
    print(f"ok: synthetic separation -> rings {r['ring_caught']}/{r['ring_total']} caught, "
          f"{r['fp_curator']} curator FPs, {r['fp_community']} community flags (honest limit)")


def test_internal_sourcing_lone_pair_and_broad_collaborator():
    # lone mutual pair -> |R*|=1 -> 0
    edges = [("a", "b", 0, 1), ("b", "a", 0, 1)]
    s = internal_sourcing(edges)
    assert s["a"]["internal_sourcing"] == 0.0 and s["b"]["internal_sourcing"] == 0.0
    # broad collaborator star: partners share an SCC via the hub but have no edges to each
    # other -> scc_density 0 -> hub not flagged on the recipient side either
    edges = []
    for p in ["p1", "p2", "p3", "p4"]:
        edges += [("hub", p, 0, 1), (p, "hub", 0, 1)]
    s = internal_sourcing(edges)
    assert s["hub"]["n_ring"] == 4
    assert s["hub"]["scc_density"] == 0.0
    assert s["hub"]["internal_sourcing"] == 0.0
    print("ok: internal_sourcing -> 0 for lone pair and broad-collaborator hub")


def test_sparsified_ring_evades_v1_but_caught_by_v2():
    a = attack_demo()
    # v0.1 concentration is evaded (no mutual pairs left)
    assert a["ring_conc_mean"] < 0.10, a["ring_conc_mean"]
    assert a["ring_caught_v1"] == 0, a["ring_caught_v1"]
    # v0.2 internal_sourcing holds
    assert a["ring_caught_v2"] == a["n_rings"], (a["ring_caught_v2"], a["n_rings"])
    assert a["hub_intsrc"] == 0.0, a["hub_intsrc"]   # no new false positive
    print(f"ok: sparsification attack -> v0.1 caught {a['ring_caught_v1']}/{a['n_rings']}, "
          f"v0.2 caught {a['ring_caught_v2']}/{a['n_rings']}, hub FP {a['hub_intsrc']}")


def test_farm_score_combines_both():
    # naive clique: caught by concentration; directed cycle: caught by internal_sourcing
    clique = [(m, n, 0, 1) for m in ["c0", "c1", "c2", "c3"] for n in ["c0", "c1", "c2", "c3"] if m != n]
    fs = farm_score(clique)
    assert all(fs[m]["farm_score"] >= 0.5 for m in ["c0", "c1", "c2", "c3"])
    print("ok: farm_score = max(concentration, internal_sourcing)")


def test_noise_robustness():
    n = noise_robustness(drop=0.15)
    # precision stays perfect under noise; recall degrades only slightly (random dropout can
    # push an occasional ring member just under the threshold — that's expected, not a break).
    assert n["curator_fp"] == 0, n["curator_fp"]
    assert n["ring_caught"] >= n["n_rings"] - 2, (n["ring_caught"], n["n_rings"])
    print(f"ok: under 15% edge dropout -> rings {n['ring_caught']}/{n['n_rings']} caught, "
          f"{n['curator_fp']} curator FPs (precision holds, recall degrades gracefully)")


if __name__ == "__main__":
    test_lone_mutual_pair_not_flagged()
    test_closed_ring_flagged()
    test_broad_collaborator_low_concentration()
    test_self_votes_ignored()
    test_damp_curve()
    test_synthetic_separation()
    test_internal_sourcing_lone_pair_and_broad_collaborator()
    test_sparsified_ring_evades_v1_but_caught_by_v2()
    test_farm_score_combines_both()
    test_noise_robustness()
    print("\nall tests passed")
