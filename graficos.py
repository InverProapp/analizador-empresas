"""Gráficos interactivos comunes: periodo exacto, zoom, comparación, granularidad y estadísticas del tramo visible."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import datos

VERDE, ROJO, AZUL, GRIS, NARANJA, MORADO = "#1a9e5c", "#d64545", "#2a6fdb", "#9aa4b2", "#f39c12", "#8e44ad"
CONFIG = {"scrollZoom": True, "displaylogo": False, "doubleClick": "reset",
          "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
          "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "grafico"}}

PERIODOS = {"1S": pd.DateOffset(weeks=1), "1M": pd.DateOffset(months=1), "3M": pd.DateOffset(months=3),
            "6M": pd.DateOffset(months=6), "Año": "ytd", "1A": pd.DateOffset(years=1), "3A": pd.DateOffset(years=3),
            "5A": pd.DateOffset(years=5), "10A": pd.DateOffset(years=10), "Máx": None}
FECHAS = "📅 Fechas"
INDICES = {"IBEX 35": "^IBEX", "Euro Stoxx 50": "^STOXX50E", "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "DAX": "^GDAXI",
           "CAC 40": "^FCHI", "FTSE 100": "^FTSE", "MSCI World (ETF)": "URTH", "Oro": "GC=F", "Bitcoin": "BTC-USD"}
COLORES_COMP = [AZUL, NARANJA, MORADO, "#16a085", "#c0392b", "#7f8c8d", "#2c3e50"]


def pulir(fig: go.Figure, fechas: bool = True) -> go.Figure:
    """Lectura cómoda en todos los gráficos: cruz que sigue al ratón, tooltip conjunto y zoom arrastrando."""
    fig.update_layout(hovermode="x unified" if fechas else "closest", separators=",.", dragmode="zoom",
                      hoverlabel=dict(bgcolor="rgba(255,255,255,.95)", font_size=12))
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikedash="dot", spikecolor="#999")
    fig.update_yaxes(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, spikedash="dot", spikecolor="#bbb")
    return fig


def mostrar(fig: go.Figure, fechas: bool = True, **kw):
    st.plotly_chart(pulir(fig, fechas), width="stretch", config=CONFIG, **kw)


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def historico(ticker: str) -> pd.DataFrame:
    try:
        h = datos.precios_historicos(ticker)
    except Exception:
        return pd.DataFrame()
    if h is None or h.empty:
        return pd.DataFrame()
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in h]
    return h[cols].dropna(subset=["Close"])


def remuestrear(h: pd.DataFrame, regla: str) -> pd.DataFrame:
    regla = {"W": "W-FRI", "M": "ME"}.get(regla, regla)
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return h.resample(regla).agg({k: v for k, v in agg.items() if k in h}).dropna(subset=["Close"])


def indice_de(ticker: str) -> str:
    sufijo = ticker.split(".")[-1] if "." in ticker else ""
    return {"MC": "IBEX 35", "PA": "CAC 40", "DE": "DAX", "L": "FTSE 100", "AS": "Euro Stoxx 50", "MI": "Euro Stoxx 50",
            "LS": "Euro Stoxx 50", "BR": "Euro Stoxx 50", "SW": "Euro Stoxx 50"}.get(sufijo, "S&P 500")


def _rango(h: pd.DataFrame, periodo: str, clave: str):
    fin = h.index[-1]
    if periodo == FECHAS:
        defecto = (max(h.index[0], fin - pd.DateOffset(years=1)).date(), fin.date())
        sel = st.date_input("Desde – hasta", value=defecto, min_value=h.index[0].date(), max_value=fin.date(),
                            format="DD/MM/YYYY", key=f"{clave}_fechas")
        if isinstance(sel, (tuple, list)) and len(sel) == 2:
            return pd.Timestamp(sel[0]), pd.Timestamp(sel[1]) + pd.Timedelta(hours=23)
        return pd.Timestamp(defecto[0]), fin
    off = PERIODOS.get(periodo)
    if off is None:
        return h.index[0], fin
    if off == "ytd":
        return pd.Timestamp(f"{fin.year}-01-01"), fin
    return fin - off, fin


def _estadisticas(diario: pd.DataFrame, mon: str):
    """Fila compacta con lo esencial del tramo elegido."""
    c = diario["Close"]
    if len(c) < 2:
        return
    r = c.pct_change().dropna()
    var = c.iloc[-1] / c.iloc[0] - 1
    celdas = [("Variación en el periodo", f"{var * 100:+.2f}%".replace(".", ","), f"de {_n(c.iloc[0])} a {_n(c.iloc[-1])} {mon}",
               VERDE if var >= 0 else ROJO),
              ("Máximo", _n(c.max()), f"el {c.idxmax():%d/%m/%Y}", None),
              ("Mínimo", _n(c.min()), f"el {c.idxmin():%d/%m/%Y}", None),
              ("Volatilidad anual", f"{r.std() * np.sqrt(252) * 100:.1f}%".replace(".", ",") if len(r) > 5 else "—",
               "lo que se mueve de normal en un año", None)]
    if len(r):
        celdas += [("Mejor día", f"{r.max() * 100:+.1f}%".replace(".", ","), f"el {r.idxmax():%d/%m/%Y}", VERDE),
                   ("Peor día", f"{r.min() * 100:+.1f}%".replace(".", ","), f"el {r.idxmin():%d/%m/%Y}", ROJO)]
    html = "".join(
        f"<div style='flex:1;min-width:120px'><div style='font-size:12px;color:#777'>{et}</div>"
        f"<div style='font-size:21px;font-weight:600;color:{col or 'inherit'}'>{val}</div>"
        f"<div style='font-size:11.5px;color:#999'>{sub}</div></div>" for et, val, sub, col in celdas)
    st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:10px;margin:4px 0 2px 0'>{html}</div>", unsafe_allow_html=True)


def _n(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def grafico_precio(clave: str, ticker: str, mon: str = "", completo: bool = True, zona_compra: float | None = None,
                   marcas: pd.DataFrame | None = None, periodo_def: str = "1A", h_base: pd.DataFrame | None = None,
                   comparar_def: list[str] | None = None):
    """Gráfico de cotización con periodo a elegir (botones o fechas exactas), velas o línea, granularidad,
    indicadores, paneles, escala logarítmica y comparación con índices u otras empresas.
    Devuelve (desde, hasta) del tramo mostrado."""
    h = historico(ticker)
    if h.empty and h_base is not None and not h_base.empty:
        h = h_base[[c for c in ("Open", "High", "Low", "Close", "Volume") if c in h_base]].dropna(subset=["Close"])
    if h.empty:
        st.info("No hay histórico de precios para dibujar el gráfico.")
        return None, None

    # Controles -----------------------------------------------------------------------
    opciones = list(PERIODOS) + [FECHAS]
    periodo = st.segmented_control("Periodo", opciones, default=periodo_def, key=f"{clave}_per",
                                   label_visibility="collapsed") or periodo_def
    tipo, gran, capas, paneles, log, comparar = "Área", "Auto", [], [], False, []
    if completo:
        c2, c3, _ = st.columns([1.2, 1.4, 3], vertical_alignment="bottom")
        tipo = c2.segmented_control("Dibujo", ["Velas", "Línea"], default="Velas", key=f"{clave}_tipo") or "Velas"
        gran = c3.selectbox("Cada vela es", ["Auto", "1 día", "1 semana", "1 mes"], key=f"{clave}_gran",
                            help="Auto: diaria hasta 1 año, semanal hasta 5 y mensual para más.")
    desde, hasta = _rango(h, periodo, clave)
    if completo:
        with st.expander("⚙️ Indicadores, paneles y comparar", expanded=False):
            e1, e2, e3 = st.columns([2.2, 1.4, 1])
            capas = e1.multiselect("Sobre el precio", ["Media 20", "Media 50", "Media 200", "Bollinger", "Zona de compra",
                                                       "Máx./mín. del periodo"], default=["Media 50", "Media 200"] +
                                   (["Zona de compra"] if zona_compra else []), key=f"{clave}_capas")
            paneles = e2.multiselect("Paneles debajo", ["Volumen", "RSI", "MACD"], default=["Volumen"], key=f"{clave}_paneles")
            log = e3.toggle("Escala logarítmica", key=f"{clave}_log",
                            help="Útil en periodos largos: la misma distancia vertical = la misma subida en %.")
            idx = indice_de(ticker)
            comparar = st.multiselect("Comparar con (rentabilidad en %, desde el inicio del periodo)",
                                      list(INDICES), default=comparar_def or [], key=f"{clave}_comp",
                                      accept_new_options=True, placeholder=f"Por ejemplo {idx}, o escribe el nombre de otra empresa",
                                      help="Elige índices o escribe nombres de empresas (Enter para añadir).")
    elif comparar_def:
        comparar = comparar_def

    span = (hasta - desde).days
    regla = {"1 día": "D", "1 semana": "W", "1 mes": "M"}.get(gran) or ("D" if span <= 400 else "W" if span <= 2000 else "M")
    serie = h if regla == "D" else remuestrear(h, regla)
    t = datos.tecnicos(serie)
    v = t[(t.index >= desde) & (t.index <= hasta)]
    diario = h[(h.index >= desde) & (h.index <= hasta)]
    if len(v) < 2:
        st.info("Ese periodo no tiene suficientes datos: elige uno más largo.")
        return desde, hasta
    _estadisticas(diario, mon)

    # Comparación: todo en % desde el inicio del tramo --------------------------------
    if comparar:
        from comun import resolver
        fig = go.Figure()
        base = v["Close"].iloc[0]
        fig.add_scatter(x=v.index, y=(v["Close"] / base - 1) * 100, name=ticker, line=dict(color="#222", width=2.4),
                        hovertemplate="%{y:+.1f}%")
        for i, nombre in enumerate(comparar):
            tk2 = INDICES.get(nombre) or resolver(nombre)[0]
            if not tk2:
                st.caption(f"No encuentro «{nombre}».")
                continue
            h2 = historico(tk2)
            if h2.empty:
                st.caption(f"Sin datos para «{nombre}».")
                continue
            s2 = (h2 if regla == "D" else remuestrear(h2, regla))["Close"]
            s2 = s2[(s2.index >= desde) & (s2.index <= hasta)]
            if len(s2) < 2:
                continue
            fig.add_scatter(x=s2.index, y=(s2 / s2.iloc[0] - 1) * 100, name=nombre if nombre in INDICES else f"{nombre} ({tk2})",
                            line=dict(color=COLORES_COMP[i % len(COLORES_COMP)], width=1.8), hovertemplate="%{y:+.1f}%")
        fig.add_hline(y=0, line=dict(color="#999", width=1, dash="dot"))
        fig.update_layout(height=460 if completo else 320, margin=dict(l=8, r=8, t=10, b=8), yaxis_title="% desde el inicio",
                          yaxis_ticksuffix="%", legend=dict(orientation="h", y=1.06))
        mostrar(fig)
        st.caption("Todas las líneas parten de 0% al inicio del periodo: así se ve quién lo ha hecho mejor. "
                   "Quita las comparaciones para volver al gráfico de precio.")
        return desde, hasta

    # Gráfico de precio ------------------------------------------------------------------
    filas = 1 + len(paneles)
    alturas = [0.62] + [0.38 / max(len(paneles), 1)] * len(paneles) if paneles else [1]
    fig = make_subplots(rows=filas, cols=1, shared_xaxes=True, row_heights=alturas, vertical_spacing=0.025)
    if tipo == "Velas" and completo:
        fig.add_candlestick(x=v.index, open=v["Open"], high=v["High"], low=v["Low"], close=v["Close"], name="Precio",
                            increasing_line_color=VERDE, decreasing_line_color=ROJO, row=1, col=1)
    else:
        sube = v["Close"].iloc[-1] >= v["Close"].iloc[0]
        fig.add_scatter(x=v.index, y=v["Close"], name="Cierre", mode="lines", line=dict(color=VERDE if sube else ROJO, width=2),
                        fill="tozeroy" if not completo and not log else None,
                        fillcolor="rgba(26,158,92,0.08)" if sube else "rgba(214,69,69,0.08)",
                        customdata=(v["Close"] / v["Close"].iloc[0] - 1) * 100,
                        hovertemplate="%{y:,.2f} " + mon + " (%{customdata:+.1f}% en el periodo)<extra></extra>", row=1, col=1)
    lineas = {"Media 20": ("SMA20", AZUL), "Media 50": ("SMA50", NARANJA), "Media 200": ("SMA200", MORADO)}
    for capa in capas:
        if capa in lineas:
            col, color = lineas[capa]
            fig.add_scatter(x=v.index, y=v[col], name=capa, line=dict(color=color, width=1.5), row=1, col=1)
    if "Bollinger" in capas:
        fig.add_scatter(x=v.index, y=v["BB_sup"], name="Bollinger sup.", line=dict(color=GRIS, width=1, dash="dot"), row=1, col=1)
        fig.add_scatter(x=v.index, y=v["BB_inf"], name="Bollinger inf.", line=dict(color=GRIS, width=1, dash="dot"),
                        fill="tonexty", fillcolor="rgba(154,164,178,.10)", row=1, col=1)
    if "Zona de compra" in capas and zona_compra:
        fig.add_hline(y=zona_compra, line=dict(color=VERDE, dash="dash"), annotation_text="zona de compra", row=1, col=1)
    if "Máx./mín. del periodo" in capas:
        fig.add_hline(y=float(v["High"].max()), line=dict(color=ROJO, dash="dot", width=1), annotation_text="máximo", row=1, col=1)
        fig.add_hline(y=float(v["Low"].min()), line=dict(color=VERDE, dash="dot", width=1), annotation_text="mínimo",
                      annotation_position="bottom right", row=1, col=1)
    if marcas is not None and not marcas.empty:
        marcas = marcas[(marcas["x"] >= v.index[0]) & (marcas["x"] <= v.index[-1])]
    if marcas is not None and not marcas.empty:
        for _, g in marcas.groupby("color"):
            fig.add_scatter(x=g["x"], y=g["y"], mode="markers", name=g["grupo"].iloc[0], text=g["texto"],
                            marker=dict(symbol=g["simbolo"].iloc[0], size=11, color=g["color"].iloc[0], line=dict(width=1, color="white")),
                            hovertemplate="%{text}<extra></extra>", row=1, col=1)
    for i, p in enumerate(paneles, start=2):
        if p == "Volumen":
            colores = [VERDE if c >= o else ROJO for o, c in zip(v["Open"], v["Close"])] if "Open" in v else GRIS
            fig.add_bar(x=v.index, y=v["Volume"], name="Volumen", marker_color=colores, opacity=0.6, row=i, col=1)
            fig.add_scatter(x=v.index, y=v["Volume"].rolling(20, min_periods=1).mean(), name="Volumen medio",
                            line=dict(color="#555", width=1), row=i, col=1)
            fig.update_yaxes(title_text="Vol.", row=i, col=1)
        elif p == "RSI":
            fig.add_scatter(x=v.index, y=v["RSI"], name="RSI", line=dict(color=AZUL, width=1.4), row=i, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor="rgba(214,69,69,.08)", line_width=0, row=i, col=1)
            fig.add_hrect(y0=0, y1=30, fillcolor="rgba(26,158,92,.08)", line_width=0, row=i, col=1)
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=i, col=1)
        elif p == "MACD":
            fig.add_bar(x=v.index, y=v["MACD_hist"], name="MACD hist.",
                        marker_color=[VERDE if x >= 0 else ROJO for x in v["MACD_hist"].fillna(0)], row=i, col=1)
            fig.add_scatter(x=v.index, y=v["MACD"], name="MACD", line=dict(color="#222", width=1), row=i, col=1)
            fig.add_scatter(x=v.index, y=v["MACD_senal"], name="Señal", line=dict(color=NARANJA, width=1), row=i, col=1)
            fig.update_yaxes(title_text="MACD", row=i, col=1)
    lo, hi = float(v["Low"].min()), float(v["High"].max())
    if "Zona de compra" in capas and zona_compra and lo * 0.7 < zona_compra < lo:
        lo = zona_compra
    pad = (hi - lo) * 0.06 or hi * 0.02
    if log:
        fig.update_yaxes(type="log", row=1, col=1)
    else:
        fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=1)
    fig.update_yaxes(side="right", row=1, col=1)
    if regla == "D" and span <= 400:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_layout(height=(470 if completo else 300) + 120 * len(paneles), xaxis_rangeslider_visible=False,
                      margin=dict(l=8, r=8, t=10, b=8), showlegend=completo, legend=dict(orientation="h", y=1.04))
    mostrar(fig)
    nombre_vela = {"D": "un día", "W": "una semana", "M": "un mes"}[regla]
    st.caption(f"Cada {'vela' if completo and tipo == 'Velas' else 'punto'} es **{nombre_vela}**. Arrastra sobre el gráfico para "
               "ampliar una zona, usa la rueda del ratón para acercar y **doble clic** para volver."
               + (" Las medias usan el mismo intervalo (Media 50 = 50 velas)." if completo and capas else ""))
    return desde, hasta
