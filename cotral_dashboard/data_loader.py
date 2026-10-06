"""Predictive maintenance - data layer (accumulating store, plain-English labels)."""
from __future__ import annotations
import os, glob
import pandas as pd
import numpy as np

EXTRACTED_COLS = {"TestoBreve_Luogo":"location","TestoBreve_TipoIntervento":"intervention_type",
    "TestoBreve_Sintomo":"symptom","TestoBreve_Sistema":"system","TestoBreve_Azione":"action",
    "TestoBreve_Componente":"component","TestoBreve_Esito":"outcome"}
CORE_COLS = {"Claim":"claim","Tipo OdM":"order_type","bus":"bus","Conta Km":"km",
    "descrizione attività":"description","Data inizio guasto":"date_start","Data fine guasto":"date_end"}
TEXT_CANDIDATES = ["Testo Breve 1 (Originale)","Testo Breve 1"]
MULTI_VALUE_COLS = ["action","component"]
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
SYSTEM_LABELS = {"PNEUMATICI":"Tyres","RAFFREDDAMENTO":"Cooling system","CLIMATIZZAZIONE":"Air conditioning",
    "IMPIANTO_ELETTRICO":"Electrical system","IMP_ELETTRICO":"Electrical system","ELETTRICO":"Electrical system",
    "FRENI":"Brakes","MOTORE":"Engine","PORTE":"Doors","SOSPENSIONI":"Suspension",
    "ADBLUE_SCR":"AdBlue / emissions (SCR)","ALIMENTAZIONE":"Fuel system",
    "CENTRALINE_ELETTRONICHE":"Electronic control units","TRASMISSIONE":"Transmission","STERZO":"Steering",
    "SCARICO":"Exhaust","ILLUMINAZIONE":"Lighting","CARROZZERIA":"Bodywork","CAMBIO":"Gearbox","ALTRO":"Other (unclassified)"}
SYMPTOM_LABELS = {"PERDITA_LIQUIDO":"Fluid leak","PNEUMATICO_BUCATO":"Flat tyre","SPIA_ACCESA":"Warning light on",
    "PERDITA_ARIA":"Air leak","NON_FUNZIONA":"Not working","RUMORE":"Noise","RUMORE_ANOMALO":"Abnormal noise",
    "SERVIZIO":"Routine service","SURRISCALDAMENTO":"Overheating","VIBRAZIONE":"Vibration","FUMO":"Smoke",
    "ODORE":"Smell / odour","PERDITA_POTENZA":"Power loss","RIDUZIONE_POTENZA":"Reduced power",
    "LIMITAZIONE_POTENZA":"Power limited","MALFUNZIONAMENTO":"Malfunction","LUCE_MOTORE_ACCESA":"Engine light on",
    "MOTORE_NON_AVVIA":"Engine won't start","MOTORE_NON_FUNZIONANTE":"Engine not running",
    "MANCATA_COMUNICAZIONE":"Communication failure","INIEZIONE_AD_BLUE":"AdBlue injection issue",
    "SEDUTA_FISSA":"Seat stuck","ALTRO":"Other"}
WHERE_LABELS = {"OFFICINA":"Workshop","STRADA":"Road","SOCCORSO_STRADALE":"Roadside rescue","DEPOSITO":"Depot","ALTRO":"Other"}
ACTION_LABELS = {"SOSTITUZIONE":"Replacement","RIPRISTINO":"Repair / restore","RABBOCCO":"Top-up (fluid)",
    "SMONTAGGIO_RIMONTAGGIO":"Remove & refit","PULIZIA":"Cleaning","REGOLAZIONE":"Adjustment",
    "CONTROLLO":"Check / inspection","RIPARAZIONE":"Repair","RICARICA":"Recharge","VERIFICA":"Verification",
    "AGGIORNAMENTO":"Software update","SERRAGGIO":"Tightening","DIAGNOSI":"Diagnosis"}
OUTCOME_LABELS = {"POSITIVO":"Resolved","NEGATIVO":"Not resolved","NON_SPECIFICATO":"Unspecified","PARZIALE":"Partial"}

def prettify(v):
    if pd.isna(v): return v
    return str(v).replace("_"," ").strip().capitalize()
def label(v, mp):
    if pd.isna(v): return v
    return mp.get(str(v).strip().upper(), prettify(v))
def _clean_multivalue(x):
    if pd.isna(x): return []
    out=[]
    for p in str(x).split(","):
        p=p.strip()
        if not p or p.upper() in {"N/A","NON_SPECIFICATO","NAN","NONE"}: continue
        out.append(p)
    return out

