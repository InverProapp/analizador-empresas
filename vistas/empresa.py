"""Sección Empresa: análisis completo de una compañía."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import datos
import ia
import scoring as sc
from comun import *  # noqa: F401,F403
from comun import ajustes, analizar, cargar, competidores, metrica, noticias, selector_empresa

ticker = selector_empresa()

aj = ajustes()
pesos, u_comprar, u_vender = aj["pesos"], aj["u_comprar"], aj["u_vender"]
margen_seg, wacc, g_term = aj["margen_seg"], aj["wacc"], aj["g_term"]

# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
if not ticker:
    st.title("Analizador de empresas")
    st.write("Busca una empresa en la barra lateral para empezar.")
    st.stop()

with st.spinner(f"Descargando {ticker}…"):
    try:
        e, m, r = analizar(ticker, aj)
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
import usuario as us
from comun import abrir_empresa

c_tit, c_acc = st.columns([2.6, 2.4], vertical_alignment="center")
with c_tit:
    st.title(e.nombre)
    sector_es = sc.SECTORES_ES.get(e.sector, e.sector)
    st.caption(f"**{e.ticker}** · {sector_es} · {e.info.get('industry', '')} · {e.info.get('country', '')} · "
               f"{e.info.get('exchange', '')} · moneda {mon}")
with c_acc:
    a1, a2, a3 = st.columns(3)
    fav = us.es_favorito(ticker)
    a1.button("⭐ Favorito" if fav else "☆ Favorito", key="btn_fav", type="primary" if fav else "secondary",
              on_click=us.alternar_favorito, args=(ticker, e.nombre, precio), disabled=not us.cargado(), width="stretch",
              help="Quitar de tu lista" if fav else "Guardar en tu lista (en este navegador)")
    mis_alertas = us.alertas_de(ticker)
    estados = us.comprobar(mis_alertas, lambda tk: (m, r)) if mis_alertas else {}
    n_cumplen = sum(1 for v in estados.values() if v[0])
    with a2.popover(f"🔔 Alertas{f' ({len(mis_alertas)})' if mis_alertas else ''}", width="stretch"):
        st.markdown(f"**Alertas de {e.ticker}**")
        if not us.cargado():
            st.caption("Cargando tus datos…")
        for al in mis_alertas:
            cumple, detalle = estados.get(al["id"], (None, ""))
            icono = "✅" if cumple else "⏳" if cumple is False else "❔"
            f1, f2 = st.columns([6, 1], vertical_alignment="center")
            f1.markdown(f"{icono} {us.describir(al, mon)}  \n<span style='color:#888;font-size:12px'>{detalle} · creada {al['creada']}</span>",
                        unsafe_allow_html=True)
            f2.button("🗑️", key=f"borrar_{al['id']}", on_click=us.borrar_alerta, args=(al["id"],), help="Borrar alerta")
        if mis_alertas:
            st.divider()
        st.markdown("**Nueva alerta**")
        tipo = st.selectbox("Avísame cuando…", list(us.TIPOS), format_func=lambda t: us.TIPOS[t][0], key="alerta_tipo")
        clase_valor = us.TIPOS[tipo][1]
        valor = None
        if clase_valor == "precio":
            base = (precio or 0) * (1.05 if tipo == "precio_mayor" else 0.95)
            valor = st.number_input(f"Precio ({mon})", min_value=0.0, value=float(round(base, 2)), step=0.05, key=f"alerta_valor_{tipo}")
        elif clase_valor in ("pct", "num"):
            valor = st.number_input("Valor", min_value=0.0, value=float(us.DEFECTOS.get(tipo, 5)), step=0.5, key=f"alerta_valor_{tipo}")
        st.button("➕ Crear alerta", type="primary", on_click=us.crear_alerta, args=(ticker, e.nombre, tipo, valor),
                  disabled=not us.cargado(), width="stretch")
        st.caption("Las alertas se comprueban cada vez que abres la web (precios con ~15 min de retraso). "
                   "Se guardan en este navegador. Todas, en ⭐ Mi lista y alertas.")
    if a3.button("🎯 Simular", width="stretch", help="Abrir esta empresa en el simulador"):
        abrir_empresa(ticker, "vistas/simulador.py")
    if n_cumplen:
        st.success(f"🔔 {n_cumplen} de tus alertas de esta empresa se cumple{'n' if n_cumplen > 1 else ''} ahora.", icon="🔔")

k1, k2, k3, k4, k5 = st.columns(5)
metrica(k1, "Precio", f"{f_num(precio)} {mon}", f_pct(var_dia, 2) if var_dia is not None else None, "precio")
metrica(k2, "Capitalización", f_dinero(m.get("market_cap"), mon), clave="capitalizacion")
metrica(k3, "PER", f_x(m.get("per")), clave="per")
metrica(k4, "Rent. dividendo", f_pct(m.get("rent_dividendo"), 2), clave="rent_dividendo")
metrica(k5, "Beta", f_num(m.get("beta")), clave="beta")

# Franja de mercado: rentabilidades, rango de 52 semanas, eventos y gráfico rápido
cierres = e.hist["Close"].dropna() if e.hist is not None and not e.hist.empty else pd.Series(dtype=float)
if len(cierres) > 5:
    def rent_desde(dias=None, desde_fecha=None):
        if desde_fecha is not None:
            base = cierres[cierres.index < desde_fecha]
            return cierres.iloc[-1] / base.iloc[-1] - 1 if len(base) else None
        return cierres.iloc[-1] / cierres.iloc[-1 - dias] - 1 if len(cierres) > dias else None
    rents = [("1 semana", rent_desde(5)), ("1 mes", rent_desde(21)), ("3 meses", rent_desde(63)),
             ("En el año", rent_desde(desde_fecha=pd.Timestamp(f"{cierres.index[-1].year}-01-01"))),
             ("1 año", rent_desde(252)), ("3 años", rent_desde(756)), ("5 años", rent_desde(1260))]
    chips = "".join(
        f"<span style='display:inline-block;margin:2px 6px 2px 0;padding:3px 10px;border-radius:12px;font-size:13px;"
        f"background:{'#e6f4ec' if v >= 0 else '#fbe9e9'};color:{'#14653d' if v >= 0 else '#a12b2b'}'>{t} <b>{f_pct(v)}</b></span>"
        for t, v in rents if v is not None)
    ult = cierres.iloc[-252:]
    mn, mx = float(ult.min()), float(ult.max())
    pos = (precio - mn) / (mx - mn) if precio and mx > mn else None
    eventos = []
    for campo, nombre in (("earningsTimestamp", "📅 Resultados"), ("earningsTimestampStart", "📅 Resultados"),
                          ("exDividendDate", "💸 Fecha ex-dividendo"), ("dividendDate", "💸 Pago de dividendo")):
        ts = e.info.get(campo)
        if ts and not any(nombre == ev[0] for ev in eventos):
            try:
                f = pd.Timestamp(int(ts), unit="s")
                cuando = "próximo" if f >= pd.Timestamp.now() - pd.Timedelta(days=1) else "último"
                eventos.append((nombre, f"{f:%d/%m/%Y}", cuando))
            except Exception:
                pass
    c1, c2 = st.columns([1.6, 1])
    with c1:
        st.markdown(chips, unsafe_allow_html=True)
        if pos is not None:
            st.markdown(
                f"<div style='font-size:12px;color:#666;margin-top:8px'>Rango de 52 semanas</div>"
                f"<div style='display:flex;align-items:center;gap:8px;font-size:13px'><span>{f_num(mn)}</span>"
                f"<div style='flex:1;height:8px;border-radius:4px;background:linear-gradient(90deg,#f4c7c7,#f7e3a8,#bfe6cf);position:relative'>"
                f"<div style='position:absolute;left:calc({pos * 100:.1f}% - 7px);top:-4px;width:14px;height:14px;border-radius:50%;"
                f"background:#222;border:2px solid #fff;box-shadow:0 0 2px #0006'></div></div><span>{f_num(mx)}</span></div>"
                f"<div style='font-size:12px;color:#666;margin-top:4px'>Hoy está al {pos * 100:.0f}% del rango "
                f"({f_pct(precio / mx - 1)} desde el máximo, {f_pct(precio / mn - 1)} sobre el mínimo)</div>",
                unsafe_allow_html=True)
        if eventos:
            st.markdown(" · ".join(f"{n} ({c}): **{fe}**" for n, fe, c in eventos))
        enlaces = [f"[Yahoo Finance](https://finance.yahoo.com/quote/{ticker})"]
        if e.info.get("website"):
            enlaces.append(f"[Web de la empresa]({e.info['website']})")
        st.caption(" · ".join(enlaces))
    with c2:
        periodo_g = st.segmented_control("Periodo", ["1M", "6M", "1A", "5A"], default="1A", key="mini_periodo",
                                         label_visibility="collapsed") or "1A"
        n_dias = {"1M": 21, "6M": 126, "1A": 252, "5A": 1260}[periodo_g]
        tramo = cierres.iloc[-n_dias:]
        sube = tramo.iloc[-1] >= tramo.iloc[0]
        col_l = COLOR["Comprar"] if sube else COLOR["Vender"]
        fig = go.Figure(go.Scatter(x=tramo.index, y=tramo, mode="lines", line=dict(color=col_l, width=2), fill="tozeroy",
                                   fillcolor="rgba(26,158,92,0.08)" if sube else "rgba(214,69,69,0.08)", hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>"))
        lo, hi = float(tramo.min()), float(tramo.max())
        fig.update_layout(height=170, margin=dict(l=0, r=0, t=0, b=0), yaxis=dict(range=[lo - (hi - lo) * 0.08, hi + (hi - lo) * 0.08], side="right"),
                          xaxis=dict(showgrid=False), showlegend=False)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

e1, e2 = st.columns(2)
with e1.expander("🏢 Sobre la empresa"):
    if e.info.get("longBusinessSummary"):
        st.write(e.info["longBusinessSummary"])
    datos_emp = [(k, e.info.get(c)) for k, c in (("Empleados", "fullTimeEmployees"), ("Sede", "city"), ("País", "country"))]
    st.caption(" · ".join(f"{k}: {f'{v:,}'.replace(',', '.') if isinstance(v, int) else v}" for k, v in datos_emp if v))
with e2.expander("📝 Mis notas sobre esta empresa" + (" ✏️" if us.nota(ticker) else "")):
    texto_nota = st.text_area("Tu tesis de inversión, ideas, a qué precio entrarías…", value=us.nota(ticker), key=f"nota_{ticker}",
                              height=120, label_visibility="collapsed", placeholder="Tu tesis de inversión, ideas, a qué precio entrarías…")
    st.button("💾 Guardar nota", on_click=lambda: us.guardar_nota(ticker, st.session_state[f"nota_{ticker}"]), disabled=not us.cargado())
    st.caption("Se guarda en este navegador.")

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
    import glosario
    with st.popover("¿Qué significa el veredicto?", type="tertiary", icon=":material/info:"):
        st.markdown(glosario.texto("veredicto"))
        st.markdown(glosario.texto("nota"))
    if r.veredicto != r.veredicto_bruto:
        st.caption(f"Por nota saldría **{r.veredicto_bruto}**, pero las alertas lo limitan a **{r.veredicto}**.")
    v1, v2 = st.columns(2)
    metrica(v1, "Valor justo estimado", f"{f_num(r.valor_justo)} {mon}" if r.valor_justo else "—", clave="valor_justo", delta=
              f_pct(r.valor_justo / precio - 1) if r.valor_justo and precio else None)
    metrica(v2, f"Zona de compra (−{margen_seg * 100:.0f}%)", f"{f_num(r.precio_compra)} {mon}" if r.precio_compra else "—", clave="zona_compra")

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
# Análisis con IA desactivado de momento: pon MOSTRAR_IA = True para recuperarlo (requiere API key de Anthropic)
MOSTRAR_IA = False
nombres_tabs = ["🧭 Resumen", "💶 Valoración", "🕰️ Histórico", "🆚 Competidores"] + (
    ["🤖 Análisis IA"] if MOSTRAR_IA else []) + ["📈 Finanzas", "📉 Técnico", "💸 Dividendos", "📘 Metodología"]
tabs = dict(zip(nombres_tabs, st.tabs(nombres_tabs)))
T_RES, T_VAL, T_HIS, T_COMP = (tabs[n] for n in nombres_tabs[:4])
T_FIN, T_TEC, T_DIV, T_MET = (tabs[n] for n in nombres_tabs[-4:])
T_IA = tabs.get("🤖 Análisis IA")

# Resumen ---------------------------------------------------------------------
with T_RES:
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
with T_VAL:
    c1, c2, c3, c4 = st.columns(4)
    metrica(c1, "PER", f_x(m.get("per")), clave="per")
    metrica(c2, "PER futuro", f_x(m.get("per_fwd")), clave="per_fwd")
    metrica(c3, "EV/EBITDA", f_x(m.get("ev_ebitda")), clave="ev_ebitda")
    metrica(c4, "Precio / valor contable", f_x(m.get("p_vc")), clave="p_vc")
    metrica(c1, "PEG", f_x(m.get("peg"), 2), clave="peg")
    metrica(c2, "Precio / ventas", f_x(m.get("p_ventas")), clave="p_ventas")
    metrica(c3, "Rentabilidad FCF", f_pct(m.get("fcf_yield")), clave="fcf_yield")
    metrica(c4, "Valor empresa (EV)", f_dinero(m.get("ev"), mon), clave="ev")

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
        metrica(d4, "Valor por acción (DCF)", f"{f_num(m.get('valor_dcf'))} {mon}", f_pct(m.get("margen_seguridad_dcf")), clave="dcf")
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
with T_FIN:
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
with T_TEC:
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
            metrica(col, nombre, f_pct(val), clave="volatilidad" if nombre.startswith("Volatilidad") else None)
        c = st.columns(6)
        metrica(c[0], "RSI (14)", f_num(m.get("rsi"), 0), clave="rsi")
        metrica(c[1], "vs media 200", f_pct(m.get("sobre_sma200")), clave="medias")
        c[2].metric("Máx. 52 sem.", f_num(m.get("max_52s")))
        c[3].metric("Mín. 52 sem.", f_num(m.get("min_52s")))
        metrica(c[4], "Caída desde máximos", f_pct(m.get("drawdown_actual")), clave="drawdown")
        metrica(c[5], "Peor caída (5a)", f_pct(m.get("max_drawdown")), clave="drawdown")

# Dividendos ------------------------------------------------------------------
with T_DIV:
    c = st.columns(4)
    metrica(c[0], "Rentabilidad (12 m)", f_pct(m.get("rent_dividendo"), 2), clave="rent_dividendo")
    metrica(c[1], "Payout", f_pct(m.get("payout"), 0), clave="payout")
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


# Histórico de múltiplos ------------------------------------------------------
with T_HIS:
    from comun import historico
    hm = historico(ticker)
    if hm.empty:
        st.info("No hay suficientes datos (cuentas anuales en la misma moneda que la cotización) para reconstruir el histórico.")
    else:
        st.caption(f"Múltiplos calculados cada semana con el precio de ese día y las últimas cuentas anuales publicadas "
                   f"(se asume que se publican 90 días después del cierre). Periodo: {hm.index[0]:%m/%Y} – {hm.index[-1]:%m/%Y}. "
                   "Yahoo solo ofrece ~4 ejercicios, por eso el histórico es corto.")
        # True = un valor más bajo es más barato
        sentido = {"PER": True, "Precio/Valor contable": True, "Precio/Ventas": True, "EV/EBITDA": True, "Rentabilidad FCF": False}
        filas = []
        for col, bajo_barato in sentido.items():
            s = hm[col].dropna()
            if len(s) < 10:
                continue
            actual = s.iloc[-1]
            barato_que = (s > actual).mean() if bajo_barato else (s < actual).mean()
            filas.append({"Múltiplo": col, "Actual": actual, "Mediana": s.median(), "Mínimo": s.min(), "Máximo": s.max(),
                          "Más barata que el % del periodo": barato_que})
        if filas:
            tabla = pd.DataFrame(filas)
            st.dataframe(tabla, hide_index=True, width="stretch", column_config={
                "Actual": st.column_config.NumberColumn(format="%.2f"), "Mediana": st.column_config.NumberColumn(format="%.2f"),
                "Mínimo": st.column_config.NumberColumn(format="%.2f"), "Máximo": st.column_config.NumberColumn(format="%.2f"),
                "Más barata que el % del periodo": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")})
            media_bar = tabla["Más barata que el % del periodo"].mean()
            if media_bar >= 0.7:
                st.success(f"Respecto a su propia historia reciente cotiza **barata**: de media, más barata que el {media_bar * 100:.0f}% del periodo.")
            elif media_bar <= 0.3:
                st.warning(f"Respecto a su propia historia reciente cotiza **cara**: solo más barata que el {media_bar * 100:.0f}% del periodo.")
            else:
                st.info(f"Respecto a su propia historia reciente cotiza en **zona media** (más barata que el {media_bar * 100:.0f}% del periodo).")
        elegido = st.radio("Ver", [c for c in sentido if hm[c].notna().sum() >= 10], horizontal=True)
        s = hm[elegido].dropna()
        fig = go.Figure()
        fig.add_scatter(x=s.index, y=s, mode="lines", name=elegido, line=dict(color=AZUL, width=2))
        fig.add_hline(y=s.median(), line=dict(color=GRIS, dash="dash"), annotation_text="mediana")
        fig.add_scatter(x=[s.index[-1]], y=[s.iloc[-1]], mode="markers", marker=dict(size=10, color="#222"), name="hoy")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                          yaxis_tickformat=".1%" if elegido == "Rentabilidad FCF" else None)
        st.plotly_chart(fig, width="stretch")

# Competidores ----------------------------------------------------------------
with T_COMP:
    from comun import cargar_varias, config_columnas, fila_resumen
    sugeridos = competidores(ticker)
    st.write("Compara la empresa con su competencia usando exactamente los mismos criterios.")
    if sugeridos:
        st.caption("Sugeridos: las mayores empresas de su industria según Yahoo (suele tirar hacia EE. UU.). "
                   "Añade o quita los que quieras, por ejemplo competidores europeos.")
    else:
        st.caption("Yahoo no sugiere competidores para esta empresa: escríbelos tú.")
    lista_peers = st.text_input("Competidores (tickers separados por comas)", value=", ".join(sugeridos), key=f"peers_{ticker}")
    peers = [x.strip().upper() for x in lista_peers.split(",") if x.strip() and x.strip().upper() != ticker][:12]
    clave = f"comp_{ticker}_{','.join(peers)}"
    if st.button("Comparar con la competencia", type="primary", disabled=not peers):
        cargadas = cargar_varias(peers, "Descargando competidores")
        filas = [fila_resumen(ticker, e, m, r)]
        for tk2, e2 in cargadas.items():
            try:
                _, m2, r2 = analizar(tk2, aj, e2)
                filas.append(fila_resumen(tk2, e2, m2, r2))
            except Exception:
                pass
        st.session_state[clave] = pd.DataFrame(filas)
        faltan = [p for p in peers if p not in cargadas]
        if faltan:
            st.warning("Sin datos para: " + ", ".join(faltan))
    comp = st.session_state.get(clave)
    if comp is not None and len(comp) > 1:
        comp = comp.sort_values("Nota", ascending=False, na_position="last")
        st.dataframe(comp, hide_index=True, width="stretch", column_config=config_columnas())
        # Posición de la empresa dentro del grupo
        yo = comp[comp["Ticker"] == ticker].iloc[0]
        otros = comp[comp["Ticker"] != ticker]
        criterios = [("Nota", True, "Nota global"), ("PER", False, "PER (más barato)"), ("EV/EBITDA", False, "EV/EBITDA (más barato)"),
                     ("ROE", True, "ROE"), ("Margen op.", True, "Margen operativo"),
                     ("Crec. ingresos", True, "Crecimiento"), ("Deuda neta/EBITDA", False, "Endeudamiento (menos deuda)")]
        frases = []
        for col, alto_mejor, nombre in criterios:
            if pd.isna(yo.get(col)) or otros[col].dropna().empty:
                continue
            o = otros[col].dropna()
            mejor_que = (o < yo[col]).sum() if alto_mejor else (o > yo[col]).sum()
            frases.append(f"- **{nombre}**: mejor que {mejor_que} de {len(o)}")
        if frases:
            st.markdown(f"**{e.nombre} frente a su competencia:**\n" + "\n".join(frases))
        fig = go.Figure(go.Bar(x=comp["Ticker"], y=comp["Nota"],
                               marker_color=["#222" if t == ticker else COLOR.get(v, GRIS) for t, v in zip(comp["Ticker"], comp["Veredicto"])],
                               text=comp["Veredicto"], textposition="outside"))
        fig.update_layout(height=320, yaxis=dict(range=[0, 105]), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

# Análisis con IA -------------------------------------------------------------
if MOSTRAR_IA:
    with T_IA:
        from comun import secreto
        st.write("Claude lee la descripción del negocio, las métricas, el veredicto del modelo y las noticias recientes, "
                 "y te da la parte que los números no ven: ventajas competitivas, riesgos, catalizadores y qué ha cambiado.")
        clave_propietario, codigo = secreto("ANTHROPIC_API_KEY"), secreto("CLAVE_ACCESO")
        api_key = None
        c1, c2 = st.columns(2)
        with c1:
            if clave_propietario and codigo:
                acceso = st.text_input("Código de acceso", type="password", key="ia_codigo",
                                       help="Pídeselo al dueño de la web. Sin código, puedes usar tu propia API key.")
                if acceso and acceso == codigo:
                    api_key = clave_propietario
                    st.caption("✅ Código correcto")
                elif acceso:
                    st.caption("❌ Código incorrecto")
            if not api_key:
                propia = st.text_input("Tu API key de Anthropic", type="password", key="ia_key",
                                       help="Se crea en console.anthropic.com. No se guarda en ningún sitio.")
                api_key = propia or None
        with c2:
            modelo_txt = st.selectbox("Modelo", list(ia.MODELOS), key="ia_modelo")
            buscar_web = st.checkbox("Buscar también en la web (más completo, algo más caro)", value=True, key="ia_web")
            pdf = st.file_uploader("Opcional: informe anual o presentación de resultados (PDF)", type=["pdf"], key=f"ia_pdf_{ticker}")

        news = noticias(ticker)
        with st.expander(f"Noticias recientes que leerá ({len(news)})"):
            if not news:
                st.caption("Yahoo no tiene noticias recientes para este valor.")
            for n in news:
                st.markdown(f"- **{n['titulo']}** · {n['fuente']} · {n['fecha']}" + (f" · [abrir]({n['url']})" if n["url"] else ""))

        resumen = "\n".join(f"- {i.nombre}: {f_item(i)}" for p in sc.PILARES for i in r.pilares[p].items if i.valor is not None)
        resumen += f"\n- Precio: {f_num(precio)} {mon} · Capitalización: {f_dinero(m.get('market_cap'), mon)}"
        if r.valor_justo:
            resumen += f"\n- Valor justo estimado por el modelo: {f_num(r.valor_justo)} {mon}"
        if r.alertas:
            resumen += "\n- Alertas del modelo: " + " | ".join(r.alertas)

        @st.cache_data(ttl=12 * 3600, show_spinner=False)
        def generar(ticker_, modelo_, web_, prompt_, _api_key):
            return ia.analizar(_api_key, modelo_, prompt_, web_)

        if st.button("🤖 Generar análisis", type="primary", disabled=not api_key):
            texto_doc = ia.texto_pdf(pdf) if pdf else ""
            if pdf and not texto_doc:
                st.warning("No se pudo leer texto del PDF (¿es un escaneo?). Sigo sin él.")
            prompt = ia.construir_prompt(e.nombre, ticker, e.info, resumen, r.veredicto, r.nota, news, texto_doc, buscar_web)
            with st.spinner("Claude está analizando la empresa… (30-90 s)"):
                try:
                    st.session_state[f"ia_{ticker}"] = generar(ticker, ia.MODELOS[modelo_txt], buscar_web, prompt, api_key)
                except Exception as ex:
                    tipo = type(ex).__name__
                    if "Authentication" in tipo:
                        st.error("La API key no es válida.")
                    elif "RateLimit" in tipo:
                        st.error("Límite de uso de la API alcanzado. Prueba en un minuto.")
                    else:
                        st.error(f"No se pudo generar el análisis ({tipo}): {ex}")
        if not api_key:
            st.caption("Introduce el código de acceso o tu API key para activar el botón.")
        if st.session_state.get(f"ia_{ticker}"):
            st.markdown(st.session_state[f"ia_{ticker}"])
            st.caption("Generado por IA a partir de datos públicos. Puede contener errores: contrasta lo importante. No es asesoramiento financiero.")

# Metodología -----------------------------------------------------------------
with T_MET:
    st.markdown(f"""
### 📖 Glosario
Pincha en cualquier dato con el icono ⓘ para ver su definición. Aquí las tienes todas:

""" + "\n".join(f"- **{t}**: {que}" + (f" {como}" if como else "") for t, que, como in __import__("glosario").G.values()) + f"""

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

### Más allá de los números de hoy
- **Histórico**: compara los múltiplos actuales con los de la propia empresa en los últimos años.
- **Competidores**: misma nota y mismas métricas para su competencia directa.
- **Simulador** (menú lateral): qué habría pasado operando la acción a tus precios de compra y venta, o con las señales del modelo.
- **Escáner** (menú lateral): recorre un índice entero y ordena las oportunidades.
- **Backtest** (menú lateral): comprueba si el veredicto habría acertado en años anteriores. Úsalo para ajustar los pesos.

### Limitaciones
- Datos de Yahoo Finance: gratuitos pero no auditados; pueden faltar o venir con errores, sobre todo en bolsas pequeñas.
- El modelo es mecánico: no sabe nada de noticias, gestión, ventajas competitivas ni del ciclo del sector.
- Es una herramienta de apoyo para tu propio análisis, **no una recomendación de inversión**.
""")
