"""Sección Aprende trading: velas, figuras, volumen, tendencias, indicadores, riesgo, órdenes, práctica y test."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lecciones as ap
import datos
import graficos
from comun import abrir_empresa, cargar, conclusion, elegir_empresa, empresa_actual, f_num, f_pct

st.title("📚 Aprende trading")
st.caption("Lo esencial para leer un gráfico: velas, figuras, volumen, tendencias e indicadores, y cómo gestionar el riesgo. "
           "Cada concepto con un dibujo de ejemplo. Al final, practica con empresas reales y ponte a prueba.")

CFG = {"displayModeBar": False}
NOMBRES = ["🕯️ Velas", "📐 Figuras", "📊 Volumen", "📈 Tendencias y soportes", "⏱️ Temporalidades", "🧭 Indicadores",
           "🛡️ Gestión del riesgo", "🧾 Órdenes y conceptos", "🔍 Practica", "✅ Test"]
_t = st.tabs(NOMBRES)
T = dict(zip(NOMBRES, _t))


@st.cache_resource(show_spinner=False)
def _figs_temporalidades():
    return ap.ej_temporalidades()


def ficha(titulo: str, etiqueta: str, fig: go.Figure, filas: list[tuple[str, str]]):
    with st.container(border=True):
        st.markdown(f"**{titulo}** · <span style='color:#888'>{etiqueta}</span>", unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", config=CFG)
        for t, txt in filas:
            st.markdown(f"**{t}** {txt}")


# 1. Velas ---------------------------------------------------------------------------------
with T["🕯️ Velas"]:
    conclusion("Cada vela resume una sesión (un día, una hora…): dónde abrió, dónde cerró y hasta dónde llegó. "
               "Una vela sola dice poco; **importa dónde aparece** (tras una subida, en un soporte…) y **qué pasa después**.")
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.plotly_chart(ap.anatomia(), width="stretch", config=CFG)
    with c2:
        st.markdown("#### Cómo se lee una vela")
        st.markdown("""
- **Cuerpo**: la distancia entre apertura y cierre. **Verde** si cerró más arriba (subió), **rojo** si cerró más abajo.
- **Mechas** (o sombras): hasta dónde llegó el precio durante la sesión pero no se mantuvo.
- **Cuerpo grande** = un bando dominó la sesión. **Cuerpo pequeño** = equilibrio o duda.
- **Mecha larga** = rechazo: el precio fue a esa zona y lo devolvieron.
- Cada vela puede ser un día, una semana o una hora: es el **marco temporal** del gráfico.
""")
        st.info("Regla de oro: **espera la confirmación**. Un patrón de giro solo vale si la vela siguiente va en la dirección esperada.")
    st.markdown("#### Patrones de velas más importantes")
    filtro = st.segmented_control("Ver", ["Todos", "Giro alcista", "Giro bajista", "Otros"], default="Todos", key="ap_velas_filtro")
    nombres = [n for n, v in ap.VELAS.items() if filtro in (None, "Todos") or (filtro == "Otros" and "Giro" not in v[0]) or v[0] == filtro]
    cols = st.columns(3)
    for k, n in enumerate(nombres):
        tipo, _, _, _, que, indica, confirma, trampa = ap.VELAS[n]
        with cols[k % 3]:
            ficha(n, tipo, ap.figura_vela(n), [("Qué es:", que), ("Qué indica:", indica), ("Cómo confirmarlo:", confirma),
                                               ("⚠️ Ojo:", trampa)])

# 2. Figuras ---------------------------------------------------------------------------------
with T["📐 Figuras"]:
    conclusion("Las figuras (chartismo) son formas que dibuja el precio durante semanas o meses. Las de **giro** avisan de que la "
               "tendencia puede cambiar; las de **continuación**, de una pausa antes de seguir. **Ninguna está completa hasta que "
               "rompe**, y el objetivo se calcula midiendo la altura de la propia figura.")
    filtro = st.segmented_control("Ver", ["Todas", "Giro", "Continuación", "Otras"], default="Todas", key="ap_fig_filtro")
    lista = [n for n, v in ap.FIGURAS.items() if filtro in (None, "Todas") or (filtro == "Giro" and "Giro" in v[0])
             or (filtro == "Continuación" and "Continuación" in v[0]) or (filtro == "Otras" and "Giro" not in v[0] and "Continuación" not in v[0])]
    cols = st.columns(2)
    for k, n in enumerate(lista):
        tipo, fn, que, confirma, consejo = ap.FIGURAS[n]
        with cols[k % 2]:
            ficha(n, tipo, fn(), [("Qué es:", que), ("Cuándo se confirma y objetivo:", confirma), ("💡 Consejo:", consejo)])
    st.caption("Dibujos esquemáticos: en la realidad las figuras son menos limpias. Puedes dibujar líneas sobre cualquier "
               "empresa en el 🎯 Simulador.")

# 3. Volumen -------------------------------------------------------------------------------------
with T["📊 Volumen"]:
    conclusion("El volumen es **cuántas acciones cambian de manos**. Es la «fuerza» detrás de cada movimiento: un movimiento con "
               "mucho volumen tiene más participantes y suele ser más fiable que uno con poco.")
    casos = [("Volumen que confirma la tendencia", "conf",
              "En una tendencia sana hay más volumen en los días a favor que en los días en contra."),
             ("Ruptura con volumen", "ruptura",
              "Cuando el precio rompe un soporte o resistencia, el volumen alto indica que hay convicción detrás."),
             ("Divergencia de volumen", "divergencia",
              "Si el precio sigue subiendo pero el volumen se apaga, cada vez hay menos compradores: posible agotamiento."),
             ("Clímax de volumen", "climax",
              "Un volumen enorme tras una caída larga suele ser pánico (todo el mundo vende a la vez) y a menudo marca un suelo.")]
    cols = st.columns(2)
    for k, (t, caso, txt) in enumerate(casos):
        with cols[k % 2]:
            with st.container(border=True):
                st.markdown(f"**{t}**")
                st.plotly_chart(ap.ej_volumen(caso), width="stretch", config=CFG)
                st.markdown(txt)
    st.markdown("#### Más sobre el volumen")
    st.markdown("""
