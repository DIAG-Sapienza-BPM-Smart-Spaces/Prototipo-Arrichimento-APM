from pathlib import Path

BASE_DIR = Path(__file__).parent

# --- Ollama ---
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_BASE_URL = "http://localhost:11434"
TEMPERATURE = 0.0

# --- Excel column names (names in the incoming data) ---
COL_DESCRIPTION = "Testo Breve 1"
COL_MATERIAL_PREFIX = "materiale /Definizione"

# --- Output keyword columns ---
KEYWORD_COLUMNS = [
    "kw_luogo",
    "kw_tipo_intervento",
    "kw_sintomo",
    "kw_sistema",
    "kw_azione",
    "kw_componente",
    "kw_esito",
    "kw_confidence",
]

# --- File paths ---
TAXONOMY_PATH = BASE_DIR / "keyword_taxonomy.json"
LEARNED_MAPPINGS_PATH = BASE_DIR / "learned_mappings.json"
MATERIAL_MAP_PATH = BASE_DIR / "material_map.json"
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

# --- Operation settings ---
BATCH_SAVE_INTERVAL = 50
MAX_RETRIES = 3

# --- Embedding semantic-match threshold ---
# Cosine-similarity cutoff for accepting the closest taxonomy value in
# validator.semantic_match(). Below this -> "ALTRO".
# Higher = stricter (more ALTRO, fewer silent misclassifications).
# Lower  = looser (fewer ALTRO, more forced/possibly-wrong matches).
# Set to 0.60 from the sweep on the 300-row gold set: overall accuracy was
# identical across all thresholds (threshold-insensitive at this data size), so
# 0.60 was chosen to convert the weak 0.55-0.60 matches into honest ALTRO flags
# (which also feed the new-term discovery pool) while keeping strong matches.
# PROVISIONAL — revisit once more data accumulates.
EMBED_THRESHOLD = 0.60


# --- Regime C: kategori listeleri VERIDEN uretilir (elle yazilan liste degil) ---
# alan -> induced dosya. Listedeki alan induced listeyi kullanir.
INDUCED_FIELDS = {
    "sistema": BASE_DIR / "taxonomy_free" / "induced_taxonomy__0_0.json",
    "sintomo": BASE_DIR / "taxonomy_free" / "induced_taxonomy_sintomo__0_0.json",
}
