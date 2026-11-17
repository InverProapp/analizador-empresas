"""Pestañas «Resultados» y «Mi tesis» de Analizar empresa."""
from __future__ import annotations

import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import graficos

import agenda
import tesis as ts
import usuario as us
from comun import COLOR, eventos_empresa, f_num, f_pct, metrica

MANUAL_ETIQ = "✍️ La reviso yo"
_ETIQ = {k: v[0] for k, v in ts.METRICAS.items()}
_INV = {v: k for k, v in _ETIQ.items()}


def sugerir(m: dict, r) -> list[dict]:
    """Pilares de partida a partir de los puntos fuertes actuales (el usuario los ajusta)."""
    out = []

    def add(texto, clave, op, valor):
        out.append({"id": ts.nuevo_id(), "texto": texto, "metrica": clave, "op": op, "valor": round(float(valor), 1)})
    g = ts.valor_metrica("crec_ingresos", m)
    if g is not None and g > 2:
        add("Las ventas siguen creciendo", "crec_ingresos", ">", max(0.0, g / 2))
    roe = ts.valor_metrica("roe", m)
    if roe is not None and roe > 10:
        add("Negocio muy rentable", "roe", ">", min(15.0, roe * 0.8))
    mo = ts.valor_metrica("margen_operativo", m)
    if mo is not None and mo > 5:
        add("Mantiene los márgenes", "margen_operativo", ">", mo * 0.8)
    d = m.get("deuda_neta_ebitda")
    if d is not None and d < 3:
        add("Deuda bajo control", "deuda_neta_ebitda", "<", max(2.5, d + 1))
    desc = ts.valor_metrica("_descuento", m, r)
    if desc is not None and desc > 0:
        add("Cotiza por debajo de lo que vale", "_descuento", ">", 0)
    rd = ts.valor_metrica("rent_dividendo", m)
    if rd is not None and rd > 3:
        add("Dividendo atractivo", "rent_dividendo", ">", rd * 0.75)
    if not out:
        add("La calidad del modelo se mantiene", "_nota", ">", 50)
    return out[:5]


