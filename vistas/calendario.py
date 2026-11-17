"""Sección Calendario: catalizadores de tus empresas y de los bancos centrales."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import agenda
import tesis as ts
import usuario as us
import previa
from comun import abrir_empresa, cargar_opcional, eventos_empresa, explicar_lista, precios_max, resolver_lista

st.title("📅 Calendario")
st.caption("Lo que puede mover tus empresas: presentaciones de resultados, dividendos, decisiones de tipos de interés "
           "y los eventos que apuntes tú. Las fechas de resultados a veces cambian: confírmalas cuando se acerquen.")

if not us.cargado():
    st.info("Cargando tus datos guardados…")
    st.stop()

d = us.datos()
favs, tesis_d = d["favoritos"], d.get("tesis", {})
universo = list(dict.fromkeys(list(favs) + list(tesis_d) + [a["ticker"] for a in d["alertas"]] +
                              [x["ticker"] for x in d.get("eventos", [])]))
nombres = {**{a["ticker"]: a.get("nombre", "") for a in d["alertas"]}, **{k: v.get("nombre", "") for k, v in tesis_d.items()},
           **{k: v.get("nombre", "") for k, v in favs.items()}}

c1, c2, c3, c4 = st.columns([2.6, 1, 1, 1.6], vertical_alignment="bottom")
horizonte = c1.segmented_control("Mostrar", ["2 semanas", "1 mes", "3 meses", "6 meses"], default="1 mes", key="cal_horizonte") or "1 mes"
ver_fed = c2.toggle("Fed (EE. UU.)", value=True, key="cal_fed")
ver_bce = c3.toggle("BCE (euro)", value=True, key="cal_bce")
extra = c4.text_input("Añadir empresas solo para esta vista", placeholder="Ej.: Apple, Inditex, Nvidia", key="cal_extra",
                      help="Nombres (o tickers) separados por comas")
_extra_tks, _trad, _faltan = resolver_lista(extra)
explicar_lista(_trad, _faltan)
universo += [t for t in _extra_tks if t not in universo]

dias = {"2 semanas": 14, "1 mes": 31, "3 meses": 92, "6 meses": 183}[horizonte]
hoy = pd.Timestamp.today().normalize()
fin = hoy + pd.Timedelta(days=dias)

if not universo:
    st.info("Todavía no sigues ninguna empresa. Pulsa **☆ Seguir** en **Analizar empresa** o escribe tickers arriba; "
            "mientras, aquí tienes las decisiones de los bancos centrales.")

eventos, historicos, sin_eventos, evs = [], {}, [], {}
if universo:
    barra = st.progress(0.0, text="Buscando eventos…")
    for k, tk in enumerate(universo):
        ev = eventos_empresa(tk)
        evs[tk] = ev
        for x in ev["proximos"]:
            eventos.append(dict(x, ticker=tk, empresa=nombres.get(tk, ""), consenso=ev.get("consenso", {})))
        historicos[tk] = ev.get("resultados")
        if not ev["proximos"]:
            sin_eventos.append(tk + (f" ({'; '.join(ev.get('errores', []))[:200]})" if ev.get("errores") else ""))
        barra.progress((k + 1) / len(universo), text=f"Buscando eventos de {tk}…")
    barra.empty()
for x in d.get("eventos", []):
    eventos.append({"fecha": pd.Timestamp(x["fecha"]), "ticker": x["ticker"], "empresa": nombres.get(x["ticker"], ""),
                    "tipo": "Propio", "texto": x["texto"], "impacto": x["impacto"]})
for tk, t in tesis_d.items():
    try:
        prox = pd.Timestamp(t.get("revisada")) + pd.Timedelta(days=ts.DIAS_REVISION)
    except Exception:
        continue
    eventos.append({"fecha": max(prox, hoy), "ticker": tk, "empresa": t.get("nombre", ""), "tipo": "Tesis",
                    "texto": "Revisión trimestral de tu tesis" + (" (atrasada)" if prox < hoy else ""), "impacto": "Bajo"})
eventos += agenda.macro(ver_fed, ver_bce)


def posicion(tk):
    p = []
    if tk in tesis_d:
        p.append("📈 Tesis alcista" if tesis_d[tk].get("posicion") == "Alcista" else "📉 Tesis bajista")
    if tk in favs:
        p.append("⭐")
    if any(a["ticker"] == tk for a in d["alertas"]):
        p.append("🔔")
    return " ".join(p)


proximos = sorted([x for x in eventos if hoy <= x["fecha"] <= fin], key=lambda x: (x["fecha"], x["ticker"]))

# Resumen semanal --------------------------------------------------------------
lunes = hoy - pd.Timedelta(days=hoy.weekday())
semanas = [("Esta semana", lunes, lunes + pd.Timedelta(days=6)),
           ("La semana que viene", lunes + pd.Timedelta(days=7), lunes + pd.Timedelta(days=13))]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
cols = st.columns(2)
for col, (titulo, ini, fin_s) in zip(cols, semanas):
    with col.container(border=True):
        st.markdown(f"**{titulo}** · {ini:%d/%m} – {fin_s:%d/%m}")
        sem = [x for x in eventos if max(ini, hoy) <= x["fecha"] <= fin_s]
        sem.sort(key=lambda x: ({"Alto": 0, "Medio": 1, "Bajo": 2}.get(x["impacto"], 3), x["fecha"]))
        if not sem:
            st.caption("Sin eventos importantes.")
        for x in sorted(sem, key=lambda x: x["fecha"]):
            linea = f"{agenda.IMPACTO_ICONO[x['impacto']][:1]} **{DIAS[x['fecha'].weekday()]} {x['fecha']:%d}** · "
            linea += f"{agenda.TIPO_ICONO.get(x['tipo'], '')} **{x['ticker']}** {x['texto']}"
            cs = x.get("consenso") or {}
            if x["tipo"] == "Resultados" and cs.get("Earnings Average") is not None:
                linea += f" · se espera BPA {cs['Earnings Average']:.2f}".replace(".", ",")
            pos = posicion(x["ticker"]) if x["tipo"] not in ("Macro",) else ""
            st.markdown(linea + (f" · {pos}" if pos else ""))
        altos = [x for x in sem if x["impacto"] == "Alto" and x["tipo"] == "Resultados" and x["ticker"] in tesis_d]
        if altos:
            st.caption("💡 Hay resultados de empresas en las que tienes tesis: repasa qué pilar pondrán a prueba "
                       "y decide antes qué harás si sorprenden para bien o para mal.")

proximas = sorted([(min(x["fecha"] for x in ev["proximos"] if x["tipo"] == "Resultados"), tk) for tk, ev in evs.items()
                   if any(x["tipo"] == "Resultados" and hoy <= x["fecha"] <= hoy + pd.Timedelta(days=14) for x in ev["proximos"])])

st.write("")
t_todos, t_prev, t_pasado = st.tabs([f"🗓️ Todos los eventos ({len(proximos)})", f"🔮 Previas de resultados ({len(proximas)})",
                                     "🗂️ Resultados recientes"])
with t_todos:
    # Tabla completa ---------------------------------------------------------------
    if proximos:
        df = pd.DataFrame([{"Fecha": x["fecha"].date(), "Faltan (días)": (x["fecha"] - hoy).days,
                            "Tipo": f"{agenda.TIPO_ICONO.get(x['tipo'], '')} {x['tipo']}", "Ticker": x["ticker"],
                            "Empresa": x.get("empresa", ""), "Evento": x["texto"],
                            "Impacto": agenda.IMPACTO_ICONO.get(x["impacto"], x["impacto"]), "Tú": posicion(x["ticker"]) if x["tipo"] != "Macro" else ""}
                           for x in proximos])
        filtro = st.multiselect("Tipos", sorted(df["Tipo"].unique()), default=sorted(df["Tipo"].unique()))
        st.dataframe(df[df["Tipo"].isin(filtro)], hide_index=True, width="stretch",
                     column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY")})
        c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")
        con_tk = sorted({x["ticker"] for x in proximos if x["tipo"] != "Macro"})
        if con_tk:
            sel = c1.selectbox("Abrir empresa", con_tk, format_func=lambda t: f"{t} · {nombres.get(t, '')}", key="cal_sel")
            if c2.button("🔎 Analizar", width="stretch"):
                abrir_empresa(sel)
        c3.download_button("📆 Pasar a mi calendario", agenda.ics(proximos), file_name="eventos_inversion.ics", mime="text/calendar",
                           width="stretch", help="Descarga un archivo .ics que puedes abrir con Google Calendar, Outlook o el calendario del móvil")
    else:
        st.caption("No hay eventos en este periodo.")
    if sin_eventos:
        st.caption(f"Yahoo no tiene próximos eventos anunciados para: {', '.join(sin_eventos)}.")


with t_prev:
    # Previas de resultados ---------------------------------------------------------
    if proximas:
        st.caption("Las empresas que presentan en las próximas dos semanas: qué se espera, qué vigilar, tres escenarios y tu plan.")
        for f, tk in proximas:
            with st.expander(f"{f:%d/%m} · {tk} {nombres.get(tk, '')} {posicion(tk)}"):
                e_tk = cargar_opcional(tk)
                hist = precios_max(tk)
                precio = float(hist["Close"].dropna().iloc[-1]) if hist is not None and len(hist) else None
                pv = previa.construir(evs[tk], hist, precio)
                if pv:
                    previa.mostrar(pv, getattr(e_tk, "sector", None), tesis_d.get(tk),
                                   (e_tk.info.get("currency") if e_tk is not None else "") or "", tk)

    if not proximas:
        st.caption("Ninguna de tus empresas presenta resultados en las próximas dos semanas.")

with t_pasado:
    # Archivo: lo que pasó ---------------------------------------------------------
    st.caption("Sorpresa del beneficio frente a lo que esperaban los analistas y cómo reaccionó la acción al día siguiente. "
               "Con el tiempo te ayuda a ver qué empresas suelen sorprender y cómo las trata el mercado.")
    filas = []
    for tk, res in historicos.items():
        if res is None or res.empty:
            continue
        df_h = agenda.historial_resultados(res.head(4), precios_max(tk))
        for f, row in df_h.iterrows():
            if f >= hoy - pd.Timedelta(days=120):
                filas.append({"Fecha": f.date(), "Ticker": tk, "Empresa": nombres.get(tk, ""), "BPA esperado": row["esperado"],
                              "BPA real": row["real"], "Sorpresa": row["sorpresa"] / 100 if pd.notna(row["sorpresa"]) else None,
                              "Reacción": row["reaccion"], "Tú": posicion(tk)})
    if filas:
        st.dataframe(pd.DataFrame(filas).sort_values("Fecha", ascending=False), hide_index=True, width="stretch", column_config={
            "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "BPA esperado": st.column_config.NumberColumn(format="%.2f"), "BPA real": st.column_config.NumberColumn(format="%.2f"),
            "Sorpresa": st.column_config.NumberColumn(format="percent"), "Reacción": st.column_config.NumberColumn(format="percent"),
        })
        st.caption("Si alguna de tus empresas tiene tesis, apunta lo que pasó en su **registro de novedades** "
                   "(Analizar empresa → pestaña *📌 Mi tesis*).")
    else:
        st.caption("Sin presentaciones en los últimos 4 meses (o Yahoo no tiene sus previsiones, algo habitual fuera de EE. UU.).")
