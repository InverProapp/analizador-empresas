"""Análisis cualitativo con Claude (API de Anthropic).

Claude recibe la descripción del negocio, las métricas y la nota del modelo, las noticias
recientes de Yahoo y, opcionalmente, un PDF (informe anual, presentación de resultados…).
Si se activa, también puede buscar en la web.
"""
from __future__ import annotations

import io

MODELOS = {
    "Claude Sonnet 5.5 (recomendado)": "claude-sonnet-5-5",
    "Claude Haiku 5.5 (rápido y barato)": "claude-haiku-5-5",
    "Claude Opus 5.5 (más profundo, más caro)": "claude-opus-5-5",
}

SISTEMA = """Eres un analista de renta variable independiente, riguroso y escéptico. Escribes en español
de España, claro y directo, para un inversor particular con formación financiera.

Tu trabajo es complementar un modelo cuantitativo que ya ha puntuado la empresa con sus números.
Aporta lo que los números no ven: modelo de negocio, ventajas competitivas, riesgos, catalizadores
y qué ha cambiado recientemente. No repitas las métricas salvo para apoyar un argumento.

Reglas:
- Distingue hechos (de los datos o fuentes que te doy) de tu opinión.
- Si no sabes algo o los datos no lo cubren, dilo; no inventes cifras ni noticias.
- Si el modelo cuantitativo y tu lectura cualitativa discrepan, explícalo.
- No des una orden de compra o venta: das elementos para que el inversor decida.
- Usa títulos en markdown (###) y viñetas cortas. Máximo ~700 palabras."""

ESTRUCTURA = """Estructura la respuesta así:
### En una frase
### El negocio y cómo gana dinero
### Ventaja competitiva (moat): ninguna / estrecha / amplia, y por qué
### Qué ha pasado últimamente
### Riesgos principales
### Catalizadores (qué podría hacer subir la acción)
### Tesis alcista vs tesis bajista
### ¿Coincide con el veredicto del modelo?
### Qué vigilar en los próximos resultados"""


def texto_pdf(archivo, max_chars: int = 60000) -> str:
    """Extrae el texto de un PDF subido (st.file_uploader)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        lector = PdfReader(io.BytesIO(archivo.getvalue()))
        partes = []
        for pagina in lector.pages:
            partes.append(pagina.extract_text() or "")
            if sum(len(p) for p in partes) > max_chars:
                break
        return "\n".join(partes)[:max_chars]
    except Exception:
        return ""


def construir_prompt(nombre, ticker, info, resumen_metricas, veredicto, nota, noticias, texto_doc, buscar_web):
    partes = [f"Empresa: {nombre} ({ticker})",
              f"Sector: {info.get('sector', '?')} · Industria: {info.get('industry', '?')} · País: {info.get('country', '?')}"]
    if info.get("longBusinessSummary"):
        partes.append("Descripción (Yahoo Finance):\n" + info["longBusinessSummary"][:3000])
    partes.append(f"Veredicto del modelo cuantitativo: {veredicto} (nota {nota:.0f}/100)" if nota is not None
                  else f"Veredicto del modelo cuantitativo: {veredicto}")
    partes.append("Métricas clave:\n" + resumen_metricas)
    if noticias:
        lineas = [f"- [{n['fecha']}] {n['titulo']} ({n['fuente']}): {n['resumen'][:300]}" for n in noticias]
        partes.append("Noticias recientes (Yahoo Finance):\n" + "\n".join(lineas))
    else:
        partes.append("No hay noticias recientes disponibles en Yahoo Finance.")
    if texto_doc:
        partes.append("Documento aportado por el usuario (extracto):\n<documento>\n" + texto_doc + "\n</documento>")
    if buscar_web:
        partes.append("Puedes buscar en la web para completar con los últimos resultados, guías de la "
                      "dirección y noticias relevantes de los últimos 6 meses. Cita las fuentes que uses.")
    partes.append(ESTRUCTURA)
    return "\n\n".join(partes)


def analizar(api_key: str, modelo: str, prompt: str, buscar_web: bool = False, max_tokens: int = 3000) -> str:
    import anthropic

    cliente = anthropic.Anthropic(api_key=api_key)
    herramientas = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}] if buscar_web else []
    mensajes = [{"role": "user", "content": prompt}]
    textos = []
    for _ in range(4):  # las búsquedas largas pueden devolver pause_turn: se continúa
        kwargs = dict(model=modelo, max_tokens=max_tokens, system=SISTEMA, messages=mensajes)
        if herramientas:
            kwargs["tools"] = herramientas
        resp = cliente.messages.create(**kwargs)
        textos = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        if resp.stop_reason != "pause_turn":
            break
        mensajes = mensajes + [{"role": "assistant", "content": resp.content}]
    return "\n".join(textos).strip()
