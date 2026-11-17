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
class _Incompleta(Exception):
    """Yahoo devolvió la empresa a medias (suele ser un límite de peticiones): no se guarda en caché."""
    def __init__(self, e):
        super().__init__("datos incompletos")
        self.empresa = e


def _descargar_completa(ticker: str) -> datos.Empresa:
    import time
    e = None
    for intento in range(2):
        e = datos.descargar(ticker)
        ficha_ok = len(e.info or {}) > 15 and any(e.info.get(k) for k in ("longName", "shortName", "currency"))
        if ficha_ok and e.hist is not None and not e.hist.empty:
            return e
        time.sleep(1.5)
    raise _Incompleta(e)


@st.cache_data(ttl=3600, show_spinner=False)
def _cargar(ticker: str) -> datos.Empresa:
    return _descargar_completa(ticker)


_INCOMPLETAS: dict = {}  # ticker -> (hora, empresa): lo que Yahoo dio a medias, se reutiliza solo 5 min


def _incompleta_reciente(ticker):
    import time
    x = _INCOMPLETAS.get(ticker)
    return x[1] if x and time.time() - x[0] < 300 else None


def _guardar_incompleta(ticker, e):
    import time
    _INCOMPLETAS[ticker] = (time.time(), e)
    return e


def cargar(ticker: str) -> datos.Empresa:
    """Empresa completa (1 h en caché, compartida). Si Yahoo la da a medias (límite de peticiones), se usa
    durante 5 minutos sin guardarla en la caché larga, para volver a intentarlo después."""
    rec = _incompleta_reciente(ticker)
    if rec is not None:
        return rec
    try:
        return _cargar(ticker)
    except _Incompleta as ex:
        return _guardar_incompleta(ticker, ex.empresa)


@st.cache_data(ttl=3600, show_spinner=False)
def buscar(texto: str, version: int = 4):
    return datos.buscar(texto)



@st.cache_data(ttl=12 * 3600, show_spinner=False, max_entries=4000)
def _cargar_opcional(ticker: str):
    return _descargar_completa(ticker)


def cargar_opcional(ticker: str):
    """Como cargar(), pero devuelve None en vez de fallar (para escáner y backtest).
    Se guarda 12 h y es compartido entre todos los usuarios de la web; lo incompleto no se guarda."""
    e = _incompleta_reciente(ticker)
    if e is None:
        try:
            return _cargar_opcional(ticker)
        except _Incompleta as ex:
            e = _guardar_incompleta(ticker, ex.empresa)
        except Exception:
            return None
    return e if e is not None and e.hist is not None and not e.hist.empty else None


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def tickers_mercado(nombre: str, n: int) -> list[str]:
    import universos
    return universos.mercado(nombre, n)


