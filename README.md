# Analizador de empresas

Dashboard que analiza cualquier empresa cotizada del mundo con datos gratuitos de Yahoo Finance
y da un veredicto **Comprar / Esperar / Vender** según reglas que puedes ajustar.

## Usarlo online

Abre el enlace de Streamlit Community Cloud (no hace falta instalar nada).

## Instalarlo en tu ordenador (opcional)

Necesitas Python 3.10 o superior.

```bash
cd analizador
pip install -r requirements.txt
```

## Arrancar

```bash
streamlit run app.py
```

Se abre solo en el navegador (http://localhost:8501). En Windows también puedes hacer doble clic en `arrancar.py` (con Python 3.13 de la Microsoft Store).

## Tickers

Usa el buscador por nombre o escribe el ticker de Yahoo Finance:

| Bolsa | Ejemplo |
|---|---|
| EE. UU. | `AAPL`, `MSFT`, `KO` |
| España | `ITX.MC`, `SAN.MC`, `IBE.MC` |
| París / Fráncfort / Ámsterdam | `MC.PA`, `SAP.DE`, `ASML.AS` |
| Londres / Suiza | `ULVR.L`, `NESN.SW` |
| Japón / Hong Kong | `7203.T`, `0700.HK` |

## Archivos

- `app.py`: la interfaz (pestañas, gráficos y barra lateral).
- `datos.py`: descarga de datos y cálculo de métricas (ratios, Piotroski, Altman Z, DCF, Graham, indicadores técnicos).
- `scoring.py`: **aquí se decide el veredicto**. Contiene los umbrales por sector, los pesos por defecto y las alertas. Edítalo para afinar el modelo a tu criterio.

## Aviso

Es un modelo mecánico de apoyo al análisis, no asesoramiento financiero. Los datos de Yahoo son gratuitos
y no están auditados: pueden faltar o venir con errores, sobre todo en bolsas pequeñas.
