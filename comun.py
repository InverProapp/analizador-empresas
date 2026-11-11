"""Piezas compartidas por todas las secciones: formato, datos cacheados y ajustes."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import backtest as bt
import datos
import scoring as sc

COLOR = {"Comprar": "#1a9e5c", "Esperar": "#d99a00", "Vender": "#d64545", "Sin datos": "#888888"}
AZUL, GRIS = "#2a6fdb", "#9aa4b2"


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------
def f_pct(x, dec=1):
    return "—" if x is None else f"{x * 100:.{dec}f}%".replace(".", ",")


def f_x(x, dec=1):
    return "—" if x is None else f"{x:.{dec}f}x".replace(".", ",")


def f_num(x, dec=2):
    return "—" if x is None else f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def f_dinero(x, moneda=""):
    if x is None:
        return "—"
    a = abs(x)
    for lim, suf in ((1e12, "B"), (1e9, "mm"), (1e6, "M"), (1e3, "k")):
        if a >= lim:
            return f"{x / lim:,.1f} {suf} {moneda}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{f_num(x)} {moneda}"


def f_item(i: sc.Item):
    if i.valor is None:
        return "—"
    if i.formato == "%":
        return f_pct(i.valor)
    if i.formato == "x":
        return f_x(i.valor)
    if i.formato == "bool":
        return "Sí" if i.valor else "No"
    return f_num(i.valor, 1)


def color_nota(n):
    if n is None:
        return GRIS
    return COLOR["Comprar"] if n >= 65 else COLOR["Esperar"] if n >= 45 else COLOR["Vender"]


# ---------------------------------------------------------------------------
# Datos cacheados
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def cargar(ticker: str) -> datos.Empresa:
    return datos.descargar(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def buscar(texto: str, version: int = 4):
    return datos.buscar(texto)



@st.cache_data(ttl=12 * 3600, show_spinner=False, max_entries=4000)
def cargar_opcional(ticker: str):
    """Como cargar(), pero devuelve None en vez de fallar (para escáner y backtest).
    Se guarda 12 h y es compartido entre todos los usuarios de la web."""
    import time
    for intento in range(2):
        try:
            e = datos.descargar(ticker)
            if e.hist is not None and not e.hist.empty:
                return e
        except Exception:
            pass
        time.sleep(2)  # Yahoo a veces limita peticiones: reintentamos una vez
    return None


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def tickers_mercado(nombre: str, n: int) -> list[str]:
    import universos
    return universos.mercado(nombre, n)


def selector_universo(prefijo: str, defecto_lista: str = "ITX.MC, SAN.MC, AAPL, MSFT, MC.PA"):
    """Selector de empresas: índice, mercado entero de un país o lista propia.
    Devuelve (etiqueta, lista de tickers)."""
    import universos
    tipo = st.radio("¿Qué quieres analizar?", ["Índices", "Mercados por país", "Lista personalizada"],
                    horizontal=True, key=f"{prefijo}_tipo")
    if tipo == "Índices":
        nombre = st.selectbox("Índice", list(universos.UNIVERSOS), key=f"{prefijo}_indice")
        return nombre, universos.lista(nombre)
    if tipo == "Mercados por país":
        c1, c2 = st.columns([2, 1])
        nombre = c1.selectbox("Mercado", list(universos.MERCADOS), key=f"{prefijo}_mercado")
        n = c2.select_slider("Empresas (las más grandes)", [25, 50, 100, 200, 300, 500, 750, 1000], value=100,
                             key=f"{prefijo}_n")
        try:
            with st.spinner("Obteniendo la lista de empresas de Yahoo…"):
                tks = tickers_mercado(nombre, n)
        except Exception as ex:
            st.error(f"Yahoo no devolvió la lista de empresas ({type(ex).__name__}). Prueba en un momento.")
            tks = []
        return f"{nombre} · top {len(tks)}", tks
    texto = st.text_area("Tickers (separados por comas)", value=defecto_lista, key=f"{prefijo}_lista")
    return "Lista personalizada", universos.lista("Lista personalizada", texto)


def tiempo_estimado(n: int) -> str:
    seg = n * 0.9  # ~0,9 s por empresa con 8 descargas en paralelo, la primera vez
    return f"{seg / 60:.0f} min" if seg >= 90 else f"{seg:.0f} s"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def competidores(ticker: str):
    return datos.competidores(cargar(ticker))


@st.cache_data(ttl=3 * 3600, show_spinner=False)
def noticias(ticker: str):
    return datos.noticias(ticker)


def cargar_varias(tickers, etiqueta="Descargando"):
    """Descarga varias empresas en paralelo con barra de progreso."""
    barra = st.progress(0.0, text=f"{etiqueta}…")

    def prog(frac, t):
        barra.progress(frac, text=f"{etiqueta} {t} ({frac * 100:.0f}%)")
    out = bt.descargar_varias(tickers, cargar_opcional, hilos=8, progreso=prog)
    barra.empty()
    return out


# ---------------------------------------------------------------------------
# Ajustes (barra lateral, compartidos entre secciones)
# ---------------------------------------------------------------------------
def _persistente(widget, etiqueta, clave, defecto, **kw):
    """Widget cuyo valor se conserva al cambiar de sección (Streamlit borra el estado de los
    widgets que no se dibujan en la página actual)."""
    copia = "_guardado_" + clave
    if copia not in st.session_state:
        st.session_state[copia] = defecto
    st.session_state[clave] = st.session_state[copia]

    def guardar():
        st.session_state[copia] = st.session_state[clave]
    return widget(etiqueta, key=clave, on_change=guardar, **kw)


def ajustes() -> dict:
    sl, cb = st.slider, st.checkbox
    with st.sidebar.expander("⚖️ Pesos de cada pilar", expanded=False):
        pesos = {p: _persistente(sl, p, f"peso_{p}", sc.PESOS_DEFECTO[p], min_value=0, max_value=50, step=5)
                 for p in sc.PILARES}
        if st.button("Restablecer pesos", key="reset_pesos"):
            for p in sc.PILARES:
                st.session_state["_guardado_peso_" + p] = sc.PESOS_DEFECTO[p]
            st.rerun()

    with st.sidebar.expander("🎯 Umbrales del veredicto", expanded=False):
        u_comprar = _persistente(sl, "Comprar si la nota ≥", "u_comprar", sc.UMBRAL_COMPRAR, min_value=50, max_value=90)
        u_vender = _persistente(sl, "Vender si la nota <", "u_vender", sc.UMBRAL_VENDER, min_value=20, max_value=60)
        if u_vender >= u_comprar:
            st.warning("El umbral de venta debe ser menor que el de compra.")
            u_vender = u_comprar - 1
        margen_seg = _persistente(sl, "Margen de seguridad para el precio de compra", "margen_seg", 15,
                                  min_value=0, max_value=40, step=5, format="%d%%") / 100
        respetar_tendencia = _persistente(cb, "No dar 'Comprar' con tendencia bajista fuerte", "tendencia", True)

    with st.sidebar.expander("💰 Parámetros del DCF", expanded=False):
        auto_g = _persistente(cb, "Crecimiento automático (histórico, máx. 15%)", "auto_g", True)
        g_manual = _persistente(sl, "Crecimiento FCF años 1-5", "g_manual", 8, min_value=-5, max_value=30, step=1,
                                format="%d%%", disabled=auto_g) / 100
        wacc = _persistente(sl, "Tasa de descuento", "wacc", 9.0, min_value=5.0, max_value=15.0, step=0.5, format="%.1f%%") / 100
        g_term = _persistente(sl, "Crecimiento terminal", "g_term", 2.5, min_value=0.0, max_value=4.0, step=0.5, format="%.1f%%") / 100

    st.sidebar.caption("Datos: Yahoo Finance vía yfinance (gratis, con ~15 min de retraso). "
                       "Herramienta de análisis según reglas: no es asesoramiento financiero.")
    return dict(pesos=pesos, u_comprar=u_comprar, u_vender=u_vender, margen_seg=margen_seg,
                respetar_tendencia=respetar_tendencia, g=None if auto_g else g_manual, wacc=wacc, g_term=g_term)


def analizar(tk: str, aj: dict, e: datos.Empresa | None = None):
    e = e or cargar(tk)
    m = datos.metricas(e, aj["g"], aj["wacc"], aj["g_term"])
    r = sc.evaluar(m, e.sector, aj["pesos"], aj["u_comprar"], aj["u_vender"], aj["margen_seg"], aj["respetar_tendencia"])
    return e, m, r


def tabla_resultados(filas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(filas)
    if "Nota" in df:
        df = df.sort_values("Nota", ascending=False, na_position="last")
    return df


def config_columnas():
    cfg = {p: st.column_config.ProgressColumn(p, min_value=0, max_value=100, format="%.0f") for p in ["Nota"] + sc.PILARES}
    for c in ("ROE", "Div.", "Potencial", "Margen op.", "Crec. ingresos", "vs zona compra"):
        cfg[c] = st.column_config.NumberColumn(c, format="percent")
    for c in ("PER", "EV/EBITDA", "Deuda neta/EBITDA"):
        cfg[c] = st.column_config.NumberColumn(c, format="%.1f")
    return cfg


def fila_resumen(tk, e, m, r) -> dict:
    fila = {"Ticker": tk, "Empresa": e.nombre, "Sector": sc.SECTORES_ES.get(e.sector, e.sector),
            "Veredicto": r.veredicto, "Nota": r.nota}
    fila.update({p: r.pilares[p].nota for p in sc.PILARES})
    precio = m.get("precio")
    fila.update({"PER": m.get("per"), "EV/EBITDA": m.get("ev_ebitda"), "ROE": m.get("roe"),
                 "Margen op.": m.get("margen_operativo"), "Crec. ingresos": m.get("crec_ingresos"),
                 "Deuda neta/EBITDA": m.get("deuda_neta_ebitda"), "Div.": m.get("rent_dividendo"),
                 "Potencial": (r.valor_justo / precio - 1) if r.valor_justo and precio else None,
                 "vs zona compra": (precio / r.precio_compra - 1) if r.precio_compra and precio else None})
    return fila


@st.cache_data(ttl=3600, show_spinner=False)
def historico(ticker: str) -> pd.DataFrame:
    return datos.historico_multiples(cargar(ticker))


def secreto(nombre: str):
    try:
        return st.secrets.get(nombre)
    except Exception:
        return None



def selector_empresa(titulo: str = "📊 Analizador"):
    """Buscador de empresa en la barra lateral. La empresa elegida se mantiene al cambiar de sección."""
    st.sidebar.title(titulo)
    modo = _persistente(st.sidebar.radio, "Buscar por", "modo_busqueda", "Nombre", options=["Nombre", "Ticker"],
                        horizontal=True)
    if modo == "Nombre":
        q = _persistente(st.sidebar.text_input, "Empresa", "texto_busqueda", "Inditex",
                         help="Escribe el nombre y elige el ticker de la bolsa que quieras.")
        resultados = buscar(q, 4) if q else []
        if not resultados:
            if q:
                st.sidebar.info("Sin resultados. Prueba con el ticker directamente.")
            return None
        opciones = {f"{r['symbol']} · {r['nombre']} ({r['bolsa']})": r["symbol"] for r in resultados}
        etiquetas = list(opciones)
        guardada = st.session_state.get("_guardado_resultado")
        if guardada not in etiquetas:
            st.session_state["_guardado_resultado"] = etiquetas[0]
        elegida = _persistente(st.sidebar.selectbox, "Resultados", "resultado", etiquetas[0], options=etiquetas)
        return opciones[elegida]
    tk = _persistente(st.sidebar.text_input, "Ticker de Yahoo Finance", "ticker_directo", "ITX.MC",
                      help="Ejemplos: AAPL, MSFT, SAN.MC, ITX.MC, MC.PA, SAP.DE, 7203.T, NESN.SW")
    return tk.strip().upper() or None


def abrir_empresa(tk: str, pagina: str = "vistas/empresa.py"):
    """Abre una empresa concreta en otra sección (desde el escáner, por ejemplo)."""
    st.session_state["_guardado_modo_busqueda"] = "Ticker"
    st.session_state["_guardado_ticker_directo"] = tk
    st.switch_page(pagina)



@st.cache_data(ttl=12 * 3600, show_spinner=False)
def precios_max(ticker: str) -> pd.DataFrame:
    try:
        return datos.precios_historicos(ticker)
    except Exception:
        return pd.DataFrame()
