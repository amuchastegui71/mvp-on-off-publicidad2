import streamlit as st
import pandas as pd
from utils import registrar_evento

st.title("Cotizar y Reservar")

if "carrito" not in st.session_state or len(st.session_state.carrito)==0:
    st.warning("El carrito está vacío. Agregue inventario desde 'Buscar Inventario'.")
    st.stop()

df = pd.DataFrame(st.session_state.carrito).copy()

st.markdown("### Parámetros")
c1, c2 = st.columns(2)
with c1:
    presupuesto = st.number_input("Presupuesto total", min_value=0.0, value=float(df.get("precio_referencia", pd.Series([0])).sum()))
with c2:
    estrategia = st.selectbox("Estrategia", ["Proporcional a precio", "50% ON / 50% OFF"])

df["costo_estimado"] = 0.0
mask_on = df["tipo"]=="ON"
mask_off = df["tipo"]=="OFF"
if mask_on.any():
    df.loc[mask_on, "costo_estimado"] = (df.loc[mask_on, "impresiones_previstas"]/1000.0) * df.loc[mask_on, "cpm"]
if mask_off.any():
    df.loc[mask_off, "costo_estimado"] = df.loc[mask_off, "unidades"] * df.loc[mask_off, "tarifa_unitaria"]

costo_total_ref = df["costo_estimado"].sum()
st.metric("Costo estimado (referencia)", round(costo_total_ref,2))

df["asignado"] = 0.0
if estrategia == "Proporcional a precio" and costo_total_ref > 0:
    df["asignado"] = presupuesto * (df["costo_estimado"] / costo_total_ref)
elif estrategia == "50% ON / 50% OFF":
    total_on = df.loc[mask_on, "costo_estimado"].sum()
    total_off = df.loc[mask_off, "costo_estimado"].sum()
    if total_on>0:
        df.loc[mask_on, "asignado"] = (presupuesto*0.5) * (df.loc[mask_on, "costo_estimado"] / total_on)
    if total_off>0:
        df.loc[mask_off, "asignado"] = (presupuesto*0.5) * (df.loc[mask_off, "costo_estimado"] / total_off)

st.markdown("### Detalle de cotización")
st.dataframe(df, use_container_width=True, height=360)

if st.button("Generar Orden (CSV)"):
    out = df.copy()
    out.to_csv("data/orden_compra.csv", index=False)
    registrar_evento({"ts": pd.Timestamp.utcnow().isoformat(), "tipo":"orden_csv", "detalle":"orden_compra.csv", "valor": float(presupuesto)})
    st.success("Orden generada en data/orden_compra.csv")
    st.download_button("Descargar orden_compra.csv", data=out.to_csv(index=False).encode("utf-8"), file_name="orden_compra.csv", mime="text/csv")
