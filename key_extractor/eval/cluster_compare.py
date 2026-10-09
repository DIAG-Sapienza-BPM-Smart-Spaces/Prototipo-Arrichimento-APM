#!/usr/bin/env python3
"""
cluster_compare.py — compare clustering methods for Phase 2, MEASURED against
the gold set. Nothing here is chosen by eye.

WHY THIS EXISTS
---------------
taxonomy_bootstrap.py uses average-linkage at sim 0.72. That was picked without ever
comparing it to anything. This script runs the SAME pipeline (same Phase-1 cache,
same naming step, same reference vocabulary) and changes ONLY the clustering
method, then scores every method against name_gold with name_eval. So any
difference in the score is caused by the clustering, nothing else.

METHODS (all pure numpy — no sklearn/hdbscan needed for the first four)
    single linkage     merges by the CLOSEST pair. Prone to "chaining":
                       one bridge phrase can glue two unrelated systems together.
    complete linkage   merges by the FARTHEST pair. Tight, compact clusters;
                       tends to over-split.
    average linkage    merges by the MEAN pair distance. The current default —
                       a middle ground, resists chaining.
    DBSCAN             density based. Points with enough close neighbours form a
                       cluster; lonely points are "noise" (here each noise point
                       becomes its own single-phrase category, so every phrase is
                       still placed — same convention the pipeline expects).
    HDBSCAN            hierarchical DBSCAN, no eps to pick. OPTIONAL: used only if
                       the `hdbscan` package or sklearn's HDBSCAN is importable;
                       otherwise it is skipped with a message. Never a hard error.

HOW TO READ THE RESULT
----------------------
The script prints one row per (method, parameter): weighted accuracy against the
gold, number of categories, records covered. Higher weighted accuracy = better.

DO NOT just pick the single highest number. With ~23-47 phrases that overfits the
threshold to the gold set. Prefer a method that is (a) good across several
thresholds and (b) good on BOTH slices. Run it on each slice and compare.

USAGE (on the machine that has Ollama running)
----------------------------------------------
    # slice A (records 0-150) — needs its Phase-1 cache to exist already
    python3 cluster_compare.py --slice 0_150   --score-gold name_gold.xlsx
    # slice B (records 150-300)
    python3 cluster_compare.py --slice 150_150 --score-gold name_gold.xlsx

    python3 cluster_compare.py --self-test      # offline, no Ollama

The Phase-1 description cache (c_descriptions__*__<slice>.json) must already be
present — this script never re-runs Phase 1, so the LLM's descriptions are held
fixed and only the clustering changes.
"""
import sys
import json
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collections import Counter

import numpy as np


# ==========================================================================
# Clustering — pure numpy, unit-tested by --self-test
# ==========================================================================
def _unit_rows(V):
    Vn = np.asarray(V, dtype=float)
    return Vn / np.clip(np.linalg.norm(Vn, axis=1, keepdims=True), 1e-12, None)


def _labels_from_clusters(clusters, n):
    labels = [-1] * n
    for cid, c in enumerate(sorted(clusters, key=lambda x: -len(x))):
        for i in c:
            labels[i] = cid
    return labels


def agglomerative(V, sim_threshold, linkage="average"):
    """Agglomerative clustering on cosine similarity.

    linkage: 'single' (max pair sim), 'complete' (min pair sim),
             'average' (mean pair sim). The 'average' branch is identical to
             taxonomy_bootstrap.average_linkage — verified in --self-test.
    """
    n = len(V)
    if n == 0:
        return []
    Vn = _unit_rows(V)
    S = Vn @ Vn.T
    clusters = [[i] for i in range(n)]

    def link(a, b):
        vals = [S[i, j] for i in a for j in b]
        if linkage == "single":
            return max(vals)
        if linkage == "complete":
            return min(vals)
        return sum(vals) / len(vals)

    while len(clusters) > 1:
        best, bi, bj = -1.0, None, None
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                s = link(clusters[a], clusters[b])
                if s > best:
                    best, bi, bj = s, a, b
        if bi is None or best < sim_threshold:
            break
        clusters[bi] += clusters[bj]
        del clusters[bj]
    return _labels_from_clusters(clusters, n)


