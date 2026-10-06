"""
Visual theme for the dashboard: a professional dark look.

Self-sufficient: the dark background and text colors are forced in CSS, so the
app looks right even if .streamlit/config.toml is not picked up. Tweak colors
in the block below.
"""

import streamlit as st
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go

PALETTE = ["#4f8cff", "#22c55e", "#f59e0b", "#ec4899",
           "#06b6d4", "#a78bfa", "#ef4444", "#94a3b8"]
ACCENT = "#4f8cff"
SEQ = [[0, "#1a2436"], [0.5, "#2f5fa8"], [1, "#7db0ff"]]

BG = "#0d0f14"
PANEL = "#0b0d12"
CARD = "#161a22"
BORDER = "#232a36"
MUTED = "#8b93a3"
TEXT = "#e6e9ef"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

/* force dark surfaces (works even without config.toml) */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
section[data-testid="stMain"] {{ background: {BG}; }}
.stApp, [data-testid="stMarkdownContainer"], .stApp p, .stApp li,
[data-testid="stMetricValue"], [data-testid="stWidgetLabel"] label {{ color: {TEXT}; }}

/* hide only the menu + footer, keep the header (so the sidebar toggle stays) */
#MainMenu, footer {{ visibility: hidden; height: 0; }}
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1320px; }}

/* headings */
h1, h2, h3 {{ font-family: 'Inter', sans-serif; letter-spacing: -0.4px; color: {TEXT}; }}
h2 {{ font-weight: 600; font-size: 1.15rem; margin: 0.2rem 0 0.4rem; }}
h3 {{ font-weight: 600; font-size: 1.02rem; }}

/* app header bar */
.app-header {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px; margin-bottom: 18px;
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px;
}}
.app-header .brand {{ font-size: 18px; font-weight: 700; color: {TEXT}; letter-spacing: -0.3px; }}
.app-header .brand span {{ color: {MUTED}; font-weight: 500; }}
.app-header .live {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; color:{MUTED}; }}
.app-header .dot {{ width:8px; height:8px; border-radius:50%; background:#22c55e; display:inline-block; }}

/* KPI cards (styled st.metric) */
[data-testid="stMetric"] {{
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px;
  padding: 16px 18px 14px;
}}
[data-testid="stMetric"] label p, [data-testid="stMetricLabel"] p {{
  color: {MUTED}; font-size: 13px; font-weight: 500;
}}
[data-testid="stMetricValue"] {{ font-weight: 600; font-size: 1.9rem; letter-spacing: -0.5px; }}
[data-testid="stMetricDelta"] {{ font-size: 12.5px; }}

/* section titles */
.sec {{ font-size: 1.02rem; font-weight: 600; color: {TEXT}; margin: 6px 0 2px; }}
.sec small {{ display:block; font-weight:400; color:{MUTED}; font-size:12.5px; margin-top:2px; }}

/* tabs -> app-like nav */
div[data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid {BORDER}; }}
button[data-baseweb="tab"] {{ padding: 9px 16px; font-weight: 500; color: {MUTED};
  border-radius: 10px 10px 0 0; }}
button[data-baseweb="tab"]:hover {{ color: {TEXT}; background: rgba(255,255,255,0.03); }}
button[data-baseweb="tab"] p {{ color: inherit !important; font-size: 15px; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: {TEXT}; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color: {TEXT} !important; }}
div[data-baseweb="tab-highlight"] {{ background: {ACCENT}; }}

/* sidebar */
section[data-testid="stSidebar"] {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
section[data-testid="stSidebar"] * {{ color: {TEXT}; }}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}

/* dividers / tables */
hr {{ border-color: {BORDER}; margin: 1.1rem 0; }}
[data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 12px; }}
</style>
"""


def apply():
    st.markdown(_CSS, unsafe_allow_html=True)
    tmpl = go.layout.Template(layout=dict(
        font=dict(family="Inter, sans-serif", color=TEXT, size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=PALETTE,
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, linecolor=BORDER),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=14, b=10, l=10, r=10),
    ))
    pio.templates["cotral"] = tmpl
    pio.templates.default = "cotral"
    px.defaults.template = "cotral"
    px.defaults.color_discrete_sequence = PALETTE


def header(brand_main, brand_sub, right="local · live"):
    st.markdown(
        f'<div class="app-header">'
        f'<div><div class="brand">{brand_main} <span>{brand_sub}</span></div></div>'
        f'<div class="live"><span class="dot"></span>{right}</div>'
        f'</div>', unsafe_allow_html=True)


def section(title, caption=None):
    html = f'<div class="sec">{title}'
    if caption:
        html += f'<small>{caption}</small>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)
