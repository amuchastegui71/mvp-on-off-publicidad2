import streamlit as st
import pandas as pd
from pathlib import Path

st.title("Analítica / Logs")

log_path = Path("data/event_log.csv")
if log_path.exists():
    df = pd.read_csv(log_path)
    st.metric("Eventos registrados", len(df))
    st.dataframe(df.tail(200), use_container_width=True, height=300)
    if "valor" in df.columns:
        try:
            st.bar_chart(df["valor"])
        except Exception:
            pass
else:
    st.info("Aún no hay eventos.")