def dbscan_cosine(V, eps_sim, min_samples=2):
    """DBSCAN on cosine similarity. Two points are neighbours if their cosine
    similarity >= eps_sim. Noise points each become their own singleton cluster,
    so every phrase ends up categorised (the pipeline has no 'noise' bucket).
    """
    n = len(V)
    if n == 0:
        return []
    Vn = _unit_rows(V)
    S = Vn @ Vn.T
    neigh = [set(np.where(S[i] >= eps_sim)[0].tolist()) for i in range(n)]

    labels = [-1] * n
    visited = [False] * n
    cid = 0
    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        if len(neigh[i]) < min_samples:
            continue  # provisional noise; may be claimed as a border point below
        labels[i] = cid
        seeds = set(neigh[i]) - {i}
        while seeds:
            j = seeds.pop()
            if not visited[j]:
                visited[j] = True
                if len(neigh[j]) >= min_samples:
                    seeds |= (neigh[j] - {j})
            if labels[j] == -1:
                labels[j] = cid
        cid += 1
    for i in range(n):        # leftover noise -> singleton categories
        if labels[i] == -1:
            labels[i] = cid
            cid += 1
    return labels


def hdbscan_cosine(V, min_cluster_size=2):
    """HDBSCAN via precomputed cosine distance. Returns labels, or None if no
    HDBSCAN implementation is installed (caller then skips this method)."""
    n = len(V)
    if n == 0:
        return []
    Vn = _unit_rows(V)
    D = np.clip(1.0 - Vn @ Vn.T, 0.0, 2.0)
    np.fill_diagonal(D, 0.0)
    impl = None
    try:
        import hdbscan
        impl = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,
                               metric="precomputed")
    except Exception:
        try:
            from sklearn.cluster import HDBSCAN as SKH
            impl = SKH(min_cluster_size=min_cluster_size, metric="precomputed")
        except Exception:
            return None
    labels = list(impl.fit_predict(D.astype(float)))
    cid = max([l for l in labels if l >= 0], default=-1) + 1
    out = []
    for l in labels:               # noise (-1) -> singleton categories
        if l < 0:
            out.append(cid)
            cid += 1
        else:
            out.append(int(l))
    return out


# ==========================================================================
# Naming — reused verbatim from the frozen pipeline (only clustering changes)
# ==========================================================================
def _build_taxonomy(uniq, counts, vecs, labels, min_support,
                    llm, reference, ref_vecs, name_cache):
    """Turn cluster labels into an induced-taxonomy dict, using the EXACT naming
    logic of taxonomy_bootstrap.run (standard term if one fits, else invent; then
    merge clusters that resolve to the same term). Identical clusters are named
    once and cached, so re-naming across methods is cheap."""
    from taxonomy_bootstrap import (group_by_label, taxonomy_key, resolve_name,
                                merge_by_key, PROMPT_MATCH_STANDARD,
                                PROMPT_INVENT, _ask)
    from name_normalizer import shortlist

    groups = group_by_label(labels, uniq)
    kept = {k: g for k, g in groups.items()
            if sum(counts[p] for p in g) >= min_support}

    raw = []
    for _, g in sorted(kept.items(),
                       key=lambda kv: -sum(counts[p] for p in kv[1])):
        support = sum(counts[p] for p in g)
        ck = tuple(sorted(g))
        if ck in name_cache:
            name, status, desc = name_cache[ck]
        else:
            centroid = np.mean([vecs[uniq.index(p)] for p in g], axis=0)
            cand = [t for t, _ in shortlist(centroid, ref_vecs, 4)]
            options = "\n".join(f"- {t}: {reference[t]}" for t in cand)
            phr = "\n".join(f"- {p}" for p in g)
            try:
                ans = str(_ask(llm, PROMPT_MATCH_STANDARD.format(
                    phrases=phr, examples="", options=options)
                ).get("corrisponde_a", ""))
            except Exception:
                ans = "NONE"
            name, status = resolve_name(ans, cand, fallback_name=None)
            if status == "standard":
                desc = reference[name]
            else:
                try:
                    inv = _ask(llm, PROMPT_INVENT.format(phrases=phr, examples=""))
                    name = str(inv.get("nome", g[0])).strip()
                    desc = str(inv.get("descrizione", "")).strip()
                except Exception:
                    name, desc = g[0].upper(), ""
                status = "invented"
            name_cache[ck] = (name, status, desc)
        raw.append({"key": taxonomy_key(name), "name": name, "description": desc,
                    "status": status, "support": support, "phrases": g})

    categories = merge_by_key(raw)
    return {
        "_meta": {"source": "cluster-method comparison", "method_note": "see filename"},
        "sistema": {"description": "Vehicle system, induced from the corpus",
                    "values": [c["key"] for c in categories] + ["ALTRO"],
                    "descriptions": {c["key"]: c["description"] for c in categories}},
        "_provenance": categories,
    }


