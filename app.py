import streamlit as st

st.set_page_config(page_title="MVP ON/OFF Publicidad", page_icon="📊", layout="wide")

st.title("Plataforma ON/OFF – MVP Interactivo")
st.markdown(
    '''
**Objetivo:** Demostrar un flujo mínimo para **centralizar inventarios publicitarios ON/OFF**
(Display/Video/CTV/DOOH + OOH/TV/Radio), cotizar, reservar y **unificar KPIs**.

Incluye:
- **Búsqueda de inventario** ON/OFF con filtros y carrito.
- **Cotización** con reglas simples (CPM digital y tarifas OFF).
- **KPIs unificados** (CPM efectivo, GRPs, alcance, CTR).
- **Registro de eventos** en CSV para analítica.

> Edite `utils.py` para agregar su lógica real.
'''
)

st.info("Flujo sugerido: Buscar → Cotizar → KPIs → Analítica.")
