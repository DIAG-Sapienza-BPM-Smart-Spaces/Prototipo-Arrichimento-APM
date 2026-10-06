# ProjectSapienza — Regime C: A Self-Constructing Taxonomy for Bus-Maintenance Keyword Extraction

> <mark>**Review notes — changed in the July 2026 cleanup (delete this box before submission).**</mark>
> <mark>The passages edited during the tidy-up are marked inline with highlight below. Summary:
> (1) Section 5 was rewritten into a full folder-and-file map; (2) the evaluation set was
> consolidated into `eval/`; (3) files with Turkish or cryptic names were renamed —
> `tf_c_bootstrap.py`→`taxonomy_bootstrap.py`, `tf_cluster_compare.py`→`cluster_compare.py`,
> `tf_name_eval.py`→`name_eval.py`, `name_gold_doluişte.xlsx`→`name_gold.xlsx`,
> `_yedek/`→`_archive/`; (4) dead code (`azione_extractor.py`) and retired config paths were
> removed.</mark>

## Abstract

ProjectSapienza is a fully local NLP pipeline that converts free-text Italian
bus-maintenance reports (COTRAL fleet data) into **eight structured columns**. Its
distinguishing property — and the empirical question the thesis sets out to answer — is
that the classification categories are **not authored by a human in advance**. Instead,
the system **induces and grows its category inventory directly from the incoming data**,
online, one record at a time. There is no manually curated label set to classify into; the
taxonomy is a by-product of processing the corpus.

The thesis question, stated precisely: *given free-text maintenance notes and no
hand-written taxonomy, can a local LLM-plus-embedding pipeline construct a coherent,
reusable category system on its own — and does that self-induced taxonomy classify new
records as reliably as a human-authored one would?*

