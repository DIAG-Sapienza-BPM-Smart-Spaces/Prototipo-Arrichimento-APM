"""
evaluator.py — Automated evaluation comparing against Gold Standard.

Fixes compared to previous evaluator.py:
- Row ORDER (index) matching instead of text matching: prevents identical texts (seat x3,
  maintenance x2) from crossing over in pandas merge and ruining accuracy.
- Multi-value comparison is done order-independent (set).
- Field-based + overall accuracy + breakdown of erroneous rows.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import config

# Columns to be tested (new names in main.py)
TEST_COLUMNS = [
    "TestoBreve_Luogo",
    "TestoBreve_TipoIntervento",
    "TestoBreve_Sintomo",
    "TestoBreve_Sistema",
    "TestoBreve_Azione_Principale",
    "TestoBreve_Azione_Accessoria",
    "TestoBreve_Componente",
    "TestoBreve_Esito",
]


def _norm(value):
    """Converts a cell value to a set for order-independent comparison."""
    return set(
        p.strip().upper()
        for p in str(value).split(",")
        if p.strip() and p.strip().upper() != "NAN"
    )


def compare_values(ai_value, human_value) -> int:
    """Comparisons two values as sets. 1 if the same, 0 otherwise."""
    a, h = _norm(ai_value), _norm(human_value)
    if not a and not h:
        return 1
    return 1 if a == h else 0


def evaluate_pipeline(processed_path: str, gold_standard_path: str, verbose: bool = True):
    print("\n" + "=" * 62)
    print(" AUTOMATED EVALUATION (Gold Standard comparison)")
    print("=" * 62)

    try:
        df_ai = pd.read_excel(processed_path)
        df_gold = pd.read_excel(gold_standard_path)
    except Exception as e:
        print(f"ERROR: File could not be read: {e}")
        return None

    # --- Matching by ROW ORDER (NOT text merge) ---
    n_ai, n_gold = len(df_ai), len(df_gold)
    if n_ai != n_gold:
        print(f"WARNING: Row counts differ (AI={n_ai}, Gold={n_gold}).")
        print("Matching will be row-based up to the first min(rows).")
    N = min(n_ai, n_gold)

    # Order validation: are original texts aligned?
    desc = f"{config.COL_DESCRIPTION} (Originale)"
    if desc in df_ai.columns and desc in df_gold.columns:
        mismatch = sum(
            1 for i in range(N)
            if str(df_ai[desc].iloc[i])[:40].strip() != str(df_gold[desc].iloc[i])[:40].strip()
        )
        if mismatch > 0:
            print(f"WARNING: Text order is misaligned in {mismatch} rows! "
                  "Ensure both files are in the same order.")
        else:
            print(f"✓ Row order is aligned ({N} rows).")

    print(f"\nEvaluating on {N} rows...\n")

    scores = {}
    errors = {c: [] for c in TEST_COLUMNS}

    for col in TEST_COLUMNS:
        if col not in df_ai.columns or col not in df_gold.columns:
            print(f"  Warning: {col} not found, skipping.")
            continue
        correct = 0
        for i in range(N):
            match = compare_values(df_ai[col].iloc[i], df_gold[col].iloc[i])
            correct += match
            if match == 0:
                errors[col].append((i, df_ai[col].iloc[i], df_gold[col].iloc[i]))
        acc = correct / N * 100
        scores[col] = acc
        label = col.replace("TestoBreve_", "")
        ikon = "OK" if acc >= 90 else ("~ " if acc >= 70 else "XX")
        print(f" [{ikon}] {label:16}: %{acc:6.2f}  ({correct}/{N})")

    if scores:
        overall = sum(scores.values()) / len(scores)
        print("-" * 62)
        print(f" OVERALL ACCURACY: {overall:.2f}%")
        print("-" * 62)

    # Error breakdown (optional)
    if verbose:
        print("\n--- ERRONEOUS ROWS (field-based) ---")
        for col in TEST_COLUMNS:
            if errors.get(col):
                label = col.replace("TestoBreve_", "")
                print(f"\n[{label}]")
                for i, ai_v, gold_v in errors[col]:
                    print(f"  row {i:2}: AI={str(ai_v)!r}  GOLD={str(gold_v)!r}")

    return scores


if __name__ == "__main__":
    processed_files = list(config.OUTPUT_DIR.glob("processed_*.xlsx"))
    gold_file = config.EVAL_DIR / "gold_standard.xlsx"

    if not processed_files:
        print(f"ERROR: No processed_*.xlsx found in {config.OUTPUT_DIR}.")
    elif not gold_file.exists():
        print(f"ERROR: No gold_standard.xlsx found in {gold_file.parent}.")
    else:
        latest = max(processed_files, key=lambda p: p.stat().st_mtime)
        print(f"Evaluated output: {latest.name}")
        print(f"Gold standard: {gold_file.name}")
        evaluate_pipeline(str(latest), str(gold_file))
