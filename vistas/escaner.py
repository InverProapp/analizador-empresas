"""Sección Escáner: recorre un índice entero y ordena las empresas por nota."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from comun import (COLOR, GRIS, abrir_empresa, ajustes, analizar, cargar_varias, config_columnas, fila_resumen, selector_universo,
                   tiempo_estimado)

st.sidebar.title("📡 Escáner")
aj = ajustes()

st.title("Escáner de oportunidades")
st.write("Analiza todas las empresas de un índice con tus criterios y te dice cuáles están en **Comprar** "
         "y cuáles cotizan ya por debajo de su **zona de compra**.")

universo, tickers = selector_universo("esc")
st.caption(f"{len(tickers)} empresas · la primera vez tarda ≈ {tiempo_estimado(len(tickers))}; después se guarda 12 h "
           "para todos los usuarios. Las listas de los índices son aproximadas.")

if st.button(f"📡 Escanear {universo} ({len(tickers)} empresas)", type="primary", disabled=not tickers):
    cargadas = cargar_varias(tickers, "Analizando")
    filas = []
    for tk, e in cargadas.items():
        try:
            _, m, r = analizar(tk, aj, e)
            filas.append(fila_resumen(tk, e, m, r))
        except Exception:
            pass
    st.session_state["escaner"] = {"universo": universo, "df": pd.DataFrame(filas),
                                   "faltan": [t for t in tickers if t not in cargadas],
                                   "hora": pd.Timestamp.now(tz="Europe/Madrid").strftime("%d/%m %H:%M")}

res = st.session_state.get("escaner")
if not res or res["df"].empty:
    st.stop()

df = res["df"].sort_values("Nota", ascending=False, na_position="last")
st.subheader(f"{res['universo']} · {res['hora']}")
if res["faltan"]:
    st.caption("Sin datos de Yahoo para: " + ", ".join(res["faltan"]))

k = st.columns(4)
k[0].metric("Analizadas", len(df))
for col, v in zip(k[1:], ["Comprar", "Esperar", "Vender"]):
    col.metric(v, int((df["Veredicto"] == v).sum()))

f1, f2, f3 = st.columns([1, 1.4, 1.6])
solo_comprar = f1.checkbox("Solo 'Comprar'", key="esc_solo_comprar")
solo_zona = f2.checkbox("Solo por debajo de su zona de compra", key="esc_solo_zona")
sectores = sorted(df["Sector"].dropna().unique())
filtro_sector = f3.multiselect("Sectores", sectores, key="esc_sectores", placeholder="Todos los sectores")
vista = df
if filtro_sector:
    vista = vista[vista["Sector"].isin(filtro_sector)]
if solo_comprar:
    vista = vista[vista["Veredicto"] == "Comprar"]
if solo_zona:
    vista = vista[vista["vs zona compra"].notna() & (vista["vs zona compra"] <= 0)]

st.caption(f"Mostrando {len(vista)} de {len(df)} empresas")
st.dataframe(vista, hide_index=True, width="stretch", column_config=config_columnas(), height=min(36 * (len(vista) + 1), 640))
st.caption("**vs zona compra**: cuánto está el precio por encima (+) o por debajo (−) del precio de compra con margen de seguridad. "
           "**Potencial**: distancia al valor justo estimado.")

# Mapa nota vs potencial
d = vista.dropna(subset=["Nota", "Potencial"])
d = d[d["Potencial"].between(-0.9, 3)]  # fuera valores absurdos que aplastan el gráfico
if not d.empty:
    fig = go.Figure()
    for v in ["Comprar", "Esperar", "Vender"]:
        dv = d[d["Veredicto"] == v]
        etiquetas = len(d) <= 60
        fig.add_scatter(x=dv["Nota"], y=dv["Potencial"], mode="markers+text" if etiquetas else "markers",
                        text=dv["Ticker"], textposition="top center", name=v, hovertext=dv["Empresa"],
                        marker=dict(size=11 if etiquetas else 7, color=COLOR[v]), textfont=dict(size=10))
    fig.add_hline(y=0, line=dict(color=GRIS, dash="dot"))
    fig.update_layout(height=460, xaxis_title="Nota del modelo", yaxis_title="Potencial hasta el valor justo",
                      yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
    st.subheader("Mapa: calidad del conjunto vs margen hasta su valor")
    st.caption("Arriba a la derecha: buena nota y con recorrido. Abajo a la izquierda: mala nota y cara.")
    st.plotly_chart(fig, width="stretch")

st.subheader("Ver una empresa en detalle")
c1, c2, c3 = st.columns([3, 1, 1])
elegida = c1.selectbox("Empresa", [f"{t} · {n}" for t, n in zip(df["Ticker"], df["Empresa"])], label_visibility="collapsed")
if c2.button("Abrir análisis →"):
    abrir_empresa(elegida.split(" · ")[0])
if c3.button("Simular →"):
    abrir_empresa(elegida.split(" · ")[0], "vistas/simulador.py")
