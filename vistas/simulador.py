"""Sección Simulador: qué habría pasado operando una acción a unos precios concretos."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import backtest as bt
import datos
import scoring as sc
import simulador as simu
from comun import AZUL, COLOR, GRIS, ajustes, cargar, f_num, f_pct, selector_empresa

ticker = selector_empresa("🎯 Simulador")
aj = ajustes()

st.title("Simulador de operaciones")
if not ticker:
    st.write("Busca una empresa en la barra lateral para empezar.")
    st.stop()

with st.spinner(f"Descargando {ticker}…"):
    try:
        e = cargar(ticker)
    except Exception as ex:
        st.error(f"No se pudo descargar {ticker}: {ex}")
        st.stop()
if e.hist is None or e.hist.empty:
    st.error(f"Yahoo Finance no devuelve precios para **{ticker}**.")
    st.stop()

mon = e.moneda
ult = e.hist["Close"].dropna()
st.subheader(f"{e.nombre} · {ticker}")
st.caption(f"Último precio: {f_num(ult.iloc[-1])} {mon} · {sc.SECTORES_ES.get(e.sector, e.sector)}")


st.write("¿Qué habría pasado si hubieras operado esta acción comprando y vendiendo a unos precios concretos? "
         "Se compara con **comprar el primer día y no vender nunca**.")
hist_sim = e.hist.dropna(subset=["Close"]) if e.hist is not None else pd.DataFrame()
if hist_sim.empty or len(hist_sim) < 60:
    st.info("No hay suficiente histórico de precios.")
else:
    c1, c2, c3 = st.columns([1.3, 1, 1])
    modo_sim = c1.radio("Estrategia", ["Mis precios", "Señales del modelo"], horizontal=True, key="sim_modo",
                        help="Señales del modelo: compra cuando el precio entra en la zona de compra que calculaba "
                             "el modelo en cada momento y vende al llegar a su valor justo.")
    años_disp = max(1, int((hist_sim.index[-1] - hist_sim.index[0]).days / 365))
    opciones_p = [a for a in (1, 2, 3, 5) if a <= años_disp] + ["Todo"]
    periodo = c2.selectbox("Periodo", opciones_p, index=min(2, len(opciones_p) - 1),
                           format_func=lambda x: "Todo el histórico" if x == "Todo" else f"Últimos {x} años" if x > 1 else "Último año",
                           key="sim_periodo")
    capital_ini = c3.number_input(f"Capital inicial ({mon})", 1000, 10_000_000, 10_000, 1000, key="sim_capital")
    h = hist_sim if periodo == "Todo" else hist_sim[hist_sim.index >= hist_sim.index[-1] - pd.DateOffset(years=periodo)]
    cierre = h["Close"]

    niveles = pd.DataFrame()
    if modo_sim == "Mis precios":
        st.caption("Valores iniciales sugeridos: zona baja y alta del periodo. Cámbialos por los tuyos.")
        d1, d2, d3, d4 = st.columns(4)
        sufijo = f"{ticker}_{periodo}"
        p_compra = d1.number_input(f"Comprar si baja a ({mon})", min_value=0.0,
                                   value=float(round(cierre.quantile(0.25), 2)), step=0.5, key=f"sim_compra_{sufijo}")
        p_venta = d2.number_input(f"Vender si sube a ({mon})", min_value=0.0,
                                  value=float(round(cierre.quantile(0.75), 2)), step=0.5, key=f"sim_venta_{sufijo}")
        stop = d3.number_input("Stop-loss (% de caída, 0 = sin stop)", 0, 90, 0, 5, key="sim_stop") / 100
        repetir = d4.checkbox("Repetir cada vez que se dé", value=True, key="sim_repetir",
                              help="Si lo desmarcas, solo hace una compra y una venta.")
        nivel_c, nivel_v = p_compra, p_venta
        if p_venta <= p_compra:
            st.warning("El precio de venta debería ser mayor que el de compra.")
    else:
        stop = 0.0
        repetir = True

        def evaluar_en(fecha):
            pasada = bt.recortar(e, fecha)
            if pasada is None:
                return None
            pes = dict(aj["pesos"]); pes["Analistas"] = 0
            return sc.evaluar(datos.metricas(pasada, aj["g"], aj["wacc"], aj["g_term"]), pasada.sector, pes,
                              aj["u_comprar"], aj["u_vender"], aj["margen_seg"], aj["respetar_tendencia"])
        with st.spinner("Reconstruyendo lo que decía el modelo en cada momento…"):
            niveles = simu.niveles_modelo(e, evaluar_en)
        if niveles.empty or niveles["zona_compra"].isna().all():
            st.warning("El modelo no pudo calcular un valor justo histórico para esta empresa (faltan datos o el "
                       "flujo de caja era negativo). Usa el modo 'Mis precios'.")
            nivel_c = nivel_v = None
        else:
            nivel_c, nivel_v = niveles["zona_compra"], niveles["valor_justo"]
        st.caption("La zona de compra y el valor justo se recalculan cada vez que la empresa publicaba cuentas anuales, "
                   "solo con la información disponible entonces (sin analistas).")

    if nivel_c is not None:
        comision = st.slider("Comisión por operación", 0.0, 1.0, 0.1, 0.05, format="%.2f%%", key="sim_comision") / 100
        res_sim = simu.simular(h, nivel_c, nivel_v, stop, repetir, capital_ini, comision)
        rs = res_sim.resumen(capital_ini)

        # Titular
        eur = lambda x: f"{x:,.0f} {mon}".replace(",", ".")  # noqa: E731
        dif = rs["final"] - rs["bh_final"]
        frase = (f"Con tu estrategia, {eur(capital_ini)} se habrían convertido en **{eur(rs['final'])}** "
                 f"({f_pct(rs['rent_total'])}), frente a **{eur(rs['bh_final'])}** ({f_pct(rs['bh_total'])}) "
                 f"comprando y manteniendo.")
        if rs["n_ops"] == 0:
            st.info("En este periodo el precio nunca bajó hasta " + ("tu precio de compra" if modo_sim == "Mis precios"
                    else "la zona de compra del modelo") + ": no se habría hecho ninguna operación.")
        elif dif > 0:
            st.success(frase + f" **Ganas {eur(dif)} más.**")
        else:
            st.warning(frase + f" **Habrías ganado {eur(-dif)} más sin hacer nada.**")

        k = st.columns(5)
        k[0].metric("Rentabilidad anual", f_pct(rs["rent_anual"]), f"{(rs['rent_anual'] - rs['bh_anual']) * 100:+.1f} pp vs mantener".replace(".", ","))
        k[1].metric("Operaciones", rs["n_ops"])
        k[2].metric("Ganadoras", f_pct(rs["ganadoras"], 0) if rs["ganadoras"] is not None else "—")
        k[3].metric("Peor caída", f_pct(rs["max_dd"]), f"mantener: {f_pct(rs['bh_max_dd'])}", delta_color="off")
        k[4].metric("Tiempo invertido", f_pct(rs["tiempo_invertido"], 0))

        # Gráfico de precio con operaciones
        fig = go.Figure()
        fig.add_scatter(x=cierre.index, y=cierre, mode="lines", name="Precio", line=dict(color="#555", width=1.4))
        if modo_sim == "Mis precios":
            fig.add_hline(y=nivel_c, line=dict(color=COLOR["Comprar"], dash="dash"), annotation_text="compra")
            fig.add_hline(y=nivel_v, line=dict(color=COLOR["Vender"], dash="dash"), annotation_text="venta")
            if stop > 0:
                st.caption(f"Stop-loss: se vende si cae un {stop * 100:.0f}% desde el precio de compra.")
        else:
            nv = niveles.reindex(cierre.index, method="ffill")
            fig.add_scatter(x=nv.index, y=nv["zona_compra"], mode="lines", name="Zona de compra (modelo)",
                            line=dict(color=COLOR["Comprar"], dash="dash", shape="hv"))
            fig.add_scatter(x=nv.index, y=nv["valor_justo"], mode="lines", name="Valor justo (modelo)",
                            line=dict(color=COLOR["Vender"], dash="dash", shape="hv"))
        if res_sim.compras:
            fig.add_scatter(x=[c[0] for c in res_sim.compras], y=[c[1] for c in res_sim.compras], mode="markers", name="Compra",
                            marker=dict(symbol="triangle-up", size=13, color=COLOR["Comprar"], line=dict(color="white", width=1)))
        if res_sim.ventas:
            fig.add_scatter(x=[v[0] for v in res_sim.ventas], y=[v[1] for v in res_sim.ventas], mode="markers", name="Venta",
                            text=[v[2] for v in res_sim.ventas],
                            marker=dict(symbol="triangle-down", size=13, color=COLOR["Vender"], line=dict(color="white", width=1)))
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.08),
                          yaxis_title=mon)
        st.plotly_chart(fig, width="stretch")

        # Curva de capital
        fig2 = go.Figure()
        fig2.add_scatter(x=res_sim.capital.index, y=res_sim.capital, name="Tu estrategia", line=dict(color=AZUL, width=2))
        fig2.add_scatter(x=res_sim.capital_bh.index, y=res_sim.capital_bh, name="Comprar y mantener", line=dict(color=GRIS, width=2))
        fig2.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.15),
                           title="Evolución de tu dinero (con dividendos)", yaxis_title=mon)
        st.plotly_chart(fig2, width="stretch")

        if not res_sim.operaciones.empty:
            st.subheader("Operaciones")
            st.dataframe(res_sim.operaciones.drop(columns=["Importe"]), hide_index=True, width="stretch", column_config={
                "Precio compra": st.column_config.NumberColumn(format="%.2f"), "Precio venta": st.column_config.NumberColumn(format="%.2f"),
                "Resultado %": st.column_config.NumberColumn(format="percent"),
                "Resultado €": st.column_config.NumberColumn(format="%.0f €")})
            if res_sim.abierta:
                st.caption("La última operación sigue abierta: se valora al precio de hoy.")
        st.caption("Ojo con el sesgo de mirar atrás: es fácil elegir buenos precios viendo el gráfico. "
                   "Simulación con precios diarios de Yahoo (máximo, mínimo, apertura y cierre); no incluye impuestos.")

