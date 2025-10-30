# pages/01_Buscar_Inventario_ON_OFF.py
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date
from utils import unify_schema, kpi_summary

st.set_page_config(page_title="Marketplace ON/OFF", layout="wide")
st.title("Marketplace ON/OFF")
st.caption("Elegí medios y formatos según costos, benchmarks y reseñas. Agregá al plan.")

# -------------------------------
# Catálogo integrado
# -------------------------------
def load_integrated_catalog() -> pd.DataFrame:
    csv_path = Path("data/catalog.csv")
    if csv_path.exists():
        df_raw = pd.read_csv(csv_path)
        if "medium_type" not in df_raw.columns:
            off_set = {"TV", "Radio", "OOH", "Print"}
            df_raw["medium_type"] = np.where(df_raw.get("medium","").isin(off_set), "OFF", "ON")
        return unify_schema(df_raw, None)

    # Semilla mínima (puedes editar costos OFF aquí)
    seed = [
        {"medium":"Display","vendor":"MedioX","format":"300x250","audience":"Adults 18-49",
         "impressions":250_000,"grps":np.nan,"clicks":1_200,"views":np.nan,"leads":np.nan,"actions":np.nan,
         "cost":1_500,"start":np.nan,"end":np.nan,"rating":4.2,"medium_type":"ON"},
        {"medium":"Video","vendor":"MedioY","format":"Pre-roll","audience":"Adults 18-49",
         "impressions":180_000,"grps":np.nan,"clicks":900,"views":160_000,"leads":120,"actions":50,
         "cost":2_200,"start":np.nan,"end":np.nan,"rating":4.5,"medium_type":"ON"},
        {"medium":"Social","vendor":"Meta Ads","format":"Instagram Feed","audience":"18-34",
         "impressions":400_000,"grps":np.nan,"clicks":2_800,"views":np.nan,"leads":150,"actions":40,
         "cost":3_000,"start":np.nan,"end":np.nan,"rating":4.3,"medium_type":"ON"},
        {"medium":"TV","vendor":"Canal A","format":"Prime Time","audience":"Adults 18-49",
         "impressions":2_000_000,"grps":120,"clicks":np.nan,"views":np.nan,"leads":np.nan,"actions":np.nan,
         "cost":45_000,"start":np.nan,"end":np.nan,"rating":4.0,"medium_type":"OFF"},
        {"medium":"Radio","vendor":"FM Popular","format":"Mañana","audience":"Adults 25-54",
         "impressions":800_000,"grps":85,"clicks":np.nan,"views":np.nan,"leads":np.nan,"actions":np.nan,
         "cost":15_000,"start":np.nan,"end":np.nan,"rating":3.9,"medium_type":"OFF"},
        {"medium":"OOH","vendor":"Vía Pública","format":"LED 6x3","audience":"Adults 18-49",
         "impressions":350_000,"grps":np.nan,"clicks":np.nan,"views":np.nan,"leads":np.nan,"actions":np.nan,
         "cost":12_000,"start":np.nan,"end":np.nan,"rating":3.8,"medium_type":"OFF"},
        {"medium":"Print","vendor":"Diario Central","format":"Página Completa","audience":"Adults 25-64",
         "impressions":150_000,"grps":np.nan,"clicks":np.nan,"views":np.nan,"leads":np.nan,"actions":np.nan,
         "cost":6_000,"start":np.nan,"end":np.nan,"rating":3.6,"medium_type":"OFF"},
    ]
    return unify_schema(pd.DataFrame(seed), None)

df = load_integrated_catalog()
if df.empty:
    st.error("No hay catálogo disponible. Creá data/catalog.csv.")
    st.stop()

# -------------------------------
# Filtros (con keys únicos)
# -------------------------------
with st.sidebar:
    st.header("Filtros")
    mtype = st.multiselect("Tipo", options=["ON","OFF"], default=["ON","OFF"], key="flt_tipo")

    formatos_opts = sorted(df["medium"].dropna().unique().tolist())   # "Formatos"
    medios_opts   = sorted(df["vendor"].dropna().unique().tolist())   # "Medios"
    canales_opts  = sorted(df["format"].dropna().unique().tolist())   # "Canales"

    sel_formatos = st.multiselect("Formatos", formatos_opts, key="flt_formatos")
    sel_medios   = st.multiselect("Medios",   medios_opts,   key="flt_medios")
    sel_canales  = st.multiselect("Canales",  canales_opts,  key="flt_canales")

    st.markdown("---")
    st.subheader("Unidad de costo")

# Aplico filtros base
q = df.copy()
q = q[q["medium_type"].isin(mtype)]
if sel_formatos: q = q[q["medium"].isin(sel_formatos)]
if sel_medios:   q = q[q["vendor"].isin(sel_medios)]
if sel_canales:  q = q[q["format"].isin(sel_canales)]

