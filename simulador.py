"""Simulador de operaciones sobre una empresa.

Recorre el histórico día a día con precios de apertura, máximo, mínimo y cierre:
- Compra cuando el precio toca el nivel de compra (si abre por debajo, compra en la apertura).
- Vende cuando toca el nivel de venta (si abre por encima, vende en la apertura) o salta el stop-loss.
- Mientras tiene acciones, cobra los dividendos.
- Aplica una comisión por operación.

Los niveles pueden ser fijos (los que pones tú) o cambiar con el tiempo (los que calculaba
el modelo con la información de cada momento).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Resultado:
    operaciones: pd.DataFrame
    capital: pd.Series              # valor de la cartera cada día
    capital_bh: pd.Series           # comprar el primer día y mantener
    compras: list = field(default_factory=list)   # (fecha, precio)
    ventas: list = field(default_factory=list)    # (fecha, precio, motivo)
    abierta: bool = False

    def resumen(self, capital_inicial: float) -> dict:
        c, bh = self.capital, self.capital_bh
        años = max((c.index[-1] - c.index[0]).days / 365.25, 1e-9)
        ops = self.operaciones
        cerradas = ops[ops["Estado"] == "Cerrada"] if not ops.empty else ops

        def anual(final):
            return (final / capital_inicial) ** (1 / años) - 1 if final > 0 else -1.0

        def max_dd(s):
            return float((s / s.cummax() - 1).min())
        invertido = 0.0
        if not ops.empty:
            dias = sum((pd.Timestamp(r["Venta"] if pd.notna(r["Venta"]) else c.index[-1]) - pd.Timestamp(r["Compra"])).days
                       for _, r in ops.iterrows())
            invertido = dias / max((c.index[-1] - c.index[0]).days, 1)
        return {
            "final": float(c.iloc[-1]), "rent_total": float(c.iloc[-1] / capital_inicial - 1), "rent_anual": anual(c.iloc[-1]),
            "bh_final": float(bh.iloc[-1]), "bh_total": float(bh.iloc[-1] / capital_inicial - 1), "bh_anual": anual(bh.iloc[-1]),
            "n_ops": int(len(ops)), "ganadoras": float((cerradas["Resultado %"] > 0).mean()) if len(cerradas) else None,
            "max_dd": max_dd(c), "bh_max_dd": max_dd(bh), "tiempo_invertido": invertido, "años": años,
        }


def simular(hist: pd.DataFrame, nivel_compra, nivel_venta, stop_loss: float = 0.0, repetir: bool = True,
            capital: float = 10_000.0, comision: float = 0.001) -> Resultado:
    """`nivel_compra` / `nivel_venta`: número fijo o pd.Series indexada por fecha (se usa el último
    valor conocido cada día; NaN = no operar). `stop_loss`: 0.15 = vender si cae un 15% desde la compra."""
    h = hist.dropna(subset=["Close"]).copy()
    for col in ("Open", "High", "Low"):
        if col not in h:
            h[col] = h["Close"]
        h[col] = h[col].fillna(h["Close"])
    div = h["Dividends"].fillna(0) if "Dividends" in h else pd.Series(0.0, index=h.index)

    def serie(nivel):
        if isinstance(nivel, pd.Series):
            return nivel.sort_index().reindex(h.index, method="ffill")
        return pd.Series(float(nivel) if nivel is not None else np.nan, index=h.index)
    comp, vent = serie(nivel_compra), serie(nivel_venta)

    caja, acciones, entrada, fecha_entrada = capital, 0.0, None, None
    valores, ops, compras, ventas = [], [], [], []
    terminado = False
    for fecha, f in h.iterrows():
        o, hi, lo, cl = f["Open"], f["High"], f["Low"], f["Close"]
        if acciones > 0:
            if div.loc[fecha] > 0:
                caja += acciones * div.loc[fecha]
            precio_venta, motivo = None, None
            stop = entrada * (1 - stop_loss) if stop_loss > 0 else None
            if stop is not None and lo <= stop:
                precio_venta, motivo = min(o, stop), "Stop-loss"
            elif not np.isnan(vent.loc[fecha]) and hi >= vent.loc[fecha]:
                precio_venta, motivo = max(o, vent.loc[fecha]), "Objetivo"
            if precio_venta is not None:
                caja += acciones * precio_venta * (1 - comision)
                ops[-1].update({"Venta": fecha.date(), "Precio venta": precio_venta, "Motivo": motivo,
                                "Días": (fecha - fecha_entrada).days,
                                "Resultado %": precio_venta * (1 - comision) / (entrada * (1 + comision)) - 1,
                                "Estado": "Cerrada"})
                ops[-1]["Resultado €"] = ops[-1]["Importe"] * ops[-1]["Resultado %"]
                ventas.append((fecha, precio_venta, motivo))
                acciones, entrada = 0.0, None
                if not repetir:
                    terminado = True
        elif not terminado and not np.isnan(comp.loc[fecha]) and lo <= comp.loc[fecha]:
            # No recomprar el mismo día de una venta
            if not ventas or ventas[-1][0] != fecha:
                precio = min(o, comp.loc[fecha])
                importe = caja
                acciones = importe * (1 - comision) / precio
                caja = 0.0
                entrada, fecha_entrada = precio, fecha
                compras.append((fecha, precio))
                ops.append({"Compra": fecha.date(), "Precio compra": precio, "Importe": importe, "Venta": None,
                            "Precio venta": None, "Motivo": None, "Días": None, "Resultado %": None,
                            "Resultado €": None, "Estado": "Abierta"})
        valores.append(caja + acciones * cl)

    capital_serie = pd.Series(valores, index=h.index)
    # Comprar y mantener (con dividendos reinvertidos en caja)
    p0 = h["Open"].iloc[0]
    acc_bh = capital * (1 - comision) / p0
    caja_bh = (div * acc_bh).cumsum()
    bh = acc_bh * h["Close"] + caja_bh

    df_ops = pd.DataFrame(ops)
    if not df_ops.empty:
        abiertas = df_ops["Estado"] == "Abierta"
        if abiertas.any():  # valorar la posición abierta al último cierre
            ult = h["Close"].iloc[-1]
            i = df_ops.index[abiertas][0]
            r = ult / (df_ops.loc[i, "Precio compra"] * (1 + comision)) - 1
            df_ops.loc[i, ["Resultado %", "Días"]] = [r, (h.index[-1] - pd.Timestamp(df_ops.loc[i, "Compra"])).days]
            df_ops.loc[i, "Resultado €"] = df_ops.loc[i, "Importe"] * r
    return Resultado(df_ops, capital_serie, bh, compras, ventas, abierta=acciones > 0)


def niveles_modelo(e, evaluar_en_fecha) -> pd.DataFrame:
    """Zona de compra y valor justo que daba el modelo en cada momento (se actualizan cuando
    se publican unas cuentas anuales nuevas). `evaluar_en_fecha(fecha)` devuelve el Resultado
    del scoring con la información de esa fecha, o None."""
    if e.income is None or e.income.empty or e.hist is None or e.hist.empty:
        return pd.DataFrame()
    fechas = sorted(pd.Timestamp(c) + pd.Timedelta(days=120) for c in e.income.columns)
    inicio, fin = e.hist.index[0], e.hist.index[-1]
    filas = []
    for f in fechas:
        if f > fin:
            continue
        f = max(f, inicio + pd.Timedelta(days=300))  # hace falta algo de histórico de precios
        r = evaluar_en_fecha(f)
        if r is None:
            continue
        filas.append({"fecha": f, "zona_compra": r.precio_compra, "valor_justo": r.valor_justo,
                      "nota": r.nota, "veredicto": r.veredicto})
    if not filas:
        return pd.DataFrame()
    return pd.DataFrame(filas).drop_duplicates("fecha", keep="last").set_index("fecha")