def _editor(ticker: str, nombre: str, t: dict, m: dict, r, precio, mon: str):
    st.markdown("##### ✍️ " + ("Editar mi tesis" if t.get("enunciado") else "Escribir mi tesis"))
    st.caption("Una buena tesis **se puede demostrar falsa**: escribe pilares que puedas comprobar con datos. "
               "La web los revisará sola cada vez que abras la empresa.")
    with st.form(f"form_tesis_{ticker}", border=True):
        c1, c2, c3 = st.columns(3)
        posicion = c1.radio("Posición", ["Alcista", "Bajista"], index=0 if t["posicion"] == "Alcista" else 1, horizontal=True,
                            help="Alcista: crees que subirá (comprar). Bajista: crees que bajará (vender o evitar).")
        conviccion = c2.select_slider("Convicción", ts.CONVICCION[::-1], value=t.get("conviccion", "Media"))
        horizontes = ["Menos de 1 año", "1-3 años", "3-5 años", "Más de 5 años"]
        horizonte = c3.selectbox("Horizonte", horizontes, index=horizontes.index(t.get("horizonte", "1-3 años")))
        enunciado = st.text_area("La idea en una o dos frases", t.get("enunciado", ""), height=80,
                                 placeholder=f"Ej.: Alcista en {nombre}: crece a doble dígito, casi sin deuda y cotiza por debajo de su valor.")
        st.markdown("**Pilares** · qué tiene que seguir siendo cierto (3-5)")
        filas = [{"Pilar": p.get("texto", ""), "Métrica": _ETIQ.get(p.get("metrica"), MANUAL_ETIQ),
                  "Condición": p.get("op", ">"), "Valor": p.get("valor"), "Estado si la revisas tú": p.get("manual", "Va bien")}
                 for p in t.get("pilares", [])]
        df = pd.DataFrame(filas, columns=["Pilar", "Métrica", "Condición", "Valor", "Estado si la revisas tú"])
        ed = st.data_editor(df, num_rows="dynamic", hide_index=True, width="stretch", key=f"ed_pil_{ticker}", column_config={
            "Pilar": st.column_config.TextColumn(width="medium", help="Con tus palabras"),
            "Métrica": st.column_config.SelectboxColumn(options=[MANUAL_ETIQ] + list(_ETIQ.values()), width="medium", required=True,
                                                        default=MANUAL_ETIQ),
            "Condición": st.column_config.SelectboxColumn(options=[">", "<"], default=">", width="small"),
            "Valor": st.column_config.NumberColumn(help="Porcentajes en %, p. ej. 15 = 15%", width="small"),
            "Estado si la revisas tú": st.column_config.SelectboxColumn(options=ts.MANUAL, default="Va bien",
                                                                        help="Solo para pilares que no se miden con una métrica"),
        })
        riesgos = st.text_area("Riesgos que la romperían (uno por línea)", "\n".join(t.get("riesgos", [])), height=90,
                               placeholder="Ej.: Una guerra de precios en su mercado principal\nQue suba mucho la deuda para comprar otra empresa")
        c1, c2 = st.columns(2)
        vj = r.valor_justo if r is not None else None
        sug_obj = t.get("objetivo") or (round(vj, 2) if vj and precio and vj > precio * 1.05 else
                                         round(precio * 1.25, 2) if precio else None)
        sug_stop = t.get("stop") or (round(precio * 0.85, 2) if precio else None)
        objetivo = c1.number_input(f"Precio objetivo ({mon})", value=sug_obj, min_value=0.0, step=0.5, format="%.2f",
                                   help="Cuánto vale si la tesis se cumple. Por defecto, el valor justo del modelo (o +25% si el modelo la ve cara).")
        stop = c2.number_input(f"Precio de salida / stop ({mon})", value=sug_stop, min_value=0.0, step=0.5, format="%.2f",
                               help="Si llega aquí, la tesis ha fallado y sales. Por defecto, un 15% por debajo del precio actual.")
        b1, b2 = st.columns(2)
        ok = b1.form_submit_button("💾 Guardar tesis", type="primary", width="stretch")
        cancelar = b2.form_submit_button("Cancelar", width="stretch")
    if cancelar:
        st.session_state[f"editando_tesis_{ticker}"] = False
        st.rerun()
    if ok:
        pilares = []
        for _, f in ed.iterrows():
            texto = str(f.get("Pilar") or "").strip()
            met = _INV.get(f.get("Métrica"))
            if not texto and not met:
                continue
            p = {"id": ts.nuevo_id(), "texto": texto, "metrica": met, "op": f.get("Condición") or ">",
                 "valor": None if pd.isna(f.get("Valor")) else float(f.get("Valor"))}
            if not met:
                p["manual"] = f.get("Estado si la revisas tú") or "Va bien"
            pilares.append(p)
        nueva = dict(t)
        nueva.update({"posicion": posicion, "conviccion": conviccion, "horizonte": horizonte, "enunciado": enunciado.strip(),
                      "pilares": pilares, "riesgos": [x.strip() for x in riesgos.splitlines() if x.strip()],
                      "objetivo": objetivo or None, "stop": stop or None, "nombre": nombre})
        ts.guardar(ticker, nueva)
        st.session_state[f"editando_tesis_{ticker}"] = False
        st.toast("Tesis guardada", icon="📌")
        st.rerun()


def _alertas_tesis(ticker, nombre, t):
    alcista = t["posicion"] == "Alcista"
    if t.get("objetivo"):
        us.crear_alerta(ticker, nombre, "precio_mayor" if alcista else "precio_menor", float(t["objetivo"]))
    if t.get("stop"):
        us.crear_alerta(ticker, nombre, "precio_menor" if alcista else "precio_mayor", float(t["stop"]))
    st.toast("Alertas de objetivo y stop creadas", icon="🔔")


