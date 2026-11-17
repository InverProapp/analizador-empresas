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
    st.title("🔎 Analizar empresa")
    st.write("Escribe el nombre o el ticker de una empresa en la barra lateral (a la izquierda) para empezar.")
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
import glosario
import tesis as _ts
import usuario as us
from comun import abrir_empresa, cabecera, conclusion


def frase_resumen() -> str:
    """El veredicto explicado en una o dos frases normales."""
    que = {"Comprar": "El modelo la ve **para comprar**", "Esperar": "El modelo dice **esperar**",
           "Vender": "El modelo la ve **para vender o evitar**"}.get(r.veredicto, "Faltan datos para dar un veredicto")
    fuertes = [p.lower() for p in sc.PILARES if r.pilares[p].nota is not None and r.pilares[p].nota >= 65 and p != "Analistas"]
    flojos = [p.lower() for p in sc.PILARES if r.pilares[p].nota is not None and r.pilares[p].nota < 45 and p != "Analistas"]

    def lista(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]
    partes = []
    if fuertes:
        partes.append(f"es fuerte en {lista(fuertes)}")
    if flojos:
        partes.append(("pero " if fuertes else "") + f"flojea en {lista(flojos)}")
    texto = que + (": " + " ".join(partes) if partes else "") + "."
    if r.valor_justo and precio:
        dif = precio / r.valor_justo - 1
        if dif > 0.05:
            texto += f" Hoy cotiza un **{dif * 100:.0f}% por encima** de su valor justo estimado."
        elif dif < -0.05:
            texto += f" Hoy cotiza con un **{-dif * 100:.0f}% de descuento** sobre su valor justo estimado."
        else:
            texto += " Hoy cotiza **cerca** de su valor justo estimado."
        if r.precio_compra and precio <= r.precio_compra:
            texto += " Está **dentro de la zona de compra**."
    if r.veredicto != r.veredicto_bruto:
        texto += f" (Por nota saldría {r.veredicto_bruto}, pero las alertas de riesgo lo limitan.)"
    return texto


c_tit, c_acc = st.columns([2.6, 2.4], vertical_alignment="center")
with c_tit:
    st.title(e.nombre)
    sector_es = sc.SECTORES_ES.get(e.sector, e.sector)
    detalles = [f"**{e.ticker}**", sector_es, e.info.get("industry"), e.info.get("country"), e.info.get("exchange"), f"moneda {mon}"]
    st.caption(" · ".join(x for x in detalles if x))
with c_acc:
    a1, a2, a3 = st.columns(3)
    fav = us.es_favorito(ticker)
    a1.button("⭐ En mi lista" if fav else "☆ Seguir", key="btn_fav", type="primary" if fav else "secondary",
              on_click=us.alternar_favorito, args=(ticker, e.nombre, precio), disabled=not us.cargado(), width="stretch",
              help="Quitar de tu lista" if fav else "Añadir a tu lista de favoritas (se guarda en este navegador)")
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
        st.caption("Se comprueban cada vez que abres la web (precios con ~15 min de retraso) y se guardan en este navegador. "
                   "Todas, en ⭐ Mi lista y alertas.")
    if a3.button("🎯 Simular", width="stretch", help="Probar compras y ventas con el histórico de esta empresa"):
        abrir_empresa(ticker, "vistas/simulador.py")

# 1. La respuesta ----------------------------------------------------------------
col_v, col_t, col_p = st.columns([1.05, 1.75, 1.2], gap="medium")
with col_v:
    color = COLOR[r.veredicto]
    st.markdown(
        f"""<div style="border-radius:14px;padding:18px 14px;background:{color};color:white;text-align:center">
        <div style="font-size:13px;opacity:.85;letter-spacing:.08em">VEREDICTO</div>
        <div style="font-size:42px;font-weight:800;line-height:1.1">{r.veredicto.upper()}</div>
        <div style="font-size:22px;font-weight:700;margin-top:2px">{(r.nota or 0):.0f}<span style="font-size:14px;opacity:.85">/100</span></div>
        <div style="font-size:12px;opacity:.9">Confianza {r.confianza.lower()} · datos del {r.cobertura * 100:.0f}% de las métricas</div>
        </div>""", unsafe_allow_html=True)
    with st.popover("¿Qué significa?", type="tertiary", icon=":material/info:"):
        st.markdown(glosario.texto("veredicto"))
        st.markdown(glosario.texto("nota"))
