"""Datos personales de cada usuario (favoritos, alertas y notas).

Se guardan en el navegador de quien usa la web (localStorage), así cada persona tiene los
suyos sin necesidad de cuentas. No se ven desde otro navegador o dispositivo.
"""
from __future__ import annotations

import json
import time
import uuid

import numpy as np
import pandas as pd
import streamlit as st

CLAVE_NAVEGADOR = "analizador_usuario_v1"

_JS = """
export default function(component) {
  const { data, setStateValue } = component;
  const CLAVE = '%s';
  let valor = '{}';
  try {
    if (data && typeof data.guardar === 'string') localStorage.setItem(CLAVE, data.guardar);
    valor = localStorage.getItem(CLAVE) || '{}';
  } catch (e) { valor = '{"_sin_almacen": true}'; }
  if (window.__almacenAnalizador !== valor) { window.__almacenAnalizador = valor; setStateValue('datos', valor); }
}
""" % CLAVE_NAVEGADOR

_componente = st.components.v2.component("almacen_usuario", js=_JS) if hasattr(st, "components") and hasattr(st.components, "v2") else None

VACIO = {"favoritos": {}, "alertas": [], "notas": {}}


def montar():
    """Llamar una vez en cada ejecución (lo hace app.py). Sincroniza con el navegador."""
    ss = st.session_state
    if "usuario" not in ss:
        ss["usuario"] = json.loads(json.dumps(VACIO))
        ss["_usuario_cargado"] = False
    if _componente is None:  # versiones antiguas de Streamlit: solo durante la sesión
        ss["_usuario_cargado"] = True
        return
    with st.sidebar:
        res = _componente(key="almacen_usuario", data={"guardar": ss.get("_usuario_pendiente")}, on_datos_change=lambda: None)
    crudo = getattr(res, "datos", None)
    ss["_usuario_intentos"] = ss.get("_usuario_intentos", 0) + 1
    if crudo is None and ss["_usuario_intentos"] >= 3:
        ss["_usuario_cargado"] = True  # el navegador no responde: funciona solo durante esta sesión
    if crudo is not None and crudo != ss.get("_usuario_crudo"):
        ss["_usuario_crudo"] = crudo
        try:
            d = json.loads(crudo)
        except Exception:
            d = {}
        if not ss.get("_usuario_pendiente") or crudo == ss.get("_usuario_pendiente"):
            for k, v in VACIO.items():
                d.setdefault(k, json.loads(json.dumps(v)))
            ss["usuario"] = d
            ss["_usuario_pendiente"] = None
        ss["_usuario_cargado"] = True


def datos() -> dict:
    return st.session_state.setdefault("usuario", json.loads(json.dumps(VACIO)))


def cargado() -> bool:
    return bool(st.session_state.get("_usuario_cargado"))


