import streamlit as st
import pandas as pd
from utils import cargar_inventario, registrar_evento

st.title("Buscar Inventario ON/OFF")

tab_on, tab_off = st.tabs(["ON (Digital)", "OFF (Tradicional)"])

if "carrito" not in st.session_state:
    st.session_state.carrito = []

with tab_on:
    st.subheader("Digital: Display, Video, CTV, DOOH")
    df_on = cargar_inventario("data/inventario_on.csv")
    c1, c2, c3, c4 = st.columns(4)
    with c1: medio = st.selectbox("Medio", ["Todos"] + sorted(df_on["medio"].unique()))
    with c2: formato = st.selectbox("Formato", ["Todos"] + sorted(df_on["formato"].unique()))
    with c3: ubic = st.selectbox("Ubicación", ["Todas"] + sorted(df_on["ubicacion"].unique()))
    with c4: proveedor = st.selectbox("Proveedor", ["Todos"] + sorted(df_on["proveedor"].unique()))
    f = df_on.copy()
    if medio!="Todos": f=f[f["medio"]==medio]
    if formato!="Todos": f=f[f["formato"]==formato]
    if ubic!="Todas": f=f[f["ubicacion"]==ubic]
    if proveedor!="Todos": f=f[f["proveedor"]==proveedor]
    st.dataframe(f, use_container_width=True, height=320)
    sel = st.multiselect("IDs a agregar (ON)", f["id"].astype(str).tolist())
    if st.button("Agregar selección (ON)"):
        add = df_on[df_on["id"].astype(str).isin(sel)].to_dict(orient="records")
        st.session_state.carrito += [{"tipo":"ON", **r} for r in add]
        registrar_evento({"ts": pd.Timestamp.utcnow().isoformat(), "tipo":"add_on", "detalle":",".join(sel), "valor":len(sel)})
        st.success(f"Agregados {len(sel)} items ON.")

with tab_off:
    st.subheader("Tradicional: OOH, TV, Radio")
    df_off = cargar_inventario("data/inventario_off.csv")
    c1, c2, c3, c4 = st.columns(4)
    with c1: canal = st.selectbox("Canal", ["Todos"] + sorted(df_off["canal"].unique()))
    with c2: soporte = st.selectbox("Soporte", ["Todos"] + sorted(df_off["soporte"].unique()))
    with c3: plaza = st.selectbox("Plaza", ["Todas"] + sorted(df_off["plaza"].unique()))
    with c4: vendedor = st.selectbox("Vendedor", ["Todos"] + sorted(df_off["vendedor"].unique()))
    f2 = df_off.copy()
    if canal!="Todos": f2=f2[f2["canal"]==canal]
    if soporte!="Todos": f2=f2[f2["soporte"]==soporte]
    if plaza!="Todas": f2=f2[f2["plaza"]==plaza]
    if vendedor!="Todos": f2=f2[f2["vendedor"]==vendedor]
    st.dataframe(f2, use_container_width=True, height=320)
    sel2 = st.multiselect("IDs a agregar (OFF)", f2["id"].astype(str).tolist(), key="sel2")
    if st.button("Agregar selección (OFF)"):
        add = df_off[df_off["id"].astype(str).isin(sel2)].to_dict(orient="records")
        st.session_state.carrito += [{"tipo":"OFF", **r} for r in add]
        registrar_evento({"ts": pd.Timestamp.utcnow().isoformat(), "tipo":"add_off", "detalle":",".join(sel2), "valor":len(sel2)})
        st.success(f"Agregados {len(sel2)} items OFF.")

st.divider()
st.subheader("Carrito (resumen)")
if st.session_state.carrito:
    st.dataframe(pd.DataFrame(st.session_state.carrito), use_container_width=True, height=240)
else:
    st.info("Aún no hay productos en el carrito.")
