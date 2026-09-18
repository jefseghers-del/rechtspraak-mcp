# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de MCP-server zelf (rechtspraak_mcp/server.py).

Aanleiding: de server importeerde stilzwijgend niet meer nadat het `mcp`-pakket naar 2.0
ging (`mcp.server.fastmcp.FastMCP` werd `mcp.server.mcpserver.MCPServer`). Geen enkele test
raakte server.py aan, zodat de suite groen bleef terwijl de connector onbruikbaar was. Deze
tests bewaken daarom het import- en registratiepad én de doorstroom naar het VENA-veld.

Geen netwerk: met de standaardconfiguratie staat automatisch ophalen bij elke bron uit, dus
de tool-oproepen hieronder raken geen enkele bron.
"""
from __future__ import annotations

import asyncio
from datetime import date

from rechtspraak_mcp.schema import Treffer
from rechtspraak_mcp.server import _leg_lege_identifier_uit, _met_verwijzing, mcp

VERWACHTE_TOOLS = {
    "zoek_rechtspraak",
    "zoek_op_identifier",
    "haal_uitspraak",
    "zoek_wetgeving",
    "haal_norm",
}


def test_server_registreert_de_vijf_tools():
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == VERWACHTE_TOOLS


def test_elke_tool_heeft_een_beschrijving():
    # De MCP-client toont deze beschrijvingen; leeg = onbruikbaar voor het model.
    for tool in asyncio.run(mcp.list_tools()):
        assert tool.description, f"tool {tool.name} heeft geen beschrijving"


def test_zoek_rechtspraak_leeg_maar_met_uitleg_en_zoeklinks():
    # Standaardconfiguratie: vrijetekstzoeken kan nergens -> lege treffers, maar mét
    # melding en handmatige zoeklinks (geen verzonnen treffers; anti-hallucinatie).
    resultaat = asyncio.run(mcp.call_tool("zoek_rechtspraak", {"query": "zonevreemde woning"}))
    assert resultaat.is_error is False
    r = resultaat.structured_content
    assert r["treffers"] == []
    # Standaard staat browser-zoeken uit -> uitleg dat vrij zoeken de opt-in vlag vereist.
    assert "RECHTSPRAAK_MCP_BROWSER_ZOEK" in r["melding"]
    assert "zonevreemde+woning" in r["handmatige_links"]["dbrc (zoekpagina)"]


def test_zoek_op_identifier_ecli_met_fetch_uit_geeft_uitleg_en_deeplink():
    # Bron staat standaard uit -> geen treffer, wel uitleg + onbevestigde deeplink.
    resultaat = asyncio.run(
        mcp.call_tool("zoek_op_identifier", {"identifier": "ECLI:BE:CASS:2020:ARR.20201030.1N.4"})
    )
    assert resultaat.is_error is False
    r = resultaat.structured_content
    assert r["treffers"] == []
    assert "staat uit" in r["melding"]
    assert "Juportal automatisch ophalen" in r["melding"]  # de schakelaar in Claude Desktop
    assert (
        r["handmatige_links"]["juportal (onbevestigde deeplink)"]
        == "https://juportal.be/content/ECLI:BE:CASS:2020:ARR.20201030.1N.4"
    )


def test_zoek_op_identifier_cassatie_rolnummer_legt_uit():
    resultaat = asyncio.run(mcp.call_tool("zoek_op_identifier", {"identifier": "P.12.1389.N"}))
    r = resultaat.structured_content
    assert r["treffers"] == []
    assert "Cassatie" in r["melding"] and "ECLI" in r["melding"]
    assert "juportal (zoekformulier)" in r["handmatige_links"]


def test_zoek_op_identifier_onherkenbaar_legt_formaten_uit():
    resultaat = asyncio.run(mcp.call_tool("zoek_op_identifier", {"identifier": "zomaar tekst"}))
    r = resultaat.structured_content
    assert r["treffers"] == []
    assert "niet herkend" in r["melding"]


def test_verwijzing_wordt_ingevuld_op_treffers():
    treffer = Treffer(
        bron="dbrc",
        instantie="Raad voor Vergunningsbetwistingen",
        titel="RvVb-A-2223-0431",
        datum=date(2023, 1, 17),
        rolnummer="RvVb-A-2223-0431",
        url="https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf",
    )
    assert treffer.verwijzing is None
    _met_verwijzing([treffer])
    assert treffer.verwijzing.startswith("RvVb 17 januari 2023, nr. RvVb-A-2223-0431, ")


def test_verwijzing_overschrijft_bestaande_waarde_niet():
    treffer = Treffer(
        bron="dbrc",
        instantie="Raad voor Vergunningsbetwistingen",
        titel="x",
        rolnummer="RvVb-A-2223-0431",
        url="https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf",
        verwijzing="handmatig gezet",
    )
    _met_verwijzing([treffer])
    assert treffer.verwijzing == "handmatig gezet"


# ---------------------------------------------------------------------------------------
# Wetgevingstools (zoek_wetgeving / haal_norm)
# ---------------------------------------------------------------------------------------
def test_wetgevingstools_geregistreerd():
    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"zoek_wetgeving", "haal_norm"} <= tools


def test_zoek_wetgeving_bron_uit_geeft_uitleg_en_deeplink():
    # Standaard staat eurlex uit -> lege normen, melding, en bij een herkende identifier
    # een onbevestigde deeplink (anti-hallucinatie: geen verzonnen norm).
    resultaat = asyncio.run(mcp.call_tool("zoek_wetgeving", {"query": "Richtlijn 2011/92/EU"}))
    assert resultaat.is_error is False
    r = resultaat.structured_content
    assert r["normen"] == []
    assert "eurlex" in r["melding"]
    assert (
        r["handmatige_links"]["eurlex (onbevestigde deeplink)"]
        == "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092"
    )


def test_zoek_wetgeving_vrije_tekst_bron_uit_geen_deeplink():
    r = asyncio.run(
        mcp.call_tool("zoek_wetgeving", {"query": "milieueffectrapportage"})
    ).structured_content
    assert r["normen"] == []
    assert "eurlex (onbevestigde deeplink)" not in (r["handmatige_links"] or {})
    assert "milieueffectrapportage" in r["handmatige_links"]["eurlex (zoekpagina)"]


# ---------------------------------------------------------------------------------------
# Segmentatie: haal_uitspraak vult het beoordelende deel
# ---------------------------------------------------------------------------------------
def test_met_beoordeling_vult_velden():
    from rechtspraak_mcp.server import _met_beoordeling
    from rechtspraak_mcp.schema import Uitspraak

    tekst = (
        "I. Voorwerp van het beroep\nx\n"
        "IV. Onderzoek van de vordering\n"
        "Standpunt van de partijen\nDe verzoekende partij betoogt dat het besluit onwettig is.\n"
        "Beoordeling door de Raad\nDe Raad stelt vast dat het middel gegrond is.\n"
        "V. Beslissing\n1. Het beroep wordt ingewilligd.\n"
    )
    u = Uitspraak(
        treffer=Treffer(
            bron="dbrc",
            instantie="Raad voor Vergunningsbetwistingen",
            titel="x",
            rolnummer="RvVb-A-2223-0431",
            url="https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf",
        ),
        tekst=tekst,
    )
    _met_beoordeling(u)
    assert u.beoordeling is not None
    assert "De Raad stelt vast dat het middel gegrond is." in u.beoordeling
    assert "De verzoekende partij betoogt" not in u.beoordeling
    assert u.segmentatie  # melding altijd ingevuld


def test_met_beoordeling_onherkenbaar_geeft_none_met_melding():
    from rechtspraak_mcp.server import _met_beoordeling
    from rechtspraak_mcp.schema import Uitspraak

    u = Uitspraak(
        treffer=Treffer(bron="dbrc", instantie="x", titel="x", url="https://www.dbrc.be/x"),
        tekst="Zomaar wat lopende tekst zonder enige koppenstructuur.",
    )
    _met_beoordeling(u)
    assert u.beoordeling is None
    assert "niet herkend" in (u.segmentatie or "")


def test_dbrc_nummer_afgebroken_zoektocht_meldt_geen_negatieve_zekerheid():
    # Pure uitlegfunctie (geen netwerk): breekt de DBRC-zoektocht af op het tijdsbudget,
    # dan mag de melding niet suggereren dat het arrest niet bestaat, en moet ze de
    # gebruiker naar de `datum`-parameter sturen.
    r = _leg_lege_identifier_uit("RvVb-A-2425-0744", afgebroken=True)
    assert r.treffers == []
    assert "tijdsbudget" in r.melding
    assert "datum" in r.melding
    assert "dbrc (zoekpagina met nummer)" in r.handmatige_links


def test_dbrc_nummer_met_datum_meldt_iets_anders_dan_zonder_datum():
    met = _leg_lege_identifier_uit("RvVb-A-2425-0744", datum=date(2025, 6, 3))
    zonder = _leg_lege_identifier_uit("RvVb-A-2425-0744")
    assert met.melding != zonder.melding
    assert "opgegeven datum" in met.melding
    assert "`datum`" in zonder.melding


def test_zoek_op_identifier_neemt_datum_aan():
    # De datum moet als tool-parameter bestaan; zonder dat kan het model ze niet meegeven.
    tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "zoek_op_identifier")
    assert "datum" in tool.input_schema["properties"]
