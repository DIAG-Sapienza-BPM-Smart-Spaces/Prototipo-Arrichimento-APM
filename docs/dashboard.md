# Dashboard manutenzione COTRAL

La dashboard e nella root: `app.py` contiene l'interfaccia; `utils/data_loader.py` gestisce caricamento, pulizia e deduplicazione; `utils/theme.py` contiene le utilita grafiche.

## Avvio dalla root

```powershell
python -m pip install -r requirements.txt
python main_dashboard.py
```

In alternativa: `python -m streamlit run app.py`. Aprire http://localhost:8501.

## Dati integrati

La dashboard legge tutti gli Excel in `data/output/`, prodotti dal keyword extractor, e quelli aggiuntivi in `data/dashboard/`. Dopo un'elaborazione premere **Reload data** o riaprire la dashboard. La cache rileva le modifiche dei file al successivo aggiornamento dell'interfaccia.

Gli upload sono salvati in `data/dashboard/`; solo questi possono essere eliminati dalla barra laterale. Gli output dell'estrattore sono elencati separatamente. Gli ordini sono deduplicati per `Claim`, dando precedenza al file modificato piu recentemente.

I suggerimenti sono salvati in `data/dashboard_state/suggestions.json` e richiedono revisione manuale. Il report originale e in `docs/Dashboard_Report.docx`.

Le schede sono Overview, Work orders, Buses, Faults, Parts e Suggest: analizzano lo storico, senza prevedere guasti futuri.

## Docker dalla root

```powershell
 docker build -t cotral-dashboard .
 docker run --rm -p 8501:8501 --mount type=bind,source="${PWD}/data",target=/app/data cotral-dashboard
```

Il mount permette di leggere i risultati dell'estrattore e conservare caricamenti e suggerimenti. Il container esegue solo la dashboard.