- **Compáralo con su media** (por ejemplo, 20 sesiones): el valor absoluto no dice nada, lo que importa es si es alto *para esa acción*.
- **Volumen en el soporte**: si el precio cae a un soporte con poco volumen y rebota con mucho, el soporte es sólido.
- **OBV (On Balance Volume)**: suma el volumen de los días de subida y resta el de los de bajada. Si sube mientras el precio está plano, alguien está acumulando.
- **Ojo** con los días de vencimientos de derivados, cambios de índices o resultados: el volumen se dispara por motivos técnicos.
""")

# 4. Tendencias y soportes ----------------------------------------------------------------------
with T["📈 Tendencias y soportes"]:
    conclusion("Lo primero es saber **hacia dónde va** el precio. «La tendencia es tu amiga»: es más fácil ganar a favor de ella. "
               "Los **soportes** y **resistencias** son las zonas donde el precio se ha frenado antes y es probable que vuelva a hacerlo.")
    st.plotly_chart(ap.ej_tendencias(), width="stretch", config=CFG)
    st.markdown("""
- **Alcista**: cada máximo y cada mínimo son más altos que los anteriores. Se rompe cuando hace un mínimo más bajo.
- **Bajista**: cada máximo y cada mínimo son más bajos. Se rompe cuando hace un máximo más alto.
- **Lateral**: el precio va y viene entre dos niveles. Aquí las señales de tendencia fallan mucho.
- **Línea de tendencia**: une al menos dos mínimos (en alcista) o dos máximos (en bajista). Cuantas más veces se respeta, más importante es.
""")
    st.plotly_chart(ap.ej_soporte_resistencia(), width="stretch", config=CFG)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
#### Soportes y resistencias
- **Soporte**: zona donde aparecen compradores y el precio deja de caer.
- **Resistencia**: zona donde aparecen vendedores y el precio deja de subir.
- Son **zonas**, no líneas exactas.
- Cuantas más veces se toca un nivel y más volumen hay en él, más importante es.
""")
    with c2:
        st.markdown("""
#### Cambio de papeles y marcos temporales
- Una resistencia rota suele pasar a ser **soporte** (y al revés).
- Los **números redondos** (10 €, 50 €, 100 €) y los máximos y mínimos anteriores actúan a menudo como soporte o resistencia.
- Mira primero el gráfico **semanal** para la tendencia de fondo y luego el **diario** para afinar la entrada.
""")

