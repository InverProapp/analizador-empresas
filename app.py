"""Analizador de empresas — dashboard Streamlit.

Arranque:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import datos
import scoring as sc

st.set_page_config(page_title="Analizador de empresas", page_icon="📊", layout="wide")

COLOR = {"Comprar": "#1a9e5c", "Esperar": "#d99a00", "Vender": "#d64545", "Sin datos": "#888888"}
AZUL, GRIS = "#2a6fdb", "#9aa4b2"


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------
def f_pct(x, dec=1):
    return "—" if x is None else f"{x * 100:.{dec}f}%".replace(".", ",")


def f_x(x, dec=1):
    return "—" if x is None else f"{x:.{dec}f}x".replace(".", ",")


def f_num(x, dec=2):
    return "—" if x is None else f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def f_dinero(x, moneda=""):
    if x is None:
        return "—"
    a = abs(x)
    for lim, suf in ((1e12, "B"), (1e9, "mm"), (1e6, "M"), (1e3, "k")):
        if a >= lim:
            return f"{x / lim:,.1f} {suf} {moneda}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{f_num(x)} {moneda}"


def f_item(i: sc.Item):
    if i.valor is None:
        return "—"
    if i.formato == "%":
        return f_pct(i.valor)
    if i.formato == "x":
        return f_x(i.valor)
    if i.formato == "bool":
        return "Sí" if i.valor else "No"
    return f_num(i.valor, 1)


def color_nota(n):
    if n is None:
        return GRIS
    return COLOR["Comprar"] if n >= 65 else COLOR["Esperar"] if n >= 45 else COLOR["Vender"]


# ---------------------------------------------------------------------------
# Datos cacheados
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def cargar(ticker: str) -> datos.Empresa:
    return datos.descargar(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def buscar(texto: str, _v: int = 2):
    return datos.buscar(texto)


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
st.sidebar.title("📊 Analizador")
modo = st.sidebar.radio("Buscar por", ["Nombre", "Ticker"], horizontal=True)
ticker = None
if modo == "Nombre":
    q = st.sidebar.text_input("Empresa", value="Inditex", help="Escribe el nombre y elige el ticker de la bolsa que quieras.")
    resultados = buscar(q) if q else []
    if resultados:
        opciones = {f"{r['symbol']} · {r['nombre']} ({r['bolsa']})": r["symbol"] for r in resultados}
        ticker = opciones[st.sidebar.selectbox("Resultados", list(opciones))]
    elif q:
        st.sidebar.info("Sin resultados. Prueba con el ticker directamente.")
else:
    ticker = st.sidebar.text_input("Ticker de Yahoo Finance", value="ITX.MC",
                                   help="Ejemplos: AAPL, MSFT, SAN.MC, ITX.MC, MC.PA, SAP.DE, 7203.T, NESN.SW").strip().upper() or None

with st.sidebar.expander("⚖️ Pesos de cada pilar", expanded=False):
    pesos = {p: st.slider(p, 0, 50, sc.PESOS_DEFECTO[p], 5, key=f"peso_{p}") for p in sc.PILARES}

with st.sidebar.expander("🎯 Umbrales del veredicto", expanded=False):
    u_comprar = st.slider("Comprar si la nota ≥", 50, 90, sc.UMBRAL_COMPRAR)
    u_vender = st.slider("Vender si la nota <", 20, 60, sc.UMBRAL_VENDER)
    if u_vender >= u_comprar:
        st.warning("El umbral de venta debe ser menor que el de compra.")
        u_vender = u_comprar - 1
    margen_seg = st.slider("Margen de seguridad para el precio de compra", 0, 40, 15, 5, format="%d%%") / 100
    respetar_tendencia = st.checkbox("No dar 'Comprar' con tendencia bajista fuerte", value=True)

with st.sidebar.expander("💰 Parámetros del DCF", expanded=False):
    auto_g = st.checkbox("Crecimiento automático (histórico, máx. 15%)", value=True)
    g_manual = st.slider("Crecimiento FCF años 1-5", -5, 30, 8, 1, format="%d%%", disabled=auto_g) / 100
    wacc = st.slider("Tasa de descuento", 5.0, 15.0, 9.0, 0.5, format="%.1f%%") / 100
    g_term = st.slider("Crecimiento terminal", 0.0, 4.0, 2.5, 0.5, format="%.1f%%") / 100

st.sidebar.caption("Datos: Yahoo Finance vía yfinance (gratis, con ~15 min de retraso). "
                   "Herramienta de análisis según reglas: no es asesoramiento financiero.")


def analizar(tk: str):
    e = cargar(tk)
    m = datos.metricas(e, None if auto_g else g_manual, wacc, g_term)
    r = sc.evaluar(m, e.sector, pesos, u_comprar, u_vender, margen_seg, respetar_tendencia)
    return e, m, r


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
if not ticker:
    st.title("Analizador de empresas")
    st.write("Busca una empresa en la barra lateral para empezar.")
    st.stop()

with st.spinner(f"Descargando {ticker}…"):
    try:
        e, m, r = analizar(ticker)
    except Exception as ex:
        st.error(f"No se pudo descargar {ticker}: {ex}")
        st.stop()

if not e.info and (e.hist is None or e.hist.empty):
    st.error(f"Yahoo Finance no devuelve datos para **{ticker}**. Revisa el ticker (en España llevan .MC, p. ej. SAN.MC).")
    st.stop()

mon = e.moneda
precio = m.get("precio")
var_dia = None
if e.hist is not None and len(e.hist) > 1:
    var_dia = e.hist["Close"].iloc[-1] / e.hist["Close"].iloc[-2] - 1

# Cabecera ------------------------------------------------------------------
st.title(e.nombre)
sector_es = sc.SECTORES_ES.get(e.sector, e.sector)
st.caption(f"**{e.ticker}** · {sector_es} · {e.info.get('industry', '')} · {e.info.get('country', '')} · "
           f"{e.info.get('exchange', '')} · moneda {mon}")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Precio", f"{f_num(precio)} {mon}", f_pct(var_dia, 2) if var_dia is not None else None)
k2.metric("Capitalización", f_dinero(m.get("market_cap"), mon))
k3.metric("PER", f_x(m.get("per")))
k4.metric("Rent. dividendo", f_pct(m.get("rent_dividendo"), 2))
k5.metric("Beta", f_num(m.get("beta")))

# Veredicto -------------------------------------------------------------------
col_v, col_g, col_r = st.columns([1.2, 1, 1.6])
with col_v:
    color = COLOR[r.veredicto]
    st.markdown(
        f"""<div style="border-radius:14px;padding:22px;background:{color};color:white;text-align:center">
        <div style="font-size:14px;opacity:.85;letter-spacing:.08em">VEREDICTO</div>
        <div style="font-size:46px;font-weight:800;line-height:1.1">{r.veredicto.upper()}</div>
        <div style="font-size:14px;opacity:.9">Confianza {r.confianza.lower()} · datos para el {r.cobertura * 100:.0f}% de las métricas</div>
        </div>""", unsafe_allow_html=True)
    if r.veredicto != r.veredicto_bruto:
        st.caption(f"Por nota saldría **{r.veredicto_bruto}**, pero las alertas lo limitan a **{r.veredicto}**.")
    v1, v2 = st.columns(2)
    v1.metric("Valor justo estimado", f"{f_num(r.valor_justo)} {mon}" if r.valor_justo else "—",
              f_pct(r.valor_justo / precio - 1) if r.valor_justo and precio else None)
    v2.metric(f"Zona de compra (−{margen_seg * 100:.0f}%)", f"{f_num(r.precio_compra)} {mon}" if r.precio_compra else "—")

with col_g:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=r.nota or 0, number={"suffix": "/100", "font": {"size": 28}, "valueformat": ".0f"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#222", "thickness": 0.25},
               "steps": [{"range": [0, u_vender], "color": "#f4c7c7"},
                         {"range": [u_vender, u_comprar], "color": "#f7e3a8"},
                         {"range": [u_comprar, 100], "color": "#bfe6cf"}]},
        title={"text": "Nota global", "font": {"size": 16}}))
    fig.update_layout(height=280, margin=dict(l=30, r=30, t=60, b=0))
    st.plotly_chart(fig, width="stretch")

with col_r:
    nombres = [p for p in sc.PILARES if r.pilares[p].nota is not None]
    valores = [r.pilares[p].nota for p in nombres]
    fig = go.Figure(go.Scatterpolar(r=valores + valores[:1], theta=nombres + nombres[:1], fill="toself",
                                    line_color=AZUL, fillcolor="rgba(42,111,219,.25)"))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickfont_size=9)), height=280,
                      margin=dict(l=40, r=40, t=30, b=20), showlegend=False)
    st.plotly_chart(fig, width="stretch")

for a in r.alertas:
    st.warning(a, icon="⚠️")
if e.errores:
    with st.expander("Avisos de descarga"):
        for err in e.errores:
            st.caption(err)

# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------
tabs = st.tabs(["🧭 Resumen", "💶 Valoración", "📈 Finanzas", "📉 Técnico", "💸 Dividendos", "🆚 Comparador", "📘 Metodología"])

# Resumen ---------------------------------------------------------------------
with tabs[0]:
    cpos, cneg = st.columns(2)
    with cpos:
        st.subheader("✅ A favor")
        if not r.positivos:
            st.caption("Ningún punto especialmente fuerte.")
        for pilar, i in r.positivos:
            st.markdown(f"- **{i.nombre}**: {f_item(i)} <span style='color:{GRIS}'>({pilar})</span>", unsafe_allow_html=True)
    with cneg:
        st.subheader("❌ En contra")
        if not r.negativos:
            st.caption("Ningún punto especialmente débil.")
        for pilar, i in r.negativos:
            st.markdown(f"- **{i.nombre}**: {f_item(i)} <span style='color:{GRIS}'>({pilar})</span>", unsafe_allow_html=True)

    st.subheader("Nota por pilar")
    filas = []
    for p in sc.PILARES:
        pl = r.pilares[p]
        peso_ef = r.pesos.get(p, 0) if pl.nota is not None else 0
        filas.append({"Pilar": p, "Nota": pl.nota, "Peso": peso_ef})
    df_p = pd.DataFrame(filas)
    tot = df_p["Peso"].sum() or 1
    fig = go.Figure(go.Bar(
        x=df_p["Nota"].fillna(0), y=df_p["Pilar"], orientation="h",
        marker_color=[color_nota(n) for n in df_p["Nota"]],
        text=[("sin datos" if pd.isna(n) else f"{n:.0f}") + f"  · peso {w / tot * 100:.0f}%" for n, w in zip(df_p["Nota"], df_p["Peso"])],
        textposition="outside"))
    fig.update_layout(xaxis=dict(range=[0, 115]), height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Detalle de todas las métricas")
    for p in sc.PILARES:
        pl = r.pilares[p]
        etiqueta = f"{p} — {'sin datos' if pl.nota is None else f'{pl.nota:.0f}/100'}"
        with st.expander(etiqueta, expanded=False):
            if not pl.items:
                st.caption("No aplica (p. ej. la empresa no paga dividendo o tiene pocos analistas).")
                continue
            st.dataframe(pd.DataFrame([{
                "Métrica": i.nombre, "Valor": f_item(i),
                "Nota": None if i.nota is None else round(i.nota),
                "Peso": i.peso, "Referencia": i.referencia} for i in pl.items]),
                hide_index=True, width="stretch",
                column_config={"Nota": st.column_config.ProgressColumn("Nota", min_value=0, max_value=100, format="%d")})

# Valoración ------------------------------------------------------------------
with tabs[1]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PER", f_x(m.get("per")), help="Precio / beneficio últimos 12 meses")
    c2.metric("PER futuro", f_x(m.get("per_fwd")))
    c3.metric("EV/EBITDA", f_x(m.get("ev_ebitda")))
    c4.metric("Precio / valor contable", f_x(m.get("p_vc")))
    c1.metric("PEG", f_x(m.get("peg"), 2))
    c2.metric("Precio / ventas", f_x(m.get("p_ventas")))
    c3.metric("Rentabilidad FCF", f_pct(m.get("fcf_yield")))
    c4.metric("Valor empresa (EV)", f_dinero(m.get("ev"), mon))

    st.subheader("Precio actual frente a estimaciones de valor")
    est = {"Precio actual": precio, "DCF": m.get("valor_dcf"), "Graham": m.get("valor_graham"),
           "Objetivo analistas": m.get("precio_objetivo"), "Valor justo (mediana)": r.valor_justo,
           "Zona de compra": r.precio_compra}
    est = {k: v for k, v in est.items() if v}
    fig = go.Figure(go.Bar(x=list(est.values()), y=list(est.keys()), orientation="h",
                           marker_color=["#222" if k == "Precio actual" else AZUL if k != "Zona de compra" else COLOR["Comprar"] for k in est],
                           text=[f"{f_num(v)} {mon}" for v in est.values()], textposition="outside"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"),
                      xaxis=dict(range=[0, max(est.values()) * 1.25] if est else None))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Descuento de flujos de caja (DCF)")
    if not m.get("misma_moneda", True):
        st.info(f"La empresa reporta en {e.moneda_fin} y cotiza en {mon}: el DCF por acción no se calcula para no mezclar monedas.")
    elif not m.get("fcf_base_dcf") or m["fcf_base_dcf"] <= 0:
        st.info("El flujo de caja libre es negativo o no está disponible: el DCF no aplica.")
    else:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("FCF base", f_dinero(m["fcf_base_dcf"], mon))
        d2.metric("Crecimiento años 1-5", f_pct(m["crecimiento_dcf"]))
        d3.metric("Tasa de descuento", f_pct(wacc))
        d4.metric("Valor por acción", f"{f_num(m.get('valor_dcf'))} {mon}", f_pct(m.get("margen_seguridad_dcf")))
        st.caption("Dos etapas: el crecimiento elegido durante 5 años, que converge hasta el terminal en el año 10. "
                   "Al valor de la empresa se le resta la deuda neta. Cambia los supuestos en la barra lateral.")
        # Sensibilidad
        tasas = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
        crecs = [m["crecimiento_dcf"] + d for d in (-0.04, -0.02, 0, 0.02, 0.04)]
        tabla = {}
        for gc in crecs:
            fila = {}
            for t in tasas:
                ve = datos.dcf(m["fcf_base_dcf"], gc, t, g_term)
                fila[f"desc. {t * 100:.1f}%"] = ((ve - (m.get("deuda_neta") or 0)) / m["acciones"]) if ve and m.get("acciones") else None
            tabla[f"crec. {gc * 100:.0f}%"] = fila
        sens = pd.DataFrame(tabla).T

        def pintar(v):
            if v is None or pd.isna(v) or not precio:
                return ""
            return f"background-color: {'#bfe6cf' if v > precio * 1.15 else '#f4c7c7' if v < precio else '#f7e3a8'}"
        st.markdown("**Sensibilidad del valor por acción** (verde: > 15% sobre el precio · rojo: por debajo del precio)")
        st.dataframe(sens.style.format(lambda v: f_num(v)).map(pintar), width="stretch")

    st.subheader("Múltiplos frente a la referencia del sector")
    ref = sc.SECTORES.get(e.sector, sc.SECTOR_DEFECTO)
    filas = [("PER", m.get("per"), ref["per"]), ("EV/EBITDA", m.get("ev_ebitda"), ref["ev"]),
             ("Precio/Valor contable", m.get("p_vc"), ref["pvc"])]
    st.dataframe(pd.DataFrame([{"Múltiplo": n, "Empresa": f_x(v), "Barato (≤)": f_x(rf[0]) if rf else "—",
                                "Caro (≥)": f_x(rf[1]) if rf else "—"} for n, v, rf in filas]),
                 hide_index=True, width="stretch")

# Finanzas --------------------------------------------------------------------
with tabs[2]:
    series = m["series"]

    def a_df(nombres):
        cols = {}
        for n in nombres:
            s = series.get(n)
            if s is not None and len(s.dropna()):
                s = s.dropna()
                s.index = [pd.Timestamp(i).year for i in s.index]
                cols[n] = s
        return pd.DataFrame(cols).sort_index()

    df1 = a_df(["Ingresos", "EBITDA", "Beneficio neto", "Flujo de caja libre"])
    if df1.empty:
        st.info("Yahoo no tiene estados financieros anuales para este valor.")
    else:
        st.subheader(f"Cuenta de resultados y caja ({e.moneda_fin})")
        fig = go.Figure()
        for col, colr in zip(df1.columns, [GRIS, "#7aa6f0", AZUL, COLOR["Comprar"]]):
            fig.add_bar(x=df1.index.astype(str), y=df1[col], name=col, marker_color=colr)
        fig.update_layout(barmode="group", height=380, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")

        if "Ingresos" in df1:
            st.subheader("Márgenes")
            mg = pd.DataFrame(index=df1.index)
            for col, nombre in (("EBITDA", "Margen EBITDA"), ("Beneficio neto", "Margen neto"), ("Flujo de caja libre", "Margen FCF")):
                if col in df1:
                    mg[nombre] = df1[col] / df1["Ingresos"]
            fig = go.Figure()
            for col in mg:
                fig.add_scatter(x=mg.index.astype(str), y=mg[col], name=col, mode="lines+markers")
            fig.update_layout(height=300, yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
            st.plotly_chart(fig, width="stretch")

    df2 = a_df(["Patrimonio neto", "Deuda total", "Caja"])
    if not df2.empty:
        st.subheader("Balance")
        fig = go.Figure()
        for col, colr in zip(df2.columns, [AZUL, COLOR["Vender"], COLOR["Comprar"]]):
            fig.add_bar(x=df2.index.astype(str), y=df2[col], name=col, marker_color=colr)
        fig.update_layout(barmode="group", height=320, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Salud financiera")
        st.dataframe(pd.DataFrame([
            ("Deuda neta", f_dinero(m.get("deuda_neta"), e.moneda_fin)),
            ("Deuda neta / EBITDA", f_x(m.get("deuda_neta_ebitda"))),
            ("Deuda / Patrimonio", f_x(m.get("deuda_patrimonio"), 2)),
            ("Liquidez corriente", f_x(m.get("liquidez"), 2)),
            ("Prueba ácida", f_x(m.get("prueba_acida"), 2)),
            ("Cobertura de intereses", f_x(m.get("cobertura_intereses"))),
            ("Altman Z-Score", f_num(m.get("altman_z"))),
            ("ROE", f_pct(m.get("roe"))), ("ROIC aprox.", f_pct(m.get("roic"))), ("ROA", f_pct(m.get("roa"))),
        ], columns=["Indicador", "Valor"]), hide_index=True, width="stretch")
    with c2:
        st.subheader(f"Piotroski F-Score: {f_num(m.get('piotroski'), 1)}/9")
        for nombre, ok in m.get("piotroski_detalle", []):
            st.markdown(f"{'✅' if ok else '❌' if ok is False else '➖'} {nombre}")
        st.caption("➖ = sin datos. Si faltan criterios, la nota se escala a 9.")

# Técnico ---------------------------------------------------------------------
with tabs[3]:
    t = datos.tecnicos(e.hist)
    if t.empty:
        st.info("Sin histórico de precios.")
    else:
        rango = st.radio("Periodo", ["6M", "1A", "2A", "5A"], index=1, horizontal=True)
        n = {"6M": 126, "1A": 252, "2A": 504, "5A": 1260}[rango]
        v = t.iloc[-n:]
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.55, 0.12, 0.16, 0.17], vertical_spacing=0.02)
        fig.add_candlestick(x=v.index, open=v["Open"], high=v["High"], low=v["Low"], close=v["Close"], name="Precio", row=1, col=1)
        fig.add_scatter(x=v.index, y=v["SMA50"], name="Media 50", line=dict(color="#f39c12", width=1.4), row=1, col=1)
        fig.add_scatter(x=v.index, y=v["SMA200"], name="Media 200", line=dict(color="#8e44ad", width=1.6), row=1, col=1)
        fig.add_scatter(x=v.index, y=v["BB_sup"], name="Bollinger", line=dict(color=GRIS, width=0.8, dash="dot"), row=1, col=1)
        fig.add_scatter(x=v.index, y=v["BB_inf"], name="Bollinger inf.", showlegend=False, line=dict(color=GRIS, width=0.8, dash="dot"), row=1, col=1)
        if r.precio_compra:
            fig.add_hline(y=r.precio_compra, line=dict(color=COLOR["Comprar"], dash="dash"), annotation_text="zona de compra", row=1, col=1)
        fig.add_bar(x=v.index, y=v["Volume"], name="Volumen", marker_color=GRIS, row=2, col=1)
        fig.add_scatter(x=v.index, y=v["RSI"], name="RSI", line=dict(color=AZUL), row=3, col=1)
        fig.add_hline(y=70, line=dict(color=COLOR["Vender"], dash="dot", width=1), row=3, col=1)
        fig.add_hline(y=30, line=dict(color=COLOR["Comprar"], dash="dot", width=1), row=3, col=1)
        fig.add_bar(x=v.index, y=v["MACD_hist"], name="MACD hist.",
                    marker_color=[COLOR["Comprar"] if x >= 0 else COLOR["Vender"] for x in v["MACD_hist"].fillna(0)], row=4, col=1)
        fig.add_scatter(x=v.index, y=v["MACD"], name="MACD", line=dict(color="#222", width=1), row=4, col=1)
        fig.add_scatter(x=v.index, y=v["MACD_senal"], name="Señal", line=dict(color="#f39c12", width=1), row=4, col=1)
        fig.update_layout(height=820, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10),
                          legend=dict(orientation="h", y=1.02))
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
        fig.update_yaxes(title_text="MACD", row=4, col=1)
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        st.plotly_chart(fig, width="stretch")

        c = st.columns(6)
        for col, (nombre, val) in zip(c, [("1 mes", m.get("rent_1m")), ("3 meses", m.get("rent_3m")), ("6 meses", m.get("rent_6m")),
                                           ("1 año", m.get("rent_1a")), ("3 años", m.get("rent_3a")), ("Volatilidad anual", m.get("volatilidad"))]):
            col.metric(nombre, f_pct(val))
        c = st.columns(6)
        c[0].metric("RSI (14)", f_num(m.get("rsi"), 0))
        c[1].metric("vs media 200", f_pct(m.get("sobre_sma200")))
        c[2].metric("Máx. 52 sem.", f_num(m.get("max_52s")))
        c[3].metric("Mín. 52 sem.", f_num(m.get("min_52s")))
        c[4].metric("Caída desde máximos", f_pct(m.get("drawdown_actual")))
        c[5].metric("Peor caída (5a)", f_pct(m.get("max_drawdown")))

# Dividendos ------------------------------------------------------------------
with tabs[4]:
    c = st.columns(4)
    c[0].metric("Rentabilidad (12 m)", f_pct(m.get("rent_dividendo"), 2))
    c[1].metric("Payout", f_pct(m.get("payout"), 0))
    c[2].metric("Crecimiento anual 5a", f_pct(m.get("cagr_dividendo_5a")))
    c[3].metric("Años sin recortar", m.get("anos_sin_recorte", 0))
    da = m.get("div_anuales")
    if da is None or len(da) == 0:
        st.info("Esta empresa no ha pagado dividendos en el periodo disponible.")
    else:
        fig = go.Figure(go.Bar(x=da.index.astype(str), y=da.values, marker_color=AZUL,
                               text=[f_num(x, 3) for x in da.values], textposition="outside"))
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), title=f"Dividendo por acción y año ({mon}, años completos)")
        st.plotly_chart(fig, width="stretch")

# Comparador ------------------------------------------------------------------
with tabs[5]:
    st.write("Compara varias empresas con los mismos criterios (separa los tickers con comas).")
    lista = st.text_input("Tickers", value=f"{ticker}, ")
    tks = [x.strip().upper() for x in lista.split(",") if x.strip()]
    if st.button("Comparar", type="primary") and tks:
        filas, prog = [], st.progress(0.0)
        for k, tk in enumerate(tks):
            try:
                e2, m2, r2 = analizar(tk)
                fila = {"Ticker": tk, "Empresa": e2.nombre, "Sector": sc.SECTORES_ES.get(e2.sector, e2.sector),
                        "Veredicto": r2.veredicto, "Nota": r2.nota}
                fila.update({p: r2.pilares[p].nota for p in sc.PILARES})
                fila.update({"PER": m2.get("per"), "EV/EBITDA": m2.get("ev_ebitda"), "ROE": m2.get("roe"),
                             "Div.": m2.get("rent_dividendo"), "Potencial": (r2.valor_justo / m2["precio"] - 1)
                             if r2.valor_justo and m2.get("precio") else None})
                filas.append(fila)
            except Exception as ex:
                filas.append({"Ticker": tk, "Empresa": f"Error: {ex}"})
            prog.progress((k + 1) / len(tks))
        prog.empty()
        st.session_state["comparativa"] = pd.DataFrame(filas)
    comp = st.session_state.get("comparativa")
    if comp is not None and not comp.empty:
        if "Nota" in comp:
            comp = comp.sort_values("Nota", ascending=False, na_position="last")
        cfg = {p: st.column_config.ProgressColumn(p, min_value=0, max_value=100, format="%.0f") for p in ["Nota"] + sc.PILARES}
        cfg.update({"ROE": st.column_config.NumberColumn(format="percent"), "Div.": st.column_config.NumberColumn(format="percent"),
                    "Potencial": st.column_config.NumberColumn(format="percent"),
                    "PER": st.column_config.NumberColumn(format="%.1f"), "EV/EBITDA": st.column_config.NumberColumn(format="%.1f")})
        st.dataframe(comp, hide_index=True, width="stretch", column_config=cfg)
        if "Nota" in comp:
            fig = go.Figure(go.Bar(x=comp["Ticker"], y=comp["Nota"], marker_color=[COLOR.get(v, GRIS) for v in comp.get("Veredicto", [])],
                                   text=comp.get("Veredicto"), textposition="outside"))
            fig.update_layout(height=320, yaxis=dict(range=[0, 105]), margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")

# Metodología -----------------------------------------------------------------
with tabs[6]:
    st.markdown(f"""