**Operating constraints.** The entire pipeline runs offline on a single machine via
[Ollama](https://ollama.com). The reasoning/generation model is `qwen3:8b`; embeddings are
produced by `nomic-embed-text`. No component makes a network call. This is a deliberate
constraint of the study (data locality, reproducibility, no dependence on a hosted API),
not an incidental limitation.

---

## 1. Quick start

**Prerequisites**

- Ollama installed and running locally, with both models pulled:
  ```bash
  ollama pull qwen3:8b
  ollama pull nomic-embed-text
  ```
- Python dependencies: `pip install -r requirements.txt`

**Run a batch**

```bash
# place exactly ONE .xlsx/.csv of maintenance records in  input/
python3 main.py
```

The pipeline reads every row of the input file, processes it, and writes
`output/processed_<inputname>.xlsx` — the original columns plus the eight new ones. At
startup the persisted taxonomies are loaded and their current sizes reported, e.g.:

```
[Regime C] sistema: 16 categories
[Regime C] sintomo: 17 categories
[Regime C] azione: 9 categories
[Regime C] componente: 41 categories
...
[CONFIDENCE] Distribution: {'HIGH': 15, 'MEDIUM': 6, 'LOW': 8}
```

Because the taxonomies are persisted to disk (`taxonomy_free/*_online.json`), they carry
over between runs: a second batch continues to grow the same category inventory rather than
starting from scratch.

**Periodic taxonomy maintenance (optional)**

```bash
python3 taxonomy_cleanup.py --dry-run   # report proposed changes, write nothing
python3 taxonomy_cleanup.py             # apply changes (writes .bak backups first)
```

> **Throughput note.** `qwen3:8b` is a chain-of-thought ("thinking") model. End-to-end
> latency is roughly **6 minutes per record** because each record involves two LLM stages
> plus embedding calls, so a 300-row file takes on the order of 30 hours. Plan full corpus
> runs to execute overnight/unattended. Section 8 discusses how to trade accuracy for
> speed.

---

## 2. The eight output columns and how each is produced

The eight columns fall into three mechanistically distinct groups. Understanding the
difference between them is the key to reading the rest of this document.

### Group A — Self-growing online taxonomies

Four fields are **not** classified against a fixed list. Each holds an *online taxonomy*: a
set of clusters that grows as records arrive. When a new value is encountered, the system
either attaches it to an existing cluster or opens a new one (see §4 for the exact
mechanism). None of these fields ever emits `ALTRO`/"other" — every value is placed
somewhere, either in an existing category or in a freshly created one.

| Column | Semantics | How the taxonomy grows, and how a new category is *named* |
|---|---|---|
| **sistema** | The vehicle system involved (e.g. `TRAZIONE`, `IMPIANTO_FRENANTE`, `CENTRALINE_ELETTRONICHE`). | Online, self-growing. When a genuinely new cluster is created, its label is drawn from a **reference vocabulary of standard system terms** (`reference_vocabulary.json`) — the closest standard term is proposed to the LLM, and if none fits, the LLM invents a canonical label. The vocabulary is a *naming aid only*; it never restricts which clusters may exist. |
| **sintomo** | The reported symptom / failure mode (e.g. `MANCATO_AVVIAMENTO`, `PERDITA_OLIO`). | Identical mechanism to `sistema`, using a **symptom reference vocabulary** (`reference_vocabulary_sintomo.json`) for naming. |
| **azione** | The maintenance action(s) taken. **Multi-valued** (a record may carry several, comma-separated). | Online, self-growing — **not a closed list.** When a new action cluster is created, its label is drawn from a short **standard action list** of ~12 canonical verbs held in `keyword_taxonomy.json` (`SOSTITUZIONE`, `CONTROLLO`, `DIAGNOSI`, `RABBOCCO`, …). That list is used the same way the reference vocabularies above are used: purely to supply a clean canonical name when a cluster is born. An action that matches none of the standard verbs is still admitted — it gets an invented label and becomes a new category. So common actions collapse onto the standard verbs, while genuinely novel actions can still expand the inventory. |
| **componente** | The physical part(s) involved. **Multi-valued.** | Online, self-growing. Unlike the three fields above, componente has **no naming dictionary at all.** When a new cluster is created there is no external term list to consult, so the cluster's canonical label is simply the *normalized part phrase itself* — the LLM-produced part name after cleaning (article/preposition stripping, `O-RING`→`O_RING`, spacing→underscores), e.g. `pompa dell'acqua` → `POMPA_ACQUA`. In other words: for componente, the data *is* the vocabulary. A tighter join threshold (0.88 vs 0.72, see §4) is used because part names are short and lexically dense, so a stricter similarity bar is needed to avoid over-merging distinct parts. |

Why azione and componente are online rather than fixed: the space of maintenance *actions*
is small and fairly stable, but the space of *parts* is large and open-ended, and we did
not want an artificial ceiling on either. Making all four fields share the same online
mechanism also keeps the architecture uniform — one code path, one maintenance routine, one
failure model — rather than special-casing two of them. For azione specifically the online
machinery rarely needs to create a new category (most actions map to the ~12 standard
verbs), so the cost of treating it as online is negligible while the benefit — catching a
genuinely new action type instead of forcing it into `ALTRO` — is retained.

### Group B — Free text (no taxonomy)

| Column | Semantics | How produced |
|---|---|---|
| **luogo** | The location/place named in the report, if any. | Extracted verbatim by the LLM in Stage 2; lightly cleaned. No clustering, no fixed list. |

### Group C — Closed enumerations (fixed lists)

| Column | Semantics | How produced |
|---|---|---|
| **tipo_intervento** | The intervention type. | Snapped to a small **hand-written fixed list** in `keyword_taxonomy.json`. This one *is* a human-authored enum, because the set of intervention types is administratively defined and stable. |
| **esito** | The outcome/result. | Same — a small fixed enum. |

### Auxiliary output

| Column | Semantics |
|---|---|
| **AI_Confidence** | `HIGH` / `MEDIUM` / `LOW`. A self-estimate of how reliable the extraction for that row is, intended to triage which rows a human should review. Produced by `validator.py`. |

---

## 3. Worked example (one record, end to end)

**Input**

```
note:      "BUS NON PARTE. RISCONTRATA CENTRALINA MOTORE GUASTA. SOSTITUZIONE."
material:  STEROWNIK SILNIKA        (a foreign-language spare-part label — here Polish)
```

**Processing trace**

1. **Text cleaning** (`text_cleaner.py`) — normalize whitespace, casing, and punctuation;
   uppercase for consistency.
2. **Cache lookup** (`learned_mappings.json`) — has this exact note been processed before?
   If yes, the stored result is returned and the expensive stages are skipped. Here: no →
   continue.
3. **Stage 1 · free understanding (LLM).** The model reads the note without being shown any
   category list and emits *free-form* interpretive fields — deliberately not the final
   columns yet: `sistema_libero = "centralina motore"`, `sintomo_libero = "non parte"`, an
   action `"sostituito"`, and it registers the foreign material token `STEROWNIK SILNIKA`.
   The purpose of Stage 1 is comprehension, decoupled from the constraint of any label set.
4. **Online assignment of the Group-A fields.** Each free phrase from Stage 1 is routed
   through its field's online taxonomy (`online_taxonomy.py`, `assign()`):
   - Embed the phrase and find the nearest existing cluster. If cosine similarity ≥ the
     field's threshold → **join that cluster** (adopt its canonical label).
   - Otherwise consult the **LLM gate**: present the top-few nearest existing clusters and
     ask "does this phrase correspond to one of these, or is it genuinely new?" If the LLM
     says it matches one → **join** (this catches near-duplicates that the embedding
     similarity narrowly missed). If the LLM says new → **create a new cluster and name
     it** (via the reference vocabulary / standard list, or by invention).
   - Result here: `sistema = CENTRALINE_ELETTRONICHE`, `sintomo = MANCATO_AVVIAMENTO`.
5. **Stage 2 · structured completion (LLM).** With comprehension established, the model
   fills the remaining fields: `tipo_intervento` and `esito` are constrained to their fixed
   lists; `azione`, `componente`, and `luogo` are written freely. The foreign material
   `STEROWNIK SILNIKA` is translated into a clean Italian part name (`CENTRALINA_MOTORE`).
6. **Validation and normalization** (`validator.py`). Closed fields are snapped to a legal
   list value; free/part fields are normalized (`POMPA DELL'ACQUA` → `POMPA_ACQUA`). The
   `azione` and `componente` outputs — being multi-valued — are split on commas and each
   value is passed through its own online taxonomy (as in step 4), then de-duplicated.
7. **Confidence scoring.** Agreement between stages, embedding margins, and list-match
   quality yield an overall label — `HIGH` for this record.

**Output**

```
luogo            N/A
tipo_intervento  SOCCORSO_STRADALE
sintomo          MANCATO_AVVIAMENTO
sistema          CENTRALINE_ELETTRONICHE
azione           SOSTITUZIONE, DIAGNOSI
componente       CENTRALINA_MOTORE          (translated from the Polish material label)
esito            NON_SPECIFICATO
AI_Confidence    HIGH
```

Note that `CENTRALINE_ELETTRONICHE` is a category the original human schema did not contain
— it emerged because the data demanded it. This is exactly the behaviour the thesis is
testing.

---

## 4. Architecture

The system has three logical parts. The first two run per-record inside `main.py`/
`router.py`; the third is an occasional offline maintenance pass.

### ① Online taxonomy growth (embedded within per-record processing)

There is **no separate "build the taxonomy" phase.** The taxonomy is constructed
incrementally as a side effect of classifying records. The core operation is
`OnlineTaxonomy.assign(phrase)` in `online_taxonomy.py`, which implements a
centroid/leader-style online clustering with an LLM safeguard:

```
assign(phrase):
    v = embed(phrase)
    (best, sim) = nearest existing cluster by cosine(v, centroid)
    if sim >= self.sim:                     # confident match
        join(best); return best.label
    if gate enabled:                        # embedding was unsure
        m = LLM_match_existing(phrase, top-k nearest clusters)
        if m is not NONE:
            join(m); return m.label         # duplicate the embedding missed
    label = name(phrase)                    # reference vocab -> match or invent
    create_cluster(v, label); return label
```

Two thresholds govern granularity: the **join threshold** `sim` (0.72 for sistema/sintomo/
azione; 0.88 for componente) decides when a phrase is close enough to merge without asking
the LLM, and the **LLM gate** covers the uncertain region below that bar so the system does
not open a redundant category for something it already knows under a slightly different
surface form. The reference vocabularies (`reference_vocabulary*.json`, the azione standard
list) are consulted **only inside `name()`**, i.e. only when a brand-new cluster is being
labelled. They influence *names*, never *membership*, and never cap the number of
categories.

### ② Per-record classification (runtime)

`router.py::process_row` orchestrates the full path for one record:

```
clean → cache lookup → Stage 1 (free understanding)
      → online assign (sistema, sintomo, azione, componente)
      → Stage 2 (fixed lists + free fields)
      → validate/normalize → confidence → write row
```

Every Group-A value is placed in a real category; nothing is deferred to `ALTRO`.

### ③ Periodic taxonomy maintenance (`taxonomy_cleanup.py`)

Online clustering created incrementally is inevitably slightly order-dependent and can
accumulate two kinds of imperfection: near-duplicate clusters (two centroids that drifted
close) and one-off noise clusters (a typo or hapax that spawned its own category). The
maintenance pass — a redesign of what was previously a "discover/promote" loop — addresses
both, **per field**, using only the stored cluster centroids (no LLM, no embedding
recompute, fully offline and deterministic):

- **Merge pass** — merge two clusters when the cosine similarity of their centroids exceeds
  `MERGE_SIM` for that field.
- **Prune pass** — a support-1 (single-record) cluster is absorbed into its nearest
  neighbour if that neighbour is within `PRUNE_SIM`; otherwise it is kept (a genuinely
  distinct rare category is not force-merged).

`PRUNE_SIM` is deliberately kept high (≈0.82) after an observed failure where a low
threshold wrongly absorbed a distinct singleton into an unrelated cluster. `--dry-run`
reports every proposed change without touching state; the real run writes `.bak` backups
first.

*(Visual flow diagrams for ① and ② are provided alongside this repository.)*

---

## 5. Project layout — every folder and file

```
ProjectSapienza/
├── main.py                         entry point
├── router.py                       per-record orchestrator
├── text_cleaner.py                 raw-text normalization
├── keyword_extractor.py            the two LLM stages + prompts
├── online_taxonomy.py              the self-growing taxonomy engine
├── validator.py                    fixed-field snapping + confidence + material hint
├── name_normalizer.py              naming helper (reference-term shortlist)
├── taxonomy_bootstrap.py           naming-prompt library + standalone batch tool
├── taxonomy_cleanup.py             offline taxonomy maintenance (merge/prune)
├── config.py                       all paths, model names, thresholds
├── keyword_taxonomy.json           fixed enums + standard azione verb list
├── reference_vocabulary.json       sistema naming dictionary
├── reference_vocabulary_sintomo.json   sintomo naming dictionary
├── material_map.json               material→hint dictionary (feeds Stage 1)
├── learned_mappings.json           per-row result cache
├── requirements.txt                Python dependencies
│
├── input/                          the batch(es) to process (ONE .xlsx read per run)
├── output/                         processed_<name>.xlsx results
├── taxonomy_free/                  the LIVE induced taxonomies (system state)
├── eval/                           measurement suite + ground-truth sets
└── _archive/                       backups / archived material (not used at runtime)
```

### 5.1 Entry point and core pipeline (root, `*.py`)

| File | Role |
|---|---|
| `main.py` | Entry point: reads the file in `input/`, iterates rows, writes to `output/`. |
| `router.py` | Per-record orchestrator (clean → cache → Stage 1 → online assign → Stage 2 → validate → confidence). Instantiates the four `OnlineTaxonomy` objects and persists them. |
| `text_cleaner.py` | Raw-text normalization. |
| `keyword_extractor.py` | The two LLM calls — **Stage 1** (free understanding) and **Stage 2** (structured completion). Holds the prompts. |
| `online_taxonomy.py` | The self-growing taxonomy class: `assign()` = embedding nearest → LLM gate → join / create+name. Ships with `--self-test` (offline). |
| `validator.py` | Snaps closed fields to legal values, normalizes free fields, builds the material hint (`validate_material` + `material_map.json`), and computes the confidence label. Declares which fields are closed vs free. |
| `name_normalizer.py` | Helper: shortlists the nearest reference-vocabulary terms to propose as a canonical name when a new category is born. |
| <mark>`taxonomy_bootstrap.py`</mark> | The naming-prompt library (`match-standard` / `invent`) that `online_taxonomy` reuses, plus a standalone batch clustering tool (its `__main__` CLI, used during earlier experiments). <mark>(renamed from `tf_c_bootstrap.py`)</mark> |
| `taxonomy_cleanup.py` | Offline, deterministic maintenance pass over the induced taxonomies (merge duplicates + prune noise). `--dry-run`, `--field`, `--self-test`. |
| `config.py` | Central configuration: file paths, Ollama model names, embedding threshold, batch settings. Everything else imports it. |

### 5.2 Configuration and dictionaries (root, `*.json`)

| File | Role |
|---|---|
| `keyword_taxonomy.json` | Fixed enums for `tipo_intervento` / `esito`, plus the ~12-verb standard **azione** naming list. |
| `reference_vocabulary.json` | Naming dictionary for **sistema** (standard system terms). Used only to label new clusters, never to restrict them. |
| `reference_vocabulary_sintomo.json` | Naming dictionary for **sintomo**. |
| `material_map.json` | Material→hint dictionary. `validate_material` fuzzy-matches the foreign material label and passes a hint into Stage 1. |

### 5.3 Generated state (created/updated by runs)

| Path | Role |
|---|---|
| `learned_mappings.json` | Row-level result cache; lets re-runs skip already-processed rows. Reset with `echo '{}' > learned_mappings.json`. |
| `taxonomy_free/*_online.json` | The **live, persisted taxonomies** — one file per growing field (`sistema`, `sintomo`, `azione`, `componente`). Each records every cluster's canonical label, support count, and absorbed phrases. **This is the system's primary induced output.** Grows across runs. |

### 5.4 Folders

| Folder | Contents / role |
|---|---|
| `input/` | The maintenance-record file(s) to process. `main.py` reads exactly one `.xlsx`/`.csv` per run. Currently: `test_set_100to130rows.xlsx`. |
| `output/` | Results, one `processed_<inputname>.xlsx` per input (original columns + the 8 new ones). |
| `taxonomy_free/` | The four live induced-taxonomy JSONs (see 5.3). |
| `eval/` | The measurement suite — **not part of the runtime path**, used to quantify quality for the thesis. Contains: `evaluator.py` (column-by-column accuracy of a `processed_*.xlsx` against the gold standard), `gold_standard.xlsx` (row-level ground truth for the 8 columns), <mark>`name_gold.xlsx`</mark> (ground truth for naming/clustering scoring), <mark>`name_eval.py`</mark> (scores the induced taxonomy's names against that gold), <mark>`cluster_compare.py`</mark> (compares clustering methods — single/complete/average/DBSCAN — against the gold; this is where average-linkage was chosen "by measurement, not by eye"). <mark>All gold assets now live here (previously `gold_standard.xlsx` sat in the project root).</mark> |
| <mark>`_archive/`</mark> | Backups and archived material kept for provenance; nothing here is imported at runtime. Includes earlier induced-taxonomy snapshots, a `.bak` of the bootstrap module, and `removed_<date>/` where retired files (e.g. the dead `azione_extractor.py`, old experiment JSONs) were moved during cleanup. Safe to ignore or delete. <mark>(renamed from `_yedek/`)</mark> |

---

## 6. Key design decisions (and their rationale)

- **The data constructs the taxonomy; a human only standardizes names.** The category
  inventory is induced from the corpus. Reference vocabularies contribute *canonical
  spellings* for new categories, nothing more — they cannot add, remove, or cap categories.
  This separation is what lets the thesis claim a genuinely data-induced taxonomy.
- **Online, with no cold-start build phase, and no `ALTRO`.** Categories materialize as
  records arrive, so there is no chicken-and-egg preparation step, and every value is placed
  in a concrete category rather than a catch-all bucket.
- **A two-tier "is this new?" decision.** Embedding similarity is the fast first filter; the
  LLM gate adjudicates only the uncertain band. This specifically prevents the creation of a
  *duplicate* category for a value that already exists under a slightly different surface
  form — a failure the embedding alone would occasionally cause.
- **Uniform mechanism across all four growing fields.** sistema, sintomo, azione, and
  componente share one code path, one persistence format, and one maintenance routine. The
  only per-field differences are the join threshold and the naming source. Avoiding
  special-cases keeps behaviour predictable and reviewable.
- **No overfitting, no whack-a-mole.** Vocabulary descriptions are not reactively hand-tuned
  to fix individual misclassifications (doing so perturbs every cluster's ranking), and no
  hard-coded "don't confuse X with Y" rules are inserted. Errors are addressed structurally
  (thresholds, gate, cleanup), not by patching symptoms.
- **Measure, do not eyeball.** Structural choices — e.g. average- vs single-linkage in the
  offline validation experiments — were decided against a labelled gold set, not by
  inspection.

---

## 7. Known limitations and open questions

These are the honest weak points, and the most productive places for a reviewer or
collaborator to push.

- **Eager creation has no fluke guard at entry.** A brand-new phrase creates a category on
  first sight, so a one-off typo can briefly become its own tiny category. `taxonomy_cleanup`
  prunes/merges these after the fact, but a *provisional tier* — a category confirmed only
  after it recurs ≥ N times — would prevent them at ingestion, at the cost of a temporary
  "provisional" status on new categories.
- **The LLM gate covers "new" but not "wrong-join".** The gate fires only when the embedding
  reports "no confident match". If the embedding *wrongly* reports a confident match to the
  wrong cluster, the value joins without any check. Extending the gate to the uncertain band
  (roughly 0.72–0.85) would catch this, at the price of additional LLM calls per record.
- **componente synonym fragmentation.** Spelling/article variants of the same part are
  merged (normalization + strict threshold), but true lexical synonyms (`centralina` vs
  `ECU`) merge only if the embedding places them close. Without a naming dictionary for
  componente, there is no external signal to unify them.
- **No gold set yet for componente / azione / luogo.** Only `sistema` has a labelled gold
  standard, so quantitative accuracy is currently reported only for it; the other fields are
  assessed qualitatively. Building small golds for the remaining fields would make their
  changes measurable rather than anecdotal.
- **Order dependence.** Online clustering depends on the order in which records are seen. The
  periodic cleanup mitigates but does not fully eliminate this; a reviewer may reasonably ask
  for a batch re-clustering baseline for comparison.
- **Throughput.** ≈6 min/record on `qwen3:8b` (a thinking model, two LLM stages). A lighter
  or non-thinking model, or a single-stage prompt, would reduce latency substantially — the
  accuracy trade-off of doing so is not yet quantified.

---

## 8. Extending and debugging

- **Adjust category granularity.** The join threshold is `sim` in `online_taxonomy.py`
  (default 0.72; componente 0.88). A higher value yields more, tighter categories; a lower
  value yields fewer, broader ones.
- **Tune the maintenance pass.** `MERGE_SIM` / `PRUNE_SIM` per field in `taxonomy_cleanup.py`.
  Keep `PRUNE_SIM` high (~0.82) so weakly-related singletons are not force-merged.
- **Disable the LLM gate for a field** (e.g. to speed up componente): pass `gate=False` when
  that field's `OnlineTaxonomy` is constructed in `router.py`. The field then relies on
  embedding similarity alone.
- **Inspect the induced taxonomies.** Read `taxonomy_free/*_online.json`. Each cluster shows
  its canonical label, support count, and the phrases it has absorbed — this is the primary
  artifact for evaluating what the system learned.
- **Offline logic tests.** Every core module carries a `--self-test` that runs without Ollama:
  `python3 online_taxonomy.py --self-test`, `python3 taxonomy_cleanup.py --self-test`.
- **Reset a run cleanly.** Clear the row cache before a fresh full run so no stale result is
  served: `echo '{}' > learned_mappings.json`. (A common pitfall: copying a populated cache
  from a previous configuration causes cache hits that bypass Stage 2 and the online
  assignment, reproducing the *old* configuration's output.)
