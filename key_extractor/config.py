from pathlib import Path
import hashlib
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env", override=False)
DATA_DIR = BASE_DIR.parent / "data"
RESOURCES_DIR = DATA_DIR / "resources"
EVAL_DIR = DATA_DIR / "eval"

# --- Providers: ollama oppure openai ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "").strip().lower() or LLM_PROVIDER
for _provider in (LLM_PROVIDER, EMBEDDING_PROVIDER):
    if _provider not in {"ollama", "openai"}:
        raise ValueError("LLM_PROVIDER e EMBEDDING_PROVIDER devono essere ollama o openai")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))

# --- Ollama ---
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))

# Centroidi e cache di modelli diversi devono restare separati.
STATE_DIR = DATA_DIR / "extractor_state"
if (LLM_PROVIDER != "ollama" or EMBEDDING_PROVIDER != "ollama"
        or OLLAMA_MODEL != "qwen3:8b"
        or OLLAMA_EMBEDDING_MODEL != "nomic-embed-text"
        or OLLAMA_BASE_URL != "http://localhost:11434"):
    _llm_model = OPENAI_MODEL if LLM_PROVIDER == "openai" else OLLAMA_MODEL
    _embedding_model = OPENAI_EMBEDDING_MODEL if EMBEDDING_PROVIDER == "openai" else OLLAMA_EMBEDDING_MODEL
    _identity = f"{LLM_PROVIDER}:{_llm_model}|{EMBEDDING_PROVIDER}:{_embedding_model}|{OLLAMA_BASE_URL}"
    _digest = hashlib.sha256(_identity.encode()).hexdigest()[:12]
    STATE_DIR = STATE_DIR / f"{LLM_PROVIDER}_{EMBEDDING_PROVIDER}_{_digest}"
TAXONOMY_FREE_DIR = STATE_DIR / "taxonomy_free"

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
TAXONOMY_PATH = RESOURCES_DIR / "keyword_taxonomy.json"
LEARNED_MAPPINGS_PATH = STATE_DIR / "learned_mappings.json"
MATERIAL_MAP_PATH = RESOURCES_DIR / "material_map.json"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

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
    "sistema": TAXONOMY_FREE_DIR / "induced_taxonomy__0_0.json",
    "sintomo": TAXONOMY_FREE_DIR / "induced_taxonomy_sintomo__0_0.json",
}
