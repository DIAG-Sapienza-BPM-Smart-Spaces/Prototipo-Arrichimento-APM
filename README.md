# Arricchimento APM

L'estrattore arricchisce i record di manutenzione; la dashboard legge direttamente i risultati. Tutti i dati sono nella cartella `data/`.

```text
main_dashboard.py          Avvio dashboard
app.py                     Interfaccia Streamlit
utils/                     Caricamento dati e temi
requirements.txt           Dipendenze dashboard
Dockerfile, .dockerignore  Container dashboard
key_extractor.py          Avvio estrattore
key_extractor/             Codice e configurazione estrattore
  eval/                    Script di valutazione
  requirements.txt         Dipendenze estrattore
data/
  input/                   Excel/CSV originali
  output/                  Excel arricchiti, letti dalla dashboard
  dashboard/               Excel aggiuntivi caricati dall'interfaccia
  dashboard_state/         Suggerimenti della dashboard
  resources/               Tassonomia base, materiali e vocabolari
  extractor_state/          Mappature apprese e taxonomy_free/
  eval/                    Gold set per le valutazioni
docs/                      Report e istruzioni originali
```

## Avvio

Dalla root, in un ambiente Python con le dipendenze installate:

```powershell
python -m pip install -r requirements.txt -r key_extractor/requirements.txt
ollama pull qwen3:8b
ollama pull nomic-embed-text
python key_extractor.py
python main_dashboard.py
```

Ollama e il provider predefinito e deve essere attivo su `http://localhost:11434`. In alternativa e disponibile OpenAI, come descritto sotto. Modelli e parametri sono in `key_extractor/config.py`. La dashboard si apre su http://localhost:8501.

## Usare OpenAI

Il file `.env` nella root viene caricato automaticamente dall'estrattore.
Contiene provider, modelli, URL Ollama, timeout e temperatura. Per usare OpenAI
impostare `LLM_PROVIDER=openai` e compilare `OPENAI_API_KEY`, quindi avviare
`python key_extractor.py`. `EMBEDDING_PROVIDER` vuoto segue il provider LLM.
Il file e escluso da Git; `.env.example` contiene il modello senza segreti.
Le variabili gia impostate nella sessione hanno precedenza sul file `.env`.

Installare le dipendenze dell'estrattore e impostare le variabili nella stessa sessione PowerShell:

```powershell
$env:LLM_PROVIDER = "openai"
$env:OPENAI_API_KEY = "<chiave API>"
$env:OPENAI_MODEL = "gpt-4.1-mini"
$env:OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
python key_extractor.py
```

La chiave viene letta da `.env` o dall'ambiente e non va inserita nel codice. Con questa configurazione anche gli embedding usano OpenAI e Ollama non serve. I testi e i materiali necessari all'elaborazione vengono inviati alle API OpenAI, con i costi previsti dal proprio account.

Per tornare a Ollama: `$env:LLM_PROVIDER = "ollama"`. Per una configurazione mista si puo impostare separatamente `$env:EMBEDDING_PROVIDER = "ollama"` oppure `"openai"`; se non impostata segue il provider LLM.

La pipeline, il bootstrap e le valutazioni condividono la selezione del provider. Lo stato della configurazione Ollama predefinita resta in `data/extractor_state/`; le configurazioni OpenAI o miste usano sottocartelle distinte per provider e modelli, evitando di mescolare centroidi e cache. I risultati rimangono sempre in `data/output/` e sono letti dalla stessa dashboard. La temperatura configurata viene usata dal client Ollama; il client OpenAI usa quella predefinita del modello.

Implementazione basata sulla [Responses API e output JSON](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) e sull'[API Embeddings](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create).

Test offline dell'integrazione:

```powershell
python -m unittest discover -s key_extractor/tests
```

## Flusso dei dati

1. Inserire Excel o CSV in `data/input/`.
2. Eseguire `python key_extractor.py`: elabora un file per esecuzione e produce `data/output/processed_<nome>.xlsx`, anche per input CSV.
3. Aprire la dashboard o premere **Reload data** se gia aperta. Legge direttamente `data/output/`: non occorre copiare i risultati.

La dashboard legge anche `data/dashboard/`, dove salva gli Excel caricati dalla barra laterale. Gli ordini sono deduplicati per `Claim`, mantenendo il record del file modificato piu recentemente. Dall'interfaccia si possono eliminare i caricamenti aggiuntivi; gli output dell'estrattore vengono elencati separatamente.

I percorsi sono ancorati alla root del progetto e non dipendono dalla directory di avvio. L'estrattore puo sovrascrivere il risultato omonimo. Input, output e caricamenti sono esclusi da Git; vocabolari e stato appreso esistente sono conservati. I suggerimenti in `data/dashboard_state/suggestions.json` richiedono revisione manuale per essere promossi nelle tassonomie.

## Valutazioni

```powershell
python key_extractor/eval/name_eval.py --self-test
python key_extractor/eval/cluster_compare.py --self-test
python key_extractor/eval/evaluator.py
```

I gold set sono in `data/eval/`. L'evaluator confronta l'output Excel piu recente con `gold_standard.xlsx`: assicurarsi che corrispondano alle stesse righe nello stesso ordine.

## Docker dashboard

```powershell
 docker build -t cotral-dashboard .
 docker run --rm -p 8501:8501 --mount type=bind,source="${PWD}/data",target=/app/data cotral-dashboard
```

Il mount rende visibili gli output e conserva caricamenti e suggerimenti. Il container esegue solo la dashboard. Vedere anche `docs/dashboard.md` e `key_extractor/README.md`.
