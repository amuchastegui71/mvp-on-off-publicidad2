# pages/01_Marketplace.py
import io
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from datetime import date
from utils import unify_schema  # se mantiene tu helper

st.set_page_config(page_title="Marketplace ON/OFF", layout="wide")
st.title("Marketplace ON/OFF")
st.caption("Elegí medios y formatos según costos, reseñas y unidad de costo. Agregá al plan.")

# -------------------------------
# Loader robusto: lee data/inventario_on.csv y data/inventario_off.csv
# -------------------------------
def load_integrated_catalog() -> pd.DataFrame:
    base = Path("data")
    on_path  = base / "inventario_on.csv"
    off_path = base / "inventario_off.csv"

    def read_csv_loose(p: Path):
        """Lee CSV tolerante a coma/; y comillas. Devuelve DataFrame o None."""
        if not p.exists():
            return None
        raw = p.read_text(encoding="utf-8", errors="ignore")
        for attempt in (raw, raw.replace('"', '')):
            try:
                df_try = pd.read_csv(io.StringIO(attempt), sep=None, engine="python")
                if df_try.shape[1] > 1:
                    return df_try
            except Exception:
                continue
        return None

    df_on  = read_csv_loose(on_path)
    df_off = read_csv_loose(off_path)

    if df_on is None and df_off is None:
        return pd.DataFrame()

    parts = []
    if df_on is not None:  parts.append(df_on)
    if df_off is not None: parts.append(df_off)
    df_raw = pd.concat(parts, ignore_index=True)

    # Normalizar encabezados
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    rename_map = {
        "medio": "medium", "proveedor": "vendor", "medios":"vendor", "formato": "format",
        "impresiones": "impressions", "clics": "clicks", "vistas": "views",
        "costo": "cost", "calificacion": "rating", "calificación": "rating", "tipo":"medium_type"
    }
    for k,v in rename_map.items():
        if k in df_raw.columns and v not in df_raw.columns:
            df_raw = df_raw.rename(columns={k:v})

    # Asegurar columnas mínimas
    need_cols = ["medium","vendor","format","impressions","grps","clicks","views","cost","rating","medium_type","leads"]
    for c in need_cols:
        if c not in df_raw.columns:
            df_raw[c] = np.nan

    # Limpieza numérica inteligente (respeta decimales como 4.5)
    def clean_num_series(s: pd.Series) -> pd.Series:
        s = s.astype(str).str.strip()
        # "1.234,56" -> "1234.56"
        both = s.str.contains(",", regex=False) & s.str.contains(r"\.", regex=True)
        s = s.where(~both, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
        # "123,45" -> "123.45"
        only_comma = s.str.contains(",", regex=False) & ~s.str.contains(r"\.", regex=True)
        s = s.where(~only_comma, s.str.replace(",", ".", regex=False))
        return pd.to_numeric(s, errors="coerce")

    for c in ["impressions","grps","clicks","views","cost","leads","actions","rating","CPM","CPC","CPL","CPA"]:
        if c in df_raw.columns:
            df_raw[c] = clean_num_series(df_raw[c])

    # medium_type si falta
    if "medium_type" not in df_raw.columns or df_raw["medium_type"].isna().all():
        off_set = {"TV","Radio","Vía Pública","Via Pública","OOH","Cines","Print"}
        df_raw["medium_type"] = np.where(df_raw["medium"].isin(off_set), "OFF", "ON")

    # Derivados de costos
    if "CPM" not in df_raw.columns:
        df_raw["CPM"] = np.nan
    imps = pd.to_numeric(df_raw["impressions"], errors="coerce")
    df_raw.loc[imps.gt(0), "CPM"] = df_raw.loc[imps.gt(0), "cost"] / df_raw.loc[imps.gt(0), "impressions"] * 1000

    if "CPC" not in df_raw.columns:
        df_raw["CPC"] = np.nan
    clicks = pd.to_numeric(df_raw["clicks"], errors="coerce")
    df_raw.loc[clicks.gt(0), "CPC"] = df_raw.loc[clicks.gt(0), "cost"] / df_raw.loc[clicks.gt(0), "clicks"]

    if "CPL" not in df_raw.columns:
        df_raw["CPL"] = np.nan
    cpl_vendors = {"PML","US Media","Logan","TikTok"}  # NO Mercado Ads, NO Spotify, NO RappiAds
    leads = pd.to_numeric(df_raw["leads"], errors="coerce")
    mask_cpl = df_raw["vendor"].isin(cpl_vendors) & leads.gt(0)
    df_raw.loc[mask_cpl, "CPL"] = df_raw.loc[mask_cpl, "cost"] / df_raw.loc[mask_cpl, "leads"]

    # OFF: solo CPM
    is_off = df_raw["medium_type"].astype(str).str.upper().eq("OFF")
    df_raw.loc[is_off, ["CPC","CPL","CPA"]] = np.nan

    # Redondeos
    for c in ["CPM","CPC","CPL"]:
        if c in df_raw.columns:
            df_raw[c] = df_raw[c].astype(float).round(2)

    return unify_schema(df_raw, None)

# Cargar inventario
df = load_integrated_catalog()
if df.empty:
    st.error("No se pudo cargar el inventario. Verificá que existan:\n- data/inventario_on.csv\n- data/inventario_off.csv\n(con encabezados).")
    st.stop()

# -------------------------------
# Filtros (sidebar)
# -------------------------------
with st.sidebar:
    st.header("Filtros")
    tipos = sorted([t for t in ["ON","OFF"] if t in df.get("medium_type", pd.Series()).dropna().unique().tolist()] or ["ON","OFF"])
    mtype = st.multiselect("Tipo", options=tipos, default=tipos, key="flt_tipo")

    formatos_opts = sorted(df.get("medium", pd.Series()).dropna().unique().tolist())
    medios_opts   = sorted(df.get("vendor", pd.Series()).dropna().unique().tolist())
    canales_opts  = sorted(df.get("format", pd.Series()).dropna().unique().tolist())

    sel_formatos = st.multiselect("Formatos", formatos_opts, key="flt_formatos")
    sel_medios   = st.multiselect("Medios",   medios_opts,   key="flt_medios")
    sel_canales  = st.multiselect("Canales",  canales_opts,  key="flt_canales")

    st.markdown("---")
    st.subheader("Unidad de costo")

# Aplicar filtros
q = df.copy()
if mtype:        q = q[q["medium_type"].isin(mtype)]
if sel_formatos: q = q[q["medium"].isin(sel_formatos)]
if sel_medios:   q = q[q["vendor"].isin(sel_medios)]
if sel_canales:  q = q[q["format"].isin(sel_canales)]

# Derivados de costo por si faltan en datos de entrada (CPM/CPC/CPL)
if "CPM" not in q.columns: q["CPM"] = np.nan
imps = pd.to_numeric(q.get("impressions"), errors="coerce")
q["CPM"] = q["CPM"].where(q["CPM"].notna(),
                          np.where(imps.gt(0), pd.to_numeric(q.get("cost"), errors="coerce") / imps * 1000, np.nan))

if "CPC" not in q.columns: q["CPC"] = np.nan
clicks = pd.to_numeric(q.get("clicks"), errors="coerce")
q["CPC"] = q["CPC"].where(q["CPC"].notna(),
                          np.where(clicks.gt(0), pd.to_numeric(q.get("cost"), errors="coerce") / clicks, np.nan))

if "CPL" not in q.columns: q["CPL"] = np.nan
leads = pd.to_numeric(q.get("leads"), errors="coerce")
q["CPL"] = q["CPL"].where(q["CPL"].notna(),
                          np.where(q["vendor"].isin({"PML","US Media","Logan","TikTok"}) & leads.gt(0),
                                   pd.to_numeric(q.get("cost"), errors="coerce") / leads,
                                   np.nan))

# Unidades disponibles según datos visibles
allowed_units = ["CPM","CPC","CPL","CPA"]
units_present = []
for u in allowed_units:
    if u in q.columns:
        col = pd.to_numeric(q[u], errors="coerce")
        if col.notna().any() and (col.fillna(0) > 0).any():
            units_present.append(u)
if not units_present:
    units_present = ["CPM"]

with st.sidebar:
    sel_unit = st.selectbox("Unidad aplicable", options=units_present, index=0, key="flt_unit")

# Costo unitario elegido
q["costo_unitario"] = pd.to_numeric(q.get(sel_unit, np.nan), errors="coerce")

# -------------------------------
# Fechas de campaña (opcional)
# -------------------------------
if "plan_dates" not in st.session_state:
    st.session_state.plan_dates = {"applied": False, "start": None, "end": None}

with st.sidebar:
    st.markdown("---")
    st.subheader("Fechas de campaña (opcional)")
    use_dates = st.checkbox("Definir fechas", value=st.session_state.plan_dates["applied"], key="chk_dates")
    if use_dates:
        start_input = st.date_input("Inicio", value=st.session_state.plan_dates["start"] or date.today(), key="dt_start")
        end_input   = st.date_input("Fin", value=st.session_state.plan_dates["end"] or date.today(), key="dt_end")
        if st.button("Aplicar fechas", key="btn_apply_dates"):
            st.session_state.plan_dates = {"applied": True, "start": start_input, "end": end_input}
            st.rerun()
    else:
        st.session_state.plan_dates = {"applied": False, "start": None, "end": None}

dates_applied = bool(st.session_state.get("plan_dates", {}).get("applied"))
start_val = st.session_state["plan_dates"]["start"]
end_val   = st.session_state["plan_dates"]["end"]

# -------------------------------
# Tabla
# -------------------------------
def stars(x, show_num=False):
    try:
        v = float(x)
    except Exception:
        return ""
    v = max(0.0, min(5.0, v))    # clamp 0..5
    full = int(v)                # piso (4.6 => 4 estrellas)
    s = "★" * full + "☆" * (5 - full)
    return f"{s} ({v:.1f})" if show_num else s

# Asegurar rating numérico tras limpieza
q["rating_num"] = pd.to_numeric(q.get("rating"), errors="coerce")

tabla = q.rename(columns={"vendor":"Medio","format":"Formato","medium":"Canal"}).copy()
# ARS sin decimales, separador de miles con punto
tabla["Costo"] = q["costo_unitario"].apply(lambda x: "$ " + f"{int(round(x)):,.0f}".replace(",", ".") if pd.notna(x) else "—")
tabla["Unidad"] = sel_unit
tabla["Calificación"] = q["rating_num"].apply(lambda v: stars(v, show_num=False))

if dates_applied and start_val and end_val:
    tabla["Inicio"] = pd.to_datetime(start_val).strftime("%Y-%m-%d")
    tabla["Fin"]    = pd.to_datetime(end_val).strftime("%Y-%m-%d")
    cols_show = ["Medio","Formato","Canal","Inicio","Fin","Costo","Unidad","Calificación"]
else:
    cols_show = ["Medio","Formato","Canal","Costo","Unidad","Calificación"]

st.subheader("Seleccionar para el plan")
display_idx = tabla.reset_index().rename(columns={"index":"row_id"})

st.dataframe(
    display_idx[["row_id"] + cols_show].rename(columns={"row_id": "ID"}),
    use_container_width=True,
    height=520,
    hide_index=True
)

# Selección para Planner (si hay fechas aplicadas, las guardamos)
selected_ids = st.multiselect(
    "IDs seleccionados",
    options=display_idx["row_id"].astype(str).tolist(),
    key="ms_ids"
)

if st.button("Agregar al Planner", key="btn_add_planner"):
    if "basket" not in st.session_state:
        st.session_state.basket = pd.DataFrame()
    take = display_idx[display_idx["row_id"].astype(str).isin(selected_ids)].index
    to_add = q.iloc[take].copy()
    to_add["selected_unit"] = sel_unit
    to_add["selected_unit_cost"] = to_add["costo_unitario"]
    # Si se aplicaron fechas, las añadimos a los ítems seleccionados
    if dates_applied and start_val and end_val:
        to_add["start"] = pd.to_datetime(start_val)
        to_add["end"]   = pd.to_datetime(end_val)

    combined = pd.concat([st.session_state.basket, to_add], ignore_index=True)
    # Si hay fechas, considerar en la deduplicación
    dedup_keys = ["vendor","format","medium"] + (["start","end"] if dates_applied else [])
    st.session_state.basket = combined.drop_duplicates(subset=dedup_keys, keep="first").reset_index(drop=True)
    st.success(f"Se agregaron {len(take)} ítems al Planner (sin duplicados).")
