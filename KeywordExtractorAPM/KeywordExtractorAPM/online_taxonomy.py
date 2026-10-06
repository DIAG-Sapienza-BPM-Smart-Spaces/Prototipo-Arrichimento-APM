#!/usr/bin/env python3
"""
online_taxonomy.py — a taxonomy that grows AS THE DATA FLOWS. No separate build step.

For each record, the LLM describes a field freely (a phrase). The phrase is assigned
ONLINE, in a THREE-tier match so we don't create duplicate categories:

    1. embedding: close to an existing cluster (cosine >= sim)?  -> JOIN it (fast).
    2. else, LLM GATE: ask the model "does this match one of the nearest EXISTING
       categories, or is it NEW?"  (this is the old discover.py brain, done live) ->
       if it matches -> JOIN that existing cluster (prevents a duplicate the embedding
       missed); if NEW -> continue.
    3. NEW: name it — a standard term from the reference vocabulary if one fits
       (embedding shortlist -> LLM), inventing only if nothing does.

So categories appear from record #1, nothing is ALTRO, and the LLM gate stops the
system from making a new cluster for something that already exists.

The model (embedder + LLM) and the reference vocabulary are injected, so the pure logic
is testable without Ollama (with llm=None the gate is simply skipped).

State (persisted to JSON, grows across runs):
    clusters = [ {key, name, description, status, centroid[], support, phrases[]} ]
"""
import sys
import json
import re
from pathlib import Path

import numpy as np

DEFAULT_SIM = 0.72
GATE_TOPK = 4
BOILERPLATE = ("SISTEMA_DI_", "SISTEMA_DEL_", "SISTEMA_DELLA_", "SISTEMA_",
               "IMPIANTO_DI_", "IMPIANTO_", "CIRCUITO_DI_", "CIRCUITO_",
               "GRUPPO_DI_", "GRUPPO_", "APPARATO_", "DISPOSITIVO_DI_")


def taxonomy_key(name):
    s = re.sub(r"[^A-ZÀ-Ù0-9\s_]", " ", str(name).upper().strip())
    s = re.sub(r"\s+", "_", s.strip())
    for p in BOILERPLATE:
        if s.startswith(p):
            s = s[len(p):]
            break
    return s or "CATEGORIA"