def _seccion_tesis(ticker: str, nombre: str, m: dict, r, precio, mon: str):
    t = ts.de(ticker)
    clave_ed = f"editando_tesis_{ticker}"
    if not us.cargado():
        st.info("Cargando tus datos guardados…")
        return
    if t is None and not st.session_state.get(clave_ed):
        with st.popover("📌 Mi tesis de inversión", type="tertiary", icon=":material/info:"):
            import glosario
            st.markdown(glosario.texto("tesis"))
        st.write("Apunta **por qué** sigues esta empresa y **qué tendría que pasar** para que dejes de creerlo. "
                 "La web comprobará tus pilares con los datos cada vez que vuelvas, te dirá si la tesis sigue "
                 "**intacta**, hay que **vigilarla** o se ha **roto**, y te recordará revisarla cada 3 meses.")
        if st.button("✍️ Escribir mi tesis", type="primary", key=f"nueva_tesis_{ticker}"):
            base = ts.vacia()
            base["pilares"] = sugerir(m, r)
            base["nombre"] = nombre
            st.session_state[f"_borrador_tesis_{ticker}"] = base
            st.session_state[clave_ed] = True
            st.rerun()
        return
    if st.session_state.get(clave_ed):
        _editor(ticker, nombre, t or st.session_state.get(f"_borrador_tesis_{ticker}") or ts.vacia(), m, r, precio, mon)
        return

    mk = ts.marcador(t, m, r)
    color = {"🟢": COLOR["Comprar"], "🟡": COLOR["Esperar"], "🔴": COLOR["Vender"]}.get(mk["salud"][:1], "#888")
    st.markdown(f"""
<div style="border-left:6px solid {color};padding:10px 16px;background:rgba(127,127,127,.06);border-radius:6px">
  <div style="font-size:13px;opacity:.75">📌 MI TESIS · {t['posicion'].upper()} · convicción {t.get('conviccion', '').lower()} · {t.get('horizonte', '')}</div>
  <div style="font-size:19px;font-weight:600;margin:4px 0">{t.get('enunciado') or '<i>(sin enunciado)</i>'}</div>
  <div style="font-size:14px">{mk['salud']} · {mk['ok']} de {mk['n']} pilares se cumplen · creada el {t.get('creada', '')} · revisada hace {mk['dias_sin_revisar'] or 0} días</div>
</div>""", unsafe_allow_html=True)
    if mk["toca_stop"]:
        st.error("⛔ El precio ha llegado a tu **precio de salida**: según tu propio plan, la tesis ha fallado.")
    elif mk["toca_objetivo"]:
        st.success("🎯 El precio ha llegado a tu **objetivo**. ¿Sigue teniendo recorrido o es momento de recoger beneficios?")
    if mk["revisar"]:
        st.warning(f"🧐 Hace {mk['dias_sin_revisar']} días que no revisas esta tesis. Conviene mirarla al menos cada trimestre, "
                   "aunque no haya pasado nada llamativo.")

    c1, c2, c3, c4 = st.columns(4)
    metrica(c1, "Precio", f"{f_num(precio)} {mon}" if precio else "—", clave="precio")
    metrica(c2, "Objetivo", f"{f_num(t['objetivo'])} {mon}" if t.get("objetivo") else "—",
            f_pct(mk["hasta_objetivo"]) if mk["hasta_objetivo"] is not None else None, clave="valor_justo")
    metrica(c3, "Stop", f"{f_num(t['stop'])} {mon}" if t.get("stop") else "—",
            f_pct(mk["hasta_stop"]) if mk["hasta_stop"] is not None else None, clave="stop", delta_color="off")
    if t.get("objetivo") and t.get("stop") and precio:
        gan, per = abs(t["objetivo"] - precio), abs(precio - t["stop"])
        metrica(c4, "Recompensa / riesgo", f"{gan / per:.1f} : 1".replace(".", ",") if per else "—", clave="recompensa_riesgo")

    st.markdown("#### 🧱 Marcador de pilares")
    filas = []
    for p in t.get("pilares", []):
        est, ahora = ts.evaluar_pilar(p, m, r)
        filas.append({"Estado": "✅" if est is True else "❌" if est is False else ("👀" if ahora == "Vigilar" else "❔"),
                      "Pilar": p.get("texto") or _ETIQ.get(p.get("metrica"), ""),
                      "Qué tiene que pasar": (f"{_ETIQ[p['metrica']]} {ts.OPERADORES[p.get('op', '>')]} "
                                              f"{ts.fmt_valor(p['metrica'], p.get('valor') or 0)}") if p.get("metrica") else "Lo revisas tú",
                      "Ahora": ahora})
    if filas:
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    else:
        st.caption("Sin pilares. Edita la tesis para añadir 3-5.")
    if t.get("riesgos"):
        st.markdown("#### ⚠️ Riesgos que la romperían\n" + "\n".join(f"- {x}" for x in t["riesgos"]))

    b1, b2, b3, b4 = st.columns(4)
    if b1.button("✏️ Editar tesis", key=f"ed_tesis_{ticker}", width="stretch"):
        st.session_state[clave_ed] = True
        st.rerun()
    if b2.button("✔️ Revisada hoy", key=f"rev_tesis_{ticker}", width="stretch",
                 help="Marca que la has repasado aunque no cambie nada"):
        ts.guardar(ticker, t)
        st.toast("Anotado: tesis revisada hoy", icon="✔️")
        st.rerun()
    b3.button("🔔 Alertas de objetivo y stop", key=f"al_tesis_{ticker}", width="stretch",
              disabled=not (t.get("objetivo") or t.get("stop")), on_click=_alertas_tesis, args=(ticker, nombre, t))
    with b4.popover("🗑️ Borrar tesis", width="stretch"):
        st.write("¿Seguro? Se borrará también el registro de novedades.")
        if st.button("Sí, borrar", key=f"del_tesis_{ticker}", type="primary"):
            ts.borrar(ticker)
            st.rerun()

    st.markdown("#### 📒 Registro de novedades")
    st.caption("Cada dato nuevo (resultados, cambio de directivos, movimiento de un competidor…) y si refuerza o "
               "debilita la tesis. Apunta también lo que va en contra: es lo que más enseña.")
    if t.get("registro"):
        icon = {"Refuerza": "⬆️ Refuerza", "Neutral": "➖ Neutral", "Debilita": "⬇️ Debilita"}
        st.dataframe(pd.DataFrame([{"Fecha": x["fecha"], "Novedad": x["dato"], "Efecto": icon.get(x["impacto"], x["impacto"]),
                                    "Pilar": x.get("pilar", ""), "Acción": x["accion"], "Convicción": x["conviccion"]}
                                   for x in t["registro"]]), hide_index=True, width="stretch")
    else:
        st.caption("Aún no has apuntado nada.")
    with st.expander("➕ Apuntar una novedad", expanded=not t.get("registro")):
        with st.form(f"form_novedad_{ticker}", clear_on_submit=True):
            c1, c2 = st.columns([3, 1])
            dato = c1.text_input("¿Qué ha pasado?", placeholder="Ej.: Resultados del 3T: ventas +12%, margen estable")
            fecha = c2.date_input("Fecha", format="DD/MM/YYYY")
            c1, c2, c3, c4 = st.columns(4)
            impacto = c1.selectbox("Efecto en la tesis", ts.IMPACTO)
            pilares_txt = ["(general)"] + [p.get("texto") or _ETIQ.get(p.get("metrica"), "") for p in t.get("pilares", [])]
            pilar = c2.selectbox("Pilar afectado", pilares_txt)
            accion = c3.selectbox("Qué haces", ts.ACCIONES)
            conv = c4.selectbox("Convicción ahora", ts.CONVICCION, index=ts.CONVICCION.index(t.get("conviccion", "Media")))
            if st.form_submit_button("➕ Añadir al registro") and dato.strip():
                t.setdefault("registro", []).insert(0, {"fecha": fecha.strftime("%Y-%m-%d"), "dato": dato.strip(), "impacto": impacto,
                                                        "pilar": "" if pilar == "(general)" else pilar, "accion": accion, "conviccion": conv})
                t["conviccion"] = conv
                ts.guardar(ticker, t)
                st.rerun()