def guardar():
    """Marca los datos para guardarlos en el navegador (se escriben en la siguiente ejecución)."""
    st.session_state["_usuario_pendiente"] = json.dumps(datos(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Favoritos y notas
# ---------------------------------------------------------------------------
def es_favorito(ticker: str) -> bool:
    return ticker in datos()["favoritos"]


def alternar_favorito(ticker: str, nombre: str, precio):
    fav = datos()["favoritos"]
    if ticker in fav:
        del fav[ticker]
    else:
        fav[ticker] = {"nombre": nombre, "añadido": time.strftime("%Y-%m-%d"), "precio": precio}
    guardar()


def nota(ticker: str) -> str:
    return datos()["notas"].get(ticker, "")


def guardar_nota(ticker: str, texto: str):
    if texto.strip():
        datos()["notas"][ticker] = texto
    else:
        datos()["notas"].pop(ticker, None)
    guardar()


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
TIPOS = {
    "precio_mayor": ("📈 El precio sube por encima de", "precio"),
    "precio_menor": ("📉 El precio baja por debajo de", "precio"),
    "variacion": ("⚡ Se mueve en un día más de (%)", "pct"),
    "zona_compra": ("🟢 Entra en la zona de compra del modelo", None),
    "veredicto_comprar": ("✅ El veredicto pasa a Comprar", None),
    "veredicto_vender": ("⛔ El veredicto pasa a Vender", None),
    "rsi_bajo": ("📊 El RSI baja de (sobreventa)", "num"),
    "rsi_alto": ("📊 El RSI sube de (sobrecompra)", "num"),
    "bollinger_sup": ("🎢 Cierra por encima de la banda superior de Bollinger", None),
    "bollinger_inf": ("🎢 Cierra por debajo de la banda inferior de Bollinger", None),
    "cruce_dorado": ("✨ Cruce dorado (la media 50 cruza sobre la 200)", None),
    "cruce_muerte": ("☠️ Cruce de la muerte (la media 50 cruza bajo la 200)", None),
    "dividendo": ("💸 La rentabilidad por dividendo supera (%)", "pct"),
}
DEFECTOS = {"variacion": 5.0, "rsi_bajo": 30.0, "rsi_alto": 70.0, "dividendo": 5.0}
MODELO = {"zona_compra", "veredicto_comprar", "veredicto_vender", "dividendo"}


def crear_alerta(ticker: str, nombre: str, tipo: str, valor):
    datos()["alertas"].append({"id": uuid.uuid4().hex[:8], "ticker": ticker, "nombre": nombre, "tipo": tipo,
                               "valor": valor, "creada": time.strftime("%Y-%m-%d"), "disparada": None})
    guardar()


def borrar_alerta(id_: str):
    d = datos()
    d["alertas"] = [a for a in d["alertas"] if a["id"] != id_]
    guardar()


def alertas_de(ticker: str | None = None) -> list:
    return [a for a in datos()["alertas"] if ticker is None or a["ticker"] == ticker]


def describir(a: dict, moneda: str = "") -> str:
    texto, tipo_valor = TIPOS.get(a["tipo"], (a["tipo"], None))
    if tipo_valor == "precio":
        return f"{texto} {a['valor']:,.2f} {moneda}".replace(",", "X").replace(".", ",").replace("X", ".")
    if tipo_valor == "pct":
        return f"{texto.replace(' (%)', '')} {a['valor']:g}%".replace(".", ",")
    if tipo_valor == "num":
        return f"{texto.split(' (')[0]} {a['valor']:g}"
    return texto


@st.cache_data(ttl=900, show_spinner=False)
def precios_recientes(ticker: str) -> pd.DataFrame:
    """Último año de precios diarios, renovado cada 15 minutos (para comprobar alertas)."""
    import yfinance as yf
    try:
        h = yf.Ticker(ticker).history(period="14mo", auto_adjust=False)
        if h is not None and not h.empty and h.index.tz is not None:
            h.index = h.index.tz_localize(None)
        return h if h is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    p = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / p.replace(0, np.nan))


def evaluar(a: dict, hist: pd.DataFrame, resultado=None, metricas=None):
    """Devuelve (se_cumple: bool | None, detalle: str). None = no se puede comprobar."""
    if hist is None or hist.empty or "Close" not in hist or len(hist) < 2:
        return None, "sin datos de precio"
    c = hist["Close"].dropna()
    precio, previo = float(c.iloc[-1]), float(c.iloc[-2])
    t, v = a["tipo"], a.get("valor")
    fmt = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    if t == "precio_mayor":
        return precio >= v, f"precio {fmt(precio)}"
    if t == "precio_menor":
        return precio <= v, f"precio {fmt(precio)}"
    if t == "variacion":
        var = precio / previo - 1
        return abs(var) * 100 >= v, f"hoy {var * 100:+.1f}%".replace(".", ",")
    if t in ("rsi_bajo", "rsi_alto"):
        r = float(_rsi(c).iloc[-1])
        return (r <= v) if t == "rsi_bajo" else (r >= v), f"RSI {r:.0f}"
    if t in ("bollinger_sup", "bollinger_inf"):
        m, s = c.rolling(20).mean(), c.rolling(20).std()
        sup, inf = float(m.iloc[-1] + 2 * s.iloc[-1]), float(m.iloc[-1] - 2 * s.iloc[-1])
        return (precio > sup) if t == "bollinger_sup" else (precio < inf), f"bandas {fmt(inf)} – {fmt(sup)}"
    if t in ("cruce_dorado", "cruce_muerte"):
        if len(c) < 205:
            return None, "histórico insuficiente"
        m50, m200 = c.rolling(50).mean(), c.rolling(200).mean()
        arriba = (m50 > m200).iloc[-6:]
        hubo = (arriba.astype(int).diff().iloc[1:] == (1 if t == "cruce_dorado" else -1)).any()
        return bool(hubo), "media 50 " + ("sobre" if arriba.iloc[-1] else "bajo") + " la 200"
    if t in MODELO:
        if resultado is None:
            return None, "pendiente de analizar"
        if t == "zona_compra":
            zc = resultado.precio_compra
            return (zc is not None and precio <= zc), (f"zona de compra {fmt(zc)}" if zc else "sin zona de compra")
        if t == "veredicto_comprar":
            return resultado.veredicto == "Comprar", f"veredicto {resultado.veredicto}"
        if t == "veredicto_vender":
            return resultado.veredicto == "Vender", f"veredicto {resultado.veredicto}"
        if t == "dividendo":
            rd = (metricas or {}).get("rent_dividendo") or 0
            return rd * 100 >= v, f"dividendo {rd * 100:.2f}%".replace(".", ",")
    return None, ""


def marcar_disparadas(estados: dict):
    """Guarda la fecha en que cada alerta se cumplió por primera vez y devuelve las nuevas."""
    nuevas, cambio = [], False
    for a in datos()["alertas"]:
        if a["id"] not in estados:
            continue
        cumple = estados[a["id"]][0]
        if cumple and not a.get("disparada"):
            a["disparada"] = time.strftime("%d/%m/%Y %H:%M")
            nuevas.append(a)
            cambio = True
        elif cumple is False and a.get("disparada"):
            a["disparada"] = None  # se rearma cuando deja de cumplirse
            cambio = True
    if cambio:
        guardar()
    return nuevas


def comprobar(alertas: list, analizar_fn=None) -> dict:
    """Estado de cada alerta: {id: (se_cumple, detalle)}. `analizar_fn(ticker)` -> (m, r) para las del modelo."""
    estados, analisis = {}, {}
    for a in alertas:
        hist = precios_recientes(a["ticker"])
        res = met = None
        if a["tipo"] in MODELO and analizar_fn is not None:
            if a["ticker"] not in analisis:
                try:
                    analisis[a["ticker"]] = analizar_fn(a["ticker"])
                except Exception:
                    analisis[a["ticker"]] = (None, None)
            met, res = analisis[a["ticker"]]
        estados[a["id"]] = evaluar(a, hist, res, met)
    return estados
