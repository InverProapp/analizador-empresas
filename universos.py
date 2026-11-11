"""Listas de empresas (tickers de Yahoo Finance) por índice.

Las composiciones cambian con el tiempo: revisa y edita estas listas cuando haya
entradas o salidas. Un ticker que ya no exista simplemente se salta.
"""

UNIVERSOS = {
    # IBEX 35: sin cambios desde la entrada de Puig (jul-2024); revisión de jun-2026 sin cambios
    "IBEX 35": [
        "ACS.MC", "ACX.MC", "AENA.MC", "AMS.MC", "ANA.MC", "ANE.MC", "BBVA.MC", "BKT.MC", "CABK.MC",
        "CLNX.MC", "COL.MC", "ELE.MC", "ENG.MC", "FDR.MC", "FER.MC", "GRF.MC", "IAG.MC", "IBE.MC",
        "IDR.MC", "ITX.MC", "LOG.MC", "MAP.MC", "MRL.MC", "MTS.MC", "NTGY.MC", "PUIG.MC", "RED.MC",
        "REP.MC", "ROVI.MC", "SAB.MC", "SAN.MC", "SCYR.MC", "SLR.MC", "TEF.MC", "UNI.MC",
    ],
    # Euro Stoxx 50 (aprox., tras la revisión de sep-2026: entran Nokia y Engie)
    "Euro Stoxx 50": [
        "ADYEN.AS", "AD.AS", "AI.PA", "AIR.PA", "ALV.DE", "ABI.BR", "ARGX.BR", "ASML.AS", "CS.PA",
        "BAS.DE", "BAYN.DE", "BBVA.MC", "SAN.MC", "BMW.DE", "BNP.PA", "BN.PA", "DB1.DE", "DBK.DE",
        "DHL.DE", "DTE.DE", "ENEL.MI", "ENI.MI", "ENGI.PA", "EL.PA", "RACE.MI", "IBE.MC", "ITX.MC",
        "IFX.DE", "INGA.AS", "ISP.MI", "OR.PA", "MC.PA", "MBG.DE", "MUV2.DE", "NDA-FI.HE", "NOKIA.HE",
        "PRX.AS", "RHM.DE", "RMS.PA", "SAF.PA", "SAN.PA", "SAP.DE", "SU.PA", "SIE.DE", "ENR.DE",
        "SGO.PA", "STLAM.MI", "TTE.PA", "UCG.MI", "DG.PA",
    ],
    "Dow Jones 30": [
        "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON",
        "IBM", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK", "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV",
        "UNH", "V", "VZ", "WMT",
    ],
    # Nasdaq 100 (aprox.)
    "Nasdaq 100": [
        "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO", "TSLA", "COST", "NFLX", "PLTR",
        "AMD", "ASML", "CSCO", "TMUS", "AZN", "LIN", "PEP", "INTU", "ISRG", "TXN", "QCOM", "BKNG",
        "AMGN", "ADBE", "AMAT", "PDD", "HON", "GILD", "CMCSA", "PANW", "MU", "ADP", "LRCX", "KLAC",
        "SBUX", "MELI", "APP", "ADI", "INTC", "CRWD", "VRTX", "MSTR", "CEG", "MDLZ", "CTAS", "SNPS",
        "ORLY", "CDNS", "MAR", "FTNT", "DASH", "ABNB", "PYPL", "REGN", "MRVL", "CSX", "WDAY", "ADSK",
        "ROP", "CHTR", "AEP", "PCAR", "NXPI", "TEAM", "MNST", "FAST", "PAYX", "CPRT", "KDP", "ROST",
        "AXON", "EXC", "DDOG", "FANG", "TTWO", "BKR", "XEL", "CCEP", "VRSK", "KHC", "EA", "CTSH",
        "IDXX", "ZS", "GEHC", "ODFL", "CSGP", "TTD", "DXCM", "ANSS", "ON", "WBD", "LULU", "CDW",
        "BIIB", "GFS", "ARM", "MDB",
    ],
}


# ---------------------------------------------------------------------------
# Mercados enteros por país (buscador de acciones de Yahoo, ordenado por capitalización)
# ---------------------------------------------------------------------------
MERCADOS = {
    "🇪🇸 España (Mercado Continuo)": ("es", ["MCE"]),
    "🇺🇸 Estados Unidos": ("us", ["NMS", "NYQ", "NGM", "NCM", "ASE"]),
    "🇩🇪 Alemania": ("de", ["GER"]),
    "🇫🇷 Francia": ("fr", ["PAR"]),
    "🇬🇧 Reino Unido": ("gb", ["LSE"]),
    "🇮🇹 Italia": ("it", ["MIL"]),
    "🇳🇱 Países Bajos": ("nl", ["AMS"]),
    "🇨🇭 Suiza": ("ch", ["EBS"]),
    "🇸🇪 Suecia": ("se", ["STO"]),
    "🇩🇰 Dinamarca": ("dk", ["CPH"]),
    "🇳🇴 Noruega": ("no", ["OSL"]),
    "🇫🇮 Finlandia": ("fi", ["HEL"]),
    "🇧🇪 Bélgica": ("be", ["BRU"]),
    "🇵🇹 Portugal": ("pt", ["LIS"]),
    "🇦🇹 Austria": ("at", ["VIE"]),
    "🇮🇪 Irlanda": ("ie", ["ISE"]),
    "🇨🇦 Canadá": ("ca", ["TOR"]),
    "🇯🇵 Japón": ("jp", ["JPX"]),
}


def mercado(nombre: str, n: int = 100) -> list[str]:
    """Las `n` mayores empresas (por capitalización) de un mercado, vía yf.screen."""
    import yfinance as yf
    from yfinance import EquityQuery

    region, bolsas = MERCADOS[nombre]
    filtro_bolsa = EquityQuery("is-in", ["exchange", *bolsas]) if len(bolsas) > 1 else EquityQuery("eq", ["exchange", bolsas[0]])
    consulta = EquityQuery("and", [EquityQuery("eq", ["region", region]), filtro_bolsa,
                                   EquityQuery("gt", ["intradaymarketcap", 0])])
    simbolos, nombres, offset = [], set(), 0
    while len(simbolos) < n:
        tam = min(250, n - len(simbolos) + 25)  # algo de margen por duplicados
        res = yf.screen(consulta, offset=offset, size=tam, sortField="intradaymarketcap", sortAsc=False)
        quotes = (res or {}).get("quotes", [])
        if not quotes:
            break
        for q in quotes:
            sym = q.get("symbol")
            nom = (q.get("longName") or q.get("shortName") or sym or "").lower()
            if not sym or q.get("quoteType", "EQUITY") != "EQUITY" or nom in nombres:
                continue  # fuera duplicados (p. ej. GOOG/GOOGL, acciones A/B)
            nombres.add(nom)
            simbolos.append(sym)
            if len(simbolos) >= n:
                break
        offset += len(quotes)
        if len(quotes) < tam:
            break
    return simbolos


def lista(nombre: str, personalizada: str = "") -> list[str]:
    if nombre == "Lista personalizada":
        return [t.strip().upper() for t in personalizada.replace(";", ",").replace("\n", ",").split(",") if t.strip()]
    return list(dict.fromkeys(UNIVERSOS.get(nombre, [])))
