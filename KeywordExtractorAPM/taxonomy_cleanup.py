#!/usr/bin/env python3
"""
taxonomy_cleanup.py — the new job of discover/promote: keep the self-growing online
taxonomies tidy. Runs periodically, PER FIELD, over the *_online.json files.

Two data-driven passes (no hardcoding, no model call — reuses the stored centroids):
  1. MERGE near-duplicate clusters (cosine >= merge threshold): the same category that
     fragmented -> merge (support summed, phrases unioned, stronger/standard name kept).
  2. PRUNE noise: a one-off singleton (support == 1) is absorbed into its nearest
     cluster ONLY if very close (>= prune threshold); a genuinely isolated one-off is
     kept as its own category.

Replaces the old sistema-only discover.py/promote.py: works on sistema, sintomo, azione
AND componente, as maintenance of the live taxonomies.

USAGE
    python3 taxonomy_cleanup.py               # tidy all four, in place (with backup)
    python3 taxonomy_cleanup.py --dry-run     # show what WOULD change, touch nothing
    python3 taxonomy_cleanup.py --field componente
    python3 taxonomy_cleanup.py --self-test
"""
import sys
import json
from pathlib import Path

import numpy as np

FIELDS = ["sistema", "sintomo", "azione", "componente"]
MERGE_SIM = {"sistema": 0.85, "sintomo": 0.85, "azione": 0.85, "componente": 0.90}
# prune = absorb a one-off singleton into its nearest cluster ONLY if this close.
# Kept high on purpose: a weak match (e.g. 0.72) is NOT the same category, so a genuine
# "no specific system" singleton stays its own bucket instead of being force-merged.
PRUNE_SIM = {"sistema": 0.82, "sintomo": 0.82, "azione": 0.82, "componente": 0.88}
DEFAULT_MERGE, DEFAULT_PRUNE = 0.85, 0.82


def _cos(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(a @ b / d)


def _merge_two(a, b):
    sa, sb = a["support"], b["support"]
    cen = [(x * sa + y * sb) / (sa + sb) for x, y in zip(a["centroid"], b["centroid"])]
    keep = a
    if b.get("status") == "standard" and a.get("status") != "standard":
        keep = b
    elif sb > sa and not (a.get("status") == "standard" and b.get("status") != "standard"):
        keep = b
    phrases = list(dict.fromkeys(a.get("phrases", []) + b.get("phrases", [])))
    return {"key": keep["key"], "name": keep["name"],
            "description": keep.get("description", ""), "status": keep.get("status", ""),
            "centroid": cen, "support": sa + sb, "phrases": phrases}


def merge_pass(clusters, thr):
    merges = []
    changed = True
    while changed and len(clusters) > 1:
        changed = False
        best, bi, bj = -1.0, None, None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                s = _cos(clusters[i]["centroid"], clusters[j]["centroid"])
                if s > best:
                    best, bi, bj = s, i, j
        if best >= thr:
            merges.append((clusters[bi]["key"], clusters[bj]["key"], round(best, 3)))
            merged = _merge_two(clusters[bi], clusters[bj])
            clusters = [c for k, c in enumerate(clusters) if k not in (bi, bj)]
            clusters.append(merged)
            changed = True
    return clusters, merges


def prune_pass(clusters, thr):
    keep = [c for c in clusters if c["support"] > 1]
    singles = [c for c in clusters if c["support"] == 1]
    absorbed = []
    for sc in singles:
        best, bidx = -1.0, None
        for idx, c in enumerate(keep):
            s = _cos(sc["centroid"], c["centroid"])
            if s > best:
                best, bidx = s, idx
        if bidx is not None and best >= thr:
            keep[bidx] = _merge_two(keep[bidx], sc)
            absorbed.append((sc["key"], keep[bidx]["key"], round(best, 3)))
        else:
            keep.append(sc)
    return keep, absorbed


def cleanup_file(path, field, dry=False):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    clusters = data.get("clusters", [])
    n0 = len(clusters)
    clusters, merges = merge_pass(clusters, MERGE_SIM.get(field, DEFAULT_MERGE))
    clusters, absorbed = prune_pass(clusters, PRUNE_SIM.get(field, DEFAULT_PRUNE))
    clusters.sort(key=lambda c: -c["support"])
    print(f"\n[{field}]  {n0} -> {len(clusters)} clusters "
          f"(merged {len(merges)}, absorbed {len(absorbed)} singletons)")
    for a, b, s in merges[:8]:
        print(f"    merge  {a}  +  {b}   (sim {s})")
    for a, b, s in absorbed[:8]:
        print(f"    absorb {a}  ->  {b}   (sim {s})")
    if not dry:
        Path(str(path) + ".bak").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
        data["clusters"] = clusters
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return n0, len(clusters)


def run(only=None, dry=False):
    try:
        import config
        base = Path(config.BASE_DIR) / "taxonomy_free"
    except Exception:
        base = Path("taxonomy_free")
    fields = [only] if only else FIELDS
    done = 0
    for f in fields:
        p = base / f"{f}_online.json"
        if not p.exists():
            print(f"[{f}] {p.name} yok, atlandi")
            continue
        cleanup_file(p, f, dry)
        done += 1
    print(f"\n{'[DRY RUN] ' if dry else ''}Tidied {done} field(s). "
          f"{'nothing written.' if dry else 'saved (.bak backups written).'}")


def _self_test():
    print("taxonomy_cleanup self-test...")
    clusters = [
        {"key": "POMPA_ACQUA", "name": "POMPA_ACQUA", "status": "data",
         "centroid": [1.0, 0.0, 0.0], "support": 10, "phrases": ["pompa acqua"]},
        {"key": "POMPA_DELL_ACQUA", "name": "POMPA_DELL_ACQUA", "status": "data",
         "centroid": [0.99, 0.02, 0.0], "support": 3, "phrases": ["pompa dell acqua"]},
        {"key": "FILTRO_GASOLIO", "name": "FILTRO_GASOLIO", "status": "data",
         "centroid": [0.0, 1.0, 0.0], "support": 6, "phrases": ["filtro gasolio"]},
        {"key": "POMPA_H2O", "name": "POMPA_H2O", "status": "data",
         "centroid": [0.985, 0.03, 0.0], "support": 1, "phrases": ["pompa h2o"]},
    ]
    merged, m = merge_pass([dict(c) for c in clusters], 0.9)
    assert any(m), m
    pruned, ab = prune_pass(merged, 0.82)
    assert "FILTRO_GASOLIO" in {c["key"] for c in pruned}
    assert sum(c["support"] for c in pruned) == 20
    # a far singleton is NOT absorbed at 0.82
    far = [{"key": "A", "name": "A", "status": "d", "centroid": [1, 0], "support": 9,
            "phrases": []},
           {"key": "B", "name": "B", "status": "d", "centroid": [0.7, 0.7], "support": 1,
            "phrases": []}]
    kept, ab2 = prune_pass(far, 0.82)
    assert len(kept) == 2 and not ab2, (kept, ab2)
    print("taxonomy_cleanup self-test PASSED")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--self-test" in a:
        _self_test()
    else:
        only = a[a.index("--field") + 1] if "--field" in a else None
        run(only=only, dry=("--dry-run" in a))
