"""Sección Resumen del día: lo que ha pasado y lo que viene en tus empresas, para leer en dos minutos."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import agenda
import tesis as ts
import usuario as us
from comun import abrir_empresa, ajustes, analizar, cargar_opcional, eventos_empresa, f_num, f_pct, noticias

aj = ajustes()
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
ahora = pd.Timestamp.now(tz="Europe/Madrid")
hoy = pd.Timestamp(ahora.date())
st.title("☀️ Resumen del día")
st.caption(f"{DIAS[hoy.weekday()].capitalize()}, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year} · {ahora:%H:%M} · "
           "precios con ~15 min de retraso. Herramienta de análisis según reglas: no es asesoramiento financiero.")

if not us.cargado():
    st.info("Cargando tus datos guardados…")
    st.stop()

d = us.datos()
favs, tesis_d, alertas = d["favoritos"], d.get("tesis", {}), d["alertas"]
lista = list(dict.fromkeys(list(tesis_d) + list(favs) + [a["ticker"] for a in alertas]))
nombres = {**{a["ticker"]: a.get("nombre", "") for a in alertas}, **{k: v.get("nombre", "") for k, v in favs.items()},
           **{k: v.get("nombre", "") for k, v in tesis_d.items()}}
nota_md = [f"**Resumen del día — {hoy:%d/%m/%Y}**", ""]

# Mercados -----------------------------------------------------------------------------
MERCADOS = [("IBEX 35", "^IBEX"), ("Euro Stoxx 50", "^STOXX50E"), ("S&P 500", "^GSPC"), ("Nasdaq", "^IXIC"),
            ("Euro/dólar", "EURUSD=X"), ("Brent", "BZ=F"), ("Oro", "GC=F"), ("Bitcoin", "BTC-EUR")]


def cambios(tk):
    h = us.precios_recientes(tk)
    if h is None or h.empty or "Close" not in h:
        return None, None, None
    c = h["Close"].dropna()
    if len(c) < 6:
        return None, None, None
    return float(c.iloc[-1]), float(c.iloc[-1] / c.iloc[-2] - 1), float(c.iloc[-1] / c.iloc[-6] - 1)


st.markdown("#### 🌍 Mercados")
cols = st.columns(len(MERCADOS))
lineas_mkt = []
for col, (nombre, tk) in zip(cols, MERCADOS):
    p, dd, _ = cambios(tk)
    col.metric(nombre, f_num(p) if p is not None else "—", f_pct(dd) if dd is not None else None)
    if dd is not None:
        lineas_mkt.append(f"{nombre} {f_pct(dd)}")
nota_md += ["**Mercados:** " + " · ".join(lineas_mkt), ""]

if not lista:
    st.info("Aún no sigues ninguna empresa. Pulsa **☆ Seguir** en **Analizar empresa** o escribe una tesis, "
            "y aquí verás cada día lo que ha pasado y lo que viene.")
    st.page_link("vistas/empresa.py", label="Ir a Analizar empresa", icon="🔎")
    st.stop()

# Datos de tus empresas -----------------------------------------------------------------
filas, analisis = [], {}
barra = st.progress(0.0, text="Repasando tus empresas…")
for k, tk in enumerate(lista):
    p, dd, sem = cambios(tk)
    m = r = None
    try:
        e = cargar_opcional(tk)
        if e is not None:
            _, m, r = analizar(tk, aj, e)
            nombres[tk] = nombres.get(tk) or e.nombre
    except Exception:
        pass
    analisis[tk] = (m, r)
    mk = ts.marcador(tesis_d[tk], m, r) if tk in tesis_d else None
    filas.append({"tk": tk, "precio": p, "dia": dd, "semana": sem, "m": m, "r": r, "mk": mk, "ev": eventos_empresa(tk)})
    barra.progress((k + 1) / len(lista), text=f"Repasando {tk}…")
barra.empty()

# Acontecimientos priorizados -------------------------------------------------------------
puntos = []  # (prioridad, titular, detalle, ticker)
for f in filas:
    tk, mk, r, p = f["tk"], f["mk"], f["r"], f["precio"]
    nom = f"**{tk}** ({nombres.get(tk, '')})"
    if mk and mk["toca_stop"]:
        puntos.append((0, f"⛔ {tk} ha tocado tu precio de salida",
                       f"{nom} cotiza en {f_num(p)} y tu stop era {f_num(tesis_d[tk].get('stop'))}. Según tu propio plan, la tesis ha fallado.", tk))
    elif mk and mk["salud"].startswith("🔴"):
        puntos.append((1, f"🔴 Tu tesis en {tk} está rota",
                       f"Solo se cumplen {mk['ok']} de {mk['n']} pilares. Toca decidir si sigue teniendo sentido.", tk))
    for x in f["ev"]["proximos"]:
        if x["tipo"] == "Resultados" and 0 <= (x["fecha"] - hoy).days <= 1:
            cs = f["ev"].get("consenso") or {}
            esp = f" Se espera un BPA de {f_num(cs['Earnings Average'])}." if cs.get("Earnings Average") is not None else ""
            puntos.append((2, f"📊 {tk} presenta resultados {'hoy' if x['fecha'] == hoy else 'mañana'}",
                           f"{nom}.{esp} Revisa la previa y tu plan en el *Calendario*.", tk))
    res = f["ev"].get("resultados")
    if res is not None and not res.empty:
        rec = res[res.index >= hoy - pd.Timedelta(days=4)]
        if len(rec):
            fecha = rec.index[0]
            fila = agenda.historial_resultados(rec.head(1), us.precios_recientes(tk)).iloc[0]
            s, rx = fila["sorpresa"], fila["reaccion"]
            if pd.notna(s):
                bate = s > 0
                if rx is None or pd.isna(rx):
                    lectura = "Falta ver la reacción del mercado."
                elif bate and rx > 0:
                    lectura = "Bate y el mercado lo premia: buena señal para la tesis."
                elif bate and rx <= 0:
                    lectura = "Bate pero cae: el mercado esperaba más (o le preocupan las previsiones)."
                elif not bate and rx > 0:
                    lectura = "Falla pero sube: lo malo ya estaba descontado o las previsiones gustan."
                else:
                    lectura = "Falla y cae: revisa si afecta a algún pilar de tu tesis."
                puntos.append((2, f"{'✅' if bate else '❌'} {tk} {'batió' if bate else 'no alcanzó'} previsiones ({fecha:%d/%m})",
                               f"BPA {f_num(fila['real'])} frente a {f_num(fila['esperado'])} esperado ({s:+.1f}%)".replace(".", ",", 1)
                               + (f", y la acción se movió un {f_pct(rx)}." if rx is not None and pd.notna(rx) else ".") + f" {lectura}", tk))
    if f["dia"] is not None and abs(f["dia"]) >= 0.03:
        titular = ""
        try:
            nts = noticias(tk)
            titular = f" Titular reciente: «{nts[0]['titulo']}»." if nts else ""
        except Exception:
            pass
        puntos.append((3, f"{'🚀' if f['dia'] > 0 else '📉'} {tk} se mueve un {f_pct(f['dia'])} hoy",
                       f"{nom} cotiza en {f_num(f['precio'])} ({f_pct(f['semana'])} en la semana).{titular}", tk))
    if mk and mk["toca_objetivo"]:
        puntos.append((3, f"🎯 {tk} ha llegado a tu objetivo", "¿Sigue teniendo recorrido o es momento de recoger beneficios?", tk))

estados = us.comprobar(alertas, lambda t: analisis.get(t) or (None, None))
for a in us.marcar_disparadas(estados) or []:
    puntos.append((2, f"🔔 Alerta cumplida en {a['ticker']}", us.describir(a), a["ticker"]))
for a in alertas:
    if a.get("disparada") and not any(x[1].startswith(f"🔔 Alerta cumplida en {a['ticker']}") for x in puntos):
        puntos.append((4, f"🔔 Sigue cumplida una alerta de {a['ticker']}", us.describir(a), a["ticker"]))
for x in agenda.macro(True, True):
    if 0 <= (x["fecha"] - hoy).days <= 1:
        puntos.append((3, f"🏦 {x['empresa']} decide tipos {'hoy' if x['fecha'] == hoy else 'mañana'}", x["texto"], None))
for x in d.get("eventos", []):
    if 0 <= (pd.Timestamp(x["fecha"]) - hoy).days <= 1:
        puntos.append((3, f"📌 {x['ticker']}: {x['texto']}", "Evento que apuntaste tú.", x["ticker"]))
puntos.sort(key=lambda x: x[0])

# Titular principal ---------------------------------------------------------------------
st.markdown("#### 📣 Lo más importante")
if puntos:
    pr, tit, det, tk = puntos[0]
    with st.container(border=True):
        st.markdown(f"### {tit}")
        st.write(det)
        if tk and st.button("🔎 Abrir la empresa", key="top_abrir"):
            abrir_empresa(tk)
    nota_md += [f"**Lo más importante: {tit}**", det.replace("**", ""), ""]
    if len(puntos) > 1:
        st.markdown("**Además**")
        for _, tit, det, _ in puntos[1:12]:
            st.markdown(f"- **{tit}** — {det}")
        nota_md += ["**Además:**"] + [f"- {tit}: {det.replace('**', '')}" for _, tit, det, _ in puntos[1:12]] + [""]
else:
    st.success("Día tranquilo: ninguna alerta, ningún movimiento fuerte y ningún evento hoy o mañana en tus empresas.")
    nota_md += ["Día tranquilo en tus empresas.", ""]

# Tus empresas hoy ----------------------------------------------------------------------
st.markdown("#### ⭐ Tus empresas hoy")
tabla = []
for f in sorted(filas, key=lambda f: -abs(f["dia"] or 0)):
    r, mk = f["r"], f["mk"]
    tabla.append({"Ticker": f["tk"], "Empresa": nombres.get(f["tk"], ""), "Precio": f["precio"], "Hoy": f["dia"], "Semana": f["semana"],
                  "Veredicto": getattr(r, "veredicto", None), "Nota": getattr(r, "nota", None),
                  "vs zona compra": (f["precio"] / r.precio_compra - 1) if r is not None and r.precio_compra and f["precio"] else None,
                  "Mi tesis": f"{mk['salud']} {mk['ok']}/{mk['n']}" if mk else ""})
st.dataframe(pd.DataFrame(tabla), hide_index=True, width="stretch", column_config={
    "Precio": st.column_config.NumberColumn(format="%.2f"), "Hoy": st.column_config.NumberColumn(format="percent"),
    "Semana": st.column_config.NumberColumn(format="percent"), "vs zona compra": st.column_config.NumberColumn(format="percent"),
    "Nota": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f")})

# Próximos días ---------------------------------------------------------------------------
st.markdown("#### 📅 Esta semana")
sem = []
for f in filas:
    for x in f["ev"]["proximos"]:
        if 0 <= (x["fecha"] - hoy).days <= 7:
            sem.append((x["fecha"], f"{agenda.TIPO_ICONO.get(x['tipo'], '')} **{f['tk']}** {x['texto']}"))
for x in agenda.macro(True, True):
    if 0 <= (x["fecha"] - hoy).days <= 7:
        sem.append((x["fecha"], f"🏦 {x['texto']}"))
if sem:
    for fecha, txt in sorted(sem):
        st.markdown(f"- **{DIAS[fecha.weekday()]} {fecha:%d}** · {txt}")
    nota_md += ["**Esta semana:**"] + [f"- {DIAS[fch.weekday()]} {fch:%d}: {t.replace('**', '')}" for fch, t in sorted(sem)] + [""]
else:
    st.caption("Sin eventos en los próximos 7 días.")

# Ideas ----------------------------------------------------------------------------------
st.markdown("#### 💡 Ideas para hoy")
ideas_txt = []
for f in filas:
    r, m, p, tk, mk = f["r"], f["m"], f["precio"], f["tk"], f["mk"]
    if r is None or p is None:
        continue
    if r.veredicto == "Comprar" and r.precio_compra and p <= r.precio_compra and not (mk and mk["salud"].startswith("🔴")):
        riesgo = min(((r.pilares[x].nota, x) for x in ("Calidad", "Salud financiera", "Crecimiento") if r.pilares[x].nota is not None),
                     default=(None, None))
        ideas_txt.append(f"**Comprar {tk}** — en «Comprar» y por debajo de su zona de compra ({f_num(r.precio_compra)}), nota {r.nota:.0f}."
                         + (f" Riesgo: su punto más flojo es {riesgo[1].lower()} ({riesgo[0]:.0f}/100)." if riesgo[0] is not None else ""))
    elif r.veredicto == "Vender" and tk in favs:
        ideas_txt.append(f"**Revisar {tk}** — el modelo la pone en «Vender» (nota {r.nota:.0f}). Si la tienes, comprueba si tu tesis sigue en pie.")
    elif mk and mk["revisar"]:
        ideas_txt.append(f"**Repasar la tesis de {tk}** — hace {mk['dias_sin_revisar']} días que no la revisas.")
if ideas_txt:
    for x in ideas_txt[:6]:
        st.markdown(f"- {x}")
    nota_md += ["**Ideas:**"] + [f"- {x.replace('**', '')}" for x in ideas_txt[:6]]
else:
    st.caption("Ninguna de tus empresas está hoy en zona de compra ni pide revisión. Para buscar nuevas, usa las "
               "**búsquedas de ideas** del Escáner.")

# Compartir -------------------------------------------------------------------------------
st.divider()
texto = "\n".join(nota_md).strip() + "\n\n_No es asesoramiento financiero._"
c1, c2 = st.columns(2)
c1.download_button("📄 Descargar el resumen", texto, file_name=f"resumen_{hoy:%Y%m%d}.md", mime="text/markdown", width="stretch")
with c2.popover("📋 Copiar el texto", width="stretch"):
    st.code(texto, language=None, wrap_lines=True)