# 4b. Temporalidades -----------------------------------------------------------------------------------
with T["⏱️ Temporalidades"]:
    conclusion("La **temporalidad** es cuánto tiempo resume cada vela: 1 minuto, 5 minutos, 1 hora, 1 día, 1 semana… "
               "**El mismo valor puede estar subiendo en el semanal y bajando en el de 5 minutos.** Elige la temporalidad "
               "según cuánto tiempo vayas a mantener la operación y mira siempre primero la mayor.")
    st.markdown("#### 🔭 El mismo precio, cuatro temporalidades")
    st.caption("Cada gráfico es un zoom del recuadro azul del anterior (cotización inventada).")
    figs = _figs_temporalidades()
    cols = st.columns(2)
    for k, (titulo, texto, fig) in enumerate(figs):
        with cols[k % 2]:
            with st.container(border=True):
                st.markdown(f"**{titulo}**")
                st.plotly_chart(fig, width="stretch", config=CFG)
                st.caption(texto)
    st.markdown("#### 🧑‍💻 Qué temporalidad usar según tu estilo")
    st.dataframe(pd.DataFrame(ap.TEMPORALIDADES, columns=["Velas de", "Estilo", "Cuánto dura cada operación", "Ventajas", "Inconvenientes"]),
                 hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
#### 🔝 Análisis de arriba abajo (multi-temporalidad)
1. **Temporalidad mayor** (p. ej. semanal): ¿cuál es la tendencia de fondo? Solo operas a favor de ella.
2. **Temporalidad intermedia** (p. ej. diario): ¿dónde están los soportes y resistencias? ¿Hay alguna figura?
3. **Temporalidad menor** (p. ej. 4 horas o 1 hora): el momento exacto de entrada y dónde va el stop.

Regla práctica: cada temporalidad, unas **4-6 veces** la siguiente (semanal → diario → 4 horas; o 1 hora → 15 min → 5 min).
""")
        st.markdown("""
#### 📉 Ruido y fiabilidad
- Cuanto **más pequeña** la temporalidad, **más ruido**: más señales falsas y más cambios de dirección sin sentido.
- Un patrón (martillo, doble suelo…) en **diario o semanal** pesa mucho más que el mismo en 5 minutos.
- En temporalidades pequeñas, el **spread y las comisiones** son una parte grande de lo que puedes ganar en cada operación.
""")
    with c2:
        st.markdown("""
#### 🧮 Los indicadores cambian de significado
| Indicador | En velas de 5 min | En velas diarias | En velas semanales |
|---|---|---|---|
| Media de 20 | ~1h 40min | ~1 mes | ~5 meses |
| Media de 200 | ~2 sesiones | ~10 meses | ~4 años |
| RSI 14 | ~1h 10min | ~3 semanas | ~3 meses |

Una «media de 200» no es lo mismo en cada gráfico: mira siempre qué vela estás usando.
""")
        st.markdown("""
#### 🕘 Las horas del día importan (gráficos intradía)
- **Apertura** (primeros 30-60 min): mucho volumen y movimientos bruscos; los huecos de la noche se rellenan o se amplían.
- **Mediodía**: menos volumen; muchas rupturas falsas.
- **15:30 (hora española)**: abre Wall Street y vuelve el volumen a las bolsas europeas.
- **Cierre**: fondos e índices ajustan posiciones; el último precio del día es el más vigilado.
- Por eso el volumen intradía suele tener forma de **«U»**: alto al principio y al final.
""")
    st.info("🛠️ **Pruébalo**: en 🔎 Analizar empresa → 📉 Gráfico elige el periodo **1D** y *Cada vela es* **5 min**, o **5D** con "
            "**15 min**. Yahoo da velas de 1 minuto de los últimos 7 días, de 5-30 minutos de los últimos 60 días y de 1-4 horas "
            "de los últimos 2 años (con ~15 minutos de retraso).")
    st.markdown("""
#### 🛑 El stop depende de la temporalidad
- En 5 minutos el precio se mueve céntimos; en semanal, euros. Un stop pensado para el diario es enorme en 5 minutos y uno de 5 minutos salta al momento en el diario.
- Pon el stop según el **movimiento normal de esa temporalidad** (por ejemplo, debajo del último mínimo relevante de ese gráfico) y ajusta el número de acciones con la **calculadora de la pestaña 🛡️ Gestión del riesgo**: así arriesgas lo mismo en euros uses la temporalidad que uses.
""")

# 5. Indicadores -----------------------------------------------------------------------------------
with T["🧭 Indicadores"]:
    conclusion("Los indicadores son cálculos sobre el precio y el volumen. **No predicen**: resumen lo que ya ha pasado. "
               "Funcionan mejor **combinados** (tendencia + momento + volumen) y confirmando lo que ya ves en el gráfico.")
    t = datos.tecnicos(ap.serie_ejemplo())
    ind = [("Medias móviles (50 y 200)", "medias", """
- Promedio de los últimos N cierres: suavizan el ruido y muestran la tendencia.
- Precio **por encima** de la media de 200 = tendencia de fondo alcista; **por debajo** = bajista.
- **Cruce dorado**: la media de 50 cruza hacia arriba la de 200 (alcista). **Cruce de la muerte**: lo contrario.
- ⚠️ Llegan tarde: en mercados laterales dan muchas señales falsas."""),
           ("RSI (fuerza relativa)", "rsi", """
- Mide la velocidad de las subidas frente a las bajadas, de 0 a 100.
- **Por encima de 70**: sobrecompra (subió mucho y rápido). **Por debajo de 30**: sobreventa.
- Una **divergencia** (precio hace un nuevo máximo y el RSI no) avisa de agotamiento.
- ⚠️ En tendencias fuertes puede quedarse en sobrecompra semanas: no es una orden de venta."""),
           ("MACD", "macd", """
- Diferencia entre dos medias exponenciales (12 y 26) y su «señal» (media de 9).
- **MACD cruza por encima de la señal** = impulso alcista; por debajo = bajista.
- El **histograma** muestra si el impulso crece o se apaga.
- ⚠️ Como todas las medias, reacciona con retraso."""),
           ("Bandas de Bollinger", "bollinger", """
- Una media de 20 sesiones con dos bandas a ±2 desviaciones típicas: miden la **volatilidad**.
- Bandas **estrechas** = calma; suele preceder a un movimiento fuerte («squeeze»).
- Tocar la banda superior **no** es vender por sí solo: en tendencia alcista el precio «camina» por ella.
- Combínalas con las medias y el volumen (como en la estrategia del 🎯 Simulador)."""),
           ("Retrocesos de Fibonacci", "fib", """
- Tras una subida, el precio suele corregir una parte antes de seguir: los niveles **38,2%, 50% y 61,8%** son los más vigilados.
- Se dibujan desde el mínimo hasta el máximo del movimiento.
- Funcionan porque mucha gente los mira, no por magia: úsalos como zonas, junto con soportes reales.""")]
    for titulo, clave, texto in ind:
        with st.container(border=True):
            c1, c2 = st.columns([1.6, 1])
            c1.markdown(f"**{titulo}**")
            c1.plotly_chart(ap.ej_indicador(t, clave), width="stretch", config=CFG)
            c2.markdown(texto)
    st.caption("Ejemplos sobre una cotización inventada. En **🔎 Analizar empresa → 📉 Gráfico** los ves sobre cualquier empresa real.")

# 6. Gestión del riesgo ------------------------------------------------------------------------
with T["🛡️ Gestión del riesgo"]:
    conclusion("Lo que más diferencia a quien sobrevive en bolsa **no es acertar más, sino perder poco cuando falla**. "
               "Decide antes de entrar cuánto arriesgas, dónde sales si te equivocas y dónde recoges beneficios.")
    st.markdown("#### 🧮 Calculadora de tamaño de posición")
    c1, c2, c3, c4, c5 = st.columns(5)
    capital = c1.number_input("Capital total (€)", min_value=100.0, value=10000.0, step=500.0)
    riesgo_pct = c2.number_input("Riesgo por operación (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.25,
                                 help="Lo habitual es entre el 0,5% y el 2% del capital")
    entrada = c3.number_input("Precio de entrada (€)", min_value=0.01, value=50.0, step=0.5)
    stop = c4.number_input("Stop-loss (€)", min_value=0.0, value=45.0, step=0.5)
    objetivo = c5.number_input("Objetivo (€)", min_value=0.0, value=65.0, step=0.5)
    riesgo_acc = abs(entrada - stop)
    if riesgo_acc <= 0:
        st.warning("El stop no puede ser igual que el precio de entrada.")
    else:
        riesgo_eur = capital * riesgo_pct / 100
        n = int(riesgo_eur // riesgo_acc)
        invertido = n * entrada
        rr = abs(objetivo - entrada) / riesgo_acc if objetivo else None
        k = st.columns(5)
        k[0].metric("Acciones a comprar", f"{n:,}".replace(",", "."))
        k[1].metric("Dinero invertido", f"{f_num(invertido)} €", f"{invertido / capital * 100:.0f}% del capital".replace(".", ","),
                    delta_color="off")
        k[2].metric("Pérdida si salta el stop", f"−{f_num(n * riesgo_acc)} €")
        k[3].metric("Ganancia si llega al objetivo", f"+{f_num(n * abs(objetivo - entrada))} €" if objetivo else "—")
        k[4].metric("Recompensa / riesgo", f"{rr:.1f} : 1".replace(".", ",") if rr else "—")
        if invertido > capital:
            st.warning("Con ese stop tan cercano necesitarías más dinero del que tienes: amplía el stop o reduce el riesgo.")
        if rr is not None and rr < 1.5:
            st.info("Por debajo de 1,5:1 la operación arriesga mucho para lo que puede ganar: suele no compensar.")
        st.caption(f"Fórmula: acciones = (capital × riesgo%) ÷ (entrada − stop) = {f_num(riesgo_eur)} € ÷ {f_num(riesgo_acc)} € = {n}.")

    st.markdown("#### 🎲 Por qué no hace falta acertar siempre")
    c1, c2 = st.columns([1, 2])
    with c1:
        aciertos = st.slider("% de operaciones ganadoras", 20, 80, 40, step=5)
        rr2 = st.slider("Recompensa / riesgo", 0.5, 4.0, 2.0, step=0.5)
        esperanza = aciertos / 100 * rr2 - (1 - aciertos / 100)
        st.metric("Resultado medio por operación", f"{esperanza:+.2f} R".replace(".", ","),
                  help="R = lo que arriesgas en cada operación. +0,20 R significa que, de media, ganas un 20% de lo que arriesgas.")
        st.caption(f"Para no perder con {rr2:.1f}:1 necesitas acertar al menos el **{100 / (1 + rr2):.0f}%** de las veces.".replace(".", ",", 1))
    with c2:
        rng = np.random.default_rng(7)
        fig = go.Figure()
        for i in range(12):
            res = np.where(rng.random(100) < aciertos / 100, rr2, -1.0)
            fig.add_scatter(y=np.r_[0, res.cumsum()], mode="lines", line=dict(width=1.3), showlegend=False, hoverinfo="skip")
        fig.add_hline(y=0, line=dict(color="#999", dash="dot"))
        fig.update_layout(height=280, margin=dict(l=4, r=4, t=26, b=4), title=dict(text="12 simulaciones de 100 operaciones (en R)", font=dict(size=13)),
                          xaxis_title="operación", yaxis_title="resultado acumulado (R)")
        st.plotly_chart(fig, width="stretch", config=CFG)
    st.markdown("""
#### Reglas básicas
- **Arriesga poco en cada operación** (1-2% del capital). Con 10 pérdidas seguidas al 1% sigues teniendo el 90%.
- **Pon el stop donde la idea deja de ser válida** (debajo de un soporte, de la clavicular…), no a un % arbitrario.
- **No muevas el stop en contra** para «darle aire». Sí puedes subirlo a favor para proteger beneficios (*stop dinámico*).
- **Diversifica**: varias operaciones a la vez en la misma dirección y sector son, en el fondo, una sola apuesta grande.
- **Lleva un diario**: por qué entraste, dónde estaba el stop, qué pasó y qué aprendiste. Es lo que más rápido enseña.
- **Psicología**: el miedo te hace vender pronto y la avaricia, aguantar pérdidas. Tener el plan escrito antes de entrar ayuda.
""")

# 7. Órdenes y conceptos --------------------------------------------------------------------------
with T["🧾 Órdenes y conceptos"]:
    conclusion("Saber **qué tipo de orden** usar y **qué cuesta** operar evita sorpresas. Y si usas productos con apalancamiento, "
               "entiende bien que **multiplican tanto las ganancias como las pérdidas**.")
    st.markdown("#### Tipos de órdenes")
    st.dataframe(pd.DataFrame([
        ("A mercado", "Compra o vende ya, al mejor precio disponible.", "Se ejecuta seguro; el precio puede ser peor de lo que ves (sobre todo en acciones con poco volumen)."),
        ("Limitada", "Compra (o vende) solo a tu precio o mejor.", "Controlas el precio; puede no ejecutarse nunca."),
        ("Stop (stop-loss)", "Cuando el precio toca un nivel, lanza una orden a mercado.", "Limita pérdidas; en un hueco (gap) se ejecuta al precio que haya."),
        ("Stop limitada", "Al tocar el nivel, lanza una orden limitada.", "Controla el precio, pero en una caída brusca puede quedarse sin ejecutar."),
        ("Stop dinámico (trailing)", "Un stop que sube solo a una distancia fija del máximo alcanzado.", "Protege beneficios en tendencias; en mercados nerviosos salta pronto."),
        ("OCO", "Dos órdenes ligadas (p. ej. objetivo y stop): si se ejecuta una, se cancela la otra.", "Automatiza el plan completo de la operación."),
    ], columns=["Orden", "Qué hace", "Ventaja / riesgo"]), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
#### Conceptos básicos
- **Largo** (comprar): ganas si sube. **Corto** (vender sin tener la acción): ganas si baja; la pérdida potencial es ilimitada.
- **Spread**: diferencia entre el precio de compra y el de venta. Es un coste oculto en cada operación.
- **Comisiones**: con muchas operaciones pequeñas se comen la rentabilidad.
- **Gap (hueco)**: cuando el precio abre lejos del cierre anterior (por ejemplo, tras resultados). Los stops no protegen de los huecos.
- **Liquidez**: acciones con poco volumen se mueven a saltos y es difícil salir rápido.
- **Marco temporal**: *scalping* (minutos), *intradía*, *swing* (días-semanas) o *posición* (meses).
""")
    with c2:
        st.markdown("""
#### ⚠️ Apalancamiento (CFD, futuros, opciones, turbos…)
- Con 1.000 € de garantía controlas, por ejemplo, 10.000 € de acciones (apalancamiento 10×).
- Un movimiento del **10% en contra** se lleva **el 100%** de tu garantía.
- Si las pérdidas superan la garantía, el bróker te pide más dinero (**margin call**) o cierra la posición.
- Suelen tener **costes de financiación** diarios: mantenerlos mucho tiempo sale caro.
- La mayoría de cuentas minoristas que operan CFD pierden dinero, según los avisos obligatorios de los propios brókeres.
- Si los usas: **riesgo pequeño por operación, stop siempre puesto** y tamaño calculado con la calculadora de la pestaña anterior.
""")
    st.caption("Material educativo general: no es asesoramiento financiero ni una recomendación de ningún producto.")

