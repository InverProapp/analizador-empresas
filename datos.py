"""Capa de datos: descarga de Yahoo Finance (yfinance) y cálculo de métricas.

Todo lo que se calcula aquí son números "brutos". La puntuación y el
veredicto viven en scoring.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:  # permite ejecutar los tests sin yfinance
    yf = None


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def num(x):
    """Convierte a float o devuelve None si no es un número válido."""
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _row(df: pd.DataFrame | None, *names):
    """Devuelve la primera fila que exista de un estado financiero (columnas = años, más reciente primero)."""
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce")
            if isinstance(s, pd.DataFrame):
                s = s.iloc[0]
            return s
    return None


def _val(series, i=0):
    if series is None or len(series) <= i:
        return None
    return num(series.iloc[i])


def _ordenar(df):
    """Estados financieros con la columna más reciente primero."""
    if df is None or df.empty:
        return df
    try:
        cols = sorted(df.columns, key=lambda c: pd.Timestamp(c), reverse=True)
        return df[cols]
    except Exception:
        return df


# ---------------------------------------------------------------------------
# Contenedor de datos
# ---------------------------------------------------------------------------

@dataclass
class Empresa:
    ticker: str
    info: dict = field(default_factory=dict)
    hist: pd.DataFrame = field(default_factory=pd.DataFrame)
    income: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance: pd.DataFrame = field(default_factory=pd.DataFrame)
    cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)
    dividends: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    errores: list = field(default_factory=list)

    @property
    def nombre(self):
        return self.info.get("longName") or self.info.get("shortName") or self.ticker

    @property
    def moneda(self):
        return self.info.get("currency") or ""

    @property
    def moneda_fin(self):
        return self.info.get("financialCurrency") or self.moneda

    @property
    def sector(self):
        return self.info.get("sector") or "Desconocido"


def descargar(ticker: str, periodo_hist: str = "5y") -> Empresa:
    """Descarga todo lo necesario de Yahoo Finance."""
    if yf is None:
        raise RuntimeError("Falta instalar yfinance: pip install yfinance")
    ticker = ticker.strip().upper()
    t = yf.Ticker(ticker)
    e = Empresa(ticker=ticker)

    def intento(nombre, fn, defecto):
        try:
            r = fn()
            return defecto if r is None else r
        except Exception as ex:  # yfinance falla de forma irregular según el mercado
            e.errores.append(f"{nombre}: {ex}")
            return defecto

    e.info = intento("info", lambda: t.info, {}) or {}
    e.hist = intento("histórico", lambda: t.history(period=periodo_hist, auto_adjust=True), pd.DataFrame())
    e.income = _ordenar(intento("cuenta de resultados", lambda: t.income_stmt, pd.DataFrame()))
    e.balance = _ordenar(intento("balance", lambda: t.balance_sheet, pd.DataFrame()))
    e.cashflow = _ordenar(intento("flujos de caja", lambda: t.cashflow, pd.DataFrame()))
    e.dividends = intento("dividendos", lambda: t.dividends, pd.Series(dtype=float))
    if e.hist is not None and not e.hist.empty and e.hist.index.tz is not None:
        e.hist.index = e.hist.index.tz_localize(None)
    if e.dividends is not None and len(e.dividends) and getattr(e.dividends.index, "tz", None) is not None:
        e.dividends.index = e.dividends.index.tz_localize(None)
    return e


def buscar(texto: str, n: int = 10) -> list[dict]:
    """Busca empresas por nombre o ticker. Devuelve [{symbol, nombre, bolsa, tipo}]."""
    if yf is None or not texto.strip():
        return []
    try:
        res = yf.Search(texto, max_results=n, news_count=0).quotes
    except Exception:
        return []
    out = []
    for q in res:
        if q.get("quoteType") not in ("EQUITY", "ETF", None):
            continue
        out.append({
            "symbol": q.get("symbol"),
            "nombre": q.get("longname") or q.get("shortname") or q.get("symbol"),
            "bolsa": q.get("exchDisp") or q.get("exchange", ""),
            "tipo": q.get("quoteType", ""),
        })
    return out


# ---------------------------------------------------------------------------
# Indicadores técnicos
# ---------------------------------------------------------------------------

def tecnicos(hist: pd.DataFrame) -> pd.DataFrame:
    """Añade SMA50/200, Bollinger, RSI14 y MACD al histórico."""
    if hist is None or hist.empty or "Close" not in hist:
        return pd.DataFrame()
    d = hist.copy()
    c = d["Close"]
    d["SMA20"] = c.rolling(20).mean()
    d["SMA50"] = c.rolling(50).mean()
    d["SMA200"] = c.rolling(200).mean()
    std20 = c.rolling(20).std()
    d["BB_sup"] = d["SMA20"] + 2 * std20
    d["BB_inf"] = d["SMA20"] - 2 * std20
    delta = c.diff()
    ganancia = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    perdida = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = ganancia / perdida.replace(0, np.nan)
    d["RSI"] = 100 - 100 / (1 + rs)
    d.loc[perdida == 0, "RSI"] = 100
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    d["MACD"] = ema12 - ema26
    d["MACD_senal"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACD_hist"] = d["MACD"] - d["MACD_senal"]
    return d


def _rentab(c: pd.Series, dias: int):
    if len(c) <= dias:
        return None
    return num(c.iloc[-1] / c.iloc[-1 - dias] - 1)


# ---------------------------------------------------------------------------
# Métricas fundamentales
# ---------------------------------------------------------------------------

def piotroski(e: Empresa):
    """F-Score de Piotroski (0-9). Devuelve (puntos, detalle, criterios evaluados)."""
    inc, bal, cf = e.income, e.balance, e.cashflow
    ni = _row(inc, "Net Income", "Net Income Common Stockholders")
    ta = _row(bal, "Total Assets")
    cfo = _row(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    ltd = _row(bal, "Long Term Debt", "Long Term Debt And Capital Lease Obligation")
    ca = _row(bal, "Current Assets")
    cl = _row(bal, "Current Liabilities")
    shares = _row(bal, "Ordinary Shares Number", "Share Issued")
    gp = _row(inc, "Gross Profit")
    rev = _row(inc, "Total Revenue", "Operating Revenue")

    detalle = []

    def chk(nombre, cond):
        if cond is None:
            detalle.append((nombre, None))
        else:
            detalle.append((nombre, bool(cond)))

    def ratio(a, b, i):
        x, y = _val(a, i), _val(b, i)
        if x is None or not y:
            return None
        return x / y

    roa0, roa1 = ratio(ni, ta, 0), ratio(ni, ta, 1)
    cfo0 = _val(cfo, 0)
    ni0 = _val(ni, 0)
    chk("ROA positivo", None if roa0 is None else roa0 > 0)
    chk("Flujo de caja operativo positivo", None if cfo0 is None else cfo0 > 0)
    chk("ROA mejora vs año anterior", None if roa0 is None or roa1 is None else roa0 > roa1)
    chk("Caja operativa > beneficio neto (calidad)", None if cfo0 is None or ni0 is None else cfo0 > ni0)
    l0, l1 = ratio(ltd, ta, 0), ratio(ltd, ta, 1)
    if ltd is None and ta is not None:
        l0 = l1 = 0.0
    chk("Apalancamiento baja", None if l0 is None or l1 is None else l0 <= l1)
    cr0, cr1 = ratio(ca, cl, 0), ratio(ca, cl, 1)
    chk("Liquidez corriente mejora", None if cr0 is None or cr1 is None else cr0 > cr1)
    s0, s1 = _val(shares, 0), _val(shares, 1)
    chk("No emite acciones nuevas", None if s0 is None or s1 is None else s0 <= s1 * 1.005)
    gm0, gm1 = ratio(gp, rev, 0), ratio(gp, rev, 1)
    chk("Margen bruto mejora", None if gm0 is None or gm1 is None else gm0 > gm1)
    at0, at1 = ratio(rev, ta, 0), ratio(rev, ta, 1)
    chk("Rotación de activos mejora", None if at0 is None or at1 is None else at0 > at1)

    evaluados = [d for d in detalle if d[1] is not None]
    if len(evaluados) < 6:
        return None, detalle, len(evaluados)
    puntos = sum(1 for d in evaluados if d[1])
    # Escalamos a 9 si faltan criterios
    puntos_9 = round(puntos * 9 / len(evaluados), 1)
    return puntos_9, detalle, len(evaluados)


def altman_z(e: Empresa, market_cap):
    """Altman Z-Score (versión original para industriales cotizadas)."""
    bal, inc = e.balance, e.income
    ta = _val(_row(bal, "Total Assets"))
    ca = _val(_row(bal, "Current Assets"))
    cl = _val(_row(bal, "Current Liabilities"))
    re_ = _val(_row(bal, "Retained Earnings"))
    ebit = _val(_row(inc, "EBIT", "Operating Income"))
    tl = _val(_row(bal, "Total Liabilities Net Minority Interest", "Total Liabilities"))
    ventas = _val(_row(inc, "Total Revenue", "Operating Revenue"))
    if not ta or None in (ca, cl, re_, ebit, tl, ventas, market_cap) or not tl:
        return None
    return (1.2 * (ca - cl) / ta + 1.4 * re_ / ta + 3.3 * ebit / ta
            + 0.6 * market_cap / tl + 1.0 * ventas / ta)


def dcf(fcf_inicial, crecimiento, tasa_descuento, crecimiento_terminal, anos=10, anos_alto=5):
    """DCF de dos etapas. Crecimiento alto durante `anos_alto`, luego converge
    linealmente hasta el crecimiento terminal. Devuelve valor empresa (del FCF)."""
    if fcf_inicial is None or fcf_inicial <= 0 or tasa_descuento <= crecimiento_terminal:
        return None
    total, fcf = 0.0, fcf_inicial
    for a in range(1, anos + 1):
        if a <= anos_alto:
            g = crecimiento
        else:
            paso = (a - anos_alto) / (anos - anos_alto)
            g = crecimiento + (crecimiento_terminal - crecimiento) * paso
        fcf *= 1 + g
        total += fcf / (1 + tasa_descuento) ** a
    terminal = fcf * (1 + crecimiento_terminal) / (tasa_descuento - crecimiento_terminal)
    total += terminal / (1 + tasa_descuento) ** anos
    return total


def cagr(serie, anos=None):
    """CAGR de una serie (más reciente primero)."""
    if serie is None:
        return None
    s = serie.dropna()
    if len(s) < 2:
        return None
    n = len(s) - 1 if anos is None else min(anos, len(s) - 1)
    ini, fin = num(s.iloc[n]), num(s.iloc[0])
    if not ini or ini <= 0 or fin is None or fin <= 0:
        return None
    return (fin / ini) ** (1 / n) - 1


def rentabilidad_dividendo(e: Empresa, precio):
    """Calculado a partir de los dividendos pagados en los últimos 12 meses
    (evita el lío de unidades del campo dividendYield de Yahoo)."""
    if e.dividends is None or len(e.dividends) == 0 or not precio:
        return 0.0
    ult = e.dividends.index.max()
    hace12 = ult - pd.Timedelta(days=365)
    if (pd.Timestamp.now() - ult).days > 550:  # ya no paga dividendo
        return 0.0
    total = e.dividends[e.dividends.index > hace12].sum()
    return num(total / precio) or 0.0


def dividendos_anuales(e: Empresa) -> pd.Series:
    if e.dividends is None or len(e.dividends) == 0:
        return pd.Series(dtype=float)
    s = e.dividends.groupby(e.dividends.index.year).sum()
    año_actual = pd.Timestamp.now().year
    return s[s.index < año_actual]  # solo años completos


def metricas(e: Empresa, crecimiento_dcf=None, tasa_descuento=0.09, crec_terminal=0.025) -> dict:
    """Calcula todas las métricas. Las que no se pueden obtener quedan en None."""
    i = e.info
    m: dict = {}
    hist = e.hist if e.hist is not None else pd.DataFrame()
    close = hist["Close"].dropna() if "Close" in hist else pd.Series(dtype=float)

    precio = num(i.get("currentPrice")) or num(i.get("regularMarketPrice")) or (num(close.iloc[-1]) if len(close) else None)
    m["precio"] = precio
    mcap = num(i.get("marketCap"))
    m["market_cap"] = mcap
    acciones = num(i.get("sharesOutstanding")) or num(i.get("impliedSharesOutstanding"))
    if not mcap and precio and acciones:
        mcap = m["market_cap"] = precio * acciones
    if not acciones and mcap and precio:
        acciones = mcap / precio
    m["acciones"] = acciones
    misma_moneda = (e.moneda_fin or e.moneda) == e.moneda
    m["misma_moneda"] = misma_moneda

    # --- Estados financieros
    inc, bal, cf = e.income, e.balance, e.cashflow
    rev = _row(inc, "Total Revenue", "Operating Revenue")
    ni = _row(inc, "Net Income", "Net Income Common Stockholders")
    ebitda_s = _row(inc, "EBITDA", "Normalized EBITDA")
    ebit_s = _row(inc, "EBIT", "Operating Income")
    interes = _row(inc, "Interest Expense", "Interest Expense Non Operating")
    fcf_s = _row(cf, "Free Cash Flow")
    if fcf_s is None:
        cfo = _row(cf, "Operating Cash Flow")
        capex = _row(cf, "Capital Expenditure")
        if cfo is not None and capex is not None:
            fcf_s = cfo + capex
    equity = _row(bal, "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest")
    deuda_s = _row(bal, "Total Debt")
    caja_s = _row(bal, "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents")

    m["series"] = {"Ingresos": rev, "Beneficio neto": ni, "EBITDA": ebitda_s, "Flujo de caja libre": fcf_s,
                   "Patrimonio neto": equity, "Deuda total": deuda_s, "Caja": caja_s}

    # --- Valoración
    m["per"] = num(i.get("trailingPE"))
    if m["per"] is None and precio and num(i.get("trailingEps")) and num(i.get("trailingEps")) > 0:
        m["per"] = precio / num(i.get("trailingEps"))
    if m["per"] is not None and m["per"] <= 0:
        m["per"] = None
    m["per_fwd"] = num(i.get("forwardPE"))
    if m["per_fwd"] is not None and m["per_fwd"] <= 0:
        m["per_fwd"] = None
    m["peg"] = num(i.get("trailingPegRatio")) or num(i.get("pegRatio"))
    if m["peg"] is not None and m["peg"] <= 0:
        m["peg"] = None
    m["p_vc"] = num(i.get("priceToBook"))
    m["p_ventas"] = num(i.get("priceToSalesTrailing12Months"))
    m["ev_ebitda"] = num(i.get("enterpriseToEbitda"))
    if m["ev_ebitda"] is not None and m["ev_ebitda"] <= 0:
        m["ev_ebitda"] = None
    m["ev"] = num(i.get("enterpriseValue"))

    fcf_ttm = num(i.get("freeCashflow")) or _val(fcf_s)
    m["fcf"] = fcf_ttm
    m["fcf_yield"] = (fcf_ttm / mcap) if fcf_ttm is not None and mcap and misma_moneda else None

    # --- Rentabilidad
    m["roe"] = num(i.get("returnOnEquity"))
    if m["roe"] is None and _val(ni) is not None and _val(equity):
        m["roe"] = _val(ni) / _val(equity)
    m["roa"] = num(i.get("returnOnAssets"))
    m["margen_bruto"] = num(i.get("grossMargins"))
    m["margen_operativo"] = num(i.get("operatingMargins"))
    m["margen_neto"] = num(i.get("profitMargins"))
    if m["margen_neto"] is None and _val(ni) is not None and _val(rev):
        m["margen_neto"] = _val(ni) / _val(rev)
    # ROIC aproximado: EBIT*(1-25%) / (patrimonio + deuda - caja)
    capital = None
    if _val(equity) is not None and _val(deuda_s) is not None:
        capital = _val(equity) + _val(deuda_s) - (_val(caja_s) or 0)
    m["roic"] = (_val(ebit_s) * 0.75 / capital) if _val(ebit_s) is not None and capital and capital > 0 else None

    pio, pio_det, pio_n = piotroski(e)
    m["piotroski"], m["piotroski_detalle"], m["piotroski_n"] = pio, pio_det, pio_n

    # --- Salud financiera
    de = num(i.get("debtToEquity"))
    m["deuda_patrimonio"] = de / 100 if de is not None else (
        _val(deuda_s) / _val(equity) if _val(deuda_s) is not None and _val(equity) and _val(equity) > 0 else None)
    m["liquidez"] = num(i.get("currentRatio"))
    m["prueba_acida"] = num(i.get("quickRatio"))
    deuda = num(i.get("totalDebt")) if num(i.get("totalDebt")) is not None else _val(deuda_s)
    caja = num(i.get("totalCash")) if num(i.get("totalCash")) is not None else _val(caja_s)
    ebitda = num(i.get("ebitda")) or _val(ebitda_s)
    m["deuda_neta"] = (deuda - caja) if deuda is not None and caja is not None else None
    m["deuda_neta_ebitda"] = (m["deuda_neta"] / ebitda) if m["deuda_neta"] is not None and ebitda and ebitda > 0 else None
    ebit, gi = _val(ebit_s), _val(interes)
    m["cobertura_intereses"] = (ebit / abs(gi)) if ebit is not None and gi else None
    m["altman_z"] = altman_z(e, mcap) if misma_moneda else None

    # --- Crecimiento
    m["crec_ingresos"] = num(i.get("revenueGrowth"))
    m["crec_beneficio"] = num(i.get("earningsGrowth"))
    m["cagr_ingresos"] = cagr(rev)
    m["cagr_beneficio"] = cagr(ni)
    m["cagr_fcf"] = cagr(fcf_s)

    # --- Dividendo
    m["rent_dividendo"] = rentabilidad_dividendo(e, precio)
    m["payout"] = num(i.get("payoutRatio"))
    da = dividendos_anuales(e)
    m["div_anuales"] = da
    m["cagr_dividendo_5a"] = cagr(da.iloc[::-1], 5) if len(da) >= 3 else None
    # Años seguidos sin recortar el dividendo
    racha = 0
    if len(da) >= 2:
        v = da.values
        for k in range(len(v) - 1, 0, -1):
            if v[k] >= v[k - 1] * 0.98:
                racha += 1
            else:
                break
    m["anos_sin_recorte"] = racha

    # --- Valor intrínseco
    if crecimiento_dcf is None:
        candidatos = [x for x in (m["cagr_fcf"], m["cagr_ingresos"], num(i.get("earningsGrowth"))) if x is not None]
        crecimiento_dcf = float(np.clip(np.median(candidatos), 0.0, 0.15)) if candidatos else 0.05
    m["crecimiento_dcf"] = crecimiento_dcf
    m["tasa_descuento"] = tasa_descuento
    m["crec_terminal"] = crec_terminal
    base_fcf = fcf_ttm
    # Si hay histórico, normalizamos con la media de los últimos 3 años para no extrapolar un año raro
    if fcf_s is not None and len(fcf_s.dropna()) >= 3:
        media3 = num(fcf_s.dropna().iloc[:3].mean())
        if media3 and media3 > 0 and base_fcf:
            base_fcf = min(base_fcf, media3 * 1.25) if base_fcf > 0 else base_fcf
    m["fcf_base_dcf"] = base_fcf
    valor_emp = dcf(base_fcf, crecimiento_dcf, tasa_descuento, crec_terminal)
    if valor_emp and acciones and misma_moneda:
        ajuste_deuda = -(m["deuda_neta"] or 0)
        m["valor_dcf"] = (valor_emp + ajuste_deuda) / acciones
        if m["valor_dcf"] <= 0:
            m["valor_dcf"] = None
    else:
        m["valor_dcf"] = None
    eps = num(i.get("trailingEps"))
    bvps = num(i.get("bookValue"))
    m["valor_graham"] = math.sqrt(22.5 * eps * bvps) if eps and bvps and eps > 0 and bvps > 0 and misma_moneda else None
    m["margen_seguridad_dcf"] = (m["valor_dcf"] / precio - 1) if m["valor_dcf"] and precio else None
    m["margen_seguridad_graham"] = (m["valor_graham"] / precio - 1) if m["valor_graham"] and precio else None

    # --- Analistas
    objetivo = num(i.get("targetMeanPrice"))
    m["precio_objetivo"] = objetivo
    m["potencial_analistas"] = (objetivo / precio - 1) if objetivo and precio else None
    m["recomendacion_media"] = num(i.get("recommendationMean"))  # 1 = compra fuerte, 5 = venta
    m["n_analistas"] = num(i.get("numberOfAnalystOpinions"))

    # --- Técnico / riesgo
    m["beta"] = num(i.get("beta"))
    if len(close) > 30:
        t = tecnicos(hist)
        ult = t.iloc[-1]
        m["sma50"], m["sma200"] = num(ult["SMA50"]), num(ult["SMA200"])
        m["rsi"] = num(ult["RSI"])
        m["macd"], m["macd_senal"] = num(ult["MACD"]), num(ult["MACD_senal"])
        m["macd_hist"] = num(ult["MACD_hist"])
        m["sobre_sma200"] = (precio / m["sma200"] - 1) if m["sma200"] and precio else None
        m["cruce_dorado"] = (m["sma50"] > m["sma200"]) if m["sma50"] and m["sma200"] else None
        m["rent_1m"], m["rent_3m"] = _rentab(close, 21), _rentab(close, 63)
        m["rent_6m"], m["rent_1a"] = _rentab(close, 126), _rentab(close, 252)
        m["rent_3a"] = _rentab(close, 756)
        ret = close.pct_change().dropna()
        m["volatilidad"] = num(ret.iloc[-252:].std() * math.sqrt(252))
        ventana = close.iloc[-252:]
        m["max_52s"], m["min_52s"] = num(ventana.max()), num(ventana.min())
        m["pos_52s"] = ((precio - m["min_52s"]) / (m["max_52s"] - m["min_52s"])
                        if precio and m["max_52s"] and m["max_52s"] != m["min_52s"] else None)
        pico = close.cummax()
        m["max_drawdown"] = num((close / pico - 1).min())
        m["drawdown_actual"] = num(close.iloc[-1] / pico.iloc[-1] - 1)
    return m