# ==========================================================================
# Run — needs Ollama (embedder + LLM) on this machine
# ==========================================================================
def _find_cache(slice_tag):
    import config
    from taxonomy_bootstrap import OUT_DIR
    hits = sorted(Path(OUT_DIR).glob(f"c_descriptions__*__{slice_tag}.json"))
    if not hits:
        hits = sorted(Path.cwd().glob(f"c_descriptions__*__{slice_tag}.json"))
    if not hits:
        raise SystemExit(
            f"No Phase-1 cache c_descriptions__*__{slice_tag}.json found.\n"
            f"Run taxonomy_bootstrap.py on this slice first (it caches Phase 1).")
    return hits[0]


def run(slice_tag, gold_path, min_support=3):
    from taxonomy_bootstrap import strip_boilerplate, OUT_DIR
    from name_normalizer import load_reference
    from validator import embedder
    from model_provider import create_llm
    from name_eval import read_gold, score, phrase_to_category  # scoring reuse
    import config

    cache = _find_cache(slice_tag)
    data = json.loads(Path(cache).read_text(encoding="utf-8"))
    phrases = [d["phrase"] for d in data]
    counts = Counter(strip_boilerplate(p) for p in phrases)
    uniq = sorted(counts)
    print(f"slice {slice_tag}: {len(phrases)} records -> {len(uniq)} distinct phrases")
    print(f"cache: {Path(cache).name}\n")

    vecs = np.array([embedder.embed_query(u) for u in uniq], dtype=float)
    reference = load_reference()
    ref_vecs = {t: embedder.embed_query(f"{t}: {d}") for t, d in reference.items()}
    llm = create_llm()

    gold = read_gold(gold_path)

    # method grid. Thresholds swept so the landscape is visible, not one number.
    plans = []
    for lk in ("single", "average", "complete"):
        for t in (0.65, 0.70, 0.72, 0.75, 0.80):
            plans.append((f"{lk}@{t:.2f}", lambda V, t=t, lk=lk: agglomerative(V, t, lk)))
    for eps in (0.70, 0.75, 0.80):
        plans.append((f"dbscan@{eps:.2f}", lambda V, eps=eps: dbscan_cosine(V, eps, 2)))
    plans.append(("hdbscan", lambda V: hdbscan_cosine(V, 2)))

    name_cache = {}
    rows = []
    OUT = Path(OUT_DIR)
    OUT.mkdir(parents=True, exist_ok=True)
    for tag, fn in plans:
        labels = fn(vecs)
        if labels is None:
            print(f"  {tag:16} skipped (HDBSCAN not installed)")
            continue
        tax = _build_taxonomy(uniq, counts, vecs, labels, min_support,
                              llm, reference, ref_vecs, name_cache)
        out = OUT / f"induced_taxonomy__cmp_{slice_tag}_{tag.replace('@','_').replace('.','')}.json"
        out.write_text(json.dumps(tax, ensure_ascii=False, indent=2), encoding="utf-8")
        pred = {ph: c["key"] for c in tax["_provenance"] for ph in c["phrases"]}
        _, stats = score(gold, pred)
        rows.append((tag, stats["weighted"], len(tax["_provenance"]), stats["covered"]))

    rows.sort(key=lambda r: -r[1])
    print(f"\n{'method':16} {'weighted':>9} {'#cat':>5} {'scored':>7}")
    print("-" * 42)
    for tag, w, ncat, cov in rows:
        print(f"{tag:16} {w:>8.1%} {ncat:>5} {cov:>7}")
    print("\nReminder: do NOT cherry-pick the top row. Prefer a method that stays "
          "high across thresholds AND on both slices. Compare this table to the "
          "other slice before deciding.")


