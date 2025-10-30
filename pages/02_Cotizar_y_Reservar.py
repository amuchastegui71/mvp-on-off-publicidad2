# pages/02_Cotizar_y_Reservar.py
import streamlit as st
import pandas as pd
import numpy as np

from utils import (
    registrar_evento,
    preparar_plan_para_export_budget_simple,
    totales_plan_budget_simple,
    costo_unitario_visible,
    get_selected_unit,
    estimate_impressions,
)

st.set_page_config(page_title="Cotizar y Reservar", layout="wide")
st.title("Cotizar y Reservar (por presupuesto)")

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def make_uid(row) -> str:
    """UID estable por fila para keys de widgets y borrado."""
    parts = [
        str(row.get("vendor", "")),
        str(row.get("format", "")),
        str(row.get("medium", "")),
        str(row.get("start", "")),
        str(row.get("end", "")),
    ]
    return "||".join(parts)

def _fmt_date(x) -> str:
    """Fecha YYYY-MM-DD (sin hora); vacío si no hay valor."""
    try:
        return pd.to_datetime(x).strftime("%Y-%m-%d")
    except Exception:
        return ""

# ------------------------------------------------------------------------------
# Datos del plan
# ------------------------------------------------------------------------------
plan = st.session_state.get("basket", pd.DataFrame())
if plan.empty:
    st.info("Tu plan está vacío. Volvé al **Marketplace** y agregá ítems.")
    st.stop()

st.subheader("Resumen del plan")

# Evitar duplicados que puedan venir del Marketplace
editable = (
    plan.copy()
    .drop_duplicates(subset=["vendor", "format", "medium", "start", "end"], keep="first")
    .reset_index(drop=True)
)

# Estado: presupuesto entero por UID (no por índice)
if "budget_map" not in st.session_state:
    st.session_state.budget_map = {}

rows_out = []

# ------------------------------------------------------------------------------
# Render por ítem (una sola tarjeta)
# ------------------------------------------------------------------------------
for i, row in editable.iterrows():
    uid = make_uid(row)

    with st.container(border=True):
        # Fila 1: Medio / Formato / Canal / Unidad-Costo + tacho a la derecha
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 0.6])
        c1.markdown(f"**Medio:** {row.get('vendor', '')}")
        c2.markdown(f"**Formato:** {row.get('format', '')}")
        c3.markdown(f"**Canal:** {row.get('medium', '')}")
        unidad = get_selected_unit(row)
        unit_cost = costo_unitario_visible(row)
        c4.markdown(f"**Unidad / Costo:** {unidad} — {unit_cost:,.2f}")

        if c5.button("🗑️", key=f"del_{uid}", help="Eliminar este medio del plan"):
            # Borrado robusto por coincidencia de campos (no por índice)
            b = st.session_state.basket.copy()

            def _s(val):
                return "" if pd.isna(val) else str(val)

            mask = (
                (b["vendor"].astype(str) == _s(row.get("vendor", ""))) &
                (b["format"].astype(str) == _s(row.get("format", ""))) &
                (b["medium"].astype(str) == _s(row.get("medium", ""))) &
                (b.get("start", "").astype(str) == _s(row.get("start", ""))) &
                (b.get("end", "").astype(str) == _s(row.get("end", "")))
            )
            st.session_state.basket = b.loc[~mask].reset_index(drop=True)
            st.session_state.budget_map.pop(uid, None)
            st.rerun()

        # Fila 2: Fechas SOLO si existen (en una línea)
        start_raw = row.get("start", "")
        end_raw = row.get("end", "")
        parts = []
        if pd.notna(start_raw) and str(start_raw) != "":
            parts.append(f"**Inicio:** {_fmt_date(start_raw)}")
        if pd.notna(end_raw) and str(end_raw) != "":
            parts.append(f"**Fin:** {_fmt_date(end_raw)}")
        if parts:
            st.markdown(" · ".join(parts))

        st.divider()

        # Fila 3: Presupuesto entero + Impresiones estimadas
        b1, b2 = st.columns([2, 4])
        default_budget = int(st.session_state.budget_map.get(uid, 10000))
        presupuesto = b1.number_input(
            "Presupuesto del ítem",
            min_value=0,
            step=100,
            value=default_budget,
            format="%d",
            key=f"budget_{uid}",
        )
        st.session_state.budget_map[uid] = int(presupuesto)

        est_imp = estimate_impressions(row, float(presupuesto))
        if pd.notna(est_imp):
            b2.metric("Impresiones estimadas", f"{est_imp:,.0f}")
        else:
            b2.info("No hay benchmarks suficientes para estimar impresiones con la unidad seleccionada.")

        # Guardar fila con presupuesto
        cur = row.copy()
        cur["budget"] = int(presupuesto)
        rows_out.append(cur)

# ------------------------------------------------------------------------------
# Totales + acciones
# ------------------------------------------------------------------------------
plan_presupuesto = pd.DataFrame(rows_out)
resumen = totales_plan_budget_simple(plan_presupuesto)

st.divider()
c1, c2 = st.columns(2)
c1.metric("Ítems", f"{resumen['items']}")
c2.metric("Presupuesto total", f"{resumen['subtotal']:,.0f}")

# ------------------------------------------------------------------------------
# Acciones (un solo botón con modo)
# ------------------------------------------------------------------------------
st.subheader("Acciones")

# Modo de operación: define el tipo de evento que se registra
modo_accion = st.radio("Modo", ["Cotizar", "Reservar"], horizontal=True, key="modo_accion_unico")

df_export = preparar_plan_para_export_budget_simple(plan_presupuesto)
csv_bytes = df_export.to_csv(index=False).encode("utf-8")

# Descarga de la cotización siempre disponible (independiente del modo)
st.download_button(
    "⬇️ Descargar cotización (CSV)",
    data=csv_bytes,
    file_name="cotizacion_plan.csv",
    mime="text/csv",
    key="btn_dl_quote_unico",
)

# Único botón de confirmación
if st.button("Confirmar", key="btn_confirmar_unico"):
    payload = {
        "items": int(resumen["items"]),
        "subtotal": float(resumen["subtotal"]),
        "detalle": df_export.to_dict(orient="records"),
        "modo": modo_accion.lower(),  # "cotizar" o "reservar"
    }
    evento = "cotizacion_budget" if modo_accion == "Cotizar" else "reserva_budget"
    registrar_evento(evento, payload)
    st.success(f"✅ {modo_accion} registrada en `data/events_log.jsonl`.")
