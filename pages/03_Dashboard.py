# pages/03_KPIs_Unificados.py
import streamlit as st
import pandas as pd
import numpy as np
from typing import Tuple

# Helpers opcionales del proyecto (si no están, hay fallbacks abajo)
try:
    from utils import estimate_impressions, get_selected_unit, costo_unitario_visible
except Exception:
    estimate_impressions = None
    get_selected_unit = None
    costo_unitario_visible = None

st.set_page_config(page_title="KPIs unificados (ON/OFF)", layout="wide")
st.title("KPIs unificados (ON/OFF)")
st.caption("Métricas integradas para análisis de campaña y toma de decisiones.")

# =========================
# Datos base (basket/plan)
# =========================
plan = st.session_state.get("basket", pd.DataFrame())
if plan.empty:
    st.info("No hay items en el plan. Agregá medios desde **Marketplace**.")
    st.stop()

df = (
    plan.copy()
    .drop_duplicates(subset=["vendor", "format", "medium", "start", "end"], keep="first")
    .reset_index(drop=True)
)

# Benchmarks default (para evitar ceros y permitir estimaciones)
DEFAULT_BENCH = {
    "Display": {"ctr": 0.008, "cvr": 0.03},
    "Video":   {"ctr": 0.003, "cvr": 0.02},
    "Social":  {"ctr": 0.015, "cvr": 0.04},
    "Search":  {"ctr": 0.03,  "cvr": 0.05},
    "TV":      {"ctr": 0.0005, "cvr": 0.005},
    "Radio":   {"ctr": 0.0002, "cvr": 0.003},
    "OOH":     {"ctr": 0.0001, "cvr": 0.002},
    "Print":   {"ctr": 0.0002, "cvr": 0.002},
}

def bmark_for_channel(medium_val: str) -> Tuple[float, float]:
    m = str(medium_val or "").strip().lower()
    for key, d in DEFAULT_BENCH.items():
        if key.lower() in m:
            return float(d["ctr"]), float(d["cvr"])
    return 0.01, 0.03  # fallback

# Presupuestos (si 02 guardó budget_map, lo usamos; si no, valor por defecto)
budget_map = st.session_state.get("budget_map", {})
DEFAULT_BUDGET = 10000

def selected_unit(row):
    if get_selected_unit:
        return get_selected_unit(row)
    for c in ["selected_unit", "CPM", "CPC", "CPL", "CPA"]:
        if c in row and pd.notna(row[c]) and str(row[c]) != "":
            if c == "selected_unit":
                return str(row[c])
            try:
                if float(row[c]) > 0:
                    return c
            except Exception:
                pass
    return "CPM"

def unit_cost_visible(row):
    if costo_unitario_visible:
        return float(costo_unitario_visible(row))
    for c in ["selected_unit_cost", "CPM", "CPC", "CPL", "CPA", "cost"]:
        v = row.get(c)
        try:
            v = float(v)
        except Exception:
            v = np.nan
        if pd.notna(v) and v > 0:
            return v
    return 0.0

def est_impr(row, budget: float):
    if estimate_impressions is not None:
        return float(estimate_impressions(row, float(budget)))
    unit = selected_unit(row)
    try_cpm = float(row.get("CPM", np.nan)) if pd.notna(row.get("CPM", np.nan)) else np.nan
    cpc = float(row.get("CPC", np.nan)) if pd.notna(row.get("CPC", np.nan)) else np.nan
    cpl = float(row.get("CPL", np.nan)) if pd.notna(row.get("CPL", np.nan)) else np.nan
    cpa = float(row.get("CPA", np.nan)) if pd.notna(row.get("CPA", np.nan)) else np.nan
    ctr, cvr = bmark_for_channel(row.get("medium", ""))

    if unit == "CPM" and pd.notna(try_cpm) and try_cpm > 0:
        return budget / try_cpm * 1000.0
    if unit == "CPC" and pd.notna(cpc) and cpc > 0 and ctr > 0:
        clicks = budget / cpc
        return clicks / ctr
    if unit == "CPL" and pd.notna(cpl) and cpl > 0 and cvr > 0 and ctr > 0:
        leads = budget / cpl
        clicks = leads / cvr
        return clicks / ctr
    if unit == "CPA" and pd.notna(cpa) and cpa > 0 and cvr > 0 and ctr > 0:
        actions = budget / cpa
        leads = actions / cvr
        clicks = leads / cvr
        return clicks / ctr
    if pd.notna(try_cpm) and try_cpm > 0:
        return budget / try_cpm * 1000.0
    return np.nan

