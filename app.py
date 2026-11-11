"""Analizador de empresas — punto de entrada.

Arranque:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Analizador de empresas", page_icon="📊", layout="wide")

paginas = [
    st.Page("vistas/empresa.py", title="Analizar empresa", icon="🔎", default=True),
    st.Page("vistas/escaner.py", title="Escáner", icon="📡"),
    st.Page("vistas/backtest.py", title="Backtest", icon="🧪"),
]
st.navigation(paginas).run()
