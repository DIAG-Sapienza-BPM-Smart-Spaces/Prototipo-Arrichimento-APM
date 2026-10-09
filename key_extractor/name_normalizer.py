"""
name_normalizer.py — turn an invented category name into a standard workshop term.

WHY THIS EXISTS
---------------
The discovery pipeline's decisions are good but its NAMES are not. With an 8B local
model we repeatedly saw invented labels:

    cooling system      -> "SISTEMA DI RIGENERAZIONE LIQUIDO ANTIGELO"
    cooling system      -> "SISTEMA DI RIGENERAZIONE LIQUIDO REFRIGERANTE"
    hydraulics          -> "SISTEMA DI RIGENERAZIONE FLUIDI"

The cluster was right every time; the word "rigenerazione" was invented. Names are
what humans and downstream systems see, so they need an external anchor.

HOW IT WORKS  (fully automatic — no human in the loop)
------------------------------------------------------
    1. embedding shortlists the K nearest terms in reference_vocabulary.json
    2. the LLM answers ONE focused multiple-choice question:
       "is this the same system as one of these standard terms, or none of them?"
    3. match    -> the standard term replaces the invented name  (status: normalized)
       no match -> the invented name is kept, flagged non-standard (status: non_standard)

This is the same embedding-shortlists / LLM-decides pattern that worked for Gate 2.
We do NOT decide by a similarity threshold alone: in this domain unrelated systems
sit at 0.65-0.80 cosine, so a bare threshold is not trustworthy.

The reference vocabulary is a NAMING dictionary, not the taxonomy. It is broader on
purpose, so a genuinely new category can still get a standard name.

USAGE
-----
    from name_normalizer import normalize_name
    result = normalize_name("SISTEMA DI RIGENERAZIONE LIQUIDO REFRIGERANTE",
                            "circuito che raffredda il motore", embedder, llm)
    # -> {"canonical": "RAFFREDDAMENTO", "status": "normalized", ...}

    python name_normalizer.py --self-test
"""
import sys
import json
import re
from pathlib import Path

import numpy as np
import config

REF_PATH = config.RESOURCES_DIR / "reference_vocabulary.json"
TOP_K = 4


# ==========================================================================
# Pure logic — unit-tested by --self-test
# ==========================================================================
def load_reference(path=None):
    """Flatten the grouped reference file into {TERM: description}."""
    p = Path(path) if path else REF_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    flat = {}
    for group, terms in data.items():
        if group.startswith("_"):
            continue
        for term, desc in terms.items():
            flat[term] = desc
    return flat


