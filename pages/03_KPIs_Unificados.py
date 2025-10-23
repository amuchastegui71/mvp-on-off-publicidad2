import streamlit as st
import pandas as pd
from utils import cpm_efectivo, estimar_alcance_digital, estimar_grps, ctr_placeholder

st.title("KPIs Unificados")

if "carrito" not in st.session_state or len(st.session_state.carrito)==0:
    st.warning("El carrito está vacío. Agregue inventario desde 'Buscar Inventario'.")
    st.stop()

df = pd.DataFrame(st.session_state.carrito).copy()

mask_on = df["tipo"]=="ON"
df_on = df[mask_on].copy()
if not df_on.empty:
    df_on["costo"] = (df_on["impresiones_previstas"]/1000.0) * df_on["cpm"]
    df_on["alcance_est"] = df_on["impresiones_previstas"].apply(estimar_alcance_digital)
    df_on["ctr_est"] = [ctr_placeholder(m,f) for m,f in zip(df_on["medio"], df_on["formato"])]
else:
    df_on = pd.DataFrame(columns=["costo","alcance_est","ctr_est"])

mask_off = df["tipo"]=="OFF"
df_off = df[mask_off].copy()
if not df_off.empty:
    df_off["costo"] = df_off["unidades"] * df_off["tarifa_unitaria"]
    df_off["grps_est"] = df_off["rating_promedio"] * df_off["unidades"]
else:
    df_off = pd.DataFrame(columns=["costo","grps_est"])

costo_total = df_on["costo"].sum() + df_off["costo"].sum()
impresiones_totales = df_on["impresiones_previstas"].sum() if "impresiones_previstas" in df_on else 0
alcance_total = df_on["alcance_est"].sum() if "alcance_est" in df_on else 0
grps_total = df_off["grps_est"].sum() if "grps_est" in df_off else 0

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Costo total", f"{round(costo_total,2)}")
with c2: st.metric("CPM efectivo (ON)", cpm_efectivo(costo_total, max(1, impresiones_totales)))
with c3: st.metric("Alcance (est.) ON", int(alcance_total))
with c4: st.metric("GRPs (est.) OFF", round(grps_total,1))

st.markdown("### Detalle ON")
st.dataframe(df_on, use_container_width=True, height=280)

st.markdown("### Detalle OFF")
st.dataframe(df_off, use_container_width=True, height=280)

st.caption("Nota: KPIs demostrativos. Sustituir por metodología y fuentes reales.")