with col_t:
    st.markdown("**En pocas palabras**")
    st.markdown(frase_resumen())
    k1, k2, k3 = st.columns(3)
    metrica(k1, "Precio", f"{f_num(precio)} {mon}", f_pct(var_dia, 2) if var_dia is not None else None, "precio")
    metrica(k2, "Valor justo", f"{f_num(r.valor_justo)} {mon}" if r.valor_justo else "—", clave="valor_justo",
            delta=f"{f_pct(r.valor_justo / precio - 1)} vs precio" if r.valor_justo and precio else None)
    metrica(k3, "Zona de compra", f"{f_num(r.precio_compra)} {mon}" if r.precio_compra else "—", clave="zona_compra")
with col_p:
    st.markdown("**Nota por pilar**")
    barras = ""
    for p in sc.PILARES:
        n = r.pilares[p].nota
        ancho = 0 if n is None else max(n, 2)
        barras += (f"<div style='display:flex;align-items:center;gap:8px;font-size:13px;margin:3px 0'>"
                   f"<div style='width:112px;color:#555'>{p}</div>"
                   f"<div style='flex:1;background:#eee;border-radius:4px;height:10px'>"
                   f"<div style='width:{ancho}%;background:{color_nota(n) if n is not None else '#ccc'};height:10px;border-radius:4px'></div></div>"
                   f"<div style='width:44px;text-align:right'>{'—' if n is None else f'{n:.0f}'}</div></div>")
    st.markdown(barras, unsafe_allow_html=True)
    st.caption("Detalle de cada pilar en la pestaña *Resumen*.")

avisos = list(r.alertas)
for a in avisos:
    st.warning(a, icon="⚠️")
if n_cumplen:
    st.success(f"🔔 {n_cumplen} de tus alertas de esta empresa se cumple{'n' if n_cumplen > 1 else ''} ahora.")
_t = _ts.de(ticker) if us.cargado() else None
if _t:
    _mk = _ts.marcador(_t, m, r)
    st.info(f"📌 **Tu tesis {_t['posicion'].lower()}**: {_mk['salud']} · se cumplen {_mk['ok']} de {_mk['n']} pilares"
            + (" · 🧐 toca revisarla" if _mk["revisar"] else "") + " — detalle en la pestaña **📌 Mi tesis**.")

# 2. Cómo cotiza -------------------------------------------------------------------
st.markdown("#### 📈 Cómo cotiza")
k1, k2, k3, k4 = st.columns(4)
metrica(k1, "Capitalización", f_dinero(m.get("market_cap"), mon), clave="capitalizacion")
metrica(k2, "PER", f_x(m.get("per")), clave="per")
metrica(k3, "Rent. dividendo", f_pct(m.get("rent_dividendo"), 2), clave="rent_dividendo")
metrica(k4, "Beta", f_num(m.get("beta")), clave="beta")

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
    texto_nota = st.text_area("Ideas, dudas, a qué precio entrarías…", value=us.nota(ticker), key=f"nota_{ticker}",
                              height=120, label_visibility="collapsed", placeholder="Ideas, dudas, a qué precio entrarías… (para una tesis con pilares que se comprueban solos, usa la pestaña 📌 Mi tesis)")
    st.button("💾 Guardar nota", on_click=lambda: us.guardar_nota(ticker, st.session_state[f"nota_{ticker}"]), disabled=not us.cargado())
    st.caption("Se guarda en este navegador.")

if e.errores:
    with st.expander("Avisos de descarga"):
        for err in e.errores:
            st.caption(err)