# =========================
# Construcción del KPI set
# =========================
rows = []
for _, r in df.iterrows():
    uid = "||".join([str(r.get(c, "")) for c in ["vendor", "format", "medium", "start", "end"]])
    budget = int(budget_map.get(uid, DEFAULT_BUDGET))
    unit = selected_unit(r)
    ucost = unit_cost_visible(r)
    impr = est_impr(r, budget)
    ctr, cvr = bmark_for_channel(r.get("medium", ""))

    # derivaciones suaves (para análisis agregado; se ocultan si no aplican)
    clicks = impr * ctr if pd.notna(impr) else np.nan
    leads = (clicks * cvr) if pd.notna(clicks) else np.nan

    rows.append({
        "medium_type": r.get("medium_type", ""),
        "medium": r.get("medium", ""),
        "vendor": r.get("vendor", ""),
        "format": r.get("format", ""),
        "unit": unit,
        "unit_cost": ucost,
        "budget": budget,
        "est_impr": impr,
        "est_clicks": clicks,
        "est_leads": leads,
        "rating": r.get("rating", np.nan),
        "score": r.get("score", np.nan),
    })

kpi = pd.DataFrame(rows)
kpi_fill = kpi.fillna(0)

# =========================
# (1) Resumen ejecutivo
# =========================
st.subheader("Resumen ejecutivo")

total_budget = float(kpi_fill["budget"].sum())
total_impr = float(kpi_fill["est_impr"].sum())
blended_cpm = (total_budget / total_impr * 1000.0) if total_impr > 0 else np.nan

on_budget = float(kpi_fill.loc[kpi_fill["medium_type"] == "ON", "budget"].sum())
off_budget = float(kpi_fill.loc[kpi_fill["medium_type"] == "OFF", "budget"].sum())
on_share = (on_budget / total_budget) if total_budget > 0 else np.nan
off_share = (off_budget / total_budget) if total_budget > 0 else np.nan

c1, c2, c3 = st.columns(3)
c1.metric("Presupuesto total (USD)", f"{total_budget:,.0f}")
c2.metric("Impresiones estimadas", f"{total_impr:,.0f}")
c3.metric("CPM mixto (USD)", f"{blended_cpm:,.2f}" if pd.notna(blended_cpm) else "—")

# Mix ON/OFF sin truncar
st.markdown(
    f"**Mix ON/OFF:** "
    f"{'—' if pd.isna(on_share) else f'ON {on_share:.0%}'}  ·  "
    f"{'—' if pd.isna(off_share) else f'OFF {off_share:.0%}'}"
)

st.divider()

# =========================
# (2) Eficiencias por canal
# =========================
st.subheader("Eficiencias por canal (CPM mixto, rating y score)")
by_medium = kpi_fill.groupby("medium").agg(
    presupuesto=("budget", "sum"),
    impresiones=("est_impr", "sum"),
    rating_prom=("rating", "mean"),
    score_prom=("score", "mean"),
).reset_index()
by_medium["CPM_mixto"] = np.where(
    by_medium["impresiones"] > 0,
    by_medium["presupuesto"] / by_medium["impresiones"] * 1000.0,
    np.nan
)

st.dataframe(
    by_medium[["medium", "presupuesto", "impresiones", "CPM_mixto", "rating_prom", "score_prom"]]
    .sort_values("CPM_mixto", na_position="last"),
    use_container_width=True
)

st.divider()

# =========================
# (3) Distribución de inversión
# =========================
st.subheader("Distribución de inversión")
col_a, col_b = st.columns(2)

with col_a:
    inv_por_canal = (
        kpi_fill.groupby("medium", as_index=False)["budget"].sum().sort_values("budget", ascending=False)
    )
    st.markdown("**Por canal**")
    st.bar_chart(inv_por_canal.set_index("medium"))