def _cos(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(a @ b / d)


class OnlineTaxonomy:
    def __init__(self, field, embedder=None, llm=None, reference=None,
                 sim=DEFAULT_SIM, path=None, gate=True):
        self.field = field
        self.embedder = embedder
        self.llm = llm
        self.reference = reference or {}
        self.sim = sim
        self.gate = gate                 # LLM "existing or new?" check before creating new
        self.path = Path(path) if path else None
        self.clusters = []
        self._ref_vecs = None
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.clusters = data.get("clusters", [])
            self.sim = data.get("sim", self.sim)

    def save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"field": self.field, "sim": self.sim, "clusters": self.clusters},
            ensure_ascii=False, indent=2), encoding="utf-8")

    def values(self):
        return [c["key"] for c in self.clusters] + ["ALTRO"]

    # ---- core ----
    def assign(self, phrase, embed_fn=None, name_fn=None):
        phrase = str(phrase).strip()
        if not phrase:
            return "ALTRO"
        v = (embed_fn or self._embed)(phrase)

        # 1) confident embedding match -> join
        i, sim = self._nearest(v)
        if i is not None and sim >= self.sim:
            self._absorb(i, v, phrase)
            return self.clusters[i]["key"]

        # 2) LLM gate: maybe it IS an existing category the embedding missed
        j = self._llm_match_existing(phrase, v)
        if j is not None:
            self._absorb(j, v, phrase)
            return self.clusters[j]["key"]

        # 3) genuinely new -> name + create
        name, desc, status = (name_fn or self._name)(phrase, v)
        key = taxonomy_key(name)
        k = self._find_by_key(key)
        if k is not None:
            self._absorb(k, v, phrase)
            return key
        self.clusters.append({"key": key, "name": name, "description": desc,
                              "status": status, "centroid": [float(x) for x in v],
                              "support": 1, "phrases": [phrase]})
        return key

    def _nearest(self, v):
        best, bi = -1.0, None
        for idx, c in enumerate(self.clusters):
            s = _cos(v, c["centroid"])
            if s > best:
                best, bi = s, idx
        return bi, best

    def _absorb(self, i, v, phrase):
        c = self.clusters[i]
        s = c["support"]
        c["centroid"] = [(a * s + float(b)) / (s + 1) for a, b in zip(c["centroid"], v)]
        c["support"] = s + 1
        if phrase not in c["phrases"]:
            c["phrases"].append(phrase)

    def _find_by_key(self, key):
        for idx, c in enumerate(self.clusters):
            if c["key"] == key:
                return idx
        return None

    # ---- LLM gate: existing category, or new? (the discover brain, live) ----
    def _llm_match_existing(self, phrase, v):
        if not self.gate or self.llm is None or not self.clusters:
            return None
        order = sorted(range(len(self.clusters)),
                       key=lambda i: -_cos(v, self.clusters[i]["centroid"]))[:GATE_TOPK]
        opts = "\n".join(
            f"- {self.clusters[i]['key']}: "
            f"{self.clusters[i].get('description') or ', '.join(self.clusters[i].get('phrases', [])[:4])}"
            for i in order)
        prompt = (
            "Un valore estratto da un rapporto di manutenzione autobus:\n"
            f'  "{phrase}"\n\n'
            f"Categorie ESISTENTI piu' simili (campo: {self.field}):\n{opts}\n\n"
            "Il valore corrisponde a UNA di queste categorie esistenti, oppure e' NUOVO?\n"
            "Giudica dal significato, non dalle parole. Rispondi in JSON: "
            '{"corrisponde_a": "<chiave esatta tra quelle sopra, oppure NONE>"}')
        try:
            from taxonomy_bootstrap import _ask
            ans = str(_ask(self.llm, prompt).get("corrisponde_a", "")).strip()
        except Exception:
            return None
        if not ans or ans.upper() == "NONE":
            return None
        ak = taxonomy_key(ans)
        for i in order:
            if self.clusters[i]["key"] == ak:
                return i
        return None

    # ---- naming a genuinely-new cluster ----
    def _ref_vectors(self):
        if self._ref_vecs is None:
            self._ref_vecs = {t: self.embedder.embed_query(f"{t}: {d}")
                              for t, d in self.reference.items()}
        return self._ref_vecs

    def _embed(self, phrase):
        return self.embedder.embed_query(phrase)

    def _name(self, phrase, v):
        from taxonomy_bootstrap import (PROMPT_MATCH_STANDARD, PROMPT_INVENT,
                                    resolve_name, _ask)
        from name_normalizer import shortlist
        if self.reference:
            cand = [t for t, _ in shortlist(v, self._ref_vectors(), 4)]
            options = "\n".join(f"- {t}: {self.reference[t]}" for t in cand)
            try:
                ans = str(_ask(self.llm, PROMPT_MATCH_STANDARD.format(
                    phrases=f"- {phrase}", examples="", options=options)
                ).get("corrisponde_a", ""))
            except Exception:
                ans = "NONE"
            matched, st = resolve_name(ans, cand, fallback_name=None)
            if st == "standard":
                return matched, self.reference[matched], "standard"
        try:
            inv = _ask(self.llm, PROMPT_INVENT.format(phrases=f"- {phrase}", examples=""))
            return (str(inv.get("nome", phrase)).strip(),
                    str(inv.get("descrizione", "")).strip(), "invented")
        except Exception:
            return phrase.upper(), "", "invented"


def _self_test():
    print("online_taxonomy self-test (offline, llm=None so gate is skipped)...")
    VEC = {"freni": [1.0, 0.0, 0.0], "impianto freni": [0.97, 0.10, 0.0],
           "clima": [0.0, 1.0, 0.0], "sedile autista": [0.0, 0.0, 1.0]}
    embed = lambda p: VEC[p]
    def name_fn(phrase, v):
        if v[0] > 0.6: return "FRENI", "d", "standard"
        if v[1] > 0.6: return "CLIMATIZZAZIONE", "d", "standard"
        return "GUIDA", "d", "invented"
    t = OnlineTaxonomy("sistema", sim=0.72)      # llm=None -> gate skipped
    assert t.assign("freni", embed, name_fn) == "FRENI"
    assert t.assign("impianto freni", embed, name_fn) == "FRENI"
    assert len(t.clusters) == 1 and t.clusters[0]["support"] == 2
    assert t.assign("clima", embed, name_fn) == "CLIMATIZZAZIONE"
    assert t.assign("sedile autista", embed, name_fn) == "GUIDA"
    assert len(t.clusters) == 3

    # gate: a stub llm that says a far phrase matches an existing key -> JOIN, no new
    class StubLLM:
        def invoke(self, prompt):
            return '{"corrisponde_a": "FRENI"}'
    t2 = OnlineTaxonomy("sistema", llm=StubLLM(), sim=0.72)
    t2.clusters = [{"key": "FRENI", "name": "FRENI", "description": "d",
                    "status": "standard", "centroid": [1.0, 0.0, 0.0],
                    "support": 5, "phrases": ["freni"]}]
    # "elettrico" is far (cos 0) so embedding says new, but the stub LLM maps it to FRENI
    got = t2.assign("elettrico", lambda p: [0.0, 1.0, 0.0], name_fn)
    assert got == "FRENI" and len(t2.clusters) == 1, (got, len(t2.clusters))
    print("online_taxonomy self-test PASSED")


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        _self_test()
    else:
        print("import OnlineTaxonomy and call .assign(phrase) per record.")
