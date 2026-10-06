"""
Azione Extractor — Idea 1: deterministic verb extraction + rule-based mapping.

Takes the LLM's free text/cleaned text as input, performs keyword-based
deterministic mapping to the azione taxonomy, and applies the K5 filter
(eliminates smontaggio for access purposes, cleans up noise).

This module is not dependent on the LLM: same input -> always same output.
"""
import re

import config

# Azione taxonomy value -> list of keywords/patterns that trigger that value
# Patterns are searched on the cleaned (uppercase) text.
AZIONE_PATTERNS = {
    "SOSTITUZIONE": [
        r"\bSOSTITU", r"\bSOST\b", r"\bSOST\.", r"\bCAMBI",
        r"\bMONTAT[AO]\b", r"\bMONTAGGIO NUOV",
    ],
    "RIPARAZIONE": [
        r"\bRIPARAZ", r"\bRIPARAT", r"\bAGGIUST", r"\bRISANAT",
    ],
    "CONTROLLO": [
        r"\bISPEZION", r"\bVERIFIC", r"\bRICERCA GUAST",
        r"\bRICERCA PERDIT", r"\bRICERCA DI PERDIT", r"\bMESSA .* IN PRESSIONE",
        r"\bIMMISSIONE AZOTO",
        # "CONTROLLO" alone, but not if "CONTROLLO DIAGNOSI" (that belongs to DIAGNOSI)
        r"\bCONTROLL(?!O DIAGNOSI)(?!O IMPIANTO ELETTRICO PEDAL)",
    ],
    "PULIZIA": [
        r"\bPULIZIA", r"\bPULIT", r"\bLAVAGGIO", r"\bLAVAT", r"\bSGRASS",
    ],
    "RIPRISTINO": [
        # except level ripristino (RABBOCCO) and connettore ripristino (included in PULIZIA)
        r"\bRIPRISTIN(?!O CORRETTO LIVELLO)(?!O LIVELLO)(?! CONNETTOR)(?!O CONNETTOR)",
        r"\bRESET", r"\bRIATTIVAZ",
    ],
    "RABBOCCO": [
        r"\bRABBOCC", r"\bRIPRISTINO .*LIVELLO", r"\bRIPRISTINO CORRETTO LIVELLO",
        r"\bAGGIUNT[AO] .*(OLIO|LIQUID|REFRIGER|ANTIGEL)", r"\bAGGIUNTO OLIO",
        r"\bCARICA .*(GAS|REFRIGER)", r"\bRICARICA", r"\bIMMISSIONE .*(GAS|REFRIGER)",
        r"\bRIFORNIMENT",
    ],
    "REGOLAZIONE": [
        r"\bREGOLAZ", r"\bTARATUR", r"\bREGISTRAZ", r"\bCALIBRAZ", r"\bPROGRAMMAZ",
    ],
    "MANUTENZIONE_PROGRAMMATA": [
        r"\bMANUTENZIONE (PROGRAMMATA|T1|T2)", r"\bMANUTEZIONE", r"\bTAGLIAND",
        r"\bMANUT\.\s*(PROGR|T1|T2)", r"\bT1\b.*\bT2\b", r"\bMANUTENZIONE\b",
    ],
    "DIAGNOSI": [
        r"\bDIAGNOSI", r"\bDIAGNOSTIC", r"\bCANCELLAZIONE (ERRORI|GUASTI)",
        r"\bLETTURA (CODIC|ERRORI)", r"\bERRORI IN MEMORIA", r"\bRECUPERO CODIC",
    ],
    "SMONTAGGIO_RIMONTAGGIO": [
        r"\bS/R\b", r"\bSMONTAGGIO", r"\bRIMONTAGGIO", r"\bSMONTAT", r"\bRIMONTAT",
    ],
}