def selector_universo(prefijo: str, defecto_lista: str = "Inditex, Santander, Apple, Microsoft, LVMH"):
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
    texto = st.text_area("Empresas (nombres o tickers, separados por comas)", value=defecto_lista, key=f"{prefijo}_lista",
                         help="Por ejemplo: Inditex, Santander, Apple, Microsoft")
    tks, traducidos, faltan = resolver_lista(texto)
    explicar_lista(traducidos, faltan)
    return "Lista personalizada", tks


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
    """Ajustes del modelo en la barra lateral, todos dentro de un desplegable (son avanzados)."""
    sl, cb = st.slider, st.checkbox
    with st.sidebar.expander("⚙️ Ajustes del modelo (avanzado)", expanded=False):
        st.caption("Cambian la nota y el veredicto de todas las secciones. Si no sabes qué tocar, déjalos como están.")
        st.markdown("**⚖️ Peso de cada pilar en la nota**")
        pesos = {p: _persistente(sl, p, f"peso_{p}", sc.PESOS_DEFECTO[p], min_value=0, max_value=50, step=5)
                 for p in sc.PILARES}
        if st.button("Restablecer pesos", key="reset_pesos"):
            for p in sc.PILARES:
                st.session_state["_guardado_peso_" + p] = sc.PESOS_DEFECTO[p]
            st.rerun()
        st.divider()
        st.markdown("**🎯 Cuándo dar cada veredicto**")
        u_comprar = _persistente(sl, "Comprar si la nota ≥", "u_comprar", sc.UMBRAL_COMPRAR, min_value=50, max_value=90)
        u_vender = _persistente(sl, "Vender si la nota <", "u_vender", sc.UMBRAL_VENDER, min_value=20, max_value=60)
        if u_vender >= u_comprar:
            st.warning("El umbral de venta debe ser menor que el de compra.")
            u_vender = u_comprar - 1
        margen_seg = _persistente(sl, "Margen de seguridad para el precio de compra", "margen_seg", 15,
                                  min_value=0, max_value=40, step=5, format="%d%%") / 100
        respetar_tendencia = _persistente(cb, "No dar 'Comprar' con tendencia bajista fuerte", "tendencia", True)
        st.divider()
        st.markdown("**💰 Supuestos del DCF (valor justo)**")
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
    for c in ("PER", "EV/EBITDA", "Deuda neta/EBITDA", "P/VC", "PER esperado", "Beta"):
        cfg[c] = st.column_config.NumberColumn(c, format="%.1f")
    for c in ("ROIC", "Margen neto", "Crec. beneficio", "Crec. ventas 3-5a", "FCF yield", "Payout", "Desde máx. 52s",
              "Rent. 3 meses", "Rent. 1 año", "Cuota de ventas"):
        cfg[c] = st.column_config.NumberColumn(c, format="percent")
    for c in ("Cap. (mill.)", "Ventas (mill.)"):
        cfg[c] = st.column_config.NumberColumn(c, format="localized")
    cfg["Piotroski"] = st.column_config.NumberColumn("Piotroski", format="%d")
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
    # Columnas extra (búsquedas de ideas y vista de sector; el escáner no las muestra por defecto)
    mx = m.get("max_52s")
    fila.update({"Moneda": e.info.get("currency"), "Industria": e.info.get("industry"),
                 "Cap. (mill.)": (m.get("market_cap") or 0) / 1e6 or None,
                 "Ventas (mill.)": (e.info.get("totalRevenue") or 0) / 1e6 or None,
                 "ROIC": m.get("roic"), "Margen neto": m.get("margen_neto"), "Crec. beneficio": m.get("crec_beneficio"),
                 "Crec. ventas 3-5a": m.get("cagr_ingresos"), "FCF yield": m.get("fcf_yield"), "P/VC": m.get("p_vc"),
                 "PER esperado": m.get("per_fwd"), "Payout": m.get("payout"), "Piotroski": m.get("piotroski"),
                 "Desde máx. 52s": (precio / mx - 1) if precio and mx else None, "Rent. 3 meses": m.get("rent_3m"),
                 "Rent. 1 año": m.get("rent_1a"), "Beta": m.get("beta")})
    return fila


COLUMNAS_ESCANER = ["Ticker", "Empresa", "Sector", "Veredicto", "Nota"] + list(sc.PILARES) + [
    "PER", "EV/EBITDA", "ROE", "Margen op.", "Crec. ingresos", "Deuda neta/EBITDA", "Div.", "Potencial", "vs zona compra"]


@st.cache_data(ttl=3600, show_spinner=False)
def historico(ticker: str) -> pd.DataFrame:
    return datos.historico_multiples(cargar(ticker))


def secreto(nombre: str):
    try:
        return st.secrets.get(nombre)
    except Exception:
        return None



def parece_ticker(texto: str) -> bool:
    """«ITX.MC», «AAPL», «^IBEX» parecen tickers; «Inditex» o «banco santander» son nombres."""
    t = (texto or "").strip()
    if not t or " " in t:
        return False
    if any(c in t for c in ".^=-") or any(c.isdigit() for c in t):
        return True
    return t.isupper() and len(t) <= 5


def resolver(texto: str) -> tuple[str | None, str]:
    """Convierte un nombre o ticker en (ticker, nombre). Si es un nombre, toma el mejor resultado de la búsqueda."""
    t = (texto or "").strip()
    if not t:
        return None, ""
    if parece_ticker(t):
        return t.upper(), ""
    res = buscar(t, 4)
    return (res[0]["symbol"], res[0]["nombre"]) if res else (None, "")


def resolver_lista(texto: str) -> tuple[list[str], list[str], list[str]]:
    """«Inditex, Apple, SAN.MC» → (tickers, ['Inditex → ITX.MC', …], [no encontrados])."""
    tickers, traducidos, faltan = [], [], []
    for parte in [x.strip() for x in (texto or "").replace(";", ",").replace("\n", ",").split(",") if x.strip()]:
        tk, nombre = resolver(parte)
        if not tk:
            faltan.append(parte)
            continue
        if tk not in tickers:
            tickers.append(tk)
        if not parece_ticker(parte):
            traducidos.append(f"{parte} → {tk}")
    return tickers, traducidos, faltan


def explicar_lista(traducidos: list[str], faltan: list[str], donde=st):
    if traducidos:
        donde.caption("Entendido: " + " · ".join(traducidos))
    if faltan:
        donde.warning("No encuentro: " + ", ".join(faltan) + ". Prueba con otro nombre o con su ticker.")