def load_file(path_or_buffer, source_name=None):
    raw = pd.read_excel(path_or_buffer)
    df = pd.DataFrame()
    for src,dst in CORE_COLS.items(): df[dst]=raw[src] if src in raw.columns else np.nan
    tc = next((c for c in TEXT_CANDIDATES if c in raw.columns), None)
    df["text"]=raw[tc] if tc else np.nan
    for src,dst in EXTRACTED_COLS.items(): df[dst]=raw[src] if src in raw.columns else np.nan
    mat=[c for c in raw.columns if str(c).startswith("materiale /Definizione")]
    if mat: df["parts"]=raw[mat].apply(lambda r:[str(v).strip() for v in r if pd.notna(v) and str(v).strip()],axis=1)
    else: df["parts"]=[[] for _ in range(len(df))]
    df["part_count"]=df["parts"].apply(len)
    if "Quantità 1" in raw.columns:
        q=pd.to_numeric(raw["Quantità 1"].astype(str).str.replace(",",".",regex=False),errors="coerce")
        df["labor_hours"]=q.where(raw["UM1"].astype(str).str.upper().eq("H").values) if "UM1" in raw.columns else q
    else: df["labor_hours"]=np.nan
    df["bus"]=df["bus"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
    df["claim"]=df["claim"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
    df["km"]=pd.to_numeric(df["km"],errors="coerce")
    df["date_start"]=pd.to_datetime(df["date_start"],errors="coerce")
    df["date_end"]=pd.to_datetime(df["date_end"],errors="coerce")
    df["downtime_days"]=(df["date_end"]-df["date_start"]).dt.days
    df.loc[df["downtime_days"]<0,"downtime_days"]=np.nan
    ot=df["order_type"].astype(str).str.upper()
    df["planned"]=ot.str.startswith("PM")
    df["order_class"]=np.where(df["planned"],"Planned","Unplanned")
    ds=df["date_start"]
    df["date"]=ds.dt.date; df["year"]=ds.dt.year; df["month_num"]=ds.dt.month
    df["month"]=ds.dt.month.map(lambda m: MONTHS[int(m)-1] if pd.notna(m) else np.nan)
    df["year_month"]=ds.dt.to_period("M").astype(str)
    df["weekday"]=ds.dt.day_name()
    for c in ["location","intervention_type","symptom","system","outcome"]:
        df[c]=df[c].astype(str).str.strip().replace({"nan":np.nan,"":np.nan})
    df["unclassified"]=df["system"].astype(str).str.upper().eq("ALTRO")
    for c,mp in [("system",SYSTEM_LABELS),("symptom",SYMPTOM_LABELS),("intervention_type",WHERE_LABELS),("outcome",OUTCOME_LABELS)]:
        df[c+"_code"]=df[c]; df[c]=df[c].map(lambda v,m=mp: label(v,m))
    for c in MULTI_VALUE_COLS:
        rl=df[c].apply(_clean_multivalue); mp=ACTION_LABELS if c=="action" else {}
        df[c+"_list"]=rl.apply(lambda lst,m=mp:[label(v,m) for v in lst])
        df[c]=df[c+"_list"].apply(lambda lst: ", ".join(lst) if lst else np.nan)
    df["source_file"]=source_name or getattr(path_or_buffer,"name","uploaded")
    return df

def load_folder(folder):
    frames=[]
    for fp in sorted(glob.glob(os.path.join(folder,"*.xlsx"))):
        try: frames.append(load_file(fp,os.path.basename(fp)))
        except Exception as e: print("[skip]",fp,e)
    if not frames: return pd.DataFrame()
    df=pd.concat(frames,ignore_index=True)
    if "claim" in df.columns: df=df.drop_duplicates(subset="claim",keep="last").reset_index(drop=True)
    return df

def folder_signature(folder):
    sig=[]
    for fp in sorted(glob.glob(os.path.join(folder,"*.xlsx"))):
        s=os.stat(fp); sig.append((os.path.basename(fp),int(s.st_mtime),s.st_size))
    return tuple(sig)

def list_files(folder):
    return sorted([os.path.basename(p) for p in glob.glob(os.path.join(folder,"*.xlsx"))])

def explode_multi(df,field):
    col=field if field=="parts" else field+"_list"
    if col not in df.columns: return pd.DataFrame(columns=[field])
    s=df[col].explode().dropna(); s=s[s.astype(str).str.strip()!=""]
    return s.rename(field).to_frame()

def repeat_failures(df):
    d=df.dropna(subset=["date_start","system"]).copy(); d=d[~d["unclassified"]].sort_values("date_start")
    rows=[]
    for (bus,sysn),g in d.groupby(["bus","system"]):
        if len(g)>=2:
            gaps=g["date_start"].diff().dt.days.dropna()
            rows.append({"bus":bus,"system":sysn,"times":len(g),
                "avg_days_between":round(gaps.mean(),1) if len(gaps) else None,
                "last_event":g["date_start"].max().date()})
    out=pd.DataFrame(rows)
    if len(out): out=out.sort_values("times",ascending=False)
    return out.reset_index(drop=True)
