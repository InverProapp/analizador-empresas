"""Sección Backtest: ¿habría funcionado el veredicto en el pasado?"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import backtest as bt
import universos
from comun import COLOR, GRIS, AZUL, ajustes, cargar_varias, f_pct

st.sidebar.title("🧪 Backtest")
aj = ajustes()

st.title("Backtest: ¿acierta el veredicto?")
st.write("Rebobina cada empresa a fechas pasadas (30 de abril de cada año), calcula su nota **solo con la información "
         "que existía entonces** y mira qué rentabilidad tuvo en los 12 meses siguientes. Si el modelo sirve, las "
         "empresas con *Comprar* deberían haberlo hecho mejor que la media y las de *Vender*, peor.")
st.caption("Usa los pesos y umbrales de la barra lateral: cambia los pesos y vuelve a ejecutar para ver si mejora. "
           "El pilar de analistas no entra (no hay histórico gratuito de sus opiniones).")

c1, c2 = st.columns([1, 2])
with c1:
    universo = st.selectbox("Universo", list(universos.UNIVERSOS) + ["Lista personalizada"], key="bt_universo")
with c2:
    personal = ""
    if universo == "Lista personalizada":
        personal = st.text_area("Tickers", value="ITX.MC, SAN.MC, IBE.MC, TEF.MC, REP.MC, BBVA.MC, AENA.MC, FER.MC",
                                key="bt_lista")
tickers = universos.lista(universo, personal)

if st.button(f"🧪 Ejecutar backtest sobre {universo} ({len(tickers)} empresas)", type="primary", disabled=len(tickers) < 8):
    cargadas = cargar_varias(tickers, "Descargando históricos")
    with st.spinner("Rebobinando y puntuando cada empresa en cada fecha…"):
        df = bt.ejecutar(cargadas, aj["pesos"], aj["u_comprar"], aj["u_vender"], aj["margen_seg"], aj["respetar_tendencia"])
    st.session_state["backtest"] = {"universo": universo, "df": df, "n": len(cargadas)}
if len(tickers) < 8:
    st.caption("Hacen falta al menos 8 empresas para que el resultado tenga algo de sentido.")

res = st.session_state.get("backtest")
if not res:
    with st.expander("ℹ️ Limitaciones que debes conocer", expanded=True):
        st.markdown(bt.__doc__.split("Limitaciones honestas")[1].replace("---------------------", ""))
    st.stop()

df = res["df"]
val = bt.validas(df)
if val.empty:
    st.error("No se pudieron reconstruir datos históricos suficientes para este universo.")
    st.stop()

fechas = sorted(val["Fecha"].unique())
st.subheader(f"Resultado · {res['universo']} · {res['n']} empresas · {len(fechas)} años "
             f"({fechas[0]:%m/%Y} – {fechas[-1]:%m/%Y})")

pv = bt.por_veredicto(df)
ic = bt.poder_predictivo(df)
ic_global = ic.loc[ic["Factor"] == "Nota global", "Correlación media"].iloc[0] if not ic.empty and (ic["Factor"] == "Nota global").any() else None

# Titular -----------------------------------------------------------------------
k = st.columns(4)
for col, v in zip(k[:3], ["Comprar", "Esperar", "Vender"]):
    if v in pv.index:
        col.metric(f"{v} ({int(pv.loc[v, 'Empresas'])})", f_pct(pv.loc[v, "Rentabilidad_media"]),
                   f"{pv.loc[v, 'Exceso_medio'] * 100:+.1f} pp vs media".replace(".", ","))
    else:
        col.metric(v, "—")
k[3].metric("Media del universo", f_pct(val["Rentabilidad 12m"].mean()))

dif = None
if "Comprar" in pv.index and "Vender" in pv.index:
    dif = pv.loc["Comprar", "Rentabilidad_media"] - pv.loc["Vender", "Rentabilidad_media"]
if dif is not None and ic_global is not None:
    if dif > 0.03 and ic_global > 0.05:
        st.success(f"**El modelo ha funcionado en este periodo**: *Comprar* batió a *Vender* por {f_pct(dif)[:-1]} puntos al año "
                   f"y la nota se correlaciona positivamente con la rentabilidad posterior ({ic_global:.2f}).")
    elif dif > 0 and ic_global > 0:
        st.info(f"**Señal débil**: *Comprar* superó a *Vender* por {f_pct(dif)[:-1]} puntos al año, pero la relación entre nota "
                f"y rentabilidad es floja ({ic_global:.2f}). No es concluyente.")
    else:
        st.warning(f"**El modelo NO ha funcionado en este periodo**: *Comprar* no batió a *Vender* "
                   f"(diferencia {dif * 100:+.1f} puntos/año; correlación {ic_global:.2f}). Revisa los pesos.")

# Por año ---------------------------------------------------------------------
st.subheader("Rentabilidad a 12 meses por veredicto y año")
pa = bt.por_año(df)
if not pa.empty:
    fig = go.Figure()
    for col in pa.columns:
        fig.add_bar(x=[f"{f:%b %Y}" for f in pa.index], y=pa[col], name=col,
                    marker_color=COLOR.get(col, "#222"), text=[f_pct(v) if pd.notna(v) else "" for v in pa[col]],
                    textposition="outside")
    fig.update_layout(barmode="group", height=380, yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h"), xaxis_title="Fecha de la evaluación (rentabilidad de los 12 meses siguientes)")
    st.plotly_chart(fig, width="stretch")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Por quintiles de nota")
    q = bt.por_quintil(df)
    if not q.empty:
        fig = go.Figure(go.Bar(x=list(q.index.astype(str)), y=q["Exceso_medio"],
                               marker_color=[COLOR["Vender"], "#e58a8a", GRIS, "#7cc9a0", COLOR["Comprar"]][:len(q)],
                               text=[f"{v * 100:+.1f} pp" for v in q["Exceso_medio"]], textposition="outside"))
        fig.update_layout(height=320, yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=10, b=10),
                          yaxis_title="vs media del universo", xaxis_title="Q1 = peores notas · Q5 = mejores")
        st.plotly_chart(fig, width="stretch")
        st.caption("Si el modelo sirve, las barras deberían subir de izquierda a derecha.")
with c2:
    st.subheader("¿Qué pilares predicen?")
    if not ic.empty:
        ic2 = ic.sort_values("Correlación media", ascending=True)
        fig = go.Figure(go.Bar(x=ic2["Correlación media"], y=ic2["Factor"], orientation="h",
                               marker_color=[COLOR["Comprar"] if v > 0.05 else COLOR["Vender"] if v < -0.05 else GRIS
                                             for v in ic2["Correlación media"]],
                               text=[f"{v:+.2f} ({a})" for v, a in zip(ic2["Correlación media"], ic2["Años positivos"])],
                               textposition="outside"))
        fig.update_layout(height=320, margin=dict(l=10, r=40, t=10, b=10), xaxis=dict(range=[-0.5, 0.5]))
        st.plotly_chart(fig, width="stretch")
        st.caption("Correlación entre la nota de cada pilar y la rentabilidad posterior (entre paréntesis, años en que fue positiva). "
                   "En bolsa, por encima de +0,05 ya es útil. Los pilares en rojo restaron: plantéate bajarles el peso.")

st.subheader("Detalle por veredicto")
if not pv.empty:
    t = pv.copy()
    t.columns = ["Empresas", "Rentabilidad media 12m", "Exceso vs media", "% que batió a la media"]
    st.dataframe(t.style.format({"Rentabilidad media 12m": "{:.1%}", "Exceso vs media": "{:+.1%}", "% que batió a la media": "{:.0%}"}),
                 width="stretch")

with st.expander("Ver todas las evaluaciones"):
    cols = ["Fecha", "Ticker", "Empresa", "Veredicto", "Nota", "Rentabilidad 12m", "Exceso vs universo"]
    st.dataframe(val[[c for c in cols if c in val]].sort_values(["Fecha", "Nota"], ascending=[True, False]),
                 hide_index=True, width="stretch",
                 column_config={"Rentabilidad 12m": st.column_config.NumberColumn(format="percent"),
                                "Exceso vs universo": st.column_config.NumberColumn(format="percent"),
                                "Nota": st.column_config.NumberColumn(format="%.0f")})

with st.expander("ℹ️ Limitaciones del backtest"):
    st.markdown(bt.__doc__.split("Limitaciones honestas")[1].replace("---------------------", ""))