# ---------------------------------------------------------------------------
# Pestañas: primero el análisis, luego lo tuyo y al final cómo se calcula
# ---------------------------------------------------------------------------
# Análisis con IA desactivado de momento: pon MOSTRAR_IA = True para recuperarlo (requiere API key de Anthropic)
MOSTRAR_IA = False
nombres_tabs = (["🧭 Resumen", "💶 Valoración", "📊 Finanzas", "📉 Gráfico", "💸 Dividendos", "🆚 Competencia"]
                + (["🤖 IA"] if MOSTRAR_IA else []) + ["📅 Resultados", "📌 Mi tesis", "ℹ️ Cómo se calcula"])
tabs = dict(zip(nombres_tabs, st.tabs(nombres_tabs)))
T_RES, T_VAL, T_FIN, T_TEC, T_DIV, T_COMP = (tabs[n] for n in nombres_tabs[:6])
T_EVE, T_TESIS, T_MET = (tabs[n] for n in nombres_tabs[-3:])
T_IA = tabs.get("🤖 IA")

# Resumen ---------------------------------------------------------------------
with T_RES:
    conclusion(frase_resumen())
    cpos, cneg = st.columns(2)
    with cpos:
        st.markdown("#### ✅ Puntos fuertes")
        if not r.positivos:
            st.caption("Ningún punto especialmente fuerte.")
        for pilar, i in r.positivos:
            st.markdown(f"- **{i.nombre}**: {f_item(i)} <span style='color:{GRIS}'>({pilar})</span>", unsafe_allow_html=True)
    with cneg:
        st.markdown("#### ❌ Puntos débiles")
        if not r.negativos:
            st.caption("Ningún punto especialmente débil.")
        for pilar, i in r.negativos:
            st.markdown(f"- **{i.nombre}**: {f_item(i)} <span style='color:{GRIS}'>({pilar})</span>", unsafe_allow_html=True)

    st.markdown("#### 🧱 Nota de cada pilar y su peso")
    st.caption("Cada pilar se puntúa de 0 a 100. La nota global es la media ponderada con estos pesos "
               "(se cambian en ⚙️ Ajustes del modelo, en la barra lateral).")
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
    fig.update_layout(xaxis=dict(range=[0, 115]), height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

    st.markdown("#### 🔍 Todas las métricas, por pilar")
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
from comun import historico

ref = sc.SECTORES.get(e.sector, sc.SECTOR_DEFECTO)
hm = historico(ticker)
SENTIDO_HIST = {"PER": True, "Precio/Valor contable": True, "Precio/Ventas": True, "EV/EBITDA": True, "Rentabilidad FCF": False}


def tabla_historia():
    filas = []
    if hm.empty:
        return pd.DataFrame()
    for col, bajo_barato in SENTIDO_HIST.items():
        s_ = hm[col].dropna()
        if len(s_) < 10:
            continue
        actual = s_.iloc[-1]
        barato_que = (s_ > actual).mean() if bajo_barato else (s_ < actual).mean()
        filas.append({"Múltiplo": col, "Hoy": actual, "Mediana": s_.median(), "Mínimo": s_.min(), "Máximo": s_.max(),
                      "Más barata que el % del periodo": barato_que})
    return pd.DataFrame(filas)


def juicio_sector(v, rf):
    if v is None or rf is None or v <= 0:
        return None
    return "barato" if v <= rf[0] else "caro" if v >= rf[1] else "en la media"


with T_VAL:
    th = tabla_historia()
    partes = []
    if r.valor_justo and precio:
        dif = precio / r.valor_justo - 1
        partes.append(f"Su **valor justo estimado** es {f_num(r.valor_justo)} {mon}: el precio está un **{abs(dif) * 100:.0f}% "
                      f"{'por encima' if dif > 0 else 'por debajo'}**.")
    j_per = juicio_sector(m.get("per"), ref.get("per"))
    if j_per:
        partes.append(f"Frente a su sector, su PER ({f_x(m.get('per'))}) está **{j_per}**.")
    if not th.empty:
        mb = th["Más barata que el % del periodo"].mean()
        partes.append("Frente a su propia historia reciente cotiza " +
                      ("**barata**." if mb >= 0.7 else "**cara**." if mb <= 0.3 else "en **zona media**."))
    if partes:
        conclusion(" ".join(partes))

    st.markdown("#### 🎯 Precio frente a lo que podría valer")
    st.caption("El valor justo es la mediana de tres métodos (DCF, Graham y objetivo de los analistas). "
               "La zona de compra deja un margen de seguridad por si el cálculo es optimista.")
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


    st.markdown("#### 🏷️ Frente a su sector")
    filas = [("PER", m.get("per"), ref["per"]), ("EV/EBITDA", m.get("ev_ebitda"), ref["ev"]),
             ("Precio/Valor contable", m.get("p_vc"), ref["pvc"])]
    st.dataframe(pd.DataFrame([{"Múltiplo": n, "Empresa": f_x(v), "Barato si ≤": f_x(rf[0]) if rf else "—",
                                "Caro si ≥": f_x(rf[1]) if rf else "—", "Juicio": (juicio_sector(v, rf) or "—").capitalize()}
                               for n, v, rf in filas]), hide_index=True, width="stretch")
    st.caption(f"Referencias para el sector **{sc.SECTORES_ES.get(e.sector, e.sector)}**: lo que es barato en un sector "
               "puede ser caro en otro. Para compararla con empresas concretas, usa la pestaña 🆚 Competencia.")

    st.markdown("#### 🕰️ Frente a su propia historia")
    if hm.empty or th.empty:
        st.caption("No hay suficientes datos (cuentas anuales en la misma moneda que la cotización) para reconstruir su histórico.")
    else:
        vista_th = th.copy()
        for c_ in ("Hoy", "Mediana", "Mínimo", "Máximo"):
            vista_th[c_] = [f_pct(v) if mult == "Rentabilidad FCF" else f_x(v) for mult, v in zip(th["Múltiplo"], th[c_])]
        st.dataframe(vista_th, hide_index=True, width="stretch", column_config={
            "Más barata que el % del periodo": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")})
        elegido = st.segmented_control("Ver la evolución de", [c for c in SENTIDO_HIST if hm[c].notna().sum() >= 10],
                                       default="PER" if hm["PER"].notna().sum() >= 10 else None, key="hist_multiplo")
        if elegido:
            s_ = hm[elegido].dropna()
            fig = go.Figure()
            fig.add_scatter(x=s_.index, y=s_, mode="lines", name=elegido, line=dict(color=AZUL, width=2))
            fig.add_hline(y=s_.median(), line=dict(color=GRIS, dash="dash"), annotation_text="mediana")
            fig.add_scatter(x=[s_.index[-1]], y=[s_.iloc[-1]], mode="markers", marker=dict(size=10, color="#222"), name="hoy")
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                              yaxis_tickformat=".1%" if elegido == "Rentabilidad FCF" else None)
            st.plotly_chart(fig, width="stretch")
        st.caption(f"Calculado cada semana con el precio de ese día y las últimas cuentas anuales publicadas "
                   f"({hm.index[0]:%m/%Y} – {hm.index[-1]:%m/%Y}). Yahoo solo ofrece ~4 ejercicios, por eso el periodo es corto.")

    st.markdown("#### 🧮 Cálculo del DCF (descuento de flujos de caja)")
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
                   "Al valor de la empresa se le resta la deuda neta. Los supuestos se cambian en ⚙️ Ajustes del modelo (barra lateral).")
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
        with st.expander("¿Y si los supuestos cambian? Tabla de sensibilidad"):
            st.caption("Valor por acción con otras tasas de descuento y crecimientos. Verde: más de un 15% sobre el precio · "
                       "rojo: por debajo del precio.")
            st.dataframe(sens.style.format(lambda v: f_num(v)).map(pintar), width="stretch")


    st.markdown("#### 📋 Todos los múltiplos")
    c1, c2, c3, c4 = st.columns(4)
    metrica(c1, "PER", f_x(m.get("per")), clave="per")
    metrica(c2, "PER futuro", f_x(m.get("per_fwd")), clave="per_fwd")
    metrica(c3, "EV/EBITDA", f_x(m.get("ev_ebitda")), clave="ev_ebitda")
    metrica(c4, "Precio / valor contable", f_x(m.get("p_vc")), clave="p_vc")
    metrica(c1, "PEG", f_x(m.get("peg"), 2), clave="peg")
    metrica(c2, "Precio / ventas", f_x(m.get("p_ventas")), clave="p_ventas")
    metrica(c3, "Rentabilidad FCF", f_pct(m.get("fcf_yield")), clave="fcf_yield")
    metrica(c4, "Valor empresa (EV)", f_dinero(m.get("ev"), mon), clave="ev")

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
    partes = []
    if "Ingresos" in df1 and df1["Ingresos"].dropna().size >= 2:
        ing = df1["Ingresos"].dropna()
        n_a = ing.index[-1] - ing.index[0]
        if n_a > 0 and ing.iloc[0] > 0 and ing.iloc[-1] > 0:
            cagr = (ing.iloc[-1] / ing.iloc[0]) ** (1 / n_a) - 1
            partes.append(f"Las ventas {'crecen' if cagr > 0.01 else 'caen' if cagr < -0.01 else 'están estancadas'} "
                          f"(**{f_pct(cagr)} al año** entre {ing.index[0]} y {ing.index[-1]}).")
        if "Beneficio neto" in df1:
            mg_ = (df1["Beneficio neto"] / df1["Ingresos"]).dropna()
            if len(mg_) >= 2:
                cambio = mg_.iloc[-1] - mg_.iloc[0]
                partes.append(f"El margen neto es del **{f_pct(mg_.iloc[-1])}** y "
                              + ("**mejora**." if cambio > 0.01 else "**empeora**." if cambio < -0.01 else "se mantiene **estable**."))
    dne = m.get("deuda_neta_ebitda")
    if dne is not None:
        partes.append("Deuda " + ("**muy baja o caja neta**" if dne <= 0.5 else "**controlada**" if dne < 2.5 else
                                  "**elevada**" if dne < 4 else "**muy elevada**") + f" ({f_x(dne)} su EBITDA).")
    if m.get("piotroski") is not None:
        pio = m["piotroski"]
        partes.append(f"Salud contable (Piotroski) **{f_num(pio, 0)}/9**: " + ("buena." if pio >= 7 else "normal." if pio >= 4 else "débil."))
    if partes:
        conclusion(" ".join(partes))
    if df1.empty:
        st.info("Yahoo no tiene estados financieros anuales para este valor.")
    else:
        st.markdown(f"#### 💰 Ventas, beneficios y caja ({e.moneda_fin})")
        fig = go.Figure()
        for col, colr in zip(df1.columns, [GRIS, "#7aa6f0", AZUL, COLOR["Comprar"]]):
            fig.add_bar(x=df1.index.astype(str), y=df1[col], name=col, marker_color=colr)
        fig.update_layout(barmode="group", height=360, xaxis=dict(type="category"), margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")

        if "Ingresos" in df1:
            st.markdown("#### 📐 Márgenes: qué parte de cada venta se queda")
            mg = pd.DataFrame(index=df1.index)
            for col, nombre in (("EBITDA", "Margen EBITDA"), ("Beneficio neto", "Margen neto"), ("Flujo de caja libre", "Margen FCF")):
                if col in df1:
                    mg[nombre] = df1[col] / df1["Ingresos"]
            fig = go.Figure()
            for col in mg:
                fig.add_scatter(x=mg.index.astype(str), y=mg[col], name=col, mode="lines+markers")
            fig.update_layout(height=300, yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"),
                              xaxis=dict(type="category"))
            st.plotly_chart(fig, width="stretch")

    df2 = a_df(["Patrimonio neto", "Deuda total", "Caja"])
    if not df2.empty:
        st.markdown("#### 🏦 Balance: lo que tiene y lo que debe")
        fig = go.Figure()
        for col, colr in zip(df2.columns, [AZUL, COLOR["Vender"], COLOR["Comprar"]]):
            fig.add_bar(x=df2.index.astype(str), y=df2[col], name=col, marker_color=colr)
        fig.update_layout(barmode="group", height=320, xaxis=dict(type="category"), margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🩺 Indicadores de salud financiera")
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
        st.markdown(f"#### ✅ Piotroski: {f_num(m.get('piotroski'), 0)}/9")
        for nombre, ok in m.get("piotroski_detalle", []):
            st.markdown(f"{'✅' if ok else '❌' if ok is False else '➖'} {nombre}")
        st.caption("➖ = sin datos. Si faltan criterios, la nota se escala a 9.")

# Técnico ---------------------------------------------------------------------
with T_TEC:
    t = datos.tecnicos(e.hist)
    if t.empty:
        st.info("Sin histórico de precios.")
    else:
        partes = []
        sma200, sobre = m.get("sobre_sma200"), m.get("sobre_sma200")
        u = t.iloc[-1]
        if pd.notna(u.get("SMA200")) and pd.notna(u.get("SMA50")):
            alc = u["Close"] > u["SMA200"] and u["SMA50"] > u["SMA200"]
            baj = u["Close"] < u["SMA200"] and u["SMA50"] < u["SMA200"]
            partes.append("Tendencia **" + ("alcista" if alc else "bajista" if baj else "indefinida") + "**: el precio está "
                          f"{'por encima' if u['Close'] > u['SMA200'] else 'por debajo'} de su media de 200 sesiones "
                          f"({f_pct(sobre)}).")
        if m.get("rsi") is not None:
            rsi = m["rsi"]
            partes.append(f"RSI {rsi:.0f}: " + ("**sobrecompra** (ha subido mucho y rápido)." if rsi >= 70 else
                                                 "**sobreventa** (ha caído mucho y rápido)." if rsi <= 30 else "zona **neutral**."))
        if m.get("drawdown_actual") is not None:
            partes.append(f"Está un {f_pct(m['drawdown_actual'])} respecto a su máximo.")
        if partes:
            conclusion(" ".join(partes))
        c = st.columns(6)
        for col, (nombre, val) in zip(c, [("1 mes", m.get("rent_1m")), ("3 meses", m.get("rent_3m")), ("6 meses", m.get("rent_6m")),
                                           ("1 año", m.get("rent_1a")), ("3 años", m.get("rent_3a")), ("Volatilidad anual", m.get("volatilidad"))]):
            metrica(col, nombre, f_pct(val), clave="volatilidad" if nombre.startswith("Volatilidad") else None)
        st.markdown("#### 🕯️ Gráfico con indicadores")
        st.caption("Velas = precio de cada día · naranja y morada = medias de 50 y 200 sesiones · punteadas = bandas de Bollinger · "
                   "debajo: volumen, RSI y MACD. Para dibujar y probar estrategias, usa el 🎯 Simulador.")
        rango = st.segmented_control("Periodo", ["6M", "1A", "2A", "5A"], default="1A", key="tec_periodo") or "1A"
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

        st.markdown("#### 📏 Indicadores")
        c = st.columns(6)
        metrica(c[0], "RSI (14)", f_num(m.get("rsi"), 0), clave="rsi")
        metrica(c[1], "vs media 200", f_pct(m.get("sobre_sma200")), clave="medias")
        c[2].metric("Máx. 52 sem.", f_num(m.get("max_52s")))
        c[3].metric("Mín. 52 sem.", f_num(m.get("min_52s")))
        metrica(c[4], "Caída desde máximos", f_pct(m.get("drawdown_actual")), clave="drawdown")
        metrica(c[5], "Peor caída (5a)", f_pct(m.get("max_drawdown")), clave="drawdown")

# Dividendos ------------------------------------------------------------------
with T_DIV:
    rd = m.get("rent_dividendo")
    if not rd:
        conclusion("No paga dividendo (o no ha pagado en los últimos 12 meses).")
    else:
        po = m.get("payout")
        txt = f"Paga un **{f_pct(rd, 2)}** al año"
        if po is not None:
            txt += (f" y reparte el **{f_pct(po, 0)}** de su beneficio: " +
                    ("margen amplio para mantenerlo." if po < 0.6 else "algo justo." if po < 0.9 else "**reparte casi todo o más de lo que gana**, ojo."))
        else:
            txt += "."
        if m.get("anos_sin_recorte"):
            txt += f" Lleva **{m['anos_sin_recorte']} años sin recortarlo**"
            txt += f" y lo ha subido un {f_pct(m.get('cagr_dividendo_5a'))} al año." if m.get("cagr_dividendo_5a") else "."
        conclusion(txt)
    c = st.columns(4)
    metrica(c[0], "Rentabilidad (12 m)", f_pct(m.get("rent_dividendo"), 2), clave="rent_dividendo")
    metrica(c[1], "Payout", f_pct(m.get("payout"), 0), clave="payout")
    c[2].metric("Crecimiento anual (5 años)", f_pct(m.get("cagr_dividendo_5a")))
    c[3].metric("Años sin recortar", m.get("anos_sin_recorte", 0))
    da = m.get("div_anuales")
    if da is None or len(da) == 0:
        st.info("Esta empresa no ha pagado dividendos en el periodo disponible.")
    else:
        fig = go.Figure(go.Bar(x=da.index.astype(str), y=da.values, marker_color=AZUL,
                               text=[f_num(x, 3) for x in da.values], textposition="outside"))
        st.markdown(f"#### 📅 Dividendo por acción y año ({mon})")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10), xaxis=dict(type="category"))
        st.plotly_chart(fig, width="stretch")


# Competidores ----------------------------------------------------------------
with T_COMP:
    from comun import COLUMNAS_ESCANER, cargar_varias, config_columnas, fila_resumen
    sugeridos = competidores(ticker)
    st.markdown("Compara la empresa con su competencia **usando exactamente los mismos criterios**. "
                "Para ver el sector entero, usa la sección 🏭 Sectores.")
    if sugeridos:
        st.caption("Sugeridos: las mayores empresas de su industria según Yahoo (suele tirar hacia EE. UU.). "
                   "Añade o quita los que quieras, por ejemplo competidores europeos.")
    else:
        st.caption("Yahoo no sugiere competidores para esta empresa: escríbelos tú.")
    lista_peers = st.text_input("Competidores (tickers separados por comas)", value=", ".join(sugeridos), key=f"peers_{ticker}")
    peers = [x.strip().upper() for x in lista_peers.split(",") if x.strip() and x.strip().upper() != ticker][:12]
    clave = f"comp_{ticker}_{','.join(peers)}"
    if st.button("🆚 Comparar", type="primary", disabled=not peers):
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
        yo = comp[comp["Ticker"] == ticker].iloc[0]
        otros = comp[comp["Ticker"] != ticker]
        puesto = list(comp["Ticker"]).index(ticker) + 1
        criterios = [("PER", False, "más barata por PER"), ("EV/EBITDA", False, "más barata por EV/EBITDA"),
                     ("ROE", True, "más rentable (ROE)"), ("Margen op.", True, "con más margen"),
                     ("Crec. ingresos", True, "que más crece"), ("Deuda neta/EBITDA", False, "con menos deuda")]
        frases = []
        for col, alto_mejor, nombre in criterios:
            if pd.isna(yo.get(col)) or otros[col].dropna().empty:
                continue
            o = otros[col].dropna()
            mejor_que = (o < yo[col]).sum() if alto_mejor else (o > yo[col]).sum()
            frases.append(f"- {nombre.capitalize()}: mejor que **{mejor_que} de {len(o)}**")
        conclusion(f"Con la misma vara de medir, **{e.nombre}** queda **{puesto}ª de {len(comp)}** por nota global.")
        if frases:
            st.markdown("\n".join(frases))
        fig = go.Figure(go.Bar(x=comp["Ticker"], y=comp["Nota"],
                               marker_color=["#222" if t == ticker else COLOR.get(v, GRIS) for t, v in zip(comp["Ticker"], comp["Veredicto"])],
                               text=comp["Veredicto"], textposition="outside"))
        fig.update_layout(height=300, yaxis=dict(range=[0, 105], title="Nota"), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(comp, hide_index=True, width="stretch", column_config=config_columnas(),
                     column_order=[c_ for c_ in COLUMNAS_ESCANER if c_ in comp])

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

# Resultados y eventos / Mi tesis ----------------------------------------------------
import tesis_ui

with T_EVE:
    tesis_ui._seccion_eventos(ticker, e.nombre, e, mon)
with T_TESIS:
    tesis_ui._seccion_tesis(ticker, e.nombre, m, r, precio, mon)

# Cómo se calcula ---------------------------------------------------------------
with T_MET:
    st.markdown(f"""
#### 🧭 Cómo se llega al veredicto
1. **Cada métrica se puntúa de 0 a 100** entre un valor "malo" y uno "bueno". Los umbrales de PER, EV/EBITDA,
   P/VC, margen operativo, ROE y deuda cambian **según el sector** (un PER de 20 es barato en tecnología y caro en energía).
2. Las métricas se agrupan en **7 pilares**: valoración, calidad, salud financiera, crecimiento, dividendo, técnico y analistas.
   Si un pilar no tiene datos (p. ej. no paga dividendo), su peso se reparte entre los demás.
3. **Nota global** = media ponderada de los pilares (pesos en ⚙️ Ajustes del modelo, barra lateral).
4. **Veredicto**: Comprar si la nota es ≥ {u_comprar}, Vender si es < {u_vender}, Esperar en medio.
5. **Alertas que limitan**: aunque la nota dé Comprar, se baja a Esperar si hay riesgo de quiebra (Altman Z < 1,81),
   Piotroski ≤ 2, quema de caja con deuda alta, tendencia bajista fuerte (opcional) o pocos datos.
6. **Valor justo** = mediana de DCF, número de Graham y precio objetivo de analistas (si hay ≥ 3).
   **Zona de compra** = valor justo menos el margen de seguridad.

#### 🗂️ Qué hay en cada pestaña
- **🧭 Resumen**: puntos fuertes y débiles y la nota de cada pilar.
- **💶 Valoración**: si está cara o barata frente a su valor, su sector y su propia historia.
- **📊 Finanzas**: ventas, beneficios, márgenes, deuda y salud contable.
- **📉 Gráfico**: tendencia, medias, RSI, MACD y volumen.
- **💸 Dividendos** · **🆚 Competencia**: lo que paga y cómo queda frente a sus rivales.
- **📅 Resultados**: próximas fechas, previa con escenarios e historial de sorpresas.
- **📌 Mi tesis**: tu razón para seguirla, comprobada con datos.

#### ⚠️ Particularidades
- **Bancos y aseguradoras**: no se usan EV/EBITDA, DCF ni deuda/EBITDA (la deuda es su negocio). Pesa más el P/VC y el ROE.
- **Inmobiliarias**: más tolerancia a la deuda y más peso al P/VC; no se usa Altman Z.
- Si la empresa **reporta en otra moneda** (ADRs, algunas europeas en EE. UU.), se omiten DCF, Graham y Altman.

#### 🚧 Limitaciones
- Datos de Yahoo Finance: gratuitos pero no auditados; pueden faltar o venir con errores, sobre todo en bolsas pequeñas.
- El modelo es mecánico: no sabe nada de noticias, gestión, ventajas competitivas ni del ciclo del sector.
- Es una herramienta de apoyo para tu propio análisis, **no una recomendación de inversión**.
""")
    with st.expander("📖 Glosario: todas las definiciones"):
        st.caption("También puedes pinchar en cualquier dato con el icono ⓘ para ver su definición.")
        st.markdown("\n".join(f"- **{t}**: {que}" + (f" {como}" if como else "") for t, que, como in glosario.G.values()))
