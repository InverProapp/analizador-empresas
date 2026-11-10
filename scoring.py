"""Motor de puntuación: convierte las métricas en 7 pilares (0-100), una nota
global y un veredicto Comprar / Esperar / Vender.

Todos los umbrales están aquí, a la vista, para que puedas ajustarlos.
Cada métrica se puntúa de forma lineal entre un valor "malo" (0 puntos) y
uno "bueno" (100 puntos), con umbrales distintos según el sector.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Referencias por sector: (bueno, malo)
# ---------------------------------------------------------------------------
SECTORES = {
    #                        PER        EV/EBITDA   P/VC        Margen op.     ROE           DeudaNeta/EBITDA
    "Technology":           dict(per=(18, 40), ev=(12, 30), pvc=(3, 12),  mop=(.25, .05), roe=(.20, .05), dn=(0, 3)),
    "Healthcare":           dict(per=(16, 35), ev=(11, 25), pvc=(2.5, 8), mop=(.20, .03), roe=(.18, .04), dn=(0.5, 3.5)),
    "Financial Services":   dict(per=(9, 18),  ev=None,     pvc=(.8, 2),  mop=(.35, .15), roe=(.14, .06), dn=None),
    "Consumer Cyclical":    dict(per=(13, 30), ev=(8, 18),  pvc=(2, 7),   mop=(.12, .03), roe=(.18, .05), dn=(1, 4)),
    "Consumer Defensive":   dict(per=(16, 30), ev=(10, 20), pvc=(3, 9),   mop=(.12, .04), roe=(.18, .06), dn=(1.5, 4)),
    "Industrials":          dict(per=(14, 30), ev=(9, 18),  pvc=(2, 7),   mop=(.14, .04), roe=(.16, .05), dn=(1, 4)),
    "Energy":               dict(per=(8, 18),  ev=(4, 9),   pvc=(1, 3),   mop=(.15, .03), roe=(.14, .04), dn=(0.5, 3)),
    "Utilities":            dict(per=(13, 24), ev=(8, 14),  pvc=(1.2, 3), mop=(.20, .08), roe=(.11, .05), dn=(3, 6.5)),
    "Real Estate":          dict(per=(15, 40), ev=(14, 28), pvc=(.8, 2),  mop=(.35, .10), roe=(.08, .02), dn=(5, 12)),
    "Basic Materials":      dict(per=(10, 22), ev=(6, 12),  pvc=(1.2, 4), mop=(.15, .04), roe=(.14, .04), dn=(0.5, 3)),
    "Communication Services": dict(per=(14, 30), ev=(8, 18), pvc=(2, 7),  mop=(.20, .05), roe=(.15, .05), dn=(1, 3.5)),
}
SECTOR_DEFECTO = dict(per=(14, 30), ev=(9, 18), pvc=(2, 6), mop=(.15, .04), roe=(.15, .05), dn=(1, 4))

SECTORES_ES = {
    "Technology": "Tecnología", "Healthcare": "Salud", "Financial Services": "Financiero",
    "Consumer Cyclical": "Consumo cíclico", "Consumer Defensive": "Consumo defensivo",
    "Industrials": "Industria", "Energy": "Energía", "Utilities": "Utilities",
    "Real Estate": "Inmobiliario", "Basic Materials": "Materiales básicos",
    "Communication Services": "Comunicaciones",
}

PILARES = ["Valoración", "Calidad", "Salud financiera", "Crecimiento", "Dividendo", "Técnico", "Analistas"]

PESOS_DEFECTO = {"Valoración": 25, "Calidad": 20, "Salud financiera": 15, "Crecimiento": 15,
                 "Dividendo": 5, "Técnico": 10, "Analistas": 10}

UMBRAL_COMPRAR = 65
UMBRAL_VENDER = 45


def lineal(x, malo, bueno):
    """0 puntos en `malo`, 100 en `bueno`, lineal entre medias. Sirve en ambos sentidos."""
    if x is None:
        return None
    if bueno == malo:
        return 50.0
    p = (x - malo) / (bueno - malo) * 100
    return max(0.0, min(100.0, p))


# ---------------------------------------------------------------------------
# Estructuras de resultado
# ---------------------------------------------------------------------------
@dataclass
class Item:
    nombre: str
    valor: object            # valor bruto
    formato: str             # "x", "%", "num", "bool"
    nota: float | None       # 0-100
    peso: float
    referencia: str = ""     # texto con el umbral usado


@dataclass
class Pilar:
    nombre: str
    items: list = field(default_factory=list)

    @property
    def nota(self):
        v = [(i.nota, i.peso) for i in self.items if i.nota is not None]
        if not v:
            return None
        return sum(n * p for n, p in v) / sum(p for _, p in v)

    @property
    def cobertura(self):
        if not self.items:
            return 0
        return sum(1 for i in self.items if i.nota is not None) / len(self.items)


@dataclass
class Resultado:
    pilares: dict
    nota: float | None
    veredicto: str
    veredicto_bruto: str
    confianza: str
    cobertura: float
    alertas: list
    positivos: list
    negativos: list
    valor_justo: float | None
    precio_compra: float | None
    pesos: dict


def _fmt_ref(bueno, malo, formato):
    def f(v):
        if formato == "%":
            return f"{v * 100:.0f}%"
        return f"{v:g}"
    return f"bueno {f(bueno)} · malo {f(malo)}"


def _item(nombre, valor, formato, malo, bueno, peso):
    return Item(nombre, valor, formato, lineal(valor, malo, bueno), peso, _fmt_ref(bueno, malo, formato))


# ---------------------------------------------------------------------------
# Pilares
# ---------------------------------------------------------------------------
def evaluar(m: dict, sector: str, pesos: dict | None = None, umbral_comprar=UMBRAL_COMPRAR,
            umbral_vender=UMBRAL_VENDER, margen_seguridad=0.15, respetar_tendencia=True) -> Resultado:
    pesos = dict(PESOS_DEFECTO if pesos is None else pesos)
    ref = SECTORES.get(sector, SECTOR_DEFECTO)
    financiera = sector == "Financial Services"
    inmobiliaria = sector == "Real Estate"
    g = m.get

    pil = {n: Pilar(n) for n in PILARES}

    # 1. Valoración ---------------------------------------------------------
    v = pil["Valoración"].items
    v.append(_item("PER", g("per"), "x", ref["per"][1], ref["per"][0], 2))
    v.append(_item("PER futuro", g("per_fwd"), "x", ref["per"][1], ref["per"][0], 1))
    if ref["ev"]:
        v.append(_item("EV/EBITDA", g("ev_ebitda"), "x", ref["ev"][1], ref["ev"][0], 2))
    v.append(_item("Precio/Valor contable", g("p_vc"), "x", ref["pvc"][1], ref["pvc"][0], 3 if financiera or inmobiliaria else 1))
    v.append(_item("PEG", g("peg"), "x", 2.5, 1.0, 1))
    if not financiera:
        v.append(_item("Rentabilidad FCF (FCF/cap.)", g("fcf_yield"), "%", 0.01, 0.07, 2))
        v.append(_item("Margen de seguridad DCF", g("margen_seguridad_dcf"), "%", -0.30, 0.30, 2))
    v.append(_item("Margen de seguridad Graham", g("margen_seguridad_graham"), "%", -0.50, 0.30, 0.5))

    # 2. Calidad --------------------------------------------------------------
    c = pil["Calidad"].items
    c.append(_item("ROE", g("roe"), "%", ref["roe"][1], ref["roe"][0], 2))
    if not financiera:
        c.append(_item("ROIC (aprox.)", g("roic"), "%", 0.04, 0.15, 2))
        c.append(_item("Margen operativo", g("margen_operativo"), "%", ref["mop"][1], ref["mop"][0], 2))
    c.append(_item("Margen neto", g("margen_neto"), "%", 0.02, 0.15 if not financiera else 0.25, 1))
    c.append(_item("ROA", g("roa"), "%", 0.005 if financiera else 0.02, 0.015 if financiera else 0.10, 1))
    c.append(_item("Piotroski F-Score (0-9)", g("piotroski"), "num", 3, 8, 2))

    # 3. Salud financiera -----------------------------------------------------
    s = pil["Salud financiera"].items
    if not financiera:
        if ref["dn"]:
            dn = g("deuda_neta_ebitda")
            if dn is None and g("deuda_neta") is not None and g("deuda_neta") < 0:
                dn = -1.0  # caja neta
            s.append(_item("Deuda neta / EBITDA", dn, "x", ref["dn"][1], ref["dn"][0], 2))
        s.append(_item("Deuda / Patrimonio", g("deuda_patrimonio"), "x", 3.0 if inmobiliaria else 2.0,
                       0.6 if inmobiliaria else 0.3, 1))
        s.append(_item("Liquidez corriente", g("liquidez"), "x", 0.8, 2.0, 1))
        s.append(_item("Cobertura de intereses", g("cobertura_intereses"), "x", 2, 10, 2))
        if not inmobiliaria:
            s.append(_item("Altman Z-Score", g("altman_z"), "num", 1.8, 3.0, 2))
    else:
        # Para bancos y aseguradoras la deuda es su materia prima: miramos rentabilidad y P/VC
        s.append(_item("ROE (solvencia vía rentabilidad)", g("roe"), "%", 0.05, 0.12, 1))
        s.append(_item("Beta (riesgo de mercado)", g("beta"), "num", 1.6, 0.8, 1))

    # 4. Crecimiento --------------------------------------------------------
    cr = pil["Crecimiento"].items
    cr.append(_item("Crecimiento ingresos (último año)", g("crec_ingresos"), "%", -0.02, 0.15, 1))
    cr.append(_item("Crecimiento beneficio (último año)", g("crec_beneficio"), "%", -0.10, 0.15, 1))
    cr.append(_item("CAGR ingresos (≈4 años)", g("cagr_ingresos"), "%", 0.0, 0.12, 2))
    cr.append(_item("CAGR beneficio (≈4 años)", g("cagr_beneficio"), "%", -0.05, 0.12, 1))
    if not financiera:
        cr.append(_item("CAGR flujo de caja libre", g("cagr_fcf"), "%", -0.05, 0.12, 1))

    # 5. Dividendo ----------------------------------------------------------
    d = pil["Dividendo"].items
    rd = g("rent_dividendo") or 0
    if rd > 0:
        d.append(_item("Rentabilidad por dividendo", rd, "%", 0.01, 0.05, 2))
        p = g("payout")
        if p is not None:
            nota_p = (100.0 if p >= 0.2 else 75.0) if p <= 0.6 else lineal(p, 1.0, 0.6)
            d.append(Item("Payout (dividendo/beneficio)", p, "%", nota_p, 1.5, "ideal 20-60% · malo >100%"))
        d.append(_item("Crecimiento dividendo 5a", g("cagr_dividendo_5a"), "%", -0.02, 0.08, 1))
        d.append(_item("Años sin recortar dividendo", g("anos_sin_recorte"), "num", 0, 10, 1))
    # Si no paga dividendo el pilar queda vacío y su peso se reparte entre los demás

    # 6. Técnico ------------------------------------------------------------
    t = pil["Técnico"].items
    t.append(_item("Precio vs media 200 sesiones", g("sobre_sma200"), "%", -0.15, 0.10, 2))
    cd = g("cruce_dorado")
    t.append(Item("Media 50 > media 200", cd, "bool", None if cd is None else (100.0 if cd else 0.0), 1, "tendencia alcista"))
    rsi = g("rsi")
    if rsi is not None:
        nota_rsi = 75 if rsi <= 30 else 60 if rsi <= 50 else 65 if rsi <= 70 else 40 if rsi <= 80 else 20
        t.append(Item("RSI (14)", rsi, "num", float(nota_rsi), 1, "<30 sobreventa · >70 sobrecompra"))
    mh = g("macd_hist")
    t.append(Item("MACD sobre su señal", None if mh is None else mh > 0, "bool",
                  None if mh is None else (70.0 if mh > 0 else 30.0), 1, "impulso alcista"))
    t.append(_item("Rentabilidad 6 meses", g("rent_6m"), "%", -0.15, 0.15, 1))
    t.append(_item("Rentabilidad 12 meses", g("rent_1a"), "%", -0.20, 0.25, 1))

    # 7. Analistas ----------------------------------------------------------
    a = pil["Analistas"].items
    n_an = g("n_analistas") or 0
    if n_an >= 3:
        a.append(_item("Potencial al precio objetivo", g("potencial_analistas"), "%", -0.10, 0.25, 2))
        a.append(_item("Recomendación media (1 compra · 5 venta)", g("recomendacion_media"), "num", 3.5, 1.5, 1))

    # ---------------------------------------------------------------------
    # Nota global
    # ---------------------------------------------------------------------
    notas = {k: p.nota for k, p in pil.items()}
    activos = {k: pesos.get(k, 0) for k, n in notas.items() if n is not None and pesos.get(k, 0) > 0}
    nota = (sum(notas[k] * w for k, w in activos.items()) / sum(activos.values())) if activos else None

    todos = [i for p in pil.values() for i in p.items]
    cobertura = (sum(1 for i in todos if i.nota is not None) / len(todos)) if todos else 0

    if nota is None:
        bruto = "Sin datos"
    elif nota >= umbral_comprar:
        bruto = "Comprar"
    elif nota >= umbral_vender:
        bruto = "Esperar"
    else:
        bruto = "Vender"
    veredicto = bruto

    # ---------------------------------------------------------------------
    # Alertas que limitan el veredicto
    # ---------------------------------------------------------------------
    alertas = []

    def tope(texto, maximo="Esperar"):
        nonlocal veredicto
        alertas.append(texto)
        if veredicto == "Comprar" and maximo in ("Esperar", "Vender"):
            veredicto = maximo

    z = g("altman_z")
    if z is not None and z < 1.81 and not financiera and not inmobiliaria:
        z_txt = f"{z:.2f}".replace(".", ",")
        tope(f"Altman Z = {z_txt} (< 1,81): zona de riesgo financiero.")
    pio = g("piotroski")
    if pio is not None and pio <= 2:
        tope(f"Piotroski F-Score muy bajo ({pio:g}/9): fundamentales deteriorándose.")
    if (g("fcf") is not None and g("fcf") < 0 and g("deuda_neta_ebitda") is not None
            and g("deuda_neta_ebitda") > 4 and not financiera):
        tope("Quema caja (FCF negativo) con deuda alta (> 4x EBITDA).")
    if g("payout") is not None and g("payout") > 1.2 and rd > 0:
        alertas.append(f"Payout del {g('payout') * 100:.0f}%: el dividendo no está cubierto por el beneficio.")
    if (respetar_tendencia and g("sobre_sma200") is not None and g("sobre_sma200") < -0.20
            and mh is not None and mh < 0):
        tope("Tendencia bajista fuerte (> 20% bajo la media de 200 y MACD negativo): mejor esperar a que gire.")
    if not g("misma_moneda", True):
        alertas.append("La empresa reporta en una moneda distinta a la de cotización: DCF, Graham y Altman se omiten.")
    if cobertura < 0.45:
        alertas.append(f"Solo hay datos para el {cobertura * 100:.0f}% de las métricas: conclusión poco fiable.")
        if veredicto != "Sin datos":
            veredicto = "Esperar" if veredicto == "Comprar" else veredicto

    confianza = "Alta" if cobertura >= 0.75 else "Media" if cobertura >= 0.55 else "Baja"

    # ---------------------------------------------------------------------
    # Puntos fuertes y débiles
    # ---------------------------------------------------------------------
    positivos, negativos = [], []
    for p in pil.values():
        for i in p.items:
            if i.nota is None:
                continue
            if i.nota >= 80 and i.peso >= 1:
                positivos.append((p.nombre, i))
            elif i.nota <= 20 and i.peso >= 1:
                negativos.append((p.nombre, i))
    positivos.sort(key=lambda x: -x[1].peso * x[1].nota)
    negativos.sort(key=lambda x: -x[1].peso * (100 - x[1].nota))

    # ---------------------------------------------------------------------
    # Valor justo combinado y precio de compra
    # ---------------------------------------------------------------------
    estimaciones = [x for x in (g("valor_dcf"), g("valor_graham"),
                                g("precio_objetivo") if n_an >= 3 else None) if x]
    valor_justo = statistics.median(estimaciones) if estimaciones else None
    precio_compra = valor_justo * (1 - margen_seguridad) if valor_justo else None

    return Resultado(pil, nota, veredicto, bruto, confianza, cobertura, alertas,
                     positivos[:6], negativos[:6], valor_justo, precio_compra, pesos)