# 8. Practica --------------------------------------------------------------------------------------------
with T["🔍 Practica"]:
    conclusion("Pon a prueba los patrones en una empresa real: la web busca velas típicas y días de volumen anormal en su histórico y "
               "mide **qué pasó después**. Verás que ningún patrón acierta siempre: por eso se confirman y se combinan.")
    tk = elegir_empresa("ap", etiqueta="Empresa", defecto=empresa_actual("Inditex"), en_linea=True)
    ver = "6M"
    if tk:
        try:
            e = cargar(tk)
            h = e.hist
        except Exception:
            h = None
        if h is None or h.empty:
            st.warning("Yahoo no tiene histórico de precios para esa empresa. Prueba con otra o elige otra bolsa en «¿Cuál de ellas?».")
        else:
            det = ap.detectar(h)
            if det.attrs.get("aviso"):
                st.info("Yahoo no da bien los precios de apertura de esta acción (aparecen iguales al cierre), así que solo se "
                        "marcan los días de volumen anormal. Prueba con una empresa de un mercado grande.")
            simbolos = {"alcista": ("triangle-up", ap.VERDE), "bajista": ("triangle-down", ap.ROJO), "neutral": ("diamond", ap.NARANJA)}
            marcas = pd.DataFrame([{
                "x": f, "y": float(h.loc[f, "Low"]) * 0.985 if s_ == "alcista" else float(h.loc[f, "High"]) * 1.015,
                "texto": f"{p_} ({s_})", "simbolo": simbolos[s_][0], "color": simbolos[s_][1], "grupo": f"Patrón {s_}"}
                for f, p_, s_ in zip(det["Fecha"], det["Patrón"], det["Sesgo"])])
            st.markdown(f"#### {e.nombre}: patrones en el gráfico")
            desde, hasta = graficos.grafico_precio("ap", tk, e.moneda, completo=True, marcas=marcas, periodo_def=ver, h_base=h)
            st.caption("▲ verde = patrón alcista · ▼ rojo = bajista · ◆ naranja = indecisión o volumen anormal. "
                       "Pasa el ratón por encima para ver cuál es. Con velas semanales o mensuales, las marcas siguen siendo de días concretos.")
            recientes = det[(det["Fecha"] >= desde) & (det["Fecha"] <= hasta)] if desde is not None else det
            if not recientes.empty:
                st.dataframe(recientes.sort_values("Fecha", ascending=False), hide_index=True, width="stretch", column_config={
                    "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"), "Cierre": st.column_config.NumberColumn(format="%.2f"),
                    "A 5 sesiones": st.column_config.NumberColumn(format="percent"),
                    "A 20 sesiones": st.column_config.NumberColumn(format="percent")})
            st.markdown("#### ¿Funcionan en esta empresa? (todo el histórico disponible)")
            est = ap.estadisticas(det, h)
            if est.empty:
                st.caption("No hay suficientes apariciones para sacar conclusiones.")
            else:
                st.dataframe(est, hide_index=True, width="stretch", column_config={
                    "Acertó la dirección": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
                    "Rentab. media a 20 sesiones": st.column_config.NumberColumn(format="percent"),
                    "Cualquier día (referencia)": st.column_config.NumberColumn(format="percent")})
                st.caption("«Acertó la dirección»: % de veces que, 20 sesiones después, el precio fue hacia donde apuntaba el patrón. "
                           "Compáralo con el 50% (azar) y con la rentabilidad de un día cualquiera. Con pocas apariciones, "
                           "el resultado es poco fiable.")
            if st.button("🔎 Analizar esta empresa"):
                abrir_empresa(tk)

