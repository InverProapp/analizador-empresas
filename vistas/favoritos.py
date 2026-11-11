"""Sección Mi lista: favoritos, alertas y notas del usuario."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import scoring as sc
import usuario as us
from comun import COLOR, abrir_empresa, ajustes, analizar, cargar_opcional, f_num, f_pct

st.sidebar.title("⭐ Mi lista")
aj = ajustes()

st.title("⭐ Mi lista y alertas")
st.caption("Tus favoritos, alertas y notas se guardan **en este navegador**: cada persona que use la web tiene los suyos. "
           "No se ven desde otro navegador o dispositivo.")

if not us.cargado():
    st.info("Cargando tus datos guardados…")
    st.stop()

d = us.datos()
favs, alertas, notas = d["favoritos"], d["alertas"], d["notas"]
if not favs and not alertas and not notas:
    st.info("Todavía no tienes nada guardado. En **🔎 Analizar empresa** pulsa **☆ Añadir a favoritos** para seguir una empresa, "
            "o **🔔 Alertas** para que te avise cuando el precio llegue a donde quieras.")
    st.stop()


def analisis(tk):
    e = cargar_opcional(tk)
    if e is None:
        raise ValueError("sin datos")
    _, m, r = analizar(tk, aj, e)
    return m, r


# ---------------------------------------------------------------------------
# Favoritos
# ---------------------------------------------------------------------------
st.subheader(f"⭐ Favoritos ({len(favs)})")
if favs:
    filas = []
    barra = st.progress(0.0, text="Actualizando precios…")
    for k, (tk, info) in enumerate(favs.items()):
        h = us.precios_recientes(tk)
        precio = float(h["Close"].dropna().iloc[-1]) if not h.empty else None
        previo = float(h["Close"].dropna().iloc[-2]) if len(h) > 1 else None
        fila = {"Ticker": tk, "Empresa": info.get("nombre", tk), "Precio": precio,
                "Hoy": (precio / previo - 1) if precio and previo else None,
                "Desde que la añadí": (precio / info["precio"] - 1) if precio and info.get("precio") else None,
                "Añadida": info.get("añadido", "")}
        try:
            m, r = analisis(tk)
            fila.update({"Veredicto": r.veredicto, "Nota": r.nota,
                         "vs zona de compra": (precio / r.precio_compra - 1) if precio and r.precio_compra else None})
        except Exception:
            fila.update({"Veredicto": "—", "Nota": None, "vs zona de compra": None})
        n_al = [a for a in alertas if a["ticker"] == tk]
        fila["Alertas"] = f"{sum(1 for a in n_al if a.get('disparada'))} cumplidas de {len(n_al)}" if n_al else ""
        fila["Nota personal"] = "📝" if notas.get(tk) else ""
        filas.append(fila)
        barra.progress((k + 1) / len(favs), text=f"Actualizando {tk}…")
    barra.empty()
    df = pd.DataFrame(filas)
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Precio": st.column_config.NumberColumn(format="%.2f"),
        "Hoy": st.column_config.NumberColumn(format="percent"),
        "Desde que la añadí": st.column_config.NumberColumn(format="percent"),
        "vs zona de compra": st.column_config.NumberColumn(format="percent", help="Negativo = ya cotiza por debajo de la zona de compra del modelo"),
        "Nota": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
    })
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1], vertical_alignment="bottom")
    elegida = c1.selectbox("Empresa", list(favs), format_func=lambda t: f"{t} · {favs[t].get('nombre', t)}", key="fav_sel")
    if c2.button("🔎 Analizar", width="stretch"):
        abrir_empresa(elegida)
    if c3.button("🎯 Simular", width="stretch"):
        abrir_empresa(elegida, "vistas/simulador.py")
    c4.button("✖ Quitar", width="stretch", on_click=us.alternar_favorito, args=(elegida, favs[elegida].get("nombre"), None))

# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
st.subheader(f"🔔 Alertas ({len(alertas)})")
if not alertas:
    st.caption("No tienes alertas. Créalas desde el botón 🔔 Alertas de cada empresa.")
else:
    estados = us.comprobar(alertas, analisis)
    for a in us.marcar_disparadas(estados):
        st.toast(f"🔔 **{a['ticker']}**: {us.describir(a)}", icon="🔔")
    filas = []
    for a in alertas:
        cumple, detalle = estados.get(a["id"], (None, ""))
        filas.append({"Estado": "✅ Se cumple" if cumple else "⏳ Pendiente" if cumple is False else "❔ Sin datos",
                      "Empresa": f"{a['ticker']} · {a.get('nombre', '')}", "Condición": us.describir(a),
                      "Ahora": detalle, "Cumplida desde": a.get("disparada") or "", "Creada": a.get("creada", ""), "id": a["id"]})
    df = pd.DataFrame(filas).sort_values("Estado", ascending=False)
    st.dataframe(df.drop(columns=["id"]), hide_index=True, width="stretch")
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    borrar = c1.multiselect("Borrar alertas", df["id"].tolist(),
                            format_func=lambda i: next(f"{f['Empresa']} — {f['Condición']}" for f in filas if f["id"] == i), key="borrar_alertas")

    def _borrar(ids):
        for i in ids:
            us.borrar_alerta(i)
        st.session_state["borrar_alertas"] = []
    c2.button("🗑️ Borrar", disabled=not borrar, on_click=_borrar, args=(borrar,), width="stretch")
    with st.expander("ℹ️ ¿Cómo funcionan las alertas?"):
        st.markdown("""
- Se comprueban **cada vez que abres la web** (cualquier sección), con precios de Yahoo de hace ~15 minutos.
- Cuando una se cumple por primera vez verás un aviso emergente y un recordatorio en la barra lateral.
- Si deja de cumplirse, se **rearma** sola y te volverá a avisar la próxima vez.
- Las del modelo (zona de compra, veredicto, dividendo) usan los pesos y umbrales de la barra lateral.
- De momento **no envían email ni Telegram** con la web cerrada: eso necesita un servicio que se ejecute solo cada día.
""")

# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------
if notas:
    st.subheader(f"📝 Mis notas ({len(notas)})")
    for tk, texto in notas.items():
        with st.expander(f"{tk} · {favs.get(tk, {}).get('nombre', '')}"):
            st.write(texto)
