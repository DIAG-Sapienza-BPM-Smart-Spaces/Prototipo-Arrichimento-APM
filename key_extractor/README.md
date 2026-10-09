# Keyword extractor APM

Codice dell'estrattore: pipeline, validazione, normalizzazione, tassonomie e valutazioni. La configurazione e in `config.py`; tutti i dati sono in `../data/`.

## Avvio dalla root

```powershell
python -m pip install -r key_extractor/requirements.txt
ollama pull qwen3:8b
ollama pull nomic-embed-text
python key_extractor.py
```

Ollama e il provider predefinito e deve essere attivo su `http://localhost:11434`.
In alternativa, nella stessa sessione PowerShell:

```powershell
$env:LLM_PROVIDER = "openai"
$env:OPENAI_API_KEY = "<chiave API>"
$env:OPENAI_MODEL = "gpt-4.1-mini"
$env:OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
python key_extractor.py
```

`EMBEDDING_PROVIDER` segue `LLM_PROVIDER` se non impostato; puo essere configurato
separatamente per usare un provider misto. Le chiavi vengono lette dall'ambiente;
il file `.env` nella root viene caricato automaticamente, senza sovrascrivere
variabili gia presenti nella sessione. OpenAI riceve testi e materiali
necessari all'elaborazione e richiede un account API con credito disponibile.
La selezione si applica anche a bootstrap e valutazioni. Le configurazioni OpenAI
e miste conservano cache e tassonomie in sottocartelle distinte di
`data/extractor_state/`, identificate dai provider e dai modelli.

Test offline: `python -m unittest discover -s key_extractor/tests` dalla root.

Configurazione consigliata: compilare `.env` nella root. Per OpenAI impostare
`LLM_PROVIDER=openai` e `OPENAI_API_KEY`; lasciare `EMBEDDING_PROVIDER` vuoto
per seguire il provider LLM. Il file e escluso da Git. `.env.example` e il
modello riutilizzabile senza chiavi.

## Dati

- `data/input/`: Excel/CSV originali; viene elaborato il primo file trovato per esecuzione.
- `data/output/`: risultati `processed_<nome>.xlsx`, letti direttamente dalla dashboard. Anche gli input CSV producono Excel.
- `data/resources/`: tassonomia base, mappa materiali e vocabolari.
- `data/extractor_state/learned_mappings.json`: mappature apprese.
- `data/extractor_state/taxonomy_free/`: tassonomie online, cache e risultati di bootstrap.
- `data/eval/`: gold set.

Non eliminare lo stato appreso per pulire gli output. Le tassonomie indotte configurate sono opzionali: se assenti, il router usa la tassonomia base.

## Valutazioni dalla root

```powershell
python key_extractor/eval/name_eval.py --self-test
python key_extractor/eval/cluster_compare.py --self-test
python key_extractor/eval/evaluator.py
```

L'evaluator usa l'output Excel piu recente e `data/eval/gold_standard.xlsx`, che devono avere le stesse righe nello stesso ordine. `name_eval.py` usa `data/eval/name_gold.xlsx` e gli artefatti in `data/extractor_state/taxonomy_free/`. Per opzioni e confronti consultare gli script e `name_eval.py --help`.

Le istruzioni originali sono conservate in `docs/Instructions.docx`; per i percorsi attuali fare riferimento ai README.
