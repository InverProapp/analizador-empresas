"""Analizador de empresas — punto de entrada.

Arranque:  streamlit run app.py
"""
import streamlit as st

import usuario

st.set_page_config(page_title="Analizador de empresas", page_icon="📊", layout="wide")
usuario.montar()  # favoritos, alertas y notas guardados en este navegador

paginas = [
    st.Page("vistas/empresa.py", title="Analizar empresa", icon="🔎", default=True),
    st.Page("vistas/favoritos.py", title="Mi lista y alertas", icon="⭐"),
    st.Page("vistas/simulador.py", title="Simulador", icon="🎯"),
    st.Page("vistas/escaner.py", title="Escáner", icon="📡"),
    st.Page("vistas/backtest.py", title="Backtest del modelo", icon="🧪"),
]
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

pagina.run()
