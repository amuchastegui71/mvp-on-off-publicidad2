# utils.py
import json
import math
import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================
# Normalización de costos y esquema
# =========================================
def compute_unit_costs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula CPM/CPC/CPL/CPA si es posible, respetando NaN cuando no hay denominador.
    Requiere columnas: impressions, clicks, leads, actions, cost (si faltan se crean como NaN).
    """
    df = df.copy()
    for c in ["impressions", "clicks", "leads", "actions", "cost"]:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")

    imp = df["impressions"].astype(float)
    clk = df["clicks"].astype(float)
    led = df["leads"].astype(float)
    act = df["actions"].astype(float)
    cst = df["cost"].astype(float)

    df["CPM"] = np.where((imp > 0) & pd.notna(cst), cst / (imp / 1000.0), np.nan)
    df["CPC"] = np.where((clk > 0) & pd.notna(cst), cst / clk, np.nan)
    df["CPL"] = np.where((led > 0) & pd.notna(cst), cst / led, np.nan)
    df["CPA"] = np.where((act > 0) & pd.notna(cst), cst / act, np.nan)
    return df


def compute_normalized_cost(row):
    """
    Versión 'legacy' de normalización para una sola unidad por fila.
    Prioridad: CPM > CPC > CPL > CPA. Devuelve (valor, unidad).
    """
    def _to_num(x):
        try:
            return float(x)
        except Exception:
            return np.nan

    cost = _to_num(row.get("cost"))
    impressions = _to_num(row.get("impressions"))
    clicks = _to_num(row.get("clicks"))
    leads = _to_num(row.get("leads"))
    actions = _to_num(row.get("actions"))

    if pd.notna(impressions) and impressions > 0:
        return cost / (impressions / 1000.0), "CPM"
    if pd.notna(clicks) and clicks > 0:
        return cost / clicks, "CPC"
    if pd.notna(leads) and leads > 0:
        return cost / leads, "CPL"
    if pd.notna(actions) and actions > 0:
        return cost / actions, "CPA"
    return np.nan, "NA"


def unify_schema(df: pd.DataFrame, medium_type: str = None) -> pd.DataFrame:
    """
    Estandariza columnas, calcula costos unitarios (CPM/CPC/CPL/CPA),
    un 'norm_cost' de compatibilidad y un 'score' compuesto.
    """
    df = df.copy()

    # Renombres tolerantes
    rename = {
        "medio": "medium",
        "medios": "vendor",
        "proveedor": "vendor",
        "soporte": "format",
        "audiencia": "audience",
        "impresiones": "impressions",
        "GRP": "grps",
        "grp": "grps",
        "costo": "cost",
        "inicio": "start",
        "fin": "end",
        "calificacion": "rating",
        "reseñas": "rating",
        "canal": "medium",
    }
    for k, v in rename.items():
        if k in df.columns and v not in df.columns:
            df.rename(columns={k: v}, inplace=True)

    # Asegurar columnas base
    required = [
        "medium", "vendor", "format", "audience",
        "impressions", "grps", "clicks", "views", "leads", "actions",
        "rating", "cost", "start", "end"
    ]
    for c in required:
        if c not in df.columns:
            df[c] = np.nan

    # Tipo ON/OFF
    if "medium_type" not in df.columns:
        df["medium_type"] = medium_type if medium_type else "ON"

    # Tipos
    for c in ["start", "end"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ["impressions", "grps", "clicks", "views", "leads", "actions", "rating", "cost"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Costos unitarios + norm_cost (compatibilidad)
    df = compute_unit_costs(df)
    df[["norm_cost", "norm_cost_unit"]] = df.apply(
        lambda r: pd.Series(compute_normalized_cost(r)), axis=1
    )

    # Score: rating (40%) + reach_proxy (40%) + economía (20% - mejor costo unitario disponible)
    rating = df["rating"].fillna(df["rating"].median())
    reach = (
        df["impressions"].fillna(0)
        + 10000.0 * df["grps"].fillna(0)
        + 50.0 * df["clicks"].fillna(0)
        + 100.0 * df["leads"].fillna(0)
        + 150.0 * df["actions"].fillna(0)
    )
    econ = df[["CPM", "CPC", "CPL", "CPA"]].min(axis=1)

    def zseries(s: pd.Series) -> pd.Series:
        s = s.astype(float)
        mu = s.median()
        sd = s.std(ddof=0)
        if not np.isfinite(sd) or sd == 0:
            sd = 1.0
        return (s - mu) / sd

    rating_z = zseries(rating)
    reach_z = zseries(reach)
    econ_z = -zseries(econ.fillna(econ.median()))  # menor costo => mejor

    df["score"] = 0.4 * rating_z + 0.4 * reach_z + 0.2 * econ_z
    return df


def kpi_summary(df: pd.DataFrame) -> dict:
    """
    KPIs resumidos para total/ON/OFF.
    """
    out = {}
    on = df[df["medium_type"] == "ON"]
    off = df[df["medium_type"] == "OFF"]
    for label, data in [("total", df), ("ON", on), ("OFF", off)]:
        out[label] = {
            "invs": int(len(data)),
            "cost": float(data["cost"].sum(skipna=True)),
            "impressions": float(data["impressions"].sum(skipna=True)),
            "grps": float(data["grps"].sum(skipna=True)),
            "clicks": float(data["clicks"].sum(skipna=True)),
            "leads": float(data["leads"].sum(skipna=True)),
            "actions": float(data["actions"].sum(skipna=True)),
            "avg_rating": float(data["rating"].mean(skipna=True)),
        }
    return out


# =========================================
# Helpers de costo/unidad visibles
# =========================================
def costo_unitario_visible(row) -> float:
    """
    Retorna el costo unitario que ve el usuario (si existe selected_unit_cost),
    o el menor disponible entre CPM/CPC/CPL/CPA; y si no, 'cost'.
    """
    for c in ["selected_unit_cost", "CPM", "CPC", "CPL", "CPA", "cost"]:
        v = row.get(c)
        try:
            v = float(v)
        except Exception:
            v = None
        if v is not None and v == v and v > 0:
            return v
    return 0.0


def get_selected_unit(row) -> str:
    """
    Unidad visible: selected_unit si existe, si no la primera disponible de CPM/CPC/CPL/CPA.
    """
    u = row.get("selected_unit")
    if isinstance(u, str) and u:
        return u
    for cand in ["CPM", "CPC", "CPL", "CPA"]:
        try:
            v = row.get(cand)
            if v is not None and float(v) > 0:
                return cand
        except Exception:
            pass
    return "CPM"


# =========================================
# Estimación de IMPRESIONES por presupuesto
# =========================================
def estimate_impressions(row, budget: float) -> float:
    """
    Estima solo IMPRESIONES a partir de presupuesto y unidad visible.
    Reglas:
      - CPM: imp = budget / CPM * 1000
      - CPC: requiere 'ctr' (0..1) -> imp = (budget / CPC) / ctr
      - CPL: requiere 'cvr' y 'ctr' -> leads = budget/CPL; clicks = leads/cvr; imp = clicks/ctr
      - CPA: requiere 'cvr' y 'ctr' -> actions = budget/CPA; leads = actions/cvr; clicks = leads/cvr; imp = clicks/ctr
    Si faltan benchmarks necesarios, devuelve NaN.
    """
    def f(x):
        try:
            return float(x)
        except Exception:
            return math.nan

    unit = get_selected_unit(row)
    cpm = f(row.get("CPM"))
    cpc = f(row.get("CPC"))
    cpl = f(row.get("CPL"))
    cpa = f(row.get("CPA"))
    ctr = f(row.get("ctr"))  # opcional en catálogo
    cvr = f(row.get("cvr"))  # opcional en catálogo

    if unit == "CPM" and cpm and cpm > 0:
        return budget / cpm * 1000.0

    if unit == "CPC" and cpc and cpc > 0 and ctr and ctr > 0:
        clicks = budget / cpc
        return clicks / ctr

    if unit == "CPL" and cpl and cpl > 0 and cvr and cvr > 0 and ctr and ctr > 0:
        leads = budget / cpl
        clicks = leads / cvr
        return clicks / ctr

    if unit == "CPA" and cpa and cpa > 0 and cvr and cvr > 0 and ctr and ctr > 0:
        actions = budget / cpa
        leads = actions / cvr
        clicks = leads / cvr
        return clicks / ctr

    return math.nan


# =========================================
# Export / Totales para cotización (presupuesto)
# =========================================
def preparar_plan_para_export_budget_simple(df: pd.DataFrame) -> pd.DataFrame:
    """
    Exportación para cotización por presupuesto mostrando solo impresiones estimadas.
    """
    out = df.copy().reset_index(drop=True)
    out = out.rename(columns={"vendor": "Medio", "format": "Formato", "medium": "Canal"})

    def _fmt_date(x):
        try:
            return pd.to_datetime(x).strftime("%Y-%m-%d")
        except Exception:
            return ""

    out["Inicio"] = out.get("start", "").apply(_fmt_date)
    out["Fin"] = out.get("end", "").apply(_fmt_date)

    if "budget" not in out.columns:
        out["budget"] = 0

    out["Unidad"] = out.apply(get_selected_unit, axis=1)
    out["CostoUnit"] = out.apply(costo_unitario_visible, axis=1)

    out["est_impressions"] = out.apply(
        lambda r: estimate_impressions(r, float(r.get("budget", 0))), axis=1
    )
    out["TotalLinea"] = out["budget"].astype(float)

    cols = [
        "Medio", "Formato", "Canal", "Inicio", "Fin",
        "Unidad", "CostoUnit", "budget", "est_impressions", "TotalLinea"
    ]
    extras = [c for c in out.columns if c not in cols]
    return out[cols + extras]


def totales_plan_budget_simple(df: pd.DataFrame) -> dict:
    df2 = preparar_plan_para_export_budget_simple(df)
    subtotal = float(df2["TotalLinea"].sum())
    return {"items": int(len(df2)), "subtotal": subtotal}


# =========================================
# Logger robusto (JSON-safe)
# =========================================
def _jsonable(x):
    """
    Convierte recursivamente a tipos serializables en JSON.
    - NaN/Inf/NaT -> None
    - Timestamp/date -> ISO 8601
    - numpy -> nativos
    - DataFrame/Series -> dict/list
    """
    # primitivos
    if x is None or isinstance(x, (str, bool, int)):
        return x
    if isinstance(x, float):
        if np.isnan(x) or np.isinf(x):
            return None
        return x

    # pandas / numpy / fechas
    if x is pd.NaT:
        return None
    if isinstance(x, (pd.Timestamp, _dt.datetime, _dt.date)):
        try:
            return x.isoformat()
        except Exception:
            return None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        val = float(x)
        return None if (np.isnan(val) or np.isinf(val)) else val

    # colecciones
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in x]

    # pandas structures
    if isinstance(x, pd.Series):
        return _jsonable(x.to_dict())
    if isinstance(x, pd.DataFrame):
        return x.replace([np.nan, pd.NaT, np.inf, -np.inf], None).to_dict(orient="records")

    # fallback
    try:
        return str(x)
    except Exception:
        return None


def registrar_evento(evento: str, payload: dict, logfile: str = "data/events_log.jsonl") -> None:
    """
    Registra un evento en JSONL con saneamiento de tipos (no rompe con NaT/NaN/Timestamp).
    """
    Path("data").mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": _dt.datetime.utcnow().isoformat() + "Z",
        "evento": evento,
        "payload": payload,
    }
    rec = _jsonable(rec)
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
