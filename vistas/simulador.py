"""Sección Simulador: herramienta interactiva (se ejecuta en el navegador)."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pandas as pd
import streamlit as st

import backtest as bt
import datos
import scoring as sc
import simulador as simu
from comun import ajustes, cargar, f_num, precios_max, selector_empresa

PLANTILLA = Path(__file__).with_name("simulador_app.html")


def version_plotly_js() -> str:
    try:
        import plotly.offline as po
        return po.get_plotlyjs_version()
    except Exception:
        return "3.0.1"


def limpio(valores, dec=4):
    out = []
    for v in valores:
        try:
            f = float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        out.append(None if math.isnan(f) or math.isinf(f) else round(f, dec))
    return out


ticker = selector_empresa("🎯 Simulador")
aj = ajustes()

if not ticker:
    st.title("Simulador de operaciones")
    st.write("Busca una empresa en la barra lateral para empezar.")
    st.stop()

with st.spinner(f"Descargando {ticker}…"):
    try:
        e = cargar(ticker)
    except Exception as ex:
        st.error(f"No se pudo descargar {ticker}: {ex}")
        st.stop()
    largo = precios_max(ticker)

hist = largo if largo is not None and len(largo) > len(e.hist if e.hist is not None else []) else e.hist
if hist is None or hist.empty or len(hist.dropna(subset=["Close"])) < 60:
    st.error(f"No hay suficiente histórico de precios para **{ticker}**.")
    st.stop()
hist = hist.dropna(subset=["Close"])
hist = hist[~hist.index.duplicated(keep="last")].sort_index()

st.title(f"🎯 {e.nombre}")
sesiones = f"{len(hist):,}".replace(",", ".")
st.caption(f"**{ticker}** · último precio {f_num(hist['Close'].iloc[-1])} {e.moneda} · "
           f"histórico desde {hist.index[0]:%d/%m/%Y} ({sesiones} sesiones)")

# Lo que decía el modelo en cada momento (solo con la información disponible entonces)
modelo = None
try:
    def evaluar_en(fecha):
        pasada = bt.recortar(e, fecha)
        if pasada is None:
            return None
        pes = dict(aj["pesos"])
        pes["Analistas"] = 0
        return sc.evaluar(datos.metricas(pasada, aj["g"], aj["wacc"], aj["g_term"]), pasada.sector, pes,
                          aj["u_comprar"], aj["u_vender"], aj["margen_seg"], aj["respetar_tendencia"])
    niv = simu.niveles_modelo(e, evaluar_en)
    if not niv.empty and niv["zona_compra"].notna().any():
        modelo = {"fechas": [f"{f:%Y-%m-%d}" for f in niv.index],
                  "compra": limpio(niv["zona_compra"]), "venta": limpio(niv["valor_justo"])}
except Exception:
    modelo = None

# Valores iniciales: zona baja y alta de los últimos 3 años
ultimos = hist[hist.index >= hist.index[-1] - pd.DateOffset(years=3)]["Close"]
desde = max(hist.index[0], hist.index[-1] - pd.DateOffset(years=3))
datos_js = {
    "ticker": ticker, "nombre": e.nombre, "moneda": e.moneda,
    "fechas": [f"{f:%Y-%m-%d}" for f in hist.index],
    "o": limpio(hist["Open"].fillna(hist["Close"])), "h": limpio(hist["High"].fillna(hist["Close"])),
    "l": limpio(hist["Low"].fillna(hist["Close"])), "c": limpio(hist["Close"]),
    "v": limpio(hist["Volume"], 0) if "Volume" in hist else None,
    "div": limpio(hist["Dividends"].fillna(0)) if "Dividends" in hist else [0] * len(hist),
    "modelo": modelo,
    "defectos": {"compra": round(float(ultimos.quantile(0.25)), 2), "venta": round(float(ultimos.quantile(0.75)), 2),
                 "desde": f"{desde:%Y-%m-%d}"},
}
# Algunos días Yahoo trae precios a 0 o vacíos: se rellenan con el cierre
for k in ("o", "h", "l"):
    datos_js[k] = [c if (v is None or v <= 0) else v for v, c in zip(datos_js[k], datos_js["c"])]

ver = version_plotly_js()
plantilla = PLANTILLA.read_text(encoding="utf-8")
if os.environ.get("SIMULADOR_PLOTLY_LOCAL"):  # solo para pruebas sin internet
    import plotly.offline as po
    plantilla = plantilla.replace('<script src="__PLOTLY_SRC__"></script>', "<script>" + po.get_plotlyjs() + "</script>")
html = (plantilla
        .replace("__PLOTLY_SRC__", f"https://cdn.plot.ly/plotly-{ver}.min.js")
        .replace("__PLOTLY_FALLBACK__", f"https://cdn.jsdelivr.net/npm/plotly.js-dist-min@{ver}/plotly.min.js")
        .replace("__DATOS__", json.dumps(datos_js, ensure_ascii=False, allow_nan=False)))
if hasattr(st, "iframe"):
    st.iframe(html, height="content")  # se ajusta solo a la altura del contenido
else:  # versiones antiguas de Streamlit
    import streamlit.components.v1 as components
    components.html(html, height=2350, scrolling=False)
st.caption("Simulación con precios diarios de Yahoo (apertura, máximo, mínimo y cierre). Tus líneas, ajustes y dibujos se "
           "guardan en este navegador para cada empresa. Ojo con el sesgo de mirar atrás: es fácil acertar viendo el gráfico.")
