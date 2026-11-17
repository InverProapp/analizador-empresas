"""Sección Escáner: recorre un índice entero y ordena las empresas por nota."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import graficos

import ideas
from comun import (COLOR, COLUMNAS_ESCANER, GRIS, abrir_empresa, ajustes, analizar, cargar_varias, config_columnas, fila_resumen, selector_universo,
                   tiempo_estimado)

aj = ajustes()

st.title("📡 Escáner e ideas")
st.caption("Analiza un índice o un mercado entero con los mismos criterios, ordena las empresas por nota y propone "
           "búsquedas de ideas ya preparadas.")

res = st.session_state.get("escaner")
hay_res = bool(res) and not res["df"].empty
with st.expander("1️⃣ Elige qué empresas analizar" + (f" · ahora: {res['universo']}" if hay_res else ""), expanded=not hay_res):
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
        st.rerun()


res = st.session_state.get("escaner")
if not res or res["df"].empty:
    st.stop()

df = res["df"].sort_values("Nota", ascending=False, na_position="last")
st.subheader(f"2️⃣ Resultados: {res['universo']} · {res['hora']}")
if res["faltan"]:
    st.caption("Sin datos de Yahoo para: " + ", ".join(res["faltan"]))

k = st.columns(4)
k[0].metric("Analizadas", len(df))
for col, v in zip(k[1:], ["Comprar", "Esperar", "Vender"]):
    col.metric(v, int((df["Veredicto"] == v).sum()))

t_todas, t_ideas, t_mapa = st.tabs([f"📋 Todas las empresas ({len(df)})", "💡 Búsquedas de ideas", "🗺️ Mapa nota/potencial"])
with t_todas:
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
    st.dataframe(vista, hide_index=True, width="stretch", column_config=config_columnas(), height=min(36 * (len(vista) + 1), 640),
                 column_order=[c for c in COLUMNAS_ESCANER if c in vista])
    st.caption("**vs zona compra**: cuánto está el precio por encima (+) o por debajo (−) del precio de compra con margen de seguridad. "
               "**Potencial**: distancia al valor justo estimado.")


with t_ideas:
    # Búsquedas de ideas --------------------------------------------------------------
    st.caption("Filtros preparados como los que usan los analistas para encontrar candidatas. Proponen empresas que mirar, "
               "no conclusiones: abre cada una y comprueba si la historia tiene sentido.")
    busqueda = st.segmented_control("Búsqueda", list(ideas.BUSQUEDAS), key="esc_busqueda", label_visibility="collapsed")
    if not busqueda:
        st.info("👆 Elige una búsqueda para ver qué empresas de este universo la cumplen.")
    if busqueda:
        b = ideas.BUSQUEDAS[busqueda]
        if "Desde máx. 52s" not in df:
            st.warning("Este escaneo es de una versión anterior: vuelve a pulsar **Escanear** para usar todas las búsquedas.")
        st.info(f"**{busqueda}** · {b['idea']}\n\nCriterios (debe cumplir al menos {b['min']} de {len(b['criterios'])}): "
                + " · ".join(et for et, _ in b["criterios"]))
        res_ideas = ideas.aplicar(df, busqueda)
        if res_ideas.empty:
            st.caption("Ninguna empresa de este universo cumple los criterios. Prueba con otro mercado o un universo más grande.")
        else:
            cols = ["Ticker", "Empresa", "Sector", "Veredicto", "Nota", "Cumple", "Por qué", "Potencial", "PER", "ROE",
                    "Crec. ingresos", "Deuda neta/EBITDA", "Div.", "FCF yield", "Desde máx. 52s"]
            st.dataframe(res_ideas, hide_index=True, width="stretch", column_config=config_columnas(),
                         column_order=[c for c in cols if c in res_ideas], height=min(36 * (len(res_ideas) + 1), 460))
            st.markdown(f"**Las {min(5, len(res_ideas))} primeras, en una ficha**")
            for _, f in res_ideas.head(5).iterrows():
                debiles = sorted(((f.get(p), p) for p in ("Valoración", "Calidad", "Salud financiera", "Crecimiento", "Técnico")
                                  if pd.notna(f.get(p))), key=lambda x: x[0])
                with st.expander(f"{f['Ticker']} · {f['Empresa']} — {b['lado']} — cumple {f['Cumple']} · nota {f['Nota']:.0f}"):
                    st.markdown(f"- **Por qué aparece:** {f['Por qué']}.")
                    if pd.notna(f.get("Potencial")):
                        st.markdown(f"- **Hasta su valor justo:** {f['Potencial'] * 100:+.0f}%".replace(".", ","))
                    if debiles:
                        st.markdown(f"- **Qué podría salir mal:** su punto más flojo es **{debiles[0][1].lower()}** "
                                    f"({debiles[0][0]:.0f}/100). Comprueba si es pasajero.")
                    st.markdown("- **Siguiente paso:** abre el análisis, busca el catalizador y, si te convence, escribe tu tesis.")
                    if st.button("🔎 Analizar y escribir tesis", key=f"idea_{busqueda}_{f['Ticker']}"):
                        abrir_empresa(f["Ticker"])


with t_mapa:
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
        st.caption("Arriba a la derecha: buena nota y con recorrido. Abajo a la izquierda: mala nota y cara.")
        graficos.mostrar(fig, fechas=False)

    if d.empty:
        st.caption("Sin datos suficientes para el mapa.")

st.markdown("#### 🔎 Ver una empresa en detalle")
c1, c2, c3 = st.columns([3, 1, 1])
elegida = c1.selectbox("Empresa", [f"{t} · {n}" for t, n in zip(df["Ticker"], df["Empresa"])], label_visibility="collapsed")
if c2.button("Abrir análisis →"):
    abrir_empresa(elegida.split(" · ")[0])
if c3.button("Simular →"):
    abrir_empresa(elegida.split(" · ")[0], "vistas/simulador.py")