### Cómo se llega al veredicto
1. **Cada métrica se puntúa de 0 a 100** entre un valor "malo" y uno "bueno". Los umbrales de PER, EV/EBITDA,
   P/VC, margen operativo, ROE y deuda cambian **según el sector** (un PER de 20 es barato en tecnología y caro en energía).
2. Las métricas se agrupan en **7 pilares**: valoración, calidad, salud financiera, crecimiento, dividendo, técnico y analistas.
   Si un pilar no tiene datos (p. ej. no paga dividendo), su peso se reparte entre los demás.
3. **Nota global** = media ponderada de los pilares con los pesos de la barra lateral.
4. **Veredicto**: Comprar si la nota es ≥ {u_comprar}, Vender si es < {u_vender}, Esperar en medio.
5. **Alertas que limitan**: aunque la nota dé Comprar, se baja a Esperar si hay riesgo de quiebra (Altman Z < 1,81),
   Piotroski ≤ 2, quema de caja con deuda alta, tendencia bajista fuerte (opcional) o pocos datos.
6. **Valor justo** = mediana de DCF, número de Graham y precio objetivo de analistas (si hay ≥ 3).
   **Zona de compra** = valor justo menos el margen de seguridad.

### Particularidades
- **Bancos y aseguradoras**: no se usan EV/EBITDA, DCF ni deuda/EBITDA (la deuda es su negocio). Pesa más el P/VC y el ROE.
- **Inmobiliarias**: más tolerancia a la deuda y más peso al P/VC; no se usa Altman Z.
- Si la empresa **reporta en otra moneda** (ADRs, algunas europeas en EE. UU.), se omiten DCF, Graham y Altman.

### Limitaciones
- Datos de Yahoo Finance: gratuitos pero no auditados; pueden faltar o venir con errores, sobre todo en bolsas pequeñas.
- El modelo es mecánico: no sabe nada de noticias, gestión, ventajas competitivas ni del ciclo del sector.
- Es una herramienta de apoyo para tu propio análisis, **no una recomendación de inversión**.
""")
