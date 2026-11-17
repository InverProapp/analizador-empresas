"""Contenido de la sección «Aprende trading»: ejemplos dibujados, explicaciones y detectores de patrones."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

VERDE, ROJO, AZUL, GRIS, NARANJA = "#1a9e5c", "#d64545", "#2a6fdb", "#9aa4b2", "#f39c12"

# ---------------------------------------------------------------------------
# Velas japonesas
# ---------------------------------------------------------------------------
BAJA = [(20, 20.5, 18.8, 19), (19, 19.3, 17.6, 17.8), (17.8, 18.1, 16.5, 16.7), (16.7, 17, 15.6, 15.8)]
SUBE = [(10, 11.3, 9.8, 11), (11, 12.3, 10.8, 12.1), (12.1, 13.4, 11.9, 13.2), (13.2, 14.5, 13, 14.3)]

# nombre: (tipo, contexto, velas del patrón, vela de confirmación, qué es, qué indica, cómo confirmarlo, trampa)
VELAS = {
    "Martillo": ("Giro alcista", BAJA, [(15.6, 15.8, 13.6, 15.7)], (15.8, 17, 15.7, 16.9),
                 "Cuerpo pequeño arriba y una mecha inferior larga (al menos el doble del cuerpo), tras una bajada.",
                 "Los vendedores empujaron el precio muy abajo, pero los compradores lo devolvieron arriba antes del cierre: "
                 "la presión vendedora se agota.",
                 "Que la vela siguiente cierre por encima del máximo del martillo, mejor con volumen alto.",
                 "Sin bajada previa no es un martillo: es solo una vela con mecha."),
    "Hombre colgado": ("Giro bajista", SUBE, [(14.4, 14.6, 12.6, 14.5)], (14.4, 14.5, 13.2, 13.4),
                       "Misma forma que el martillo, pero aparece después de una subida.",
                       "Durante la sesión hubo ventas fuertes: aviso de que los compradores empiezan a flojear.",
                       "Que la siguiente vela cierre por debajo del cuerpo del hombre colgado.",
                       "Es una señal débil por sí sola: muchas veces la subida continúa."),
    "Estrella fugaz": ("Giro bajista", SUBE, [(14.4, 16.4, 14.3, 14.5)], (14.4, 14.5, 13.3, 13.5),
                       "Cuerpo pequeño abajo y mecha superior larga, tras una subida.",
                       "Los compradores intentaron subir más y fueron rechazados con fuerza: posible techo.",
                       "Cierre de la vela siguiente por debajo del cuerpo de la estrella.",
                       "Si el volumen es bajo, el rechazo tiene poca importancia."),
    "Martillo invertido": ("Giro alcista", BAJA, [(15.6, 17.6, 15.5, 15.75)], (15.8, 17.2, 15.7, 17.1),
                           "Cuerpo pequeño abajo y mecha superior larga, tras una bajada.",
                           "Primer intento serio de los compradores después de la caída.",
                           "Necesita una vela alcista siguiente que cierre por encima de su cuerpo.",
                           "Es de las menos fiables: espera siempre confirmación."),
    "Doji": ("Indecisión", BAJA, [(15.7, 16.4, 15.0, 15.72)], (15.8, 16.8, 15.7, 16.6),
             "Apertura y cierre casi iguales: el cuerpo es una raya.",
             "Empate entre compradores y vendedores. Tras una tendencia larga puede anunciar que se agota.",
             "La dirección de la vela siguiente decide hacia dónde se rompe el empate.",
             "En un mercado lateral, los doji son normales y no significan nada."),
    "Envolvente alcista": ("Giro alcista", BAJA, [(15.8, 16, 15.2, 15.3), (15.1, 16.6, 15, 16.5)], None,
                           "Una vela bajista pequeña seguida de una alcista cuyo cuerpo «envuelve» por completo al anterior.",
                           "Los compradores no solo frenan la caída: recuperan todo lo perdido el día anterior y más.",
                           "Mejor si aparece en un soporte y con volumen mayor que el de los días previos.",
                           "Si la vela grande cierra lejos del máximo (mecha superior larga), pierde fuerza."),
    "Envolvente bajista": ("Giro bajista", SUBE, [(14.3, 14.8, 14.2, 14.7), (14.9, 15, 13.6, 13.7)], None,
                           "Una vela alcista pequeña seguida de una bajista que la envuelve por completo.",
                           "Los vendedores toman el control de golpe en la zona alta.",
                           "Más fiable cerca de una resistencia y con volumen alto.",
                           "En tendencias alcistas muy fuertes suele quedarse en una simple pausa."),
    "Harami alcista": ("Giro alcista", BAJA, [(16.6, 16.7, 14.8, 15), (15.3, 15.9, 15.2, 15.8)], None,
                       "Una vela bajista grande seguida de una pequeña alcista que queda dentro de su cuerpo («embarazada», en japonés).",
                       "La caída pierde impulso: el segundo día los vendedores ya no consiguen bajar más.",
                       "Necesita que el precio supere después el máximo de la vela grande.",
                       "Es una señal de freno más que de giro: muchas veces solo precede a un lateral."),
    "Estrella de la mañana": ("Giro alcista", BAJA, [(16.6, 16.7, 14.9, 15), (14.7, 14.9, 14.3, 14.6), (14.9, 16.4, 14.8, 16.2)], None,
                              "Tres velas: una bajista grande, una pequeña (indecisión) y una alcista grande que cierra por encima "
                              "de la mitad de la primera.",
                              "Paso claro del control de vendedores a compradores en tres días.",
                              "Es de las más fiables. Mejor con volumen creciente en la tercera vela.",
                              "Si la tercera vela es pequeña, el patrón no está completo."),
    "Estrella de la tarde": ("Giro bajista", SUBE, [(14.3, 15.9, 14.2, 15.8), (16.0, 16.3, 15.9, 16.1), (15.8, 15.9, 14.3, 14.4)], None,
                             "La versión bajista: alcista grande, pequeña arriba y bajista grande.",
                             "Los compradores se quedan sin fuerza en lo alto y los vendedores toman el mando.",
                             "Fiable si la tercera vela cierra por debajo de la mitad de la primera.",
                             "Cuidado en mercados muy alcistas: confirma con el volumen."),
    "Tres soldados blancos": ("Continuación / giro alcista", BAJA, [(15.8, 16.9, 15.7, 16.8), (16.7, 17.9, 16.6, 17.8), (17.7, 18.9, 17.6, 18.8)], None,
                              "Tres velas alcistas seguidas, cada una abre dentro del cuerpo anterior y cierra cerca de su máximo.",
                              "Compra sostenida durante varios días: entrada de dinero fuerte.",
                              "Volumen alto y estable en las tres velas.",
                              "Después de una subida muy larga pueden marcar el final (agotamiento)."),
    "Tres cuervos negros": ("Giro bajista", SUBE, [(14.3, 14.4, 13.2, 13.3), (13.4, 13.5, 12.2, 12.3), (12.4, 12.5, 11.2, 11.3)], None,
                            "Tres velas bajistas seguidas que cierran cerca de sus mínimos.",
                            "Venta sostenida: los vendedores dominan varias sesiones seguidas.",
                            "Volumen creciente y ruptura de un soporte.",
                            "Tras una caída muy fuerte suelen venir rebotes."),
    "Marubozu": ("Fuerza", BAJA, [(15.8, 17.6, 15.8, 17.6)], None,
                 "Vela grande sin mechas (o casi): abre en el mínimo y cierra en el máximo (o al revés si es bajista).",
                 "Uno de los bandos domina toda la sesión sin oposición.",
                 "Más importante si rompe un soporte o resistencia.",
                 "Un solo día de fuerza no hace una tendencia."),
}


def grafico_velas(velas: list[tuple], resaltar: tuple[int, int] | None = None, titulo: str = "", alto: int = 250,
                  anotaciones: list[dict] | None = None) -> go.Figure:
    o, h, l, c = zip(*velas)
    x = list(range(1, len(velas) + 1))
    fig = go.Figure(go.Candlestick(x=x, open=o, high=h, low=l, close=c, increasing_line_color=VERDE,
                                   decreasing_line_color=ROJO, increasing_fillcolor=VERDE, decreasing_fillcolor=ROJO,
                                   showlegend=False, hoverinfo="skip"))
    if resaltar:
        fig.add_vrect(x0=resaltar[0] - 0.5, x1=resaltar[1] + 0.5, fillcolor="rgba(42,111,219,.10)", line_width=0)
    for a in anotaciones or []:
        fig.add_annotation(**a)
    fig.update_layout(height=alto, margin=dict(l=4, r=4, t=28 if titulo else 6, b=4), xaxis_rangeslider_visible=False,
                      title=dict(text=titulo, font=dict(size=13)), xaxis=dict(visible=False), yaxis=dict(visible=False),
                      plot_bgcolor="rgba(0,0,0,0)")
    return fig


def figura_vela(nombre: str) -> go.Figure:
    tipo, contexto, patron, confirma, *_ = VELAS[nombre]
    velas = list(contexto) + list(patron) + ([confirma] if confirma else [])
    ini = len(contexto) + 1
    fin = len(contexto) + len(patron)
    anot = [dict(x=(ini + fin) / 2, y=max(v[1] for v in patron), text=nombre, showarrow=True, arrowhead=2, ay=-28,
                 font=dict(size=11, color=AZUL))]
    if confirma:
        anot.append(dict(x=fin + 1, y=confirma[2], text="confirmación", showarrow=False, yshift=-12, font=dict(size=10, color=GRIS)))
    return grafico_velas(velas, (ini, fin), alto=230, anotaciones=anot)


def anatomia() -> go.Figure:
    velas = [(10, 13, 8.5, 12), (12, 13.5, 9, 9.8)]
    fig = grafico_velas(velas, alto=330)
    for txt, x, y, ax in [("Máximo", 1, 13, -60), ("Cierre", 1, 12, -70), ("Apertura", 1, 10, -70), ("Mínimo", 1, 8.5, -60),
                          ("Máximo", 2, 13.5, 60), ("Apertura", 2, 12, 70), ("Cierre", 2, 9.8, 70), ("Mínimo", 2, 9, 60)]:
        fig.add_annotation(x=x, y=y, text=txt, ax=ax, ay=0, showarrow=True, arrowhead=0, font=dict(size=11))
    fig.add_annotation(x=1, y=12.5, text="mecha superior", ax=-95, ay=-25, showarrow=True, font=dict(size=10, color=GRIS))
    fig.add_annotation(x=1, y=11, text="<b>cuerpo</b>", showarrow=False, font=dict(size=11, color="white"))
    fig.add_annotation(x=2, y=11, text="<b>cuerpo</b>", showarrow=False, font=dict(size=11, color="white"))
    fig.add_annotation(x=2, y=9.4, text="mecha inferior", ax=95, ay=25, showarrow=True, font=dict(size=10, color=GRIS))
    fig.add_annotation(x=1, y=8.0, text="<b>Vela alcista</b><br>cierra más arriba de lo que abrió", showarrow=False,
                       yshift=-14, font=dict(size=11, color=VERDE))
    fig.add_annotation(x=2, y=8.0, text="<b>Vela bajista</b><br>cierra más abajo de lo que abrió", showarrow=False,
                       yshift=-14, font=dict(size=11, color=ROJO))
    fig.update_layout(xaxis=dict(visible=False, range=[0, 3]), yaxis=dict(visible=False, range=[7, 14.3]))
    return fig


# ---------------------------------------------------------------------------
# Figuras (chartismo)
# ---------------------------------------------------------------------------
def camino(puntos: list[tuple[float, float]], n: int = 120, ruido: float = 0.6, semilla: int = 1) -> pd.Series:
    xs, ys = zip(*puntos)
    x = np.linspace(xs[0], xs[-1], n)
    y = np.interp(x, xs, ys)
    rng = np.random.default_rng(semilla)
    y = y + rng.normal(0, ruido, n).cumsum() * 0.15 + rng.normal(0, ruido * 0.4, n)
    # forzar que los puntos clave se respeten
    for xp, yp in puntos:
        i = int(np.argmin(np.abs(x - xp)))
        y[i] = yp
    return pd.Series(y, index=x)


def _linea(fig, x0, y0, x1, y1, color, texto=None, dash="dash", pos="top left"):
    fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=dict(color=color, width=2, dash=dash))
    if texto:
        fig.add_annotation(x=x1, y=y1, text=texto, showarrow=False, font=dict(size=11, color=color),
                           xanchor="right", yshift=10 if "top" in pos else -10)


def _objetivo(fig, x, y_desde, y_hasta, texto="objetivo"):
    fig.add_annotation(x=x, y=y_hasta, ax=x, ay=y_desde, axref="x", ayref="y", showarrow=True, arrowhead=3,
                       arrowwidth=2, arrowcolor=NARANJA, text="")
    fig.add_annotation(x=x, y=y_hasta, text=texto, showarrow=False, font=dict(size=11, color=NARANJA), xanchor="right", xshift=-6)


def _fig_linea(s: pd.Series, alto=280) -> go.Figure:
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color="#333", width=2), hoverinfo="skip"))
    fig.update_layout(height=alto, margin=dict(l=4, r=4, t=6, b=4), xaxis=dict(visible=False), yaxis=dict(visible=False),
                      showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
    return fig


def _hch(invertido=False):
    k = -1 if invertido else 1
    p = [(0, 50), (15, 50 + 10 * k), (25, 50 + 5 * k), (40, 50 + 20 * k), (55, 50 + 5 * k), (70, 50 + 11 * k), (80, 50 + 5 * k), (100, 50 - 8 * k)]
    fig = _fig_linea(camino(p, semilla=3))
    _linea(fig, 20, 55 if not invertido else 45, 92, 55 if not invertido else 45, AZUL, "línea clavicular")
    for x, t in ((15, "hombro"), (40, "cabeza"), (70, "hombro")):
        y = dict(p)[x]
        fig.add_annotation(x=x, y=y, text=t, showarrow=False, yshift=14 * k, font=dict(size=11, color=GRIS))
    base = 55 if not invertido else 45
    _objetivo(fig, 96, base, base - 15 * k)
    return fig


def _doble(techo=True):
    k = 1 if techo else -1
    p = [(0, 50), (22, 50 + 20 * k), (38, 50 + 8 * k), (55, 50 + 20 * k), (70, 50 + 8 * k), (100, 50 - 6 * k)]
    fig = _fig_linea(camino(p, semilla=5))
    _linea(fig, 30, 50 + 8 * k, 92, 50 + 8 * k, AZUL, "línea de confirmación")
    _linea(fig, 15, 50 + 20 * k, 62, 50 + 20 * k, GRIS, "techo" if techo else "suelo", dash="dot")
    _objetivo(fig, 96, 50 + 8 * k, 50 - 4 * k)
    return fig


def _triangulo(tipo):
    if tipo == "asc":
        p = [(0, 52), (12, 70), (24, 57), (36, 70), (48, 62), (58, 70), (66, 66), (72, 70), (86, 80), (100, 86)]
        lineas = [(10, 70, 74, 70, "resistencia plana"), (5, 54, 70, 67, "soporte ascendente")]
    elif tipo == "desc":
        p = [(0, 68), (12, 50), (24, 63), (36, 50), (48, 58), (58, 50), (66, 54), (72, 50), (86, 40), (100, 34)]
        lineas = [(10, 50, 74, 50, "soporte plano"), (5, 66, 70, 53, "resistencia descendente")]
    else:
        p = [(0, 50), (12, 72), (24, 52), (36, 67), (48, 56), (58, 63), (66, 59), (72, 62), (86, 72), (100, 78)]
        lineas = [(10, 73, 72, 62, "resistencia"), (20, 51, 72, 60, "soporte")]
    fig = _fig_linea(camino(p, semilla=7, ruido=0.4))
    for x0, y0, x1, y1, t in lineas:
        _linea(fig, x0, y0, x1, y1, AZUL, t)
    fig.add_annotation(x=74, y=dict(p)[72], text="ruptura", showarrow=True, ay=-30 if tipo != "desc" else 30, font=dict(size=11, color=NARANJA))
    return fig


def _bandera(banderin=False):
    if banderin:
        p = [(0, 40), (18, 66), (24, 61), (29, 65), (34, 62), (38, 64), (42, 63), (55, 80), (70, 86)]
    else:
        p = [(0, 40), (18, 66), (23, 62), (27, 65), (32, 60), (36, 63), (41, 58), (55, 76), (70, 84)]
    fig = _fig_linea(camino(p, semilla=9, ruido=0.3))
    fig.add_annotation(x=9, y=53, text="mástil", showarrow=False, xshift=-22, font=dict(size=11, color=GRIS))
    if banderin:
        _linea(fig, 18, 66, 43, 63.5, AZUL)
        _linea(fig, 22, 60.5, 43, 63, AZUL)
    else:
        _linea(fig, 18, 66.5, 41, 59.5, AZUL)
        _linea(fig, 22, 61.5, 43, 57, AZUL)
    _objetivo(fig, 62, 58, 58 + 26, "objetivo ≈ altura del mástil")
    return fig


def _cuna(subiendo=True):
    if subiendo:
        p = [(0, 40), (12, 52), (22, 47), (34, 57), (44, 54), (54, 61), (62, 59), (68, 62), (80, 50), (95, 44)]
        _l = [(5, 44, 68, 62.5), (0, 40, 66, 60)]
    else:
        p = [(0, 70), (12, 58), (22, 63), (34, 53), (44, 56), (54, 49), (62, 51), (68, 48), (80, 60), (95, 66)]
        _l = [(5, 66, 68, 47.5), (0, 70, 66, 50)]
    fig = _fig_linea(camino(p, semilla=11, ruido=0.3))
    for x0, y0, x1, y1 in _l:
        _linea(fig, x0, y0, x1, y1, AZUL)
    fig.add_annotation(x=74, y=dict(p)[80], text="ruptura", showarrow=True, ay=30 if subiendo else -30, font=dict(size=11, color=NARANJA))
    return fig


def _canal():
    p = [(0, 40), (10, 50), (18, 46), (30, 58), (38, 54), (50, 66), (58, 62), (70, 74), (78, 70), (90, 82), (100, 78)]
    fig = _fig_linea(camino(p, semilla=13, ruido=0.3))
    _linea(fig, 0, 44, 100, 86, AZUL, "techo del canal")
    _linea(fig, 0, 38, 100, 76, AZUL, "suelo del canal", pos="bottom")
    return fig


def _taza():
    x = np.linspace(0, 70, 70)
    y = 60 - 14 * np.sin(np.pi * x / 70)
    p = list(zip(x[::7], y[::7])) + [(70, 60), (78, 56), (86, 59), (92, 61), (100, 70)]
    fig = _fig_linea(camino(p, semilla=15, ruido=0.25))
    _linea(fig, 0, 60.5, 92, 60.5, AZUL, "borde de la taza")
    fig.add_annotation(x=35, y=46, text="taza", showarrow=False, yshift=-12, font=dict(size=11, color=GRIS))
    fig.add_annotation(x=80, y=56, text="asa", showarrow=False, yshift=-12, font=dict(size=11, color=GRIS))
    _objetivo(fig, 96, 60.5, 74, "objetivo ≈ profundidad")
    return fig


def _rectangulo():
    p = [(0, 45), (8, 60), (16, 50), (26, 60), (36, 50), (46, 60), (56, 50), (66, 60), (72, 56), (82, 70), (100, 74)]
    fig = _fig_linea(camino(p, semilla=17, ruido=0.25))
    _linea(fig, 5, 60, 76, 60, AZUL, "resistencia")
    _linea(fig, 10, 50, 76, 50, AZUL, "soporte", pos="bottom")
    return fig


FIGURAS = {
    "Hombro-cabeza-hombro": ("Giro bajista", lambda: _hch(False),
                             "Tres máximos: el del medio (cabeza) más alto que los de los lados (hombros). La «línea clavicular» une los mínimos entre ellos.",
                             "Se confirma cuando el precio rompe la línea clavicular hacia abajo. Objetivo típico: la altura de la cabeza a la clavicular, proyectada hacia abajo.",
                             "Muchos traders esperan el «pullback»: que el precio vuelva a tocar la clavicular desde abajo antes de seguir cayendo."),
    "Hombro-cabeza-hombro invertido": ("Giro alcista", lambda: _hch(True),
                                       "La versión al revés: tres mínimos, el central más profundo. Aparece tras caídas.",
                                       "Confirmación al superar la clavicular, idealmente con volumen alto. Objetivo: la profundidad de la cabeza proyectada hacia arriba.",
                                       "El volumen suele crecer en el hombro derecho y en la ruptura."),
    "Doble techo": ("Giro bajista", lambda: _doble(True),
                    "Dos máximos parecidos (forma de «M»): el precio no consigue superar el mismo nivel dos veces.",
                    "Se confirma al perder el mínimo entre los dos techos. Objetivo: la altura de la figura hacia abajo.",
                    "Si el segundo techo se hace con menos volumen que el primero, la señal es más fiable."),
    "Doble suelo": ("Giro alcista", lambda: _doble(False),
                    "Dos mínimos parecidos (forma de «W»): el precio no cae por debajo del mismo nivel dos veces.",
                    "Se confirma al superar el máximo entre los dos suelos. Objetivo: la altura de la figura hacia arriba.",
                    "Un doble suelo sin ruptura confirmada es solo un rango lateral."),
    "Triángulo ascendente": ("Continuación alcista (normalmente)", lambda: _triangulo("asc"),
                             "Máximos a la misma altura y mínimos cada vez más altos: los compradores aprietan contra una resistencia.",
                             "Ruptura de la resistencia plana con volumen. Objetivo: la altura de la parte más ancha.",
                             "Cuanto más cerca del vértice se rompe, menos fuerza suele tener."),
    "Triángulo descendente": ("Continuación bajista (normalmente)", lambda: _triangulo("desc"),
                              "Mínimos a la misma altura y máximos cada vez más bajos: los vendedores presionan sobre un soporte.",
                              "Ruptura del soporte plano. Objetivo: la altura de la parte más ancha hacia abajo.",
                              "Si rompe hacia arriba, la señal falsa suele dar una subida rápida."),
    "Triángulo simétrico": ("Continuación (dirección de la ruptura)", lambda: _triangulo("sim"),
                            "Máximos decrecientes y mínimos crecientes: el precio se comprime.",
                            "Se opera en la dirección en la que rompe, normalmente la de la tendencia previa.",
                            "Las rupturas falsas son frecuentes: espera cierre fuera del triángulo."),
    "Bandera": ("Continuación", lambda: _bandera(False),
                "Subida fuerte (mástil) seguida de un pequeño canal ligeramente en contra: una pausa para respirar.",
                "Ruptura del canal en la dirección del mástil. Objetivo: la altura del mástil.",
                "Debe ser corta (días o pocas semanas) y con volumen bajo durante la pausa."),
    "Banderín": ("Continuación", lambda: _bandera(True),
                 "Igual que la bandera, pero la pausa forma un pequeño triángulo.",
                 "Ruptura en la dirección del mástil. Objetivo: la altura del mástil.",
                 "Si la pausa dura demasiado, deja de ser un banderín."),
    "Cuña ascendente": ("Giro bajista", lambda: _cuna(True),
                        "El precio sube dentro de dos líneas que convergen, cada vez con menos fuerza.",
                        "Ruptura de la línea inferior. Suele llevar al inicio de la cuña.",
                        "Es bajista aunque el precio suba: el impulso se va agotando."),
    "Cuña descendente": ("Giro alcista", lambda: _cuna(False),
                         "El precio baja dentro de dos líneas convergentes, cada vez con menos fuerza.",
                         "Ruptura de la línea superior. Suele llevar al inicio de la cuña.",
                         "Mejor si el volumen crece en la ruptura."),
    "Canal": ("Tendencia", _canal,
              "El precio se mueve entre dos líneas paralelas: un techo y un suelo que suben (o bajan) a la vez.",
              "Muchos compran cerca del suelo y venden cerca del techo mientras dura. Salir del canal cambia el escenario.",
              "Un canal se rompe tarde o temprano: no lo des por eterno."),
    "Taza con asa": ("Continuación alcista", _taza,
                     "Una bajada y recuperación en forma de «U» (taza) y una pequeña bajada final (asa) antes de romper.",
                     "Ruptura del borde de la taza con volumen. Objetivo: la profundidad de la taza.",
                     "Si la taza tiene forma de «V» (muy rápida), es menos fiable."),
    "Rectángulo (lateral)": ("Indecisión / continuación", _rectangulo,
                             "El precio rebota entre un soporte y una resistencia horizontales.",
                             "Se opera la ruptura. Objetivo: la altura del rectángulo.",
                             "Dentro del rango no hay tendencia: las medias y el MACD dan señales falsas."),
}

# ---------------------------------------------------------------------------
# Tendencias, soportes y volumen (ejemplos con precio y volumen)
# ---------------------------------------------------------------------------


def _con_volumen(precio: pd.Series, volumen: np.ndarray, alto=360, colores=None) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
    fig.add_scatter(x=precio.index, y=precio.values, mode="lines", line=dict(color="#333", width=2), row=1, col=1, hoverinfo="skip")
    fig.add_bar(x=precio.index, y=volumen, marker_color=colores or GRIS, row=2, col=1, hoverinfo="skip")
    fig.update_layout(height=alto, margin=dict(l=4, r=4, t=6, b=4), showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def ej_soporte_resistencia() -> go.Figure:
    p = [(0, 50), (10, 62), (20, 52), (30, 61.5), (40, 51.5), (50, 62), (60, 52), (70, 66), (80, 63), (90, 70), (100, 74)]
    fig = _fig_linea(camino(p, semilla=21, ruido=0.25), alto=300)
    _linea(fig, 0, 62, 66, 62, ROJO, "resistencia: aquí suelen aparecer vendedores")
    _linea(fig, 0, 52, 66, 52, VERDE, "soporte: aquí suelen aparecer compradores", pos="bottom")
    _linea(fig, 72, 62, 100, 62, VERDE, "la resistencia rota pasa a ser soporte", dash="dot", pos="bottom")
    return fig


def ej_tendencias() -> go.Figure:
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Alcista: máximos y mínimos cada vez más altos",
                                                         "Bajista: máximos y mínimos cada vez más bajos",
                                                         "Lateral: sin dirección"))
    series = [camino([(0, 40), (15, 52), (25, 47), (40, 60), (50, 55), (65, 68), (75, 63), (90, 76), (100, 74)], semilla=23, ruido=0.25),
              camino([(0, 76), (15, 64), (25, 69), (40, 56), (50, 61), (65, 48), (75, 53), (90, 40), (100, 42)], semilla=25, ruido=0.25),
              camino([(0, 58), (15, 66), (30, 52), (45, 65), (60, 53), (75, 66), (90, 54), (100, 59)], semilla=27, ruido=0.25)]
    for i, s in enumerate(series, 1):
        fig.add_scatter(x=s.index, y=s.values, mode="lines", line=dict(color=[VERDE, ROJO, GRIS][i - 1], width=2), row=1, col=i,
                        hoverinfo="skip")
    fig.update_layout(height=260, margin=dict(l=4, r=4, t=40, b=4), showlegend=False, plot_bgcolor="rgba(0,0,0,0)")
    fig.update_annotations(font_size=12)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def ej_volumen(caso: str) -> go.Figure:
    rng = np.random.default_rng(31)
    if caso == "ruptura":
        p = camino([(0, 50), (10, 58), (20, 51), (30, 58), (40, 51), (50, 58.3), (55, 62), (70, 70), (100, 76)], semilla=33, ruido=0.2)
        v = rng.uniform(40, 60, len(p))
        i = int(np.argmin(np.abs(p.index - 54)))
        v[i:i + 6] = [150, 170, 140, 110, 90, 80]
        fig = _con_volumen(p, v, colores=[NARANJA if 140 <= x else GRIS for x in v])
        fig.add_annotation(x=p.index[i], y=v[i + 1], text="la ruptura llega con mucho volumen → más fiable",
                           showarrow=True, ay=-40, row=2, col=1, font=dict(size=11, color=NARANJA))
    elif caso == "divergencia":
        p = camino([(0, 40), (20, 55), (30, 52), (50, 64), (60, 61), (80, 70), (90, 68), (100, 60)], semilla=35, ruido=0.2)
        v = np.linspace(110, 35, len(p)) + rng.normal(0, 6, len(p))
        fig = _con_volumen(p, v)
        fig.add_annotation(x=p.index[80], y=float(p.iloc[80]), text="el precio sigue subiendo…", showarrow=True, ay=-30,
                           row=1, col=1, font=dict(size=11))
        fig.add_annotation(x=p.index[80], y=float(v[80]), text="…pero cada vez con menos volumen: aviso", showarrow=True,
                           ay=-35, row=2, col=1, font=dict(size=11, color=ROJO))
    elif caso == "climax":
        p = camino([(0, 70), (30, 60), (60, 47), (75, 38), (80, 36), (90, 42), (100, 46)], semilla=37, ruido=0.2)
        v = rng.uniform(40, 70, len(p))
        i = int(np.argmin(np.abs(p.index - 78)))
        v[i - 2:i + 2] = [160, 230, 260, 180]
        fig = _con_volumen(p, v, colores=[ROJO if x >= 160 else GRIS for x in v])
        fig.add_annotation(x=p.index[i], y=260, text="clímax vendedor: pánico y volumen enorme, a menudo cerca del suelo",
                           showarrow=True, ay=-20, ax=-120, row=2, col=1, font=dict(size=11, color=ROJO))
    else:  # confirmación de tendencia
        p = camino([(0, 40), (12, 50), (18, 47), (32, 58), (38, 55), (52, 66), (58, 63), (72, 75), (78, 72), (100, 84)], semilla=39, ruido=0.2)
        d = np.diff(p.values, prepend=p.values[0])
        v = np.where(d > 0, rng.uniform(80, 120, len(p)), rng.uniform(25, 50, len(p)))
        fig = _con_volumen(p, v, colores=[VERDE if x > 0 else ROJO for x in d])
        fig.add_annotation(x=p.index[30], y=110, text="más volumen en los días de subida que en los de bajada: tendencia sana",
                           showarrow=False, yshift=18, row=2, col=1, font=dict(size=11, color=VERDE))
    return fig


# ---------------------------------------------------------------------------
# Indicadores (sobre una serie inventada con OHLCV)
# ---------------------------------------------------------------------------
def serie_ejemplo(n=300, semilla=41) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    tramos = np.concatenate([np.full(90, 0.0012), np.full(70, -0.0018), np.full(80, 0.0016), np.full(n - 240, -0.0006)])
    r = tramos + rng.normal(0, 0.013, n)
    c = 50 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.01, n))
    lo = np.minimum(o, c) * (1 - rng.uniform(0, 0.01, n))
    v = rng.uniform(0.6e6, 1.4e6, n) * (1 + 3 * np.abs(r) / 0.013 * 0.25)
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c, "Volume": v}, index=idx)


def ej_indicador(t: pd.DataFrame, cual: str) -> go.Figure:
    v = t.copy()
    if cual == "medias":
        fig = go.Figure()
        fig.add_scatter(x=v.index, y=v["Close"], name="Precio", line=dict(color="#333", width=1.4))
        fig.add_scatter(x=v.index, y=v["SMA50"], name="Media 50", line=dict(color=NARANJA, width=2))
        fig.add_scatter(x=v.index, y=v["SMA200"], name="Media 200", line=dict(color="#8e44ad", width=2))
        cruce = np.sign(v["SMA50"] - v["SMA200"]).diff()
        for f, s in cruce[cruce.abs() == 2].items():
            fig.add_annotation(x=f, y=v.loc[f, "SMA50"], text="cruce dorado" if s > 0 else "cruce de la muerte", showarrow=True,
                               ay=-35 if s > 0 else 35, font=dict(size=11, color=VERDE if s > 0 else ROJO))
        fig.update_layout(height=320)
    elif cual == "rsi":
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.04)
        fig.add_scatter(x=v.index, y=v["Close"], name="Precio", line=dict(color="#333", width=1.4), row=1, col=1)
        fig.add_scatter(x=v.index, y=v["RSI"], name="RSI", line=dict(color=AZUL), row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(214,69,69,.10)", line_width=0, row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(26,158,92,.10)", line_width=0, row=2, col=1)
        fig.add_annotation(x=v.index[10], y=85, text="sobrecompra (>70)", showarrow=False, xanchor="left", row=2, col=1,
                           font=dict(size=10, color=ROJO))
        fig.add_annotation(x=v.index[10], y=15, text="sobreventa (<30)", showarrow=False, xanchor="left", row=2, col=1,
                           font=dict(size=10, color=VERDE))
        fig.update_yaxes(range=[0, 100], row=2, col=1)
        fig.update_layout(height=380)
    elif cual == "macd":
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.04)
        fig.add_scatter(x=v.index, y=v["Close"], name="Precio", line=dict(color="#333", width=1.4), row=1, col=1)
        fig.add_bar(x=v.index, y=v["MACD_hist"], name="Histograma", row=2, col=1,
                    marker_color=[VERDE if x >= 0 else ROJO for x in v["MACD_hist"].fillna(0)])
        fig.add_scatter(x=v.index, y=v["MACD"], name="MACD", line=dict(color="#222", width=1.2), row=2, col=1)
        fig.add_scatter(x=v.index, y=v["MACD_senal"], name="Señal", line=dict(color=NARANJA, width=1.2), row=2, col=1)
        fig.update_layout(height=380)
    elif cual == "bollinger":
        fig = go.Figure()
        fig.add_scatter(x=v.index, y=v["BB_sup"], name="Banda superior", line=dict(color=GRIS, width=1, dash="dot"))
        fig.add_scatter(x=v.index, y=v["BB_inf"], name="Banda inferior", line=dict(color=GRIS, width=1, dash="dot"),
                        fill="tonexty", fillcolor="rgba(154,164,178,.12)")
        fig.add_scatter(x=v.index, y=v["SMA20"] if "SMA20" in v else v["Close"].rolling(20).mean(), name="Media 20",
                        line=dict(color=AZUL, width=1))
        fig.add_scatter(x=v.index, y=v["Close"], name="Precio", line=dict(color="#333", width=1.4))
        fig.update_layout(height=320)
    else:  # fibonacci
        tramo = v["Close"].iloc[:160]
        i_min, i_max = tramo.idxmin(), v["Close"].iloc[:95].idxmax()
        alto, bajo = float(v.loc[i_max, "Close"]), float(v.loc[i_min, "Close"])
        fig = go.Figure(go.Scatter(x=v.index, y=v["Close"], line=dict(color="#333", width=1.4), name="Precio"))
        for nivel, col in ((0, GRIS), (0.236, GRIS), (0.382, AZUL), (0.5, NARANJA), (0.618, AZUL), (1, GRIS)):
            y = alto - (alto - bajo) * nivel
            fig.add_hline(y=y, line=dict(color=col, dash="dot", width=1),
                          annotation_text=f"{nivel * 100:.1f}%".replace(".0%", "%"), annotation_position="right")
        fig.update_layout(height=320)
    fig.update_layout(margin=dict(l=4, r=40, t=10, b=4), legend=dict(orientation="h", y=1.08), plot_bgcolor="rgba(0,0,0,0)")
    return fig


# ---------------------------------------------------------------------------
# Detectores de patrones de velas sobre datos reales
# ---------------------------------------------------------------------------
DETECTABLES = {
    "Martillo": "alcista", "Estrella fugaz": "bajista", "Doji": "neutral", "Envolvente alcista": "alcista",
    "Envolvente bajista": "bajista", "Marubozu alcista": "alcista", "Marubozu bajista": "bajista",
    "Volumen anormal": "neutral",
}


def detectar(h: pd.DataFrame) -> pd.DataFrame:
    """Marca patrones de velas sencillos. Devuelve una fila por aparición: fecha, patrón, sesgo y precio."""
    d = h[["Open", "High", "Low", "Close", "Volume"]].dropna().copy()
    o, hi, lo, c, v = (d[k] for k in ("Open", "High", "Low", "Close", "Volume"))
    rango = (hi - lo).replace(0, np.nan)
    cuerpo = (c - o).abs()
    sup = hi - np.maximum(o, c)
    inf = np.minimum(o, c) - lo
    tend = c / c.shift(10) - 1                         # tendencia de las 10 sesiones previas
    rango_medio = rango.rolling(20).mean()
    vol_medio = v.rolling(20).mean().shift(1)
    marcas = {
        "Martillo": (inf >= 2 * cuerpo) & (sup <= 0.3 * cuerpo + 0.1 * rango) & (tend.shift(1) < -0.03),
        "Estrella fugaz": (sup >= 2 * cuerpo) & (inf <= 0.3 * cuerpo + 0.1 * rango) & (tend.shift(1) > 0.03),
        "Doji": (cuerpo <= 0.08 * rango) & (rango >= 0.8 * rango_medio),
        "Envolvente alcista": (c.shift(1) < o.shift(1)) & (c > o) & (o <= c.shift(1)) & (c >= o.shift(1)) &
                              (cuerpo > cuerpo.shift(1) * 1.1) & (tend.shift(1) < -0.03),
        "Envolvente bajista": (c.shift(1) > o.shift(1)) & (c < o) & (o >= c.shift(1)) & (c <= o.shift(1)) &
                              (cuerpo > cuerpo.shift(1) * 1.1) & (tend.shift(1) > 0.03),
        "Marubozu alcista": (c > o) & (cuerpo >= 0.92 * rango) & (rango >= 1.5 * rango_medio),
        "Marubozu bajista": (c < o) & (cuerpo >= 0.92 * rango) & (rango >= 1.5 * rango_medio),
        "Volumen anormal": v >= 2.5 * vol_medio,
    }
    # Algunas bolsas dan la apertura igual al cierre: entonces los patrones de velas no tienen sentido
    raro = float((cuerpo <= 0.02 * rango).mean()) > 0.3
    if raro:
        marcas = {"Volumen anormal": marcas["Volumen anormal"]}
    filas = []
    for nombre, m in marcas.items():
        for f in m[m.fillna(False)].index:
            filas.append({"Fecha": f, "Patrón": nombre, "Sesgo": DETECTABLES[nombre], "Cierre": float(c[f])})
    if not filas:
        vacio = pd.DataFrame(columns=["Fecha", "Patrón", "Sesgo", "Cierre", "A 5 sesiones", "A 20 sesiones"])
        vacio.attrs["aviso"] = raro
        return vacio
    out = pd.DataFrame(filas).sort_values("Fecha")
    cierres = c
    for dias in (5, 20):
        fut = cierres.shift(-dias) / cierres - 1
        out[f"A {dias} sesiones"] = [float(fut.get(f, np.nan)) for f in out["Fecha"]]
    out.attrs["aviso"] = raro
    return out


def estadisticas(det: pd.DataFrame, h: pd.DataFrame) -> pd.DataFrame:
    """Para cada patrón: veces, % de veces que acertó la dirección a 20 sesiones y rentabilidad media, frente a la media normal."""
    if det.empty:
        return pd.DataFrame()
    c = h["Close"].dropna()
    base = (c.shift(-20) / c - 1).dropna()
    filas = []
    for nombre, g in det.dropna(subset=["A 20 sesiones"]).groupby("Patrón"):
        r = g["A 20 sesiones"]
        sesgo = DETECTABLES[nombre]
        acierto = (r > 0).mean() if sesgo == "alcista" else (r < 0).mean() if sesgo == "bajista" else None
        filas.append({"Patrón": nombre, "Sesgo esperado": sesgo, "Veces": len(r),
                      "Acertó la dirección": acierto, "Rentab. media a 20 sesiones": r.mean(),
                      "Cualquier día (referencia)": base.mean()})
    return pd.DataFrame(filas).sort_values("Veces", ascending=False) if filas else pd.DataFrame()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
PREGUNTAS = [
    ("¿Qué indica una vela con cuerpo pequeño arriba y una mecha inferior muy larga después de una bajada?",
     ["Que la caída se acelera", "Posible giro al alza (martillo)", "Nada, es ruido", "Que hay que vender ya"], 1,
     "Es un martillo: los compradores devolvieron el precio arriba tras una caída fuerte dentro de la sesión. Necesita confirmación."),
    ("En un hombro-cabeza-hombro, ¿cuándo se considera confirmada la figura?",
     ["Al formarse la cabeza", "Al formarse el segundo hombro", "Al romper la línea clavicular", "Cuando el RSI pasa de 70"], 2,
     "Hasta que no rompe la clavicular, la figura no está completa: muchas no llegan a confirmarse."),
    ("Una ruptura de resistencia con volumen muy bajo es…",
     ["Más fiable", "Menos fiable", "Igual de fiable", "Una señal de venta segura"], 1,
     "El volumen mide la convicción: las rupturas sin volumen fallan más a menudo."),
    ("Si el precio sube pero cada subida se hace con menos volumen, eso es…",
     ["Una divergencia: aviso de que la subida pierde fuerza", "Confirmación de la tendencia", "Un clímax comprador", "Un doble suelo"], 0,
     "Precio y volumen van en direcciones contrarias: la subida tiene cada vez menos participantes."),
    ("¿Qué es un «cruce dorado»?",
     ["El RSI cruza 50", "La media de 50 sesiones cruza por encima de la de 200", "El precio toca la banda superior de Bollinger", "El MACD cruza su señal a la baja"], 1,
     "Se considera una señal alcista de largo plazo (y el cruce de la muerte, la contraria). Llega tarde, pero filtra ruido."),
    ("Un RSI de 80 significa…",
     ["Que hay que vender sí o sí", "Sobrecompra: subió mucho y rápido", "Sobreventa", "Que la empresa es buena"], 1,
     "Indica sobrecompra, pero en tendencias fuertes el RSI puede quedarse alto mucho tiempo: no es una orden de venta."),
    ("Arriesgas como máximo el 1% de 10.000 € y compras a 50 € con stop en 45 €. ¿Cuántas acciones puedes comprar?",
     ["10", "20", "100", "200"], 1,
     "Riesgo máximo = 100 €. Riesgo por acción = 50 − 45 = 5 €. 100 / 5 = 20 acciones."),
    ("Con una relación recompensa/riesgo de 3:1, ¿qué porcentaje de aciertos necesitas como mínimo para no perder (sin comisiones)?",
     ["25%", "50%", "60%", "75%"], 0,
     "Ganas 3 cuando aciertas y pierdes 1 cuando fallas: con 1 de cada 4 operaciones bien quedas a cero."),
    ("Una resistencia que se rompe con claridad…",
     ["Desaparece", "Suele pasar a actuar como soporte", "Se convierte en una cuña", "Indica siempre caída"], 1,
     "Es el cambio de polaridad: el antiguo techo se convierte en suelo."),
    ("¿Para qué sirve una orden stop-loss?",
     ["Para comprar más barato", "Para limitar la pérdida si el precio va en tu contra", "Para cobrar dividendos", "Para evitar comisiones"], 1,
     "Vende automáticamente al llegar a un precio. Ojo: en un hueco (gap) puede ejecutarse peor de lo previsto."),
]