def _seccion_eventos(ticker: str, nombre: str, e, mon: str):
    ev = eventos_empresa(ticker)
    import previa
    pv = previa.construir(ev, e.hist, e.hist["Close"].dropna().iloc[-1] if e.hist is not None and len(e.hist) else None)
    if pv is not None and pv["dias"] <= 60:
        with st.container(border=True):
            previa.mostrar(pv, e.sector, ts.de(ticker) if us.cargado() else None, mon, ticker)
    st.markdown("#### 📅 Próximos eventos")
    hoy = pd.Timestamp.today().normalize()
    filas = [dict(x, ticker=ticker, empresa=nombre) for x in ev["proximos"]]
    filas += [{"fecha": pd.Timestamp(x["fecha"]), "ticker": ticker, "empresa": nombre, "tipo": "Propio",
               "texto": x["texto"], "impacto": x["impacto"], "id": x["id"]} for x in us.eventos_de(ticker)]
    fed, bce = agenda.bancos_para(mon)
    filas += agenda.macro(fed, bce)
    filas = sorted([f for f in filas if hoy <= f["fecha"] <= hoy + pd.Timedelta(days=120)], key=lambda f: f["fecha"])
    if filas:
        st.dataframe(pd.DataFrame([{"Fecha": f["fecha"].strftime("%d/%m/%Y"), "Faltan": f"{(f['fecha'] - hoy).days} días",
                                    "Evento": f"{agenda.TIPO_ICONO.get(f['tipo'], '')} {f['texto']}",
                                    "Impacto": agenda.IMPACTO_ICONO.get(f["impacto"], f["impacto"])} for f in filas]),
                     hide_index=True, width="stretch")
    else:
        st.caption("Yahoo no tiene eventos anunciados para los próximos 4 meses.")
    cs = ev.get("consenso") or {}
    if (pv is None or pv["dias"] > 60) and cs.get("Earnings Average") is not None:
        txt = f"Para la próxima presentación, los analistas esperan un **beneficio por acción de {f_num(cs['Earnings Average'])}**"
        if cs.get("Earnings Low") is not None and cs.get("Earnings High") is not None:
            txt += f" (entre {f_num(cs['Earnings Low'])} y {f_num(cs['Earnings High'])})"
        if cs.get("Revenue Average"):
            txt += f" y **ventas de {f_num(cs['Revenue Average'] / 1e9)} mil millones**"
        st.info(txt + ". Si lo supera, suele subir; si se queda corto, suele caer.")

    propios = us.eventos_de(ticker)
    with st.expander("📌 Añadir un evento propio (junta, lanzamiento, decisión de un regulador…)"):
        with st.form(f"form_evento_{ticker}", clear_on_submit=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            f = c1.date_input("Fecha", format="DD/MM/YYYY", key=f"ev_f_{ticker}")
            texto = c2.text_input("Evento", placeholder="Ej.: Día del inversor, nuevo plan estratégico")
            imp = c3.selectbox("Impacto", ["Alto", "Medio", "Bajo"], index=1)
            if st.form_submit_button("➕ Añadir") and texto.strip():
                us.crear_evento(ticker, f.strftime("%Y-%m-%d"), texto.strip(), imp)
                st.rerun()
        for x in propios:
            c1, c2 = st.columns([6, 1])
            c1.write(f"{x['fecha']} · {x['texto']} · {agenda.IMPACTO_ICONO.get(x['impacto'], '')}")
            c2.button("🗑️", key=f"del_ev_{x['id']}", on_click=us.borrar_evento, args=(x["id"],))

    st.markdown("#### 📊 Cómo le fue en presentaciones anteriores")
    df = agenda.historial_resultados(ev.get("resultados"), e.hist)
    if df.empty:
        st.caption("Yahoo no tiene el historial de previsiones de beneficio de esta empresa (es habitual fuera de EE. UU.).")
        return
    st.write(agenda.resumen_historial(df))
    graf = df.sort_index().tail(12)
    fig = go.Figure()
    fig.add_bar(x=graf.index.strftime("%b %y"), y=graf["sorpresa"], name="Sorpresa del beneficio (%)",
                marker_color=[COLOR["Comprar"] if (v or 0) >= 0 else COLOR["Vender"] for v in graf["sorpresa"]],
                hovertemplate="%{x}: %{y:.1f}%<extra>sorpresa</extra>")
    fig.add_scatter(x=graf.index.strftime("%b %y"), y=graf["reaccion"] * 100, name="Reacción del precio (%)", mode="markers+lines",
                    marker=dict(size=9, color="#4c78a8"), line=dict(dash="dot"), hovertemplate="%{x}: %{y:.1f}%<extra>reacción</extra>")
    fig.add_hline(y=0, line_color="#999", line_width=1)
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.12),
                      yaxis_title="%", separators=",.")
    graficos.mostrar(fig)
    st.dataframe(pd.DataFrame({"Fecha": df.index.strftime("%d/%m/%Y"), "BPA esperado": df["esperado"], "BPA real": df["real"],
                               "Sorpresa": df["sorpresa"] / 100, "Reacción del precio": df["reaccion"]}),
                 hide_index=True, width="stretch", column_config={
                     "BPA esperado": st.column_config.NumberColumn(format="%.2f"),
                     "BPA real": st.column_config.NumberColumn(format="%.2f"),
                     "Sorpresa": st.column_config.NumberColumn(format="percent", help="Cuánto mejor (o peor) fue el beneficio por acción que lo que esperaban los analistas"),
                     "Reacción del precio": st.column_config.NumberColumn(format="percent", help="Cierre del día siguiente frente al cierre anterior a la presentación"),
                 })


def pestaña(ticker: str, nombre: str, e, m: dict, r, mon: str):
    _seccion_tesis(ticker, nombre, m, r, m.get("precio"), mon)
    st.divider()
    _seccion_eventos(ticker, nombre, e, mon)
