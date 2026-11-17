"""Sección Sectores: radiografía de un sector (estructura, competencia, valoración y dónde está la oportunidad)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos
import scoring as sc
from comun import (COLOR, GRIS, abrir_empresa, ajustes, analizar, cargar, cargar_varias, config_columnas, f_pct, fila_resumen,
                   selector_universo, tiempo_estimado)

aj = ajustes()
st.title("🏭 Sectores")
st.caption("Compara a todas las empresas de un sector: quién vende más, quién crece y gana más, cuánto se paga por cada una "
           "y dónde parece estar la mejor relación entre riesgo y recompensa.")


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def _rivales(ticker: str, n: int) -> list[str]:
    r = datos.competidores(cargar(ticker), n=n)
    if not r:
        raise RuntimeError("sin competidores")  # no se guarda en caché: se reintenta la próxima vez
    return r


def rivales(ticker: str, n: int = 14) -> list[str]:
    try:
        return _rivales(ticker, n)
    except Exception as ex:
        st.session_state["_sec_error"] = f"{type(ex).__name__}: {ex}"
        return []


res = st.session_state.get("sector_res")
with st.expander("1️⃣ Elige el sector" + (" · cargado" if res else ""), expanded=not res):
    modo = st.radio("¿Cómo elegimos el sector?", ["A partir de una empresa", "Un sector dentro de un mercado"], horizontal=True,
                    key="sec_modo")
    base = None
    if modo == "A partir de una empresa":
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        base = c1.text_input("Ticker de la empresa", st.session_state.get("_guardado_ticker_directo") or "ITX.MC", key="sec_ticker").strip().upper()
        n = c2.slider("Nº de competidores", 5, 20, 12, key="sec_n")
        st.caption("Usa las mayores empresas de su misma industria según Yahoo Finance (de todo el mundo, con más peso de EE. UU.).")
        if st.button("🏭 Analizar sector", type="primary"):
            with st.spinner("Buscando competidores…"):
                lista = [base] + rivales(base, n)
            if len(lista) < 3:
                st.error("Yahoo no da competidores para esta empresa. Prueba con el otro modo.")
                _e = cargar(base)
                if len(_e.info or {}) <= 15:
                    st.info("Yahoo Finance no está devolviendo ahora mismo la ficha de la empresa (suele ser un límite temporal "
                            "de peticiones). Vuelve a probar en unos minutos.")
                elif datos.ULTIMO_ERROR_COMPETIDORES:
                    st.caption("Detalle técnico: " + datos.ULTIMO_ERROR_COMPETIDORES[:300])
                st.stop()
            cargadas = cargar_varias(lista, "Analizando")
            filas = []
            for tk, e in cargadas.items():
                try:
                    _, m, r = analizar(tk, aj, e)
                    filas.append(fila_resumen(tk, e, m, r))
                except Exception:
                    pass
            st.session_state["sector_res"] = {"df": pd.DataFrame(filas), "titulo": None, "base": base,
                                              "hora": pd.Timestamp.now(tz="Europe/Madrid").strftime("%d/%m/%Y %H:%M")}
            st.rerun()
    else:
        universo, tickers = selector_universo("sec")
        st.caption(f"{len(tickers)} empresas · la primera vez tarda ≈ {tiempo_estimado(len(tickers))}; luego se guarda 12 h.")
        if st.button(f"🏭 Cargar {universo}", type="primary", disabled=not tickers):
            cargadas = cargar_varias(tickers, "Analizando")
            filas = []
            for tk, e in cargadas.items():
                try:
                    _, m, r = analizar(tk, aj, e)
                    filas.append(fila_resumen(tk, e, m, r))
                except Exception:
                    pass
            st.session_state["sector_res"] = {"df": pd.DataFrame(filas), "titulo": universo, "base": None,
                                              "hora": pd.Timestamp.now(tz="Europe/Madrid").strftime("%d/%m/%Y %H:%M")}
            st.rerun()

res = st.session_state.get("sector_res")
if not res or res["df"].empty:
    st.stop()
todo = res["df"]
if "Ventas (mill.)" not in todo:
    st.warning("Estos datos son de una versión anterior: vuelve a pulsar el botón para cargarlos.")
    st.stop()

if res["titulo"]:
    sectores = todo["Sector"].value_counts()
    sector = st.selectbox("Sector", list(sectores.index), format_func=lambda s: f"{s} ({sectores[s]} empresas)", key="sec_sector")
    df = todo[todo["Sector"] == sector].copy()
    titulo = f"{sector} · {res['titulo']}"
else:
    df = todo.copy()
    fila_base = df[df["Ticker"] == res["base"]]
    sector = fila_base["Sector"].iloc[0] if len(fila_base) else df["Sector"].mode().iloc[0]
    industria = fila_base["Industria"].iloc[0] if len(fila_base) else ""
    titulo = f"{industria or sector} · {res['base']} y sus competidores"
if len(df) < 3:
    st.info("Hay menos de 3 empresas en este sector: elige otro o un mercado más grande.")
    st.stop()

st.subheader(titulo)
st.caption(f"Datos de Yahoo Finance a {res['hora']}. Las cifras de distintas monedas no se convierten: "
           "las cuotas de ventas son aproximadas si el grupo mezcla monedas.")


def mediana(col, positivos=False):
    s = pd.to_numeric(df[col], errors="coerce")
    if positivos:
        s = s.where((s > 0) & (s < 200))
    s = s.dropna()
    return float(np.median(s)) if len(s) else None


med = {c: mediana(c, c in ("PER", "EV/EBITDA", "P/VC")) for c in
       ["PER", "EV/EBITDA", "P/VC", "Margen op.", "Crec. ingresos", "ROE", "Div.", "Deuda neta/EBITDA", "Nota"]}

# 1. Foto del sector --------------------------------------------------------------
k = st.columns(6)
k[0].metric("Empresas", len(df))
k[1].metric("PER mediano", f"{med['PER']:.1f}".replace(".", ",") if med["PER"] else "—")
k[2].metric("EV/EBITDA mediano", f"{med['EV/EBITDA']:.1f}".replace(".", ",") if med["EV/EBITDA"] else "—")
k[3].metric("Crecimiento ventas", f_pct(med["Crec. ingresos"]) if med["Crec. ingresos"] is not None else "—")
k[4].metric("Margen operativo", f_pct(med["Margen op."]) if med["Margen op."] is not None else "—")
k[5].metric("ROE mediano", f_pct(med["ROE"]) if med["ROE"] is not None else "—")
if res["titulo"]:
    pm = pd.to_numeric(todo["PER"], errors="coerce")
    pm = pm.where((pm > 0) & (pm < 200)).dropna()
    if len(pm) and med["PER"]:
        dif = med["PER"] / float(np.median(pm)) - 1
        st.caption(f"El sector cotiza a un PER **{abs(dif) * 100:.0f}% {'por encima' if dif > 0 else 'por debajo'}** "
                   f"de la mediana de todo {res['titulo']} ({float(np.median(pm)):.1f}).".replace(".", ",", 1))


t_estr, t_val, t_lid, t_tab = st.tabs(["🧩 Estructura y competencia", "💶 Valoración", "🎯 Líderes y oportunidades",
                                       f"📋 Todas las empresas ({len(df)})"])
with t_estr:
    # 2. Estructura: quién vende más ---------------------------------------------------
    st.markdown("#### 🧩 Estructura: quién manda")
    v = df.dropna(subset=["Ventas (mill.)"]).sort_values("Ventas (mill.)", ascending=False)
    if len(v) >= 2:
        total = v["Ventas (mill.)"].sum()
        v = v.assign(**{"Cuota de ventas": v["Ventas (mill.)"] / total})
        top3 = v["Cuota de ventas"].head(3).sum()
        hhi = float((v["Cuota de ventas"] ** 2).sum())
        tipo = ("muy concentrado: pocos grandes se reparten casi todo" if hhi > 0.25 else
                "concentrado: unos pocos líderes claros" if hhi > 0.15 else "fragmentado: muchos competidores de tamaño parecido")
        st.write(f"Los 3 mayores suman el **{top3 * 100:.0f}%** de las ventas del grupo. Es un sector **{tipo}**.")
        fig = go.Figure(go.Bar(x=v["Cuota de ventas"] * 100, y=v["Ticker"], orientation="h", text=v["Empresa"].str[:28],
                               textposition="auto", marker_color=[COLOR["Comprar"] if t == res.get("base") else "#4c78a8" for t in v["Ticker"]],
                               hovertemplate="%{y}: %{x:.1f}% de las ventas<extra></extra>"))
        fig.update_layout(height=max(260, 26 * len(v)), margin=dict(l=10, r=10, t=10, b=10), xaxis_title="% de las ventas del grupo",
                          yaxis=dict(autorange="reversed"), separators=",.")
        st.plotly_chart(fig, width="stretch")

    # 3. Competencia: crecimiento vs rentabilidad --------------------------------------
    st.markdown("#### 🏁 Competencia: quién crece y quién gana dinero")
    d = df.dropna(subset=["Crec. ingresos", "Margen op."])
    d = d[d["Crec. ingresos"].between(-0.6, 1.5) & d["Margen op."].between(-0.6, 0.9)]
    if len(d) >= 3:
        cap = pd.to_numeric(d["Cap. (mill.)"], errors="coerce").fillna(0)
        tam = 12 + 40 * np.sqrt(cap / cap.max()) if cap.max() > 0 else 16
        fig = go.Figure()
        for ver in ["Comprar", "Esperar", "Vender"]:
            dv = d[d["Veredicto"] == ver]
            fig.add_scatter(x=dv["Crec. ingresos"] * 100, y=dv["Margen op."] * 100, mode="markers+text", text=dv["Ticker"],
                            textposition="top center", name=ver, hovertext=dv["Empresa"],
                            marker=dict(size=tam[dv.index] if hasattr(tam, "__getitem__") else tam, color=COLOR[ver], opacity=.75,
                                        line=dict(width=2, color=["#000" if t == res.get("base") else "rgba(0,0,0,0)" for t in dv["Ticker"]])))
        if med["Crec. ingresos"] is not None:
            fig.add_vline(x=med["Crec. ingresos"] * 100, line=dict(color=GRIS, dash="dot"))
        if med["Margen op."] is not None:
            fig.add_hline(y=med["Margen op."] * 100, line=dict(color=GRIS, dash="dot"))
        fig.update_layout(height=460, xaxis_title="Crecimiento de ventas (%)", yaxis_title="Margen operativo (%)",
                          margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"), separators=",.")
        st.plotly_chart(fig, width="stretch")
        st.caption("Tamaño de la burbuja = capitalización. Líneas = mediana del sector. Arriba a la derecha: crecen más y ganan más "
                   "que el resto (suelen estar ganando cuota). Abajo a la izquierda: se están quedando atrás.")

with t_val:
    # 4. Valoración ---------------------------------------------------------------------
    st.markdown("#### 💶 Valoración: ¿se paga más por más calidad?")
    d = df.dropna(subset=["EV/EBITDA", "ROE"])
    d = d[d["EV/EBITDA"].between(0, 80) & d["ROE"].between(-0.5, 1.5)]
    if len(d) >= 3:
        fig = go.Figure()
        fig.add_scatter(x=d["ROE"] * 100, y=d["EV/EBITDA"], mode="markers+text", text=d["Ticker"], textposition="top center",
                        hovertext=d["Empresa"], marker=dict(size=13, color=[COLOR.get(x, GRIS) for x in d["Veredicto"]]), showlegend=False)
        if len(d) >= 4:
            a, b = np.polyfit(d["ROE"] * 100, d["EV/EBITDA"], 1)
            xs = np.linspace((d["ROE"] * 100).min(), (d["ROE"] * 100).max(), 20)
            fig.add_scatter(x=xs, y=a * xs + b, mode="lines", line=dict(color=GRIS, dash="dash"), name="Lo «normal» en el sector",
                            hoverinfo="skip")
        fig.update_layout(height=420, xaxis_title="ROE (%)", yaxis_title="EV/EBITDA (veces)", margin=dict(l=10, r=10, t=30, b=10),
                          legend=dict(orientation="h"), separators=",.")
        st.plotly_chart(fig, width="stretch")
        st.caption("Por debajo de la línea: más baratas de lo que «tocaría» por su rentabilidad. Por encima: el mercado paga "
                   "una prima (porque espera más crecimiento… o porque está cara).")

with t_lid:
    # 5. Líderes ------------------------------------------------------------------------
    st.markdown("#### 🏆 Líderes por categoría")
    cats = [("Mejor nota del modelo", "Nota", False, lambda x: f"{x:.0f}/100"),
            ("Más crecimiento", "Crec. ingresos", False, f_pct), ("Más margen", "Margen op.", False, f_pct),
            ("Más rentable (ROE)", "ROE", False, f_pct), ("Menos deuda", "Deuda neta/EBITDA", True, lambda x: f"{x:.1f}x".replace(".", ",")),
            ("Más barata (PER)", "PER", True, lambda x: f"{x:.1f}".replace(".", ",")), ("Más dividendo", "Div.", False, f_pct)]
    cols = st.columns(4)
    for i, (et, col, asc, fmt) in enumerate(cats):
        s = pd.to_numeric(df[col], errors="coerce")
        if col == "PER":
            s = s.where(s > 0)
        s = s.dropna()
        if s.empty:
            continue
        idx = s.idxmin() if asc else s.idxmax()
        cols[i % 4].metric(et, f"{df.loc[idx, 'Ticker']}", fmt(s[idx]), delta_color="off")

    # 6. Dónde está la oportunidad y el debate -------------------------------------------
    st.markdown("#### 🎯 Dónde parece estar la oportunidad")
    op = df.dropna(subset=["Nota"]).copy()
    op["_puntos"] = op["Nota"].fillna(0) + 40 * op["Potencial"].clip(-0.5, 1).fillna(0)
    op = op.sort_values("_puntos", ascending=False)
    for _, f in op.head(3).iterrows():
        extra = f" · {f['Potencial'] * 100:+.0f}% hasta su valor justo".replace(".", ",") if pd.notna(f.get("Potencial")) else ""
        st.markdown(f"- **{f['Ticker']} · {f['Empresa']}** — {f['Veredicto']}, nota {f['Nota']:.0f}{extra}")
    st.caption("Ordenadas combinando la nota del modelo y la distancia a su valor justo. Son candidatas para estudiar, no recomendaciones.")

    alc, baj = [], []
    if med["Crec. ingresos"] is not None:
        (alc if med["Crec. ingresos"] > 0.08 else baj if med["Crec. ingresos"] < 0.02 else alc).append(
            f"Las ventas del sector crecen un {f_pct(med['Crec. ingresos'])} de mediana" if med["Crec. ingresos"] >= 0.02
            else f"El sector apenas crece ({f_pct(med['Crec. ingresos'])} de mediana)")
    if med["Margen op."] is not None:
        (alc if med["Margen op."] > 0.15 else baj if med["Margen op."] < 0.07 else alc).append(
            f"Márgenes {'altos' if med['Margen op.'] > 0.15 else 'estrechos' if med['Margen op.'] < 0.07 else 'razonables'} "
            f"({f_pct(med['Margen op.'])} operativo)")
    if med["Deuda neta/EBITDA"] is not None:
        (baj if med["Deuda neta/EBITDA"] > 3 else alc).append(
            f"Deuda {'elevada' if med['Deuda neta/EBITDA'] > 3 else 'controlada'} ({med['Deuda neta/EBITDA']:.1f}x EBITDA)".replace(".", ","))
    if med["PER"] is not None:
        (baj if med["PER"] > 25 else alc if med["PER"] < 14 else alc).append(
            f"Valoración {'exigente' if med['PER'] > 25 else 'atractiva' if med['PER'] < 14 else 'razonable'} (PER {med['PER']:.1f})".replace(".", ","))
    n_comp = int((df["Veredicto"] == "Comprar").sum())
    (alc if n_comp >= len(df) / 3 else baj).append(f"{n_comp} de {len(df)} empresas en «Comprar» según el modelo")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**👍 A favor del sector**\n" + ("\n".join(f"- {x}" for x in alc) if alc else "- —"))
    with c2:
        st.markdown("**👎 En contra**\n" + ("\n".join(f"- {x}" for x in baj) if baj else "- —"))

with t_tab:
    # 7. Tabla ----------------------------------------------------------------------------
    st.markdown("#### 📋 Todas las empresas")
    tabla = df.copy()
    if med["PER"]:
        tabla["PER vs sector"] = pd.to_numeric(tabla["PER"], errors="coerce") / med["PER"] - 1
    cfg = config_columnas()
    cfg["PER vs sector"] = st.column_config.NumberColumn("PER vs sector", format="percent",
                                                         help="Prima (+) o descuento (−) frente al PER mediano del sector")
    orden = ["Ticker", "Empresa", "Veredicto", "Nota", "Cap. (mill.)", "Ventas (mill.)", "Crec. ingresos", "Margen op.", "ROE",
             "Deuda neta/EBITDA", "PER", "PER vs sector", "EV/EBITDA", "Div.", "Potencial", "Moneda"]
    st.dataframe(tabla.sort_values("Nota", ascending=False), hide_index=True, width="stretch", column_config=cfg,
                 column_order=[c for c in orden if c in tabla])
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    sel = c1.selectbox("Abrir empresa", list(df["Ticker"]), format_func=lambda t: f"{t} · {df.set_index('Ticker').loc[t, 'Empresa']}",
                       key="sec_abrir")
    if c2.button("🔎 Analizar", width="stretch"):
        abrir_empresa(sel)
