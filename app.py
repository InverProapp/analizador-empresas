"""Analizador de empresas — punto de entrada.

Arranque:  streamlit run app.py
"""
import importlib
import os
import sys

import streamlit as st

# Tras publicar cambios, Streamlit Cloud a veces conserva en memoria la versión anterior de nuestros módulos
# (y aparecen errores tipo «no tiene el atributo…»). Recargamos cualquier módulo propio cuyo archivo haya cambiado.
_RAIZ = os.path.dirname(os.path.abspath(__file__))
for _nombre, _mod in list(sys.modules.items()) if not os.environ.get("ANALIZADOR_SIN_RECARGA") else []:
    _f = getattr(_mod, "__file__", None) or ""
    if not _f.startswith(_RAIZ) or os.sep + "vistas" + os.sep in _f or _nombre in ("__main__", "usuario"):
        continue
    try:
        _mt = os.path.getmtime(_f)
        if getattr(_mod, "_mtime_carga", None) != _mt:
            if getattr(_mod, "_mtime_carga", None) is not None or _nombre != "app":
                importlib.reload(_mod)
            _mod._mtime_carga = _mt
    except Exception:
        pass

import usuario  # noqa: E402

st.set_page_config(page_title="Analizador de empresas", page_icon="📊", layout="wide")
usuario.montar()  # favoritos, alertas y notas guardados en este navegador

# Estilo común: cifras algo más pequeñas (no se cortan) y definiciones emergentes discretas
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.7rem; }
button[kind="tertiary"][data-testid="stPopoverButton"] > div > div[aria-hidden="true"] { display: none; }
button[kind="tertiary"][data-testid="stPopoverButton"] { min-height: 0; padding: 0; }
button[kind="tertiary"][data-testid="stPopoverButton"] p { font-size: 0.875rem; opacity: .8; }
h4 { padding-top: .6rem; }
.conclusion { border-left: 5px solid #4c78a8; background: rgba(76,120,168,.08); padding: .7rem 1rem;
              border-radius: 6px; margin: .2rem 0 1rem 0; font-size: 1.02rem; }
</style>""", unsafe_allow_html=True)

paginas = {
    "Inicio": [st.Page("vistas/resumen.py", title="Resumen del día", icon="☀️")],
    "Investigar": [
        st.Page("vistas/empresa.py", title="Analizar empresa", icon="🔎", default=True),
        st.Page("vistas/escaner.py", title="Escáner e ideas", icon="📡"),
        st.Page("vistas/sectores.py", title="Sectores", icon="🏭"),
    ],
    "Mi seguimiento": [
        st.Page("vistas/favoritos.py", title="Mi lista y alertas", icon="⭐"),
        st.Page("vistas/calendario.py", title="Calendario", icon="📅"),
    ],
    "Aprender": [st.Page("vistas/aprende.py", title="Aprende trading", icon="📚")],
    "Herramientas": [
        st.Page("vistas/simulador.py", title="Simulador", icon="🎯"),
        st.Page("vistas/backtest.py", title="Backtest del modelo", icon="🧪"),
    ],
}
pagina = st.navigation(paginas)

# Aviso de alertas cumplidas (solo las de precio: son rápidas de comprobar)
if usuario.cargado() and usuario.alertas_de():
    rapidas = [a for a in usuario.alertas_de() if a["tipo"] not in usuario.MODELO]
    estados = usuario.comprobar(rapidas)
    for a in usuario.marcar_disparadas(estados):
        st.toast(f"🔔 **{a['ticker']}**: {usuario.describir(a)}", icon="🔔")
    n = sum(1 for a in usuario.alertas_de() if a.get("disparada"))
    if n:
        st.sidebar.warning(f"🔔 Tienes **{n} alerta{'s' if n > 1 else ''}** cumplida{'s' if n > 1 else ''}.")
        st.sidebar.page_link("vistas/favoritos.py", label="Ver mis alertas", icon="⭐")

# Recordatorio de tesis sin revisar en 3 meses (solo mira fechas: no descarga nada)
if usuario.cargado() and usuario.datos().get("tesis"):
    import time as _time
    import tesis as _ts
    _hoy = _time.time()
    _pend = [tk for tk, t in usuario.datos()["tesis"].items()
             if (_hoy - _time.mktime(_time.strptime(t.get("revisada", "2000-01-01"), "%Y-%m-%d"))) / 86400 >= _ts.DIAS_REVISION]
    if _pend:
        st.sidebar.info(f"🧐 Toca revisar tu tesis de **{', '.join(_pend[:3])}**{'…' if len(_pend) > 3 else ''}.")

pagina.run()