def empresa_actual(defecto: str = "ITX.MC") -> str:
    """La última empresa que se ha mirado en cualquier sección."""
    return st.session_state.get("_ultima_empresa") or defecto


def elegir_empresa(clave: str, donde=st, etiqueta: str = "Empresa", defecto: str = "Inditex", en_linea: bool = False) -> str | None:
    """Buscador por nombre (o ticker, si te lo sabes). Si hay varias coincidencias, deja elegir cuál.
    en_linea: el buscador y la lista de coincidencias, uno al lado del otro."""
    if en_linea:
        c1, c2 = donde.columns([1, 1.3], vertical_alignment="top")
        donde, donde2 = c1, c2
    else:
        donde2 = donde
    q = _persistente(donde.text_input, etiqueta, f"{clave}_q", defecto,
                     placeholder="Escribe el nombre: Inditex, Apple, Santander…",
                     help="Escribe el nombre de la empresa (no hace falta saber el ticker). Si sabes el ticker, también vale.")
    if not q or not q.strip():
        return None
    resultados = buscar(q.strip(), 4)
    opciones = {f"{r['nombre']} · {r['symbol']} ({r['bolsa']})": r["symbol"] for r in resultados}
    if parece_ticker(q) and q.strip().upper() not in opciones.values():
        opciones = {f"{q.strip().upper()} (ticker escrito)": q.strip().upper(), **opciones}
    elif parece_ticker(q):  # el ticker exacto, primero
        opciones = dict(sorted(opciones.items(), key=lambda kv: kv[1] != q.strip().upper()))
    if not opciones:
        donde2.warning("No encuentro esa empresa. Prueba con otro nombre (por ejemplo, el nombre comercial) o con su ticker.")
        return None
    etiquetas = list(opciones)
    if len(etiquetas) == 1:
        donde2.caption(f"✔️ {etiquetas[0]}")
        return opciones[etiquetas[0]]
    if st.session_state.get(f"_guardado_{clave}_sel") not in etiquetas:
        st.session_state[f"_guardado_{clave}_sel"] = etiquetas[0]
    elegida = _persistente(donde2.selectbox, "¿Cuál de ellas?", f"{clave}_sel", etiquetas[0], options=etiquetas,
                           help="La misma empresa puede cotizar en varias bolsas: la primera suele ser la principal.")
    return opciones[elegida]


def selector_empresa(titulo: str = "🔎 Buscar empresa"):
    """Buscador de empresa arriba de la página (se ve también en el móvil). La empresa se mantiene al cambiar de sección."""
    tk = elegir_empresa("busqueda", st, etiqueta="🔎 Busca una empresa por su nombre", en_linea=True)
    if tk:
        st.session_state["_ultima_empresa"] = tk
    return tk


def abrir_empresa(tk: str, pagina: str = "vistas/empresa.py"):
    """Abre una empresa concreta en otra sección (desde el escáner, por ejemplo)."""
    st.session_state["_guardado_busqueda_q"] = tk
    st.session_state.pop("_guardado_busqueda_sel", None)
    st.session_state["_ultima_empresa"] = tk
    st.switch_page(pagina)


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def precios_max(ticker: str) -> pd.DataFrame:
    try:
        return datos.precios_historicos(ticker)
    except Exception:
        return pd.DataFrame()


def metrica(col, etiqueta: str, valor, delta=None, clave: str | None = None, delta_color: str = "normal", ayuda: str | None = None):
    """Como st.metric, pero la etiqueta se puede pinchar para ver una mini definición."""
    import glosario
    with col:
        if clave and clave in glosario.G:
            with st.popover(etiqueta, type="tertiary", icon=":material/info:"):
                st.markdown(glosario.texto(clave))
            st.metric(etiqueta, valor, delta, delta_color=delta_color, label_visibility="collapsed")
        else:
            st.metric(etiqueta, valor, delta, delta_color=delta_color, help=ayuda)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def eventos_empresa(ticker: str) -> dict:
    """Próximos eventos (resultados, dividendos) y sorpresas de resultados pasadas. 6 h, compartido."""
    try:
        return datos.eventos(ticker)
    except Exception:
        return {"proximos": [], "consenso": {}, "resultados": pd.DataFrame()}



def cabecera(titulo: str, subtitulo: str):
    """Título de sección con una línea que explica para qué sirve (igual en todas las páginas)."""
    st.title(titulo)
    st.caption(subtitulo)


def conclusion(texto: str):
    """Recuadro «En pocas palabras» al principio de cada bloque."""
    import re
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    html = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", html)
    st.markdown(f'<div class="conclusion">💬 {html}</div>', unsafe_allow_html=True)
