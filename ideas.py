"""Búsquedas de ideas preparadas (método de generación de ideas de los analistas).

Cada búsqueda es una lista de criterios. Una empresa entra si cumple un mínimo de ellos; se ordenan por
criterios cumplidos y nota. Las comparaciones «frente al sector» usan la mediana de su sector dentro del
universo escaneado. Una búsqueda propone candidatas, no conclusiones.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _v(fila, col):
    x = fila.get(col)
    try:
        return None if x is None or pd.isna(x) else float(x)
    except Exception:
        return None


def _menor(col, umbral):
    return lambda f, med: (v := _v(f, col)) is not None and v < umbral


def _mayor(col, umbral):
    return lambda f, med: (v := _v(f, col)) is not None and v > umbral


def _bajo_sector(col, factor=1.0):
    def fn(f, med):
        v, m = _v(f, col), med.get((f.get("Sector"), col))
        return v is not None and v > 0 and m is not None and v < m * factor
    return fn


def _sobre_sector(col, factor=1.0):
    def fn(f, med):
        v, m = _v(f, col), med.get((f.get("Sector"), col))
        return v is not None and m is not None and v > m * factor
    return fn


BUSQUEDAS = {
    "💎 Calidad a buen precio": {
        "lado": "Alcista", "min": 4,
        "idea": "Negocios excelentes que hoy no cotizan caros. Suele ser la mejor combinación: calidad que aguanta y precio que deja margen.",
        "criterios": [
            ("ROE > 15%", _mayor("ROE", 0.15)),
            ("Margen operativo > 15%", _mayor("Margen op.", 0.15)),
            ("Deuda neta/EBITDA < 2", lambda f, m: (v := _v(f, "Deuda neta/EBITDA")) is not None and v < 2),
            ("PER por debajo de su sector", _bajo_sector("PER")),
            ("Por debajo de su valor justo", _mayor("Potencial", 0)),
        ]},
    "📈 Crecimiento rentable": {
        "lado": "Alcista", "min": 3,
        "idea": "Empresas que crecen deprisa y además ganan dinero con ese crecimiento (no crecimiento a cualquier precio).",
        "criterios": [
            ("Ventas +15% en el año", _mayor("Crec. ingresos", 0.15)),
            ("Beneficio +20% en el año", _mayor("Crec. beneficio", 0.20)),
            ("Crecimiento sostenido varios años > 10%", _mayor("Crec. ventas 3-5a", 0.10)),
            ("ROIC > 15%", _mayor("ROIC", 0.15)),
            ("Margen mejor que su sector", _sobre_sector("Margen op.")),
        ]},
    "💰 Valor (baratas de verdad)": {
        "lado": "Alcista", "min": 4,
        "idea": "Cotizan barato por varios lados a la vez. Lo barato suele tener un motivo: busca cuál y si es pasajero.",
        "criterios": [
            ("PER por debajo de su sector", _bajo_sector("PER")),
            ("EV/EBITDA por debajo de su sector", _bajo_sector("EV/EBITDA")),
            ("Rentabilidad por flujo de caja > 5%", _mayor("FCF yield", 0.05)),
            ("Precio/valor contable < 1,5", lambda f, m: (v := _v(f, "P/VC")) is not None and 0 < v < 1.5),
            ("Dividendo por encima de su sector", _sobre_sector("Div.")),
        ]},
    "💸 Dividendo sostenible": {
        "lado": "Alcista", "min": 4,
        "idea": "Buen dividendo que la empresa puede seguir pagando: no reparte más de lo que gana y no está endeudada.",
        "criterios": [
            ("Rentabilidad por dividendo > 3,5%", _mayor("Div.", 0.035)),
            ("Payout < 75%", lambda f, m: (v := _v(f, "Payout")) is not None and 0 < v < 0.75),
            ("Deuda neta/EBITDA < 3", lambda f, m: (v := _v(f, "Deuda neta/EBITDA")) is not None and v < 3),
            ("Piotroski ≥ 5 (salud contable)", lambda f, m: (v := _v(f, "Piotroski")) is not None and v >= 5),
            ("Flujo de caja libre positivo", _mayor("FCF yield", 0)),
        ]},
    "🩹 Caída exagerada en empresa sana": {
        "lado": "Alcista", "min": 3,
        "idea": "Buenas empresas que han caído mucho. Las mejores ideas suelen estar donde un problema pasajero hunde a un buen negocio. "
                "Necesitan un catalizador: sin él, llegar pronto es lo mismo que equivocarse.",
        "criterios": [
            ("Cae más del 25% desde su máximo del año", _menor("Desde máx. 52s", -0.25)),
            ("Calidad ≥ 60", _mayor("Calidad", 59.9)),
            ("Salud financiera ≥ 60", _mayor("Salud financiera", 59.9)),
            ("Ventas aún creciendo", _mayor("Crec. ingresos", 0)),
        ]},
    "🚀 Pequeñas que crecen rápido": {
        "lado": "Alcista", "min": 3,
        "idea": "Compañías pequeñas con crecimiento fuerte y las cuentas en orden. Más riesgo y más volatilidad, pero también más recorrido.",
        "criterios": [
            ("Capitalización < 2.000 millones", lambda f, m: (v := _v(f, "Cap. (mill.)")) is not None and v < 2000),
            ("Ventas +15% en el año", _mayor("Crec. ingresos", 0.15)),
            ("Margen operativo positivo", _mayor("Margen op.", 0)),
            ("Deuda neta/EBITDA < 2,5", lambda f, m: (v := _v(f, "Deuda neta/EBITDA")) is not None and v < 2.5),
        ]},
    "⚠️ Señales de alerta (evitar o vender)": {
        "lado": "Bajista", "min": 3,
        "idea": "Empresas con varias banderas rojas a la vez. Útil para revisar si tienes alguna o para no caer en una trampa de valor.",
        "criterios": [
            ("Ventas cayendo", _menor("Crec. ingresos", 0)),
            ("Beneficio cayendo más de un 15%", _menor("Crec. beneficio", -0.15)),
            ("Deuda neta/EBITDA > 4", _mayor("Deuda neta/EBITDA", 4)),
            ("PER muy por encima de su sector", _sobre_sector("PER", 1.5)),
            ("Piotroski ≤ 3 (salud contable débil)", lambda f, m: (v := _v(f, "Piotroski")) is not None and v <= 3),
            ("Nota del modelo < 40", _menor("Nota", 40)),
        ]},
}

_COLS_MEDIANA = ["PER", "EV/EBITDA", "Margen op.", "Div.", "ROE"]


def medianas_sector(df: pd.DataFrame) -> dict:
    out = {}
    for col in _COLS_MEDIANA:
        if col not in df:
            continue
        serie = pd.to_numeric(df[col], errors="coerce")
        if col in ("PER", "EV/EBITDA"):
            serie = serie.where((serie > 0) & (serie < 200))
        for sector, g in serie.groupby(df["Sector"]):
            g = g.dropna()
            if len(g) >= 2:
                out[(sector, col)] = float(np.median(g))
    return out


def aplicar(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    b = BUSQUEDAS[nombre]
    med = medianas_sector(df)
    filas = []
    for _, f in df.iterrows():
        f = f.to_dict()
        cumple = [et for et, fn in b["criterios"] if _ok(fn, f, med)]
        if len(cumple) >= b["min"]:
            f["Cumple"] = f"{len(cumple)}/{len(b['criterios'])}"
            f["_n"] = len(cumple)
            f["Por qué"] = " · ".join(cumple)
            filas.append(f)
    if not filas:
        return pd.DataFrame()
    out = pd.DataFrame(filas)
    asc_nota = b["lado"] == "Bajista"
    return out.sort_values(["_n", "Nota"], ascending=[False, asc_nota]).drop(columns="_n")


def _ok(fn, f, med):
    try:
        return bool(fn(f, med))
    except Exception:
        return False
