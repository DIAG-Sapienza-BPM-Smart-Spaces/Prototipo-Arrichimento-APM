"""Predictive Maintenance dashboard - Streamlit (SAP-style, linked charts + suggestions)."""
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go

import data_loader as dl

PALETTE = ["#0a6ed1", "#107e3e", "#e9730c", "#bb0000", "#6a6d70", "#0070f2", "#925ace", "#1c4c98"]
ACCENT = "#0a6ed1"
SHELL = "#354a5f"
BG, PANEL, CARD, BORDER, MUTED, TEXT = "#f5f6f7", "#ffffff", "#ffffff", "#d9d9d9", "#6a6d70", "#32363a"
DATA_DIR = "data"
SUGG_FILE = "suggestions.json"

st.set_page_config(page_title="Predictive Maintenance", layout="wide", page_icon="🔧",
                   initial_sidebar_state="expanded")

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html {{ font-size: 15.5px; }}
html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', Arial, sans-serif; }}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section[data-testid="stMain"] {{ background: {BG}; }}
.stApp, [data-testid="stMarkdownContainer"], .stApp p, .stApp li, [data-testid="stWidgetLabel"] label {{ color: {TEXT}; }}
#MainMenu, footer {{ visibility: hidden; height: 0; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1rem; padding-bottom: 3rem; max-width: 1320px; }}
h1, h2, h3 {{ font-family: 'Inter', sans-serif; color: {TEXT}; }}
.app-header {{ display:flex; align-items:center; justify-content:space-between; padding:15px 22px; margin-bottom:14px;
  background:{SHELL}; border-radius:8px; }}