def cosine(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    d = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(a @ b / d)


def shortlist(query_vec, ref_vecs, k=TOP_K):
    """Return [(term, similarity), ...] — the k nearest reference terms."""
    scored = [(t, cosine(query_vec, v)) for t, v in ref_vecs.items()]
    scored.sort(key=lambda x: -x[1])
    return scored[:k]


def normalize_key(s):
    s = str(s).upper().strip()
    s = re.sub(r"[^A-ZÀ-Ù0-9\s_]", " ", s)
    s = re.sub(r"\s+", "_", s.strip())
    for p in ("SISTEMA_DI_", "SISTEMA_DEL_", "SISTEMA_", "IMPIANTO_DI_", "IMPIANTO_"):
        if s.startswith(p):
            s = s[len(p):]
            break
    return s


def resolve_decision(llm_answer, candidates, proposed_name):
    """
    Turn the LLM's answer into a result.
      llm_answer : the term it chose, or "NONE"
      candidates : the shortlisted reference terms offered to it
    Returns (canonical_name, status, matched_term).
    """
    ans = normalize_key(llm_answer) if llm_answer else "NONE"
    if ans and ans != "NONE":
        for term in candidates:
            if normalize_key(term) == ans:
                return term, "normalized", term
    # backstop: the invented name IS literally a standard term
    for term in candidates:
        if normalize_key(proposed_name) == normalize_key(term):
            return term, "normalized", term
    return proposed_name, "non_standard", ""


# ==========================================================================
# LLM step
# ==========================================================================
PROMPT = """Un sistema automatico ha individuato una nuova categoria di guasti e le ha
dato questo nome provvisorio:

  nome proposto : {name}
  descrizione   : {desc}

Ecco alcuni termini STANDARD da manuale d'officina:
{options}

Domanda: la categoria descritta sopra corrisponde a UNO di questi termini standard,
oppure a NESSUNO di essi?

Giudica dal SIGNIFICATO, non dalle parole usate.
Rispondi in JSON: {{"corrisponde_a": "<termine esatto tra quelli sopra, oppure NONE>"}}"""


def _ask(llm, prompt):
    raw = llm.invoke(prompt)
    txt = re.sub(r"```json|```", "", raw)
    s, e = txt.find("{"), txt.rfind("}")
    return json.loads(txt[s:e + 1])


def normalize_name(proposed_name, proposed_desc, embedder, llm,
                   reference=None, k=TOP_K):
    """
    Full pipeline. Returns:
      {"canonical", "status", "matched", "proposed", "shortlist"}
    status is "normalized" (standard term adopted) or "non_standard" (kept as-is).
    """
    reference = reference or load_reference()
    ref_vecs = {t: embedder.embed_query(f"{t}: {d}") for t, d in reference.items()}
    qvec = embedder.embed_query(f"{proposed_name}: {proposed_desc}")
    cand = shortlist(qvec, ref_vecs, k)
    cand_terms = [t for t, _ in cand]

    options = "\n".join(f"- {t}: {reference[t]}" for t in cand_terms)
    try:
        ans = str(_ask(llm, PROMPT.format(name=proposed_name, desc=proposed_desc,
                                          options=options)).get("corrisponde_a", ""))
    except Exception:
        ans = "NONE"

    canonical, status, matched = resolve_decision(ans, cand_terms, proposed_name)
    return {"canonical": canonical, "status": status, "matched": matched,
            "proposed": proposed_name,
            "shortlist": [(t, round(s, 3)) for t, s in cand]}


# ==========================================================================
def _self_test():
    print("name_normalizer self-test...")

    ref = load_reference()
    assert "RAFFREDDAMENTO" in ref and "CENTRALINE_ELETTRONICHE" in ref
    assert "TACHIGRAFO" in ref and "INFOTAINMENT" in ref
    print(f"  reference vocabulary: {len(ref)} standard terms")

    # shortlist picks the nearest terms
    rv = {"RAFFREDDAMENTO": [1, 0, 0], "FRENI": [0, 1, 0], "PORTE": [0, 0, 1]}
    sl = shortlist([0.9, 0.2, 0], rv, k=2)
    assert [t for t, _ in sl] == ["RAFFREDDAMENTO", "FRENI"], sl

    cands = ["RAFFREDDAMENTO", "CLIMATIZZAZIONE"]

    # the real case: invented name, LLM recognises the standard term
    canon, status, matched = resolve_decision(
        "RAFFREDDAMENTO", cands, "SISTEMA DI RIGENERAZIONE LIQUIDO REFRIGERANTE")
    assert (canon, status) == ("RAFFREDDAMENTO", "normalized"), (canon, status)

    # genuinely new: LLM says NONE -> invented name kept, flagged
    canon2, status2, _ = resolve_decision("NONE", cands, "SISTEMA PEDANA DISABILI")
    assert (canon2, status2) == ("SISTEMA PEDANA DISABILI", "non_standard")

    # backstop: proposed name already IS a standard term, even if the LLM fumbles
    canon3, status3, _ = resolve_decision("", cands, "sistema di raffreddamento")
    assert (canon3, status3) == ("RAFFREDDAMENTO", "normalized"), (canon3, status3)

    # boilerplate-insensitive matching
    assert normalize_key("sistema di raffreddamento") == normalize_key("RAFFREDDAMENTO")
    print("name_normalizer self-test PASSED")


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        _self_test()
    else:
        ref = load_reference()
        print(f"Reference vocabulary: {len(ref)} standard terms")
        for t in sorted(ref):
            print(f"  {t}")
