from pathlib import Path
import pandas as pd
import hashlib
from datetime import datetime

DATA_DIR = Path("data")
LOG_FILE = DATA_DIR / "event_log.csv"

def costo_digital_cpm(impresiones, cpm):
    return (impresiones / 1000.0) * cpm

def costo_off_tarifa(unidades, tarifa_unitaria):
    return unidades * tarifa_unitaria

def estimar_alcance_digital(impresiones, freq=1.4):
    return max(1, int(impresiones / max(0.5, freq)))

def estimar_grps(tv_rating_promedio, inserciones):
    return tv_rating_promedio * inserciones

def ctr_placeholder(medio, formato):
    base = int(hashlib.sha256((medio+formato).encode("utf-8")).hexdigest(), 16) % 40
    return round(0.3 + base/1000.0, 3)  # ~0.3%..3.9%

def cpm_efectivo(total_costo, total_impresiones):
    if total_impresiones <= 0:
        return None
    return round((total_costo / total_impresiones) * 1000.0, 2)

def registrar_evento(evento: dict):
    cols = ["ts", "tipo", "detalle", "valor"]
    df = pd.DataFrame([evento], columns=cols)
    if LOG_FILE.exists():
        df.to_csv(LOG_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(LOG_FILE, index=False)

def cargar_inventario(path):
    df = pd.read_csv(path)
    for col in ["fecha_desde", "fecha_hasta"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    return df