with col_b:
    inv_por_tipo = (
        kpi_fill.groupby("medium_type", as_index=False)["budget"].sum().sort_values("budget", ascending=False)
    )
    st.markdown("**ON vs OFF**")
    st.bar_chart(inv_por_tipo.set_index("medium_type"))

st.divider()

# =========================
# (4) Detalle por medio
# =========================
st.subheader("Detalle por medio")
detalle_cols = ["vendor", "format", "medium", "unit", "unit_cost", "budget", "est_impr", "rating", "score"]
st.dataframe(
    kpi_fill[detalle_cols].sort_values(["medium", "vendor"]),
    use_container_width=True, height=360
)

st.divider()

# =========================
# (5) Panel "tiempo real" (prototipo)
# =========================
st.subheader("Panel de seguimiento en tiempo real (prototipo)")


# Controles demo (no traen datos reales; sirven para visualizar el panel)
col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    camp_days = st.number_input("Duración campaña (días)", min_value=1, value=30, step=1, format="%d")
with col_cfg2:
    day_now = st.slider("Día actual de la campaña", min_value=1, max_value=camp_days, value=min(7, camp_days), step=1)

time_progress = day_now / camp_days

# Derivaciones simples para demo (no son datos reales)
planned_impr = total_impr if total_impr > 0 else 1_000_000
delivered_impr = planned_impr * min(time_progress * 0.95, 1.0)  # simulación de leve infrapacing
pacing_spend = time_progress * 0.9  # 10% por debajo del ideal en esta demo

ra, rb, rc = st.columns(3)
ra.metric("Alcance entregado", f"{delivered_impr:,.0f}", help="Impresiones servidas hasta hoy (estimado).")
rb.metric("Pacing de inversión", f"{pacing_spend:,.0%}", help="Gasto acumulado sobre el total planificado.")
rc.metric("Progreso temporal", f"{time_progress:,.0%}", help="% de días transcurridos respecto al total de la campaña.")

st.progress(min(pacing_spend, 1.0), text="Pacing vs tiempo")

# Métricas ON (solo visualización con valores ejemplo)
on_ctr = 0.008  # 0.8%
on_view = 0.62  # 62%
on_cvr = 0.03   # 3%
rd, re, rf = st.columns(3)
rd.metric("Viewability (ON)", f"{on_view:.0%}", help="Porcentaje de impresiones visibles (MRC).")
re.metric("CTR (ON)", f"{on_ctr:.2%}", help="Tasa de clics promedio.")
rf.metric("CVR (ON)", f"{on_cvr:.2%}", help="Tasa de conversión promedio en ON.")

# Métricas OFF (ejemplos)
off_grps = 120.0
off_spots = 230
off_ooh = 4800
rg, rh, ri = st.columns(3)
rg.metric("GRPs entregados (OFF)", f"{off_grps:.1f}", help="Puntos de rating brutos acumulados.")
rh.metric("Spots emitidos (OFF)", f"{off_spots:,}", help="Cantidad de spots pautados efectivamente.")
ri.metric("OOH plays (OFF)", f"{off_ooh:,}", help="Reproducciones en vía pública.")

st.markdown(
    "- **Alcance entregado vs plan**: impresiones efectivamente servidas comparadas contra impresiones planificadas.\n"
    "- **Pacing de inversión**: % gastado vs % de tiempo transcurrido. Detecta sobre/infra-delivery.\n"
    "- **Viewability (ON)**: % de impresiones visibles (MRC). Clave para calidad de exposición.\n"
    "- **CTR (ON)**: tasa de clics; proxy de interés. Útil en Display/Social/Search.\n"
    "- **CVR / CPA (ON)**: conversión y costo por acción; métricas de performance.\n"
    "- **GRPs entregados (OFF)**: presión publicitaria efectiva en TV/Radio.\n"
    "- **Spots emitidos / OOH plays (OFF)**: control operativo/logístico.\n"
    "- **Alertas**: pacing fuera de tolerancia, viewability baja, CTR anómalo, desvío de GRPs."
)

st.info(
    "Este panel ilustra **qué** se monitorearía en vivo. En una versión productiva, estos valores "
    "se alimentarían desde ad servers, DSPs/SSPs, herramientas de analítica y proveedores OFF (logs de emisión)."
)