.app-header .brand {{ font-size:18px; font-weight:600; color:#ffffff; letter-spacing:.2px; }}
.app-header .brand span {{ color:#b9c4cd; font-weight:400; }}
.app-header .live {{ display:inline-flex; align-items:center; gap:7px; font-size:12.5px; color:#c6d0d8; }}
.app-header .dot {{ width:8px; height:8px; border-radius:50%; background:#36c48f; display:inline-block; }}
.intro {{ color:{MUTED}; font-size:13.5px; margin:2px 0 14px; }}
[data-testid="stMetric"] {{ background:{CARD}; border:1px solid {BORDER}; border-radius:8px; padding:16px 18px 14px;
  box-shadow:0 1px 2px rgba(53,74,95,0.06); }}
[data-testid="stMetric"] label p, [data-testid="stMetricLabel"] p {{ color:{MUTED}; font-size:13px; font-weight:500; }}
[data-testid="stMetricValue"] {{ font-weight:600; font-size:1.75rem; color:{SHELL}; font-variant-numeric:tabular-nums; }}
.sec {{ font-size:1rem; font-weight:600; color:{TEXT}; margin:8px 0 2px; }}
.sec small {{ display:block; font-weight:400; color:{MUTED}; font-size:12.5px; margin-top:3px; }}
div[data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid {BORDER}; flex-wrap:wrap; }}
button[data-baseweb="tab"] {{ padding:9px 16px; font-weight:500; color:{MUTED}; }}
button[data-baseweb="tab"]:hover {{ color:{TEXT}; background:#eaedf0; }}
button[data-baseweb="tab"] p {{ color:inherit !important; font-size:14.5px; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color:{ACCENT} !important; font-weight:600; }}
div[data-baseweb="tab-highlight"] {{ background:{ACCENT}; height:3px; }}
section[data-testid="stSidebar"] {{ background:{PANEL}; border-right:1px solid {BORDER}; }}
section[data-testid="stSidebar"] * {{ color:{TEXT}; }}
hr {{ border-color:{BORDER}; margin:1rem 0; }}
[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius:8px; font-variant-numeric:tabular-nums; }}
.bus-hero {{ background:{CARD}; border:1px solid {BORDER}; border-radius:8px; padding:16px 22px 18px; margin-bottom:14px; box-shadow:0 1px 2px rgba(53,74,95,0.06); }}
.bus-hero .name {{ font-size:17px; font-weight:600; color:{SHELL}; }}
.bus-hero .stat {{ display:inline-block; margin-right:28px; margin-top:10px; }}
.bus-hero .stat b {{ display:block; font-size:19px; color:{TEXT}; font-variant-numeric:tabular-nums; }}
.bus-hero .stat span {{ font-size:12px; color:{MUTED}; }}
.job-card {{ background:{CARD}; border:1px solid {BORDER}; border-radius:8px; padding:13px 16px; margin-bottom:9px; box-shadow:0 1px 2px rgba(53,74,95,0.05); }}
.job-card .row1 {{ display:flex; align-items:center; justify-content:space-between; }}
.job-card .title {{ font-size:14.5px; font-weight:600; color:{TEXT}; }}
.job-card .hrs {{ background:#eaf1fb; color:#0a4a8f; font-weight:600; font-size:12px; padding:3px 11px; border-radius:12px; }}
.job-card .date {{ font-size:12px; color:{MUTED}; margin-top:2px; }}
.job-card .meta {{ margin-top:9px; display:flex; flex-wrap:wrap; gap:7px; }}
.job-card .chip {{ background:#eef1f3; color:{TEXT}; font-size:11.5px; padding:3px 9px; border-radius:4px; }}
.job-card .chip.warn {{ background:#fdf1e6; color:#a35300; }}
.job-card .chip.plan {{ background:#ebf5ee; color:#0a5a2c; }}
.wo-detail {{ background:{CARD}; border:1px solid {BORDER}; border-radius:8px; padding:20px 24px; box-shadow:0 1px 2px rgba(53,74,95,0.06); }}
.wo-head {{ display:flex; justify-content:space-between; align-items:flex-start; }}
.wo-title {{ font-size:21px; font-weight:600; color:{SHELL}; }}
.wo-sub {{ font-size:13px; color:{MUTED}; margin-top:2px; }}
.wo-badge {{ font-size:12px; font-weight:600; padding:4px 12px; border-radius:12px; }}
.wo-badge.warn {{ background:#fdf1e6; color:#a35300; }}
.wo-badge.plan {{ background:#ebf5ee; color:#0a5a2c; }}
.wo-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:18px 0; padding:16px 0; border-top:1px solid {BORDER}; border-bottom:1px solid {BORDER}; }}
.wo-f span {{ display:block; font-size:11px; color:{MUTED}; text-transform:uppercase; letter-spacing:.4px; }}
.wo-f b {{ font-size:14.5px; color:{TEXT}; }}
.wo-block {{ margin-top:12px; }}
.wo-block span {{ font-size:11px; color:{MUTED}; text-transform:uppercase; letter-spacing:.4px; }}
.wo-block p {{ margin:3px 0 0; color:{TEXT}; font-size:14px; }}
.wo-block .note {{ background:{BG}; border:1px solid {BORDER}; border-radius:6px; padding:11px 13px; font-size:13px; color:{TEXT}; white-space:pre-wrap; line-height:1.5; }}
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

_tmpl = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", color=TEXT, size=13),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=PALETTE,
    xaxis=dict(gridcolor="#e5e7ea", zerolinecolor="#e5e7ea", linecolor=BORDER),
    yaxis=dict(gridcolor="#e5e7ea", zerolinecolor="#e5e7ea", linecolor=BORDER),
    legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(t=14, b=10, l=10, r=10)))
pio.templates["sap"] = _tmpl
pio.templates.default = "sap"
px.defaults.template = "sap"
px.defaults.color_discrete_sequence = PALETTE


def app_header(main, sub, right):
    st.markdown(f'<div class="app-header"><div><div class="brand">{main} <span>{sub}</span></div></div>'
                f'<div class="live"><span class="dot"></span>{right}</div></div>', unsafe_allow_html=True)


def intro(text):
    st.markdown(f'<div class="intro">{text}</div>', unsafe_allow_html=True)


def section(title, caption=None):
    st.markdown(f'<div class="sec">{title}' + (f'<small>{caption}</small>' if caption else '') + '</div>',
                unsafe_allow_html=True)


def _bar_click(ev):
    try:
        pts = ev.selection.points
        if pts:
            p = pts[0]
            return p.get("y") or p.get("label") or p.get("x")
    except Exception:
        pass
    return None


def _row_click(ev, frame, col):
    try:
        rows = ev.selection.rows
        if rows:
            return frame.iloc[rows[0]][col]
    except Exception:
        pass
    return None


def bar_h(series_counts, xlab="count", color=ACCENT, height=340):
    d = series_counts.reset_index()
    d.columns = ["label", xlab]
    fig = px.bar(d.sort_values(xlab), x=xlab, y="label", orientation="h", color_discrete_sequence=[color])
    fig.update_layout(height=height, yaxis_title="", xaxis_title=xlab)
    return fig


def click_bar(series_counts, key, color=ACCENT, xlab="count", n=12, height=340):
    if series_counts is None or not len(series_counts):
        st.info("No data.")
        return None
    fig = bar_h(series_counts.head(n), xlab=xlab, color=color, height=height)
    try:
        ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=key)
        return _bar_click(ev)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)
        return None


def load_suggestions():
    if os.path.exists(SUGG_FILE):
        try:
            return json.load(open(SUGG_FILE, encoding="utf-8"))
        except Exception:
            return []
    return []


def save_suggestion(rec):
    data = load_suggestions()
    data.append(rec)
    json.dump(data, open(SUGG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


os.makedirs(DATA_DIR, exist_ok=True)


@st.cache_data(show_spinner=False)
def load_store(signature):
    return dl.load_folder(DATA_DIR)


st.sidebar.markdown("### 🔧 Predictive Maintenance")
st.sidebar.caption("Fleet maintenance analytics")
with st.sidebar.expander("➕ Add data (Excel to the pile)"):
    ups = st.file_uploader("Drop .xlsx file(s)", type=["xlsx"], accept_multiple_files=True)
    if ups:
        for u in ups:
            with open(os.path.join(DATA_DIR, u.name), "wb") as fh:
                fh.write(u.getbuffer())
        st.success(f"Added {len(ups)} file(s).")
        st.cache_data.clear()
with st.sidebar.expander("🗂 Files in the pile / remove"):
    files = dl.list_files(DATA_DIR)
    if files:
        for fn in files:
            st.caption(f"• {fn}")
        rm = st.multiselect("Remove file(s)", files, key="rm_files")
        if st.button("Delete selected", key="del_btn"):
            if rm:
                for name in rm:
                    try:
                        os.remove(os.path.join(DATA_DIR, name))
                    except OSError:
                        pass
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Pick file(s) first.")
    else:
        st.caption("No files yet.")
if st.sidebar.button("🔄 Reload data", use_container_width=True):
    st.cache_data.clear()

df = load_store(dl.folder_signature(DATA_DIR))
if len(df) == 0:
    app_header("Predictive Maintenance", "", "no data")
    st.info(f"No data yet. Put processed Excel files into **`{DATA_DIR}/`** or use **Add data**, then **Reload data**.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")
st.sidebar.caption("Pick any of these to narrow everything down.")
f = df.copy()


def multi(col, label):
    global f
    if col in f.columns:
        opts = sorted([x for x in f[col].dropna().unique()], key=lambda v: str(v))
        if opts:
            sel = st.sidebar.multiselect(label, opts)
            if sel:
                f = f[f[col].isin(sel)]


years = sorted([int(y) for y in f["year"].dropna().unique()])
if years:
    ysel = st.sidebar.multiselect("Year", years)
    if ysel: f = f[f["year"].isin(ysel)]
months = [m for m in dl.MONTHS if m in set(f["month"].dropna())]
if months:
    msel = st.sidebar.multiselect("Month", months)
    if msel: f = f[f["month"].isin(msel)]
if f["date_start"].notna().any():
    dmin, dmax = f["date_start"].min().date(), f["date_start"].max().date()
    if dmin < dmax:
        rng = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            a, b = pd.to_datetime(rng[0]), pd.to_datetime(rng[1])
            f = f[(f["date_start"] >= a) & (f["date_start"] <= b)]
multi("order_class", "Planned or unplanned")
multi("system", "Fault system")
multi("symptom", "Symptom")
multi("intervention_type", "Where (workshop / road)")
bus_opts = sorted(f["bus"].dropna().unique())
bsel = st.sidebar.multiselect("Bus", bus_opts)
if bsel: f = f[f["bus"].isin(bsel)]

st.sidebar.markdown("---")
st.sidebar.caption(f"Data: {df['source_file'].nunique()} file(s) - {len(df)} records")
st.sidebar.caption(f"Showing: {len(f)} records")

app_header("Predictive Maintenance", "", f"{df['source_file'].nunique()} sources - {len(df)} records")
tabs = st.tabs(["Overview", "Work orders", "Buses", "Faults", "Parts", "Suggest"])

with tabs[0]:
    if len(f) == 0:
        st.info("No records match these filters. Clear some on the left.")
    else:
        intro("The big picture: how much maintenance is happening, which faults dominate, and the trend over time.")
        r1 = st.columns(4)
        r1[0].metric("Total jobs", f"{len(f)}", help="Number of maintenance work orders.")
        r1[1].metric("Buses involved", f["bus"].nunique())
        r1[2].metric("Jobs per bus", round(len(f) / max(f["bus"].nunique(), 1), 1))
        avg_h = f["labor_hours"].mean(skipna=True)
        r1[3].metric("Avg hours / job", f"{0 if pd.isna(avg_h) else round(avg_h,1)} h", help="Average labor time per job.")
        st.write("")
        r2 = st.columns(4)
        r2[0].metric("Unplanned", f"{round(100*(f['order_class']=='Unplanned').mean())}%",
                     help="Share that were breakdowns, not scheduled. Higher = more firefighting.")
        road = f["intervention_type"].astype(str).isin(["Road", "Roadside rescue"])
        r2[1].metric("Broke down on the road", f"{round(100*road.mean())}%")
        lh = f["labor_hours"].sum(skipna=True)
        r2[2].metric("Total work hours", f"{0 if pd.isna(lh) else round(lh)} h")
        r2[3].metric("Needs review", f"{round(100*f['unclassified'].mean())}%", help="Records the system could not classify.")
        st.markdown("---")
        cL, cR = st.columns(2)
        with cL:
            section("Which systems fail most")
            vc = f["system"].value_counts().reset_index(); vc.columns = ["system", "records"]
            fig = px.pie(vc, names="system", values="records", hole=0.62, color_discrete_sequence=PALETTE)
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(showlegend=False, height=340); st.plotly_chart(fig, use_container_width=True)
        with cR:
            section("Planned vs unplanned work")
            oc = f["order_class"].value_counts().reset_index(); oc.columns = ["class", "records"]
            fig = px.pie(oc, names="class", values="records", hole=0.62, color="class",
                         color_discrete_map={"Planned": "#107e3e", "Unplanned": "#e9730c"})
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(showlegend=False, height=340); st.plotly_chart(fig, use_container_width=True)
        st.markdown("---")
        section("How maintenance changes over time")
        gran = st.radio("View by", ["Day", "Week", "Month", "Year"], index=2, horizontal=True, key="ov_gran")
        g = f.dropna(subset=["date_start"]).copy()
        if len(g):
            if gran == "Day": key = g["date_start"].dt.date.astype(str)
            elif gran == "Week": key = g["date_start"].dt.to_period("W").astype(str)
            elif gran == "Year": key = g["date_start"].dt.year.astype(str)
            else: key = g["date_start"].dt.to_period("M").astype(str)
            tr = g.assign(bucket=key).groupby("bucket").size().reset_index(name="records")
            fig = px.area(tr, x="bucket", y="records", markers=True, color_discrete_sequence=[ACCENT])
            fig.update_traces(fillcolor="rgba(10,110,209,0.10)")
            fig.update_layout(height=290, xaxis_title="", yaxis_title="jobs"); st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    intro("Every maintenance record as a work order. Click one on the left to open its full detail.")
    if len(f) == 0:
        st.info("No records match these filters.")
    else:
        q = st.text_input("Search", placeholder="Search by system, symptom, bus or work order #", label_visibility="collapsed")
        wo = f.copy()
        if q:
            ql = q.lower()
            m = (wo["system"].astype(str).str.lower().str.contains(ql, na=False) |
                 wo["symptom"].astype(str).str.lower().str.contains(ql, na=False) |
                 wo["bus"].astype(str).str.lower().str.contains(ql, na=False) |
                 wo["claim"].astype(str).str.lower().str.contains(ql, na=False))
            wo = wo[m]
        wo = wo.sort_values("date_start", ascending=False)
        st.caption(f"{len(wo)} work orders")
        left, right = st.columns([1, 1.8])
        with left:
            with st.container(height=560):
                for _, r in wo.head(200).iterrows():
                    dot = "🔴" if r["order_class"] == "Unplanned" else "🟢"
                    d = r["date_start"].date().isoformat() if pd.notna(r["date_start"]) else "-"
                    sysn = r["system"] if pd.notna(r["system"]) else "-"
                    if st.button(f'{dot}  {sysn}  ·  bus {r["bus"]}  ·  {d}', key=f'wo_{r["claim"]}', use_container_width=True):
                        st.session_state["sel_wo"] = r["claim"]
        sel = st.session_state.get("sel_wo")
        if sel is None or sel not in set(wo["claim"]):
            sel = wo.iloc[0]["claim"] if len(wo) else None
        with right:
            if sel is None:
                st.info("No work orders match.")
            else:
                r = f[f["claim"] == sel].iloc[0]
                pr = "High" if r["order_class"] == "Unplanned" else "Low"
                cls = "warn" if r["order_class"] == "Unplanned" else "plan"
                d = r["date_start"].date().isoformat() if pd.notna(r["date_start"]) else "-"
                km = f'{int(r["km"]):,} km' if pd.notna(r["km"]) else "-"
                hrs = f'{r["labor_hours"]:g} h' if pd.notna(r["labor_hours"]) else "-"
                sysn = r["system"] if pd.notna(r["system"]) else "-"
                fields = [("Priority", pr), ("Date", d),
                          ("Where", r["intervention_type"] if pd.notna(r["intervention_type"]) else "-"),
                          ("Bus", r["bus"]), ("Mileage", km), ("Work hours", hrs),
                          ("Result", r["outcome"] if pd.notna(r["outcome"]) else "-"),
                          ("Fault system", sysn)]
                grid = "".join(f'<div class="wo-f"><span>{k}</span><b>{v}</b></div>' for k, v in fields)
                sym = r["symptom"] if pd.notna(r["symptom"]) else "-"
                act = r["action"] if pd.notna(r["action"]) else "-"
                comp = r["component"] if pd.notna(r["component"]) else "-"
                parts = ", ".join(r["parts"]) if isinstance(r["parts"], list) and r["parts"] else "-"
                note = str(r["text"]) if pd.notna(r["text"]) else (str(r["description"]) if pd.notna(r["description"]) else "-")
                note = note.replace("<", "&lt;").replace(">", "&gt;")
                st.markdown(
                    f'<div class="wo-detail"><div class="wo-head"><div>'
                    f'<div class="wo-title">{sysn}</div>'
                    f'<div class="wo-sub">Work order #{r["claim"]}</div></div>'
                    f'<span class="wo-badge {cls}">{r["order_class"]}</span></div>'
                    f'<div class="wo-grid">{grid}</div>'
                    f'<div class="wo-block"><span>Symptom</span><p>{sym}</p></div>'
                    f'<div class="wo-block"><span>Action taken</span><p>{act}</p></div>'
                    f'<div class="wo-block"><span>Components</span><p>{comp}</p></div>'
                    f'<div class="wo-block"><span>Parts used</span><p>{parts}</p></div>'
                    f'<div class="wo-block"><span>Original note</span><p class="note">{note}</p></div>'
                    f'</div>', unsafe_allow_html=True)

with tabs[2]:
    intro("Look at the fleet bus by bus. Click a row in a table to open that bus below - no manual search needed.")
    if len(f) == 0:
        st.info("No records match these filters.")
    else:
        picked = None
        section("Buses that need the most attention", "Click a row to open that bus.")
        agg = f.groupby("bus").agg(jobs=("claim", "count"), systems_affected=("system", "nunique"),
            work_hours=("labor_hours", "sum"),
            unplanned=("order_class", lambda s: int((s == "Unplanned").sum()))).reset_index().sort_values("jobs", ascending=False)
        agg["work_hours"] = agg["work_hours"].round(1)
        aggH = agg.head(25).reset_index(drop=True)
        try:
            ev_w = st.dataframe(aggH, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="worst_tbl")
            rw = _row_click(ev_w, aggH, "bus")
            if rw is not None and st.session_state.get("_w_last") != rw:
                st.session_state["_w_last"] = rw; picked = rw
        except TypeError:
            st.dataframe(aggH, use_container_width=True, hide_index=True)
        st.markdown("---")
        section("Buses to send for early maintenance", "Same bus + same fault 2+ times. Click a row to open that bus.")
        rf = dl.repeat_failures(f)
        if len(rf):
            try:
                ev_r = st.dataframe(rf, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="rf_tbl")
                rr = _row_click(ev_r, rf, "bus")
                if rr is not None and st.session_state.get("_r_last") != rr:
                    st.session_state["_r_last"] = rr; picked = rr
            except TypeError:
                st.dataframe(rf, use_container_width=True, hide_index=True)
        else:
            st.info("No bus repeated the same fault in this selection.")
        st.markdown("---")
        section("One bus in detail", "Driven by the row you click above, or pick one here.")
        buses_sorted = sorted(f["bus"].dropna().unique())
        if picked in buses_sorted:
            st.session_state["bus_pick"] = picked
        if st.session_state.get("bus_pick") not in buses_sorted:
            st.session_state["bus_pick"] = buses_sorted[0] if buses_sorted else None
        bsel2 = st.selectbox("Choose a bus", buses_sorted, key="bus_pick")
        one = f[f["bus"] == bsel2].copy()
        total_h = round(one["labor_hours"].sum(skipna=True), 1)
        last_km = int(one["km"].max()) if one["km"].notna().any() else 0
        last_date = one["date_start"].max()
        last_txt = last_date.date().isoformat() if pd.notna(last_date) else "-"
        st.markdown(f'<div class="bus-hero"><div class="name">Bus {bsel2}</div>'
            f'<div class="stat"><b>{len(one)}</b><span>service jobs</span></div>'
            f'<div class="stat"><b>{total_h} h</b><span>total work hours</span></div>'
            f'<div class="stat"><b>{one["system"].nunique()}</b><span>systems affected</span></div>'
            f'<div class="stat"><b>{last_km:,} km</b><span>latest mileage</span></div>'
            f'<div class="stat"><b>{last_txt}</b><span>last service</span></div></div>', unsafe_allow_html=True)
        srt = st.radio("Sort", ["Newest", "Oldest", "Most work"], horizontal=True, key="bus_sort", label_visibility="collapsed")
        if srt == "Oldest": one = one.sort_values("date_start", ascending=True)
        elif srt == "Most work": one = one.sort_values("labor_hours", ascending=False)
        else: one = one.sort_values("date_start", ascending=False)
        for _, r in one.iterrows():
            d = r["date_start"].date().isoformat() if pd.notna(r["date_start"]) else "-"
            hrs = "-" if pd.isna(r["labor_hours"]) else f'{r["labor_hours"]:g} h'
            cls = "plan" if r["order_class"] == "Planned" else "warn"
            chips = ""
            if pd.notna(r["symptom"]): chips += f'<span class="chip">{r["symptom"]}</span>'
            if pd.notna(r["action"]): chips += f'<span class="chip">{r["action"]}</span>'
            if pd.notna(r["km"]): chips += f'<span class="chip">{int(r["km"]):,} km</span>'
            chips += f'<span class="chip {cls}">{r["order_class"]}</span>'
            st.markdown(f'<div class="job-card"><div class="row1"><div class="title">{r["system"]}</div>'
                        f'<div class="hrs">{hrs}</div></div><div class="date">{d}</div>'
                        f'<div class="meta">{chips}</div></div>', unsafe_allow_html=True)

with tabs[3]:
    intro("What breaks, why, and where. Click any bar to drill into it.")
    if len(f) == 0:
        st.info("No records match these filters.")
    else:
        cA, cB = st.columns(2)
        with cA:
            section("Most common systems", "Click a system to see its symptoms.")
            sysclick = click_bar(f["system"].value_counts(), "flt_sys")
        with cB:
            section("Most common symptoms", "Click a symptom to see its systems.")
            symclick = click_bar(f["symptom"].value_counts(), "flt_sym", color="#925ace")
        if sysclick:
            section(f'Symptoms seen with "{sysclick}"')
            sub = f[f["system"] == sysclick]
            vc = sub["symptom"].value_counts()
            if len(vc): st.plotly_chart(bar_h(vc.head(12), color="#925ace"), use_container_width=True)
            else: st.info("No symptom recorded for this system.")
        if symclick:
            section(f'Systems that showed "{symclick}"')
            sub = f[f["symptom"] == symclick]
            st.plotly_chart(bar_h(sub["system"].value_counts().head(12)), use_container_width=True)
        st.markdown("---")
        cC, cD = st.columns(2)
        with cC:
            section("Where faults happen")
            loc = f["intervention_type"].value_counts().reset_index(); loc.columns = ["where", "records"]
            fig = px.pie(loc, names="where", values="records", hole=0.62, color_discrete_sequence=PALETTE)
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(showlegend=False, height=320); st.plotly_chart(fig, use_container_width=True)
        with cD:
            section("What the technicians did", "Click an action to see which systems.")
            acts = dl.explode_multi(f, "action")
            actclick = click_bar(acts["action"].value_counts(), "flt_act", color="#107e3e") if len(acts) else None
        if actclick:
            section(f'Systems where "{actclick}" was done')
            sub = f[f["action_list"].apply(lambda l: isinstance(l, list) and actclick in l)]
            st.plotly_chart(bar_h(sub["system"].value_counts().head(12), color="#107e3e"), use_container_width=True)
        st.markdown("---")
        section("Which faults take the most work", "Typical work hours per system (one bar per fault system).")
        cost = f.groupby("system").agg(work_hours=("labor_hours", "median"), jobs=("claim", "count")).reset_index()
        cost = cost.dropna(subset=["work_hours"]).sort_values("work_hours", ascending=True)
        if len(cost):
            fig = px.bar(cost, x="work_hours", y="system", orientation="h", color_discrete_sequence=["#e9730c"], hover_data=["jobs"])
            fig.update_layout(height=340, yaxis_title="", xaxis_title="typical work hours"); st.plotly_chart(fig, use_container_width=True)

with tabs[4]:
    intro("Which spare parts get used the most. Click a part to see which buses used it.")
    if len(f) == 0:
        st.info("No records match these filters.")
    else:
        parts = dl.explode_multi(f, "parts")
        cE, cF = st.columns(2)
        with cE:
            section("Most used parts", "Click a part to see its buses.")
            partclick = click_bar(parts["parts"].value_counts(), "parts_used", n=15) if len(parts) else None
        with cF:
            section("Parts used per bus")
            pb = f.groupby("bus")["part_count"].sum().sort_values(ascending=False).head(15)
            st.plotly_chart(bar_h(pb, xlab="parts", color="#0070f2"), use_container_width=True)
        if partclick:
            section(f'Buses that used "{partclick}"')
            sub = f[f["parts"].apply(lambda l: isinstance(l, list) and partclick in l)]
            if len(sub):
                st.plotly_chart(bar_h(sub["bus"].value_counts().head(15), xlab="times used", color="#0070f2"), use_container_width=True)
            else:
                st.info("No buses found for this part.")
        st.markdown("---")
        section("Parts needed month by month", "Helps plan stock ahead of time.")
        g = f.dropna(subset=["date_start"]).copy()
        if len(g):
            dem = g.assign(bucket=g["date_start"].dt.to_period("M").astype(str)).groupby("bucket")["part_count"].sum().reset_index()
            fig = px.bar(dem, x="bucket", y="part_count", color_discrete_sequence=[ACCENT])
            fig.update_layout(height=290, xaxis_title="", yaxis_title="parts used"); st.plotly_chart(fig, use_container_width=True)

with tabs[5]:
    intro("Spotted a new category the system keeps missing? Add it here. Suggestions are saved to suggestions.json "
          "for the pipeline to review and promote - they do NOT change the live taxonomy directly.")
    section("Records the system couldn't classify", "These fell into 'Other'. Look for a repeating new pattern worth naming.")
    unc = f[f["unclassified"]][["date_start", "bus", "system", "symptom", "description", "text"]]
    if len(unc):
        st.dataframe(unc, use_container_width=True, hide_index=True)
    else:
        st.caption("None in the current filter.")
    st.markdown("---")
    section("Suggest a new category")
    with st.form("suggest_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        s_field = c1.selectbox("Field", ["System", "Symptom", "Action", "Component"])
        s_name = c2.text_input("New category name", placeholder="e.g. Exhaust  /  SCARICO")
        s_desc = st.text_area("Description / definition", placeholder="What does this category mean? When should it be used?")
        s_kw = st.text_input("Example keywords (comma-separated)", placeholder="scarico, marmitta, DPF, fumo nero")
        s_link = st.text_input("Related work order # (optional)")
        submitted = st.form_submit_button("Save suggestion")
        if submitted:
            if s_name.strip():
                save_suggestion({
                    "field": s_field, "name": s_name.strip(), "description": s_desc.strip(),
                    "keywords": [k.strip() for k in s_kw.split(",") if k.strip()],
                    "work_order": s_link.strip() or None,
                    "created": datetime.now().isoformat(timespec="seconds"),
                })
                st.success("Saved to suggestions.json. The pipeline can read it for review / promotion.")
            else:
                st.warning("Give the category a name first.")
    st.markdown("---")
    section("Suggestions so far")
    data = load_suggestions()
    if data:
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        st.download_button("Download suggestions.json", data=json.dumps(data, ensure_ascii=False, indent=2),
                           file_name="suggestions.json", mime="application/json")
        if st.button("Clear all suggestions"):
            try:
                os.remove(SUGG_FILE)
            except OSError:
                pass
            st.rerun()
    else:
        st.caption("No suggestions yet.")
