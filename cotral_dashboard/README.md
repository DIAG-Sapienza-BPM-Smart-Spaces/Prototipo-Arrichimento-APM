# COTRAL fleet maintenance dashboard

A professional, multi-tab Streamlit dashboard over an **accumulating data
store**, built from the structured output of your pipeline (processed Excel
with the extracted columns). Everything runs locally; no data leaves your
machine.

## Files
- `app.py` — the dashboard (6 tabs, global filters).
- `data_loader.py` — reads the whole `data/` folder, cleans, de-duplicates, derives fields.
- `theme.py` — professional dark theme (CSS + one plotly template).
- `.streamlit/config.toml` — Streamlit dark theme settings.
- `requirements.txt` — dependencies.

## The data model: an accumulating pile
A `data/` folder (next to `app.py`) is the growing pile. Drop every processed
Excel there as it arrives; the app reads them all, stacks them, and
de-duplicates by work order id (`Claim`). New file → press **Reload data**.

## Install & run
```bash
cd cotral_dashboard
pip3 install -r requirements.txt      # or: python3 -m pip install -r requirements.txt
streamlit run app.py
```
Opens http://localhost:8501. If the pile is empty, drop `.xlsx` files into
`data/` or use **Add processed Excel to the pile** in the sidebar, then
**Reload data**.

## Tabs
- **Overview** — 8 KPIs, system distribution, planned vs unplanned, trend (day/week/month/year).
- **Buses** — fleet heat map, worst-bus ranking, repeat-failure signal, single-bus history.
- **Faults** — top systems/symptoms, system × symptom matrix, workshop vs road, actions, costliest fault.
- **Parts** — most used parts, parts per bus, part ↔ system matrix, demand over time.
- **Explore** — free bubble explorer + mileage-vs-downtime relationship.
- **Data quality** — unclassified (ALTRO) count/trend, rows needing a human look.

## Global filters
Year · Month · Date range · Order type · System · Symptom · Where (workshop/road) · Outcome · Bus.

## Field notes
- Downtime uses the **median** (outliers skew the mean).
- Labor hours = `Quantità 1` (unit H) — effort/cost proxy; no monetary cost in data.
- Planned vs unplanned from `Tipo OdM` (PM* = planned).
- Where (workshop/road) from `TipoIntervento`, not Luogo (mostly empty).
- Top system and repeat-failure exclude ALTRO (unclassified catch-all).

## Design
Dark, low-chroma surfaces with one accent, 1px-bordered KPI cards, Inter type,
and a single consistent chart template. Tweak everything in `theme.py`.

## Not in scope
Monetary cost, real geographic map (no GPS), future prediction/RUL (this
describes history, it doesn't forecast).