# Unidades dinámicas disponibles en el subset
allowed_units = ["CPM","CPC","CPL","CPA"]
units_present = []
if (q["CPM"].notna() & (q["CPM"] > 0)).any(): units_present.append("CPM")
if (q["CPC"].notna() & (q["CPC"] > 0)).any(): units_present.append("CPC")
if (q["CPL"].notna() & (q["CPL"] > 0)).any(): units_present.append("CPL")
if (q["CPA"].notna() & (q["CPA"] > 0)).any(): units_present.append("CPA")
units_present = [u for u in allowed_units if u in units_present] or ["CPM"]

with st.sidebar:
    sel_unit = st.selectbox("Unidad aplicable", options=units_present, index=0, key="flt_unit")

# Costo unitario elegido para la vista y orden
q["costo_unitario"] = q[sel_unit]
q = q.sort_values(["score"], ascending=False)

# -------------------------------
# Fechas opcionales (sin hora) con keys únicos
# -------------------------------
if "plan_dates" not in st.session_state:
    st.session_state.plan_dates = {"applied": False, "start": None, "end": None}

with st.sidebar:
    st.markdown("---")
    st.subheader("Fechas de campaña (opcional)")
    use_dates = st.checkbox("Definir fechas", value=False, key="chk_dates")
    if use_dates:
        start_input = st.date_input("Inicio", value=date.today(), key="dt_start")
        end_input   = st.date_input("Fin", value=date.today(), key="dt_end")
        if st.button("Aplicar fechas", key="btn_apply_dates"):
            st.session_state.plan_dates = {"applied": True, "start": start_input, "end": end_input}
    else:
        st.session_state.plan_dates = {"applied": False, "start": None, "end": None}

# -------------------------------
# Tabla ÚNICA (al principio) + selección
# -------------------------------
def stars(x):
    try:
        v = float(x)
    except Exception:
        return ""
    v = max(0.0, min(5.0, v))
    full = int(round(v))
    return "★" * full + "☆" * (5 - full)

tabla = q.rename(columns={"vendor":"Medio","format":"Formato","medium":"Canal"})

# Mostrar fechas solo si fueron aplicadas (sin hora)
show_dates = bool(st.session_state.get("plan_dates", {}).get("applied"))
if show_dates:
    ini = pd.to_datetime(st.session_state["plan_dates"]["start"])
    fin = pd.to_datetime(st.session_state["plan_dates"]["end"])
    tabla["Inicio"] = pd.Series([ini]).repeat(len(q)).dt.strftime("%Y-%m-%d").values
    tabla["Fin"]    = pd.Series([fin]).repeat(len(q)).dt.strftime("%Y-%m-%d").values

tabla["Costo"] = q["costo_unitario"].round(2)
tabla["Unidad"] = sel_unit
tabla["Calificación"] = q["rating"].apply(stars)

base_cols = ["Medio","Formato","Canal","Costo","Unidad","Calificación"]
cols_show = (["Medio","Formato","Canal","Inicio","Fin","Costo","Unidad","Calificación"]
             if show_dates else base_cols)

st.subheader("Seleccionar para el plan")
display_idx = tabla.reset_index().rename(columns={"index":"row_id"})
st.dataframe(display_idx[["row_id"] + cols_show], use_container_width=True, height=520)

selected_ids = st.multiselect(
    "IDs seleccionados",
    options=display_idx["row_id"].astype(str).tolist(),
    key="ms_ids"  # <-- clave única
)

if st.button("Agregar al Planner", key="btn_add_planner"):
    if "basket" not in st.session_state:
        st.session_state.basket = pd.DataFrame()
    take = display_idx[display_idx["row_id"].astype(str).isin(selected_ids)].index
    to_add = q.iloc[take].copy()
    to_add["selected_unit"] = sel_unit
    to_add["selected_unit_cost"] = to_add["costo_unitario"]

    # 🧹 Evitar duplicados por (Medio, Formato, Canal, Fechas)
    combined = pd.concat([st.session_state.basket, to_add], ignore_index=True)
    st.session_state.basket = combined.drop_duplicates(
        subset=["vendor","format","medium","start","end"], keep="first"
    ).reset_index(drop=True)

    st.success(f"Se agregaron {len(take)} ítems al Planner (sin duplicados).")


# (Opcional) KPIs rápidos
if not q.empty:
    s = kpi_summary(q)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Ofertas visibles", f"{s['total']['invs']}")
    c2.metric("Costo total (suma bruta)", f"{s['total']['cost']:,.0f}")
    c3.metric("Imp. totales", f"{s['total']['impressions']:,.0f}")
    c4.metric("GRPs totales", f"{s['total']['grps']:,.1f}")
