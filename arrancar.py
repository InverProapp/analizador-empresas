"""Doble clic aquí para instalar (la primera vez) y arrancar el Analizador."""
import os
import subprocess
import sys
import traceback

CARPETA = os.path.dirname(os.path.abspath(__file__))
os.chdir(CARPETA)
LOG = os.path.join(CARPETA, "arranque.log")


def log(txt):
    print(txt)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(txt + "\n")


open(LOG, "w", encoding="utf-8").close()
log(f"Python: {sys.executable} {sys.version}")
try:
    log("Comprobando/instalando dependencias (la primera vez tarda 1-2 minutos)...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                        "-r", "requirements.txt"], capture_output=True, text=True)
    log(r.stdout[-3000:])
    log(r.stderr[-3000:])
    if r.returncode != 0:
        raise RuntimeError(f"pip terminó con código {r.returncode}")
    log("Dependencias OK. Arrancando el Analizador en http://localhost:8501 ...")
    log("No cierres esta ventana mientras lo uses.")
    import threading, webbrowser
    threading.Timer(6, lambda: webbrowser.open("http://localhost:8501")).start()
    with open(LOG, "a", encoding="utf-8") as f:
        subprocess.call([sys.executable, "-m", "streamlit", "run", "app.py",
                         "--browser.gatherUsageStats", "false", "--server.port", "8501",
                         "--server.headless", "true"],
                        stdout=f, stderr=subprocess.STDOUT)
except Exception:
    log(traceback.format_exc())
input("\nPulsa Enter para cerrar...")
