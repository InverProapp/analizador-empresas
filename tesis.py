"""Tesis de inversión: por qué sigues una empresa y qué tendría que pasar para que dejes de creerlo.

Método inspirado en el seguimiento de tesis de los analistas (equity research):
- Una frase con la idea central y una posición (alcista o bajista).
- 3-5 pilares que se pueden comprobar con datos (la web los revisa sola) o a mano.
- Riesgos que la invalidarían, precio objetivo y precio de salida (stop).
- Un registro con cada novedad: refuerza / debilita / neutral, y la convicción resultante.
- Una tesis debe poder fallar: si nada puede demostrar que te equivocas, no es una tesis.
"""
from __future__ import annotations

import time
import uuid

import usuario as us

# clave -> (etiqueta, formato, de dónde sale)   formato: pct (en %), x (veces), num
METRICAS = {
    "crec_ingresos": ("Crecimiento de ventas (último año)", "pct"),
    "cagr_ingresos": ("Crecimiento anual de ventas (varios años)", "pct"),
    "crec_beneficio": ("Crecimiento del beneficio (último año)", "pct"),
    "margen_operativo": ("Margen operativo", "pct"),
    "margen_neto": ("Margen neto", "pct"),
    "roe": ("ROE (rentabilidad sobre fondos propios)", "pct"),
    "roic": ("ROIC (rentabilidad del capital invertido)", "pct"),
    "deuda_neta_ebitda": ("Deuda neta / EBITDA", "x"),
    "liquidez": ("Ratio de liquidez", "x"),
    "per": ("PER", "x"),
    "per_fwd": ("PER esperado (próximo año)", "x"),
    "ev_ebitda": ("EV / EBITDA", "x"),
    "fcf_yield": ("Rentabilidad por flujo de caja libre", "pct"),
    "rent_dividendo": ("Rentabilidad por dividendo", "pct"),
    "payout": ("Payout (parte del beneficio que reparte)", "pct"),
    "piotroski": ("Piotroski (0-9)", "num"),
    "altman_z": ("Altman Z (riesgo de quiebra)", "num"),
    "_nota": ("Nota global del modelo (0-100)", "num"),
    "_descuento": ("Descuento frente al valor justo", "pct"),
}
OPERADORES = {">": "mayor que", "<": "menor que"}
CONVICCION = ["Alta", "Media", "Baja"]
IMPACTO = ["Refuerza", "Neutral", "Debilita"]
ACCIONES = ["Sin cambios", "Comprar más", "Reducir", "Vender / cerrar"]
MANUAL = ["Va bien", "Vigilar", "Falla"]
DIAS_REVISION = 90


def vacia() -> dict:
    hoy = time.strftime("%Y-%m-%d")
    return {"posicion": "Alcista", "enunciado": "", "pilares": [], "riesgos": [], "objetivo": None, "stop": None,
            "conviccion": "Media", "horizonte": "1-3 años", "creada": hoy, "revisada": hoy, "registro": []}


def de(ticker: str) -> dict | None:
    return us.datos().setdefault("tesis", {}).get(ticker)


def todas() -> dict:
    return us.datos().setdefault("tesis", {})


def guardar(ticker: str, t: dict, revisada: bool = True):
    if revisada:
        t["revisada"] = time.strftime("%Y-%m-%d")
    todas()[ticker] = t
    us.guardar()


def borrar(ticker: str):
    todas().pop(ticker, None)
    us.guardar()


def nuevo_id() -> str:
    return uuid.uuid4().hex[:6]


def valor_metrica(clave: str, m: dict | None, r=None):
    """Valor actual de una métrica en las mismas unidades que escribe el usuario (% como 15 = 15%)."""
    if m is None:
        return None
    if clave == "_nota":
        return getattr(r, "nota", None) if r is not None else None
    if clave == "_descuento":
        vj, p = getattr(r, "valor_justo", None), m.get("precio")
        return (vj / p - 1) * 100 if vj and p else None
    v = m.get(clave)
    if v is None:
        return None
    return v * 100 if METRICAS.get(clave, ("", ""))[1] == "pct" and clave != "_descuento" else v


def fmt_valor(clave: str, v) -> str:
    if v is None:
        return "—"
    f = METRICAS.get(clave, ("", "num"))[1]
    txt = f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return txt + ("%" if f == "pct" else "x" if f == "x" else "")


def evaluar_pilar(p: dict, m: dict | None, r=None):
    """(estado, texto actual). estado: True cumple, False falla, None sin dato / 'Vigilar'."""
    if not p.get("metrica"):
        e = p.get("manual", "Va bien")
        return {"Va bien": True, "Falla": False}.get(e), e
    v = valor_metrica(p["metrica"], m, r)
    if v is None:
        return None, "sin dato"
    objetivo = p.get("valor") or 0
    ok = v > objetivo if p.get("op", ">") == ">" else v < objetivo
    return ok, fmt_valor(p["metrica"], v)


def describir_pilar(p: dict) -> str:
    if not p.get("metrica"):
        return p.get("texto", "")
    et, f = METRICAS[p["metrica"]]
    obj = fmt_valor(p["metrica"], p.get("valor") or 0)
    base = f"{et} {OPERADORES[p.get('op', '>')]} {obj}"
    return f"{p['texto']} · {base}" if p.get("texto") else base


def marcador(t: dict, m: dict | None, r=None) -> dict:
    """Resumen del estado de la tesis: pilares que se cumplen, objetivo/stop y si toca revisarla."""
    estados = [evaluar_pilar(p, m, r)[0] for p in t.get("pilares", [])]
    precio = (m or {}).get("precio")
    alcista = t.get("posicion", "Alcista") == "Alcista"
    obj, stop = t.get("objetivo"), t.get("stop")
    dias = None
    try:
        dias = int((time.time() - time.mktime(time.strptime(t.get("revisada", ""), "%Y-%m-%d"))) // 86400)
    except Exception:
        pass
    toca_stop = bool(precio and stop and ((precio <= stop) if alcista else (precio >= stop)))
    toca_obj = bool(precio and obj and ((precio >= obj) if alcista else (precio <= obj)))
    n_ok, n_mal, n = sum(1 for e in estados if e is True), sum(1 for e in estados if e is False), len(estados)
    if toca_stop or (n and n_mal >= max(2, n / 2)):
        salud = "🔴 Rota"
    elif n_mal or toca_obj:
        salud = "🟡 Vigilar"
    elif n:
        salud = "🟢 Intacta"
    else:
        salud = "⚪ Sin pilares"
    return {"ok": n_ok, "mal": n_mal, "n": n, "salud": salud, "toca_stop": toca_stop, "toca_objetivo": toca_obj,
            "hasta_objetivo": (obj / precio - 1) if obj and precio else None,
            "hasta_stop": (stop / precio - 1) if stop and precio else None,
            "dias_sin_revisar": dias, "revisar": dias is not None and dias >= DIAS_REVISION}
