"""Backtest del veredicto: ¿las empresas que el modelo habría marcado como "Comprar"
lo hicieron mejor después que las de "Vender"?

Método
------
- Para cada fecha de evaluación (30 de abril de cada año) se "rebobina" cada empresa:
  solo se usan las cuentas anuales de ejercicios cerrados al menos 120 días antes
  (ya publicadas) y los precios hasta esa fecha.
- Con esos datos se calculan las mismas métricas y la misma nota que hoy (sin el pilar
  de analistas, porque no hay histórico gratuito de sus opiniones).
- Se mide la rentabilidad total (con dividendos) de los 12 meses siguientes.
- Se compara cada grupo con la media del universo (todas las empresas a partes iguales).

Limitaciones honestas
---------------------
- Yahoo solo da ~4 ejercicios anuales: el backtest cubre 2-3 años. Es una muestra pequeña.
- Sesgo de supervivencia: se usa la composición actual del índice (las que cayeron del
  índice no están).
- Sector y moneda se toman de hoy.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

import datos
import scoring as sc

RETRASO_CUENTAS = pd.Timedelta(days=120)
CAMPOS_INFO = ("sector", "industry", "currency", "financialCurrency", "longName", "shortName", "country")


def recortar(e: datos.Empresa, fecha: pd.Timestamp) -> datos.Empresa | None:
    """Devuelve la empresa tal como se veía en `fecha` (sin información del futuro)."""
    if e.income is None or e.income.empty or e.hist is None or e.hist.empty:
        return None
    corte = fecha - RETRASO_CUENTAS
    cols = [c for c in e.income.columns if pd.Timestamp(c) <= corte]
    if not cols:
        return None

    def filtrar(df):
        if df is None or df.empty:
            return pd.DataFrame()
        return df[[c for c in df.columns if pd.Timestamp(c) <= corte]]

    hist = e.hist[e.hist.index <= fecha]
    if len(hist) < 200:
        return None
    r = datos.Empresa(ticker=e.ticker)
    r.info = {k: e.info.get(k) for k in CAMPOS_INFO if e.info.get(k)}
    r.hist = hist
    r.income, r.balance, r.cashflow = filtrar(e.income), filtrar(e.balance), filtrar(e.cashflow)
    r.dividends = e.dividends[e.dividends.index <= fecha] if e.dividends is not None and len(e.dividends) else pd.Series(dtype=float)
    r.fecha_ref = fecha
    acc_bal = datos._val(datos._row(r.balance, "Ordinary Shares Number", "Share Issued"))
    acc = datos.acciones_coherentes(acc_bal, datos.num(e.info.get("sharesOutstanding")))
    if acc:
        r.info["sharesOutstanding"] = acc
    return r


def rentabilidad_futura(e: datos.Empresa, fecha: pd.Timestamp, dias: int = 365):
    """Rentabilidad total (precio ajustado por dividendos) entre `fecha` y `fecha + dias`."""
    col = "Adj Close" if "Adj Close" in e.hist else "Close"
    s = e.hist[col].dropna()
    if s.empty or s.index[-1] < fecha + pd.Timedelta(days=dias - 5):
        return None
    ini = s.asof(fecha)
    fin = s.asof(fecha + pd.Timedelta(days=dias))
    if not ini or pd.isna(ini) or pd.isna(fin):
        return None
    return float(fin / ini - 1)


def fechas_evaluacion(empresas: dict, dias: int = 365) -> list[pd.Timestamp]:
    """30 de abril de cada año con 12 meses posteriores ya cerrados."""
    fin = max((e.hist.index[-1] for e in empresas.values() if e.hist is not None and not e.hist.empty),
              default=pd.Timestamp.now())
    ini = min((e.hist.index[0] for e in empresas.values() if e.hist is not None and not e.hist.empty),
              default=fin)
    out = []
    for y in range(ini.year + 1, fin.year + 1):
        f = pd.Timestamp(f"{y}-04-30")
        if f - pd.Timedelta(days=300) >= ini and f + pd.Timedelta(days=dias) <= fin:
            out.append(f)
    return out


def evaluar_empresa(e, fecha, pesos, u_comprar, u_vender, margen_seg, respetar_tendencia):
    pasada = recortar(e, fecha)
    ret = rentabilidad_futura(e, fecha)
    fila = {"Ticker": e.ticker, "Empresa": e.nombre, "Fecha": fecha.date(), "Rentabilidad 12m": ret}
    if pasada is None:
        return fila
    m = datos.metricas(pasada)
    r = sc.evaluar(m, pasada.sector, pesos, u_comprar, u_vender, margen_seg, respetar_tendencia)
    fila.update({"Nota": r.nota, "Veredicto": r.veredicto, "Cobertura": r.cobertura})
    fila.update({p: r.pilares[p].nota for p in sc.PILARES})
    return fila


def ejecutar(empresas: dict, pesos: dict, u_comprar=sc.UMBRAL_COMPRAR, u_vender=sc.UMBRAL_VENDER,
             margen_seg=0.15, respetar_tendencia=True) -> pd.DataFrame:
    pesos = dict(pesos)
    pesos["Analistas"] = 0  # no hay histórico de recomendaciones
    fechas = fechas_evaluacion(empresas)
    filas = []
    for f in fechas:
        for e in empresas.values():
            try:
                filas.append(evaluar_empresa(e, f, pesos, u_comprar, u_vender, margen_seg, respetar_tendencia))
            except Exception as ex:  # una empresa rara no debe tumbar el backtest
                filas.append({"Ticker": e.ticker, "Fecha": f.date(), "Error": str(ex)})
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    # Rentabilidad frente a la media del universo de esa fecha
    media = df.groupby("Fecha")["Rentabilidad 12m"].transform("mean")
    df["Exceso vs universo"] = df["Rentabilidad 12m"] - media
    return df


# ---------------------------------------------------------------------------
# Resúmenes
# ---------------------------------------------------------------------------
def validas(df):
    if df.empty or "Nota" not in df:
        return df.iloc[0:0]
    return df.dropna(subset=["Nota", "Rentabilidad 12m"])


def por_veredicto(df: pd.DataFrame) -> pd.DataFrame:
    v = validas(df)
    if v.empty:
        return pd.DataFrame()
    g = v.groupby("Veredicto").agg(
        Empresas=("Ticker", "count"),
        Rentabilidad_media=("Rentabilidad 12m", "mean"),
        Exceso_medio=("Exceso vs universo", "mean"),
        Aciertos=("Exceso vs universo", lambda x: (x > 0).mean()),
    )
    orden = [x for x in ["Comprar", "Esperar", "Vender"] if x in g.index]
    return g.loc[orden]


def por_quintil(df: pd.DataFrame) -> pd.DataFrame:
    """Divide cada año en 5 grupos por nota (Q5 = mejores notas)."""
    v = validas(df).copy()
    if len(v) < 10:
        return pd.DataFrame()

    def q(x):
        n = min(5, len(x))
        return pd.qcut(x.rank(method="first"), n, labels=[f"Q{i + 1}" for i in range(n)])
    v["Quintil"] = v.groupby("Fecha")["Nota"].transform(q)
    g = v.groupby("Quintil", observed=True).agg(
        Empresas=("Ticker", "count"),
        Nota_media=("Nota", "mean"),
        Rentabilidad_media=("Rentabilidad 12m", "mean"),
        Exceso_medio=("Exceso vs universo", "mean"),
    )
    return g


def poder_predictivo(df: pd.DataFrame) -> pd.DataFrame:
    """Correlación de rangos (Spearman) entre la nota de cada pilar y la rentabilidad posterior,
    calculada año a año y promediada. >0,05 ya es algo; >0,10 es bueno en finanzas."""
    v = validas(df)
    if v.empty:
        return pd.DataFrame()
    filas = []
    for col in ["Nota"] + sc.PILARES:
        if col not in v:
            continue
        ics = []
        for _, g in v.groupby("Fecha"):
            g2 = g[[col, "Rentabilidad 12m"]].dropna()
            if len(g2) >= 8 and g2[col].nunique() > 1:
                ics.append(g2[col].rank().corr(g2["Rentabilidad 12m"].rank()))
        if ics:
            filas.append({"Factor": "Nota global" if col == "Nota" else col, "Correlación media": float(np.mean(ics)),
                          "Años positivos": f"{sum(1 for x in ics if x > 0)}/{len(ics)}"})
    return pd.DataFrame(filas)


def por_año(df: pd.DataFrame) -> pd.DataFrame:
    v = validas(df)
    if v.empty:
        return pd.DataFrame()
    t = v.pivot_table(index="Fecha", columns="Veredicto", values="Rentabilidad 12m", aggfunc="mean")
    t["Universo"] = v.groupby("Fecha")["Rentabilidad 12m"].mean()
    return t[[c for c in ["Comprar", "Esperar", "Vender", "Universo"] if c in t]]


def descargar_varias(tickers: list[str], funcion, hilos: int = 6, progreso=None) -> dict:
    """Descarga en paralelo. `funcion(ticker)` devuelve una Empresa."""
    out = {}
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        futuros = {ex.submit(funcion, t): t for t in tickers}
        for k, fut in enumerate(futuros):
            t = futuros[fut]
            try:
                e = fut.result()
                if e is not None and e.hist is not None and not e.hist.empty:
                    out[t] = e
            except Exception:
                pass
            if progreso:
                progreso((k + 1) / len(tickers), t)
    return out