# ==========================================================================
def _self_test():
    print("cluster_compare self-test (offline, pure numpy)...")

    # 1) average branch must equal the frozen pipeline's average_linkage
    try:
        from taxonomy_bootstrap import average_linkage
        V = np.array([[1, 0], [0.9, 0.1], [0, 1], [0.1, 0.9], [0.7, 0.7]], dtype=float)
        for t in (0.5, 0.7, 0.9):
            assert agglomerative(V, t, "average") == average_linkage(V, t), t
        print("  average == taxonomy_bootstrap.average_linkage  OK")
    except ImportError:
        print("  (taxonomy_bootstrap not importable here; skipping equality check)")

    # 2) single linkage chains through a bridge; complete linkage does not
    a = np.array([[1, 0, 0], [0.98, 0.10, 0]], dtype=float)
    bridge = np.array([[0.72, 0.70, 0]], dtype=float)
    b = np.array([[0.10, 0.98, 0], [0, 1, 0]], dtype=float)
    V2 = np.vstack([a, bridge, b])
    n_single = len(set(agglomerative(V2, 0.68, "single")))
    n_complete = len(set(agglomerative(V2, 0.68, "complete")))
    assert n_single < n_complete, (n_single, n_complete)
    print(f"  single chains ({n_single} clusters) < complete ({n_complete})  OK")

    # 3) DBSCAN: two dense clusters + one outlier -> 2 clusters + 1 singleton
    V3 = np.array([[1, 0], [0.99, 0.02], [0.98, 0.03],
                   [0, 1], [0.02, 0.99], [0.01, 0.98],
                   [0.7, 0.72]], dtype=float)          # outlier between the two
    lab = dbscan_cosine(V3, 0.98, min_samples=2)
    sizes = sorted(Counter(lab).values(), reverse=True)
    assert sizes == [3, 3, 1], (lab, sizes)
    print(f"  DBSCAN 3+3+1 -> {sizes}  OK")

    # 4) DBSCAN with an unreachable eps -> every point its own singleton
    lab2 = dbscan_cosine(V3, 0.999999, min_samples=2)
    assert len(set(lab2)) == len(V3), lab2
    print("  DBSCAN all-singletons at extreme eps  OK")

    # 5) empty input is safe for every method
    assert agglomerative([], 0.7, "single") == []
    assert dbscan_cosine([], 0.7) == []
    assert hdbscan_cosine([]) == []
    print("  empty-input guards  OK")

    # 6) labels are contiguous 0..k-1 and cover every point
    for lab_ in (agglomerative(V2, 0.68, "average"), dbscan_cosine(V2, 0.8)):
        assert set(lab_) == set(range(len(set(lab_)))), lab_
        assert len(lab_) == len(V2)
    print("  contiguous full-coverage labels  OK")

    print("cluster_compare self-test PASSED")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--self-test" in args:
        _self_test()
    elif "--slice" in args:
        slice_tag = args[args.index("--slice") + 1]
        gold = (args[args.index("--score-gold") + 1]
                if "--score-gold" in args else str(Path(__file__).resolve().parents[2] / "data" / "eval" / "name_gold.xlsx"))
        ms = int(args[args.index("--min-support") + 1]) if "--min-support" in args else 3
        run(slice_tag, gold, ms)
    else:
        print("Usage:\n"
              "  python3 cluster_compare.py --slice 150_150 "
              "--score-gold name_gold.xlsx\n"
              "  python3 cluster_compare.py --self-test")