# Which actions count as MAIN work. When main work is present, an S/R
# (smontaggio/rimontaggio) is done only to ACCESS the part -> it is accessory,
# not the primary action. Previously such S/R was DROPPED; now it is kept in the
# accessory column so nothing is lost.
MAIN_WORK = {"SOSTITUZIONE", "RIPARAZIONE"}

# When scheduled maintenance (MANUTENZIONE_PROGRAMMATA) is present, only it and
# any top-up (RABBOCCO) are considered primary; every other detected action is
# routine/preparatory and goes to the accessory column.
MP_KEEP_PRIMARY = {"MANUTENZIONE_PROGRAMMATA", "RABBOCCO"}


def extract_azione(cleaned_text: str, azione_libera: str = "", embedder=None, azione_values=None):
    """
    Performs deterministic azione extraction on the cleaned text.

    Returns a tuple (principale, accessoria), both comma-separated strings.
    NOTHING is ever dropped: every detected action ends up in exactly one of the
    two columns, so principale + accessoria together = ALL detected actions.

    - principale  : the substantive / main actions.
    - accessoria  : preparatory / access-only / routine actions that used to be
                    filtered out (access-only S/R, extra steps during scheduled
                    maintenance, etc.).

    Safety net: if the code finds NO azione (unknown/new operation),
    and embedder+azione_values are provided, maps the LLM's free azione summary
    to the closest taxonomy value via embedding (result goes to principale).
    """
    # NOTE: azione_libera (LLM summary) is only used for the safety net,
    # main extraction is done on the cleaned text (less noise).
    haystack = cleaned_text.upper()

    found = []
    for azione, patterns in AZIONE_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, haystack):
                found.append(azione)
                break

    # Remove duplicates, preserve order of first appearance
    seen = set()
    unique = []
    for a in found:
        if a not in seen:
            seen.add(a)
            unique.append(a)

    # --- Decide which detected actions are ACCESSORY (instead of dropping them) ---
    accessory = set()

    # K5: access-only S/R -> accessory (only when a main work is also present)
    if "SMONTAGGIO_RIMONTAGGIO" in unique and any(m in unique for m in MAIN_WORK):
        accessory.add("SMONTAGGIO_RIMONTAGGIO")

    # Scheduled maintenance: everything except MP/RABBOCCO -> accessory
    if "MANUTENZIONE_PROGRAMMATA" in unique:
        for a in unique:
            if a not in MP_KEEP_PRIMARY:
                accessory.add(a)

    principale = [a for a in unique if a not in accessory]
    accessoria = [a for a in unique if a in accessory]

    # Defensive: never leave principale empty while actions exist
    if not principale and accessoria:
        principale, accessoria = accessoria, []

    # --- SAFETY NET: fall back to embedding if the code found nothing ---
    if not principale and not accessoria:
        if embedder is not None and azione_values:
            fallback = _embedding_fallback(cleaned_text, azione_libera, embedder, azione_values)
            if fallback:
                return fallback, ""
        return "ALTRO", ""

    return ", ".join(principale), ", ".join(accessoria)


def _embedding_fallback(cleaned_text, azione_libera, embedder, azione_values):
    """When the code cannot find a known word: map the LLM summary/text to the closest azione value via embedding. For new/unseen operations."""
    import numpy as np
    query = (azione_libera or cleaned_text).strip()
    if not query:
        return ""
    try:
        qv = np.array(embedder.embed_query(query))
        best, best_score = None, -1.0
        for val in azione_values:
            if val in ("ALTRO",):
                continue
            vv = np.array(embedder.embed_query(val))
            denom = (np.linalg.norm(qv) * np.linalg.norm(vv))
            if denom == 0:
                continue
            score = float(np.dot(qv, vv) / denom)
            if score > best_score:
                best_score, best = score, val
        # Use if close enough, otherwise ALTRO
        # Same cutoff as the rest of the system (config.EMBED_THRESHOLD),
        # so there is one single place to tune embedding acceptance.
        if best_score >= getattr(config, "EMBED_THRESHOLD", 0.60):
            return best
    except Exception:
        pass
    return ""