# 9. Test -----------------------------------------------------------------------------------------------
with T["✅ Test"]:
    conclusion(f"{len(ap.PREGUNTAS)} preguntas para comprobar lo que has aprendido. Responde todas y pulsa **Corregir**.")
    with st.form("test_trading"):
        respuestas = []
        for i, (preg, opciones, _, _) in enumerate(ap.PREGUNTAS, 1):
            respuestas.append(st.radio(f"**{i}. {preg}**", opciones, index=None, key=f"test_{i}"))
        corregir = st.form_submit_button("✅ Corregir", type="primary")
    if corregir:
        aciertos = 0
        for i, ((preg, opciones, ok, expl), resp) in enumerate(zip(ap.PREGUNTAS, respuestas), 1):
            bien = resp == opciones[ok]
            aciertos += bien
            if bien:
                st.success(f"**{i}.** Correcto. {expl}")
            else:
                st.error(f"**{i}.** {'Sin responder' if resp is None else 'Incorrecto'}. La respuesta era «{opciones[ok]}». {expl}")
        nota = aciertos / len(ap.PREGUNTAS)
        st.metric("Tu resultado", f"{aciertos} de {len(ap.PREGUNTAS)}")
        if nota >= 0.8:
            st.balloons()
            st.success("¡Muy bien! Tienes clara la base. El siguiente paso es practicar en el 🎯 Simulador sin arriesgar dinero.")
        elif nota >= 0.5:
            st.info("Vas bien. Repasa las pestañas de las preguntas que has fallado.")
        else:
            st.warning("Conviene repasar las pestañas antes de operar con dinero real.")
