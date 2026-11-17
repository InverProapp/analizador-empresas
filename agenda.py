"""Calendario de catalizadores: eventos de empresas, bancos centrales y tus propios eventos."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

# Reuniones de política monetaria (día de la decisión). Fuentes: federalreserve.gov (calendario 2027
# revisado el 12/11/2026: la reunión de octubre de 2027 es de estrategia, sin decisión) y ecb.europa.eu.
FED = ["2026-12-09", "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15",
       "2027-11-17", "2028-01-26"]
BCE = ["2026-12-17", "2027-02-04", "2027-03-18", "2027-04-29", "2027-06-10", "2027-07-22", "2027-09-09",
       "2027-10-28", "2027-12-16"]

IMPACTO_ICONO = {"Alto": "🔴 Alto", "Medio": "🟡 Medio", "Bajo": "🟢 Bajo"}
TIPO_ICONO = {"Resultados": "📊", "Dividendo": "💸", "Macro": "🏦", "Propio": "📌", "Tesis": "🧐"}


def macro(fed: bool = True, bce: bool = True) -> list[dict]:
    out = []
    if fed:
        out += [{"fecha": pd.Timestamp(f), "ticker": "EE. UU.", "empresa": "Reserva Federal", "tipo": "Macro",
                 "texto": "Decisión de tipos de la Fed (20:00 h España)", "impacto": "Alto"} for f in FED]
    if bce:
        out += [{"fecha": pd.Timestamp(f), "ticker": "Zona euro", "empresa": "Banco Central Europeo", "tipo": "Macro",
                 "texto": "Decisión de tipos del BCE (14:15 h España)", "impacto": "Alto"} for f in BCE]
    return out


def bancos_para(moneda: str) -> tuple[bool, bool]:
    """Qué banco central mueve más a una empresa según su moneda (fed, bce)."""
    if moneda == "EUR":
        return False, True
    if moneda == "USD":
        return True, False
    return True, True


def reaccion(hist: pd.DataFrame | None, fecha) -> float | None:
    """Movimiento del precio alrededor de una presentación: cierre del día siguiente frente al día anterior.
    Cubre tanto si presentan antes de abrir como después de cerrar."""
    if hist is None or hist.empty or "Close" not in hist:
        return None
    c = hist["Close"].dropna()
    f = pd.Timestamp(fecha).normalize()
    antes = c[c.index < f]
    despues = c[c.index > f]
    if antes.empty or despues.empty:
        return None
    return float(despues.iloc[0] / antes.iloc[-1] - 1)


def historial_resultados(res: pd.DataFrame, hist: pd.DataFrame | None) -> pd.DataFrame:
    if res is None or res.empty:
        return pd.DataFrame()
    df = res.copy()
    df["reaccion"] = [reaccion(hist, f) for f in df.index]
    df["sorpresa"] = df["sorpresa"].astype(float)
    falta = df["sorpresa"].isna() & df["esperado"].notna() & df["real"].notna() & (df["esperado"].abs() > 0)
    df.loc[falta, "sorpresa"] = (df["real"] - df["esperado"]) / df["esperado"].abs() * 100
    return df


def resumen_historial(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    s = df["sorpresa"].dropna()
    rx = df["reaccion"].dropna()
    partes = []
    if len(s):
        partes.append(f"ha **batido** la previsión de beneficio en **{int((s > 0).sum())} de {len(s)}** presentaciones")
    if len(rx):
        sube = int((rx > 0).sum())
        partes.append(f"la acción **subió** al día siguiente en **{sube} de {len(rx)}** "
                      f"(movimiento medio {np.mean(np.abs(rx)) * 100:.1f}%)".replace(".", ","))
    return "En las últimas presentaciones " + " y ".join(partes) + "." if partes else ""


def _ics_fecha(f) -> str:
    return pd.Timestamp(f).strftime("%Y%m%d")


def ics(eventos: list[dict]) -> str:
    """Archivo .ics para importar en Google Calendar, Outlook o el calendario del móvil."""
    lineas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Analizador de empresas//ES", "CALSCALE:GREGORIAN"]
    sello = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for k, ev in enumerate(eventos):
        f = pd.Timestamp(ev["fecha"])
        titulo = f"{TIPO_ICONO.get(ev['tipo'], '')} {ev['ticker']}: {ev['texto']}".strip()
        titulo = titulo.replace(",", r"\,").replace(";", r"\;")
        lineas += ["BEGIN:VEVENT", f"UID:{_ics_fecha(f)}-{k}-{abs(hash(titulo)) % 10**8}@analizador",
                   f"DTSTAMP:{sello}", f"DTSTART;VALUE=DATE:{_ics_fecha(f)}",
                   f"DTEND;VALUE=DATE:{_ics_fecha(f + pd.Timedelta(days=1))}", f"SUMMARY:{titulo}",
                   f"DESCRIPTION:Impacto {ev.get('impacto', '')}. {ev.get('empresa', '')}".replace(",", r"\,"),
                   "END:VEVENT"]
    lineas.append("END:VCALENDAR")
    return "\r\n".join(lineas) + "\r\n"
