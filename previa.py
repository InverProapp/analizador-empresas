"""Previa de resultados: qué espera el mercado, qué vigilar y tres escenarios antes de que una empresa presente."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import agenda
from comun import COLOR, f_num, f_pct

# Métricas operativas que más mueven la acción en cada sector (sectores de Yahoo)
VIGILAR_SECTOR = {
    "Technology": ["Ingresos recurrentes (suscripciones) y su crecimiento", "Retención de clientes", "Cartera de contratos firmados pendientes"],
    "Communication Services": ["Número de abonados o usuarios", "Ingreso medio por usuario (ARPU)", "Bajas de clientes (churn)"],
    "Consumer Cyclical": ["Ventas en tiendas comparables", "Tráfico de clientes y ticket medio", "Inventarios frente a ventas"],
    "Consumer Defensive": ["Crecimiento de ventas: precio frente a volumen", "Margen bruto (costes de materias primas)", "Cuota de mercado"],
    "Industrials": ["Cartera de pedidos", "Pedidos nuevos frente a facturación (book-to-bill)", "Subidas de precio frente a volumen"],
    "Financial Services": ["Margen de intereses", "Morosidad y provisiones", "Crecimiento del crédito y de las comisiones"],
    "Healthcare": ["Ventas de los productos principales", "Avances en ensayos y aprobaciones", "Patentes que caducan"],
    "Energy": ["Producción", "Precio de venta conseguido (petróleo, gas, electricidad)", "Inversiones (capex) y recompras"],
    "Basic Materials": ["Volúmenes vendidos", "Precios de venta frente a costes", "Coste de la energía"],
    "Real Estate": ["Ocupación", "Subida de las rentas", "Coste y vencimientos de la deuda"],
    "Utilities": ["Demanda y precios de la energía", "Inversiones reguladas y su retribución", "Deuda"],
}
VIGILAR_GENERAL = ["Beneficio por acción frente a lo esperado", "Ventas frente a lo esperado",
                   "Márgenes: ¿mejoran o empeoran?", "Previsiones para el próximo trimestre/año (suele mover más que el dato)",
                   "Flujo de caja libre"]


def construir(ev: dict, hist: pd.DataFrame | None, precio: float | None) -> dict | None:
    """Datos de la previa para la próxima presentación de resultados (None si no hay fecha anunciada)."""
    hoy = pd.Timestamp.today().normalize()
    prox = [x for x in ev.get("proximos", []) if x["tipo"] == "Resultados" and x["fecha"] >= hoy]
    if not prox:
        return None
    fecha = min(x["fecha"] for x in prox)
    cs = ev.get("consenso") or {}
    h = agenda.historial_resultados(ev.get("resultados"), hist)
    rx = h["reaccion"].dropna() if not h.empty else pd.Series(dtype=float)
    sor = h["sorpresa"] if not h.empty else pd.Series(dtype=float)
    mov = float(np.mean(np.abs(rx))) if len(rx) >= 2 else None

    def media(mask):
        r = h.loc[mask, "reaccion"].dropna() if not h.empty else pd.Series(dtype=float)
        return (float(r.mean()), len(r)) if len(r) else (None, 0)

    reac_bate = media(sor >= 2) if len(sor) else (None, 0)
    reac_linea = media(sor.between(-2, 2)) if len(sor) else (None, 0)
    reac_falla = media(sor <= -2) if len(sor) else (None, 0)
    close = hist["Close"].dropna() if hist is not None and "Close" in hist else pd.Series(dtype=float)

    def rent(dias):
        if len(close) < dias + 1:
            return None
        return float(close.iloc[-1] / close.iloc[-dias - 1] - 1)
    bpa, lo, hi = cs.get("Earnings Average"), cs.get("Earnings Low"), cs.get("Earnings High")
    tipica = float(np.median(np.abs(sor.dropna()))) / 100 if len(sor.dropna()) >= 2 else 0.05
    esc = []
    if bpa is not None:
        bueno = hi if hi is not None and hi > bpa else bpa * (1 + max(tipica, 0.03))
        malo = lo if lo is not None and lo < bpa else bpa * (1 - max(tipica, 0.03))
        esc = [("🟢 Bueno", f"BPA de {f_num(bueno)} o más", "Bate con holgura y mejora previsiones", reac_bate, 1),
               ("🟡 Normal", f"BPA cerca de {f_num(bpa)}", "En línea y mantiene previsiones", reac_linea, 0),
               ("🔴 Malo", f"BPA de {f_num(malo)} o menos", "Se queda corto o rebaja previsiones", reac_falla, -1)]
    return {"fecha": fecha, "dias": (fecha - hoy).days, "consenso": cs, "mov_tipico": mov, "n_hist": len(rx),
            "bate": int((sor > 0).sum()) if len(sor) else 0, "n_sor": int(sor.notna().sum()) if len(sor) else 0,
            "rent_1m": rent(21), "rent_3m": rent(63), "escenarios": esc, "precio": precio}


def mostrar(pv: dict, sector: str | None, tesis: dict | None, mon: str, clave: str):
    """Pinta la previa (equity research → versión para inversor particular)."""
    cs = pv["consenso"]
    cuando = "hoy" if pv["dias"] == 0 else "mañana" if pv["dias"] == 1 else f"en {pv['dias']} días"
    st.markdown(f"##### 🔮 Previa de resultados · {pv['fecha']:%d/%m/%Y} ({cuando})")
    c = st.columns(4)
    c[0].metric("BPA esperado", f_num(cs.get("Earnings Average")) if cs.get("Earnings Average") is not None else "—",
                help="Beneficio por acción que esperan de media los analistas (fuente: Yahoo Finance).")
    if cs.get("Earnings Low") is not None and cs.get("Earnings High") is not None:
        c[1].metric("Rango de analistas", f"{f_num(cs['Earnings Low'])} – {f_num(cs['Earnings High'])}")
    if cs.get("Revenue Average"):
        c[2].metric("Ventas esperadas", f"{f_num(cs['Revenue Average'] / 1e9)} mil mill.")
    if pv["mov_tipico"] is not None:
        c[3].metric("Movimiento típico", f"±{pv['mov_tipico'] * 100:.1f}%".replace(".", ","),
                    help=f"Media de lo que se ha movido la acción al día siguiente en sus últimas {pv['n_hist']} presentaciones.")

    llega = []
    if pv["rent_1m"] is not None:
        llega.append(f"llega con un **{f_pct(pv['rent_1m'])}** en el último mes y **{f_pct(pv['rent_3m'])}** en tres meses")
    if pv["n_sor"]:
        llega.append(f"ha batido previsiones en **{pv['bate']} de sus últimas {pv['n_sor']}** presentaciones")
    if llega:
        texto = "La acción " + " y ".join(llega) + "."
        if pv["rent_3m"] is not None and pv["rent_3m"] > 0.15:
            texto += " Con esa subida, **el listón está alto**: puede caer incluso si bate."
        elif pv["rent_3m"] is not None and pv["rent_3m"] < -0.15:
            texto += " Con esa caída, **las expectativas están bajas**: un dato simplemente correcto puede bastar para que rebote."
        st.write(texto)

    if pv["escenarios"]:
        filas = []
        for nombre, bpa, que, (reac, n), signo in pv["escenarios"]:
            if (reac is None or n < 2) and pv["mov_tipico"] is not None:
                reac = signo * pv["mov_tipico"]
                base = "estimada con el movimiento típico"
            elif reac is not None:
                base = f"media de {n} veces parecidas"
            else:
                base = "sin historial"
            precio = pv["precio"] * (1 + reac) if pv["precio"] and reac is not None else None
            filas.append({"Escenario": nombre, "Dato": bpa, "Qué tendría que pasar": que,
                          "Reacción probable": f"{reac * 100:+.1f}% ({base})".replace(".", ",") if reac is not None else "—",
                          "Precio aprox.": f"{f_num(precio)} {mon}" if precio else "—"})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        st.caption("Escenarios orientativos: se construyen con el rango de los analistas y con cómo reaccionó la acción "
                   "otras veces. Las previsiones de la empresa para el futuro suelen pesar más que el dato del trimestre.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Qué vigilar (por orden de importancia)**")
        lista = VIGILAR_GENERAL[:2] + VIGILAR_SECTOR.get(sector or "", [])[:3] + VIGILAR_GENERAL[2:]
        st.markdown("\n".join(f"{i}. {x}" for i, x in enumerate(lista, 1)))
    with c2:
        st.markdown("**Qué pone a prueba de tu tesis**")
        if tesis and tesis.get("pilares"):
            st.markdown("\n".join(f"- {p.get('texto') or p.get('metrica')}" for p in tesis["pilares"]))
            st.caption("Después de los resultados, apunta en el registro si cada pilar sale reforzado o debilitado.")
        else:
            st.caption("No tienes tesis en esta empresa. Escribirla antes de los resultados te ayuda a juzgarlos sin prisas.")

    import usuario as us
    if us.cargado():
        planes = us.datos().setdefault("planes", {})
        plan = planes.get(clave, {})
        with st.form(f"plan_{clave}"):
            st.markdown("**Mi plan** — decide ahora qué harás, para no reaccionar en caliente")
            p1, p2 = st.columns(2)
            bien = p1.text_input("Si sale bien…", plan.get("bien", ""), placeholder="Ej.: mantengo; compro más si baja de 30")
            mal = p2.text_input("Si sale mal…", plan.get("mal", ""), placeholder="Ej.: vendo la mitad si rebaja previsiones")
            if st.form_submit_button("💾 Guardar plan"):
                planes[clave] = {"fecha": str(pv["fecha"].date()), "bien": bien, "mal": mal}
                us.guardar()
                st.toast("Plan guardado", icon="🔮")
