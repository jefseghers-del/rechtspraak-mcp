# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de Vlaamse Codex-wetgevingsadapter (rechtspraak_mcp/wetgeving/codex.py).

Zelfde opzet als test_ehrm.py en test_eurlex_wetgeving.py:

* Offline (default): pure parsers op vaste fixtures (ingekorte maar echte API-responsen
  van 2026-08-09: codex_zoeken.json, codex_document.json, codex_volledig.json), plus
  geïsoleerde adapter-tests met httpx.MockTransport.
* Live (marker `live`): één echte call naar de Codex-API. Alleen met RUN_LIVE=1.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import httpx
import pytest

from rechtspraak_mcp.wetgeving.codex import (
    CodexAdapter,
    document_deeplink,
    is_numac,
    parse_document,
    parse_volledig_document,
    parse_zoekrespons,
)

FIXTURES = Path(__file__).parent / "fixtures"
ZOEKEN = json.loads((FIXTURES / "codex_zoeken.json").read_text(encoding="utf-8"))
DOCUMENT = json.loads((FIXTURES / "codex_document.json").read_text(encoding="utf-8"))
VOLLEDIG = json.loads((FIXTURES / "codex_volledig.json").read_text(encoding="utf-8"))

#: Document-Id en numac uit de fixtures (decreet van 6 maart 2026, BS 27 maart 2026).
DOC_ID = 1041865
NUMAC = "2026002345"
PORTAAL_URL = f"https://codex.vlaanderen.be/Zoeken/Document.aspx?DID={DOC_ID}&param=inhoud"


# ---------------------------------------------------------------------------------------
# Pure functies
# ---------------------------------------------------------------------------------------
def test_is_numac():
    assert is_numac("2014035564")
    assert is_numac(NUMAC)
    assert is_numac("  2026002345  ")  # whitespace wordt gestript
    # geen numacs
    assert not is_numac("")
    assert not is_numac("12345")  # te kort
    assert not is_numac("20260023456")  # te lang
    assert not is_numac("2026-02345")  # geen 10 cijfers
    assert not is_numac("0026002345")  # jaartal 0026 is niet plausibel
    assert not is_numac("9999002345")  # jaartal in de verre toekomst
    assert not is_numac("RvVb-A-1920-0284")
    assert not is_numac("32011L0092")  # CELEX, geen numac


def test_document_deeplink():
    assert document_deeplink(DOC_ID) == PORTAAL_URL


def test_parse_zoekrespons_fixture():
    normen = parse_zoekrespons(ZOEKEN)
    assert len(normen) == 3

    n = normen[0]
    assert n.bron == "codex"
    assert n.type == "decreet"  # prefixlezing van het Zoeken-opschrift
    assert n.opschrift.startswith("Decreet tot wijziging van verschillende decreten")
    assert n.datum == date(2026, 3, 6)
    assert n.vindplaats == "BS 27.3.2026"  # uit BSDatum "2026-03-27T00:00:00Z"
    assert n.nummer is None  # het zoekendpoint geeft geen numac mee
    assert n.url == PORTAAL_URL

    # tweede treffer: samengesteld typewoord wint van het kortere "besluit"
    assert normen[1].type == "besluit van de vlaamse regering"
    assert normen[1].url.endswith("DID=1041786&param=inhoud")
    assert normen[2].datum == date(2025, 11, 21)


def test_parse_zoekrespons_onvolledig_resultaat_overgeslagen():
    data = {
        "ResultatenLijst": [
            {"Id": 1, "Opschrift": ""},  # geen benoembare norm
            {"Opschrift": "Decreet zonder Id"},  # geen controleerbare link
            {"Id": 2, "Opschrift": "Onherkenbaar opschrift zonder typewoord"},
        ]
    }
    normen = parse_zoekrespons(data)
    assert len(normen) == 1
    assert normen[0].type is None  # onherkenbaar prefix -> None, nooit geraden


def test_parse_zoekrespons_leeg():
    assert parse_zoekrespons({}) == []
    assert parse_zoekrespons({"GevondenDocumenten": 0, "ResultatenLijst": []}) == []


def test_parse_document_fixture():
    n = parse_document(DOCUMENT)
    assert n is not None
    assert n.bron == "codex"
    assert n.type == "decreet"  # lowercase WetgevingDocumentType
    assert n.nummer == NUMAC  # integerveld Numac, als string
    # het detail-opschrift mist het typewoord; dat wordt bijgeplakt
    assert n.opschrift.startswith("Decreet tot wijziging van verschillende decreten")
    assert n.datum == date(2026, 3, 6)
    assert n.vindplaats == "BS 27.3.2026"
    assert n.url == PORTAAL_URL


def test_parse_document_onherkenbaar():
    assert parse_document({}) is None
    assert parse_document({"Id": DOC_ID, "Opschrift": ""}) is None
    assert parse_document({"Opschrift": "tot wijziging van ..."}) is None


def test_parse_document_zonder_type_en_numac():
    n = parse_document({"Id": 7, "Opschrift": "over iets", "Numac": None})
    assert n is not None
    assert n.type is None
    assert n.nummer is None
    assert n.opschrift == "over iets"  # geen typewoord om bij te plakken


def test_parse_volledig_document_fixture():
    tekst = parse_volledig_document(VOLLEDIG)
    assert tekst.startswith("Art. 1.\nDit decreet regelt een gewestaangelegenheid.")
    assert "Art. 2." in tekst
    assert "Art. 38." in tekst  # ook het laatste artikel uit de fixture
    assert "Richtlijn (EU) 2023/2413" in tekst  # letterlijke artikeltekst


def test_parse_volledig_document_leeg():
    assert parse_volledig_document({}) == ""
    assert parse_volledig_document({"Inhoud": {"ArtikelVersies": []}}) == ""
    assert parse_volledig_document({"Inhoud": None}) == ""


# ---------------------------------------------------------------------------------------
# Adapter met MockTransport (geen echt netwerk)
# ---------------------------------------------------------------------------------------
def _mock_adapter(handler, *, sta_fetch: bool = False) -> CodexAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    adapter = CodexAdapter(client=client, rate_limit_s=0.0)  # geen echte sleep in tests
    adapter.sta_fetch = sta_fetch
    return adapter


def _api_handler(request):
    """Handler die de drie geverifieerde endpoints met de fixtures beantwoordt."""
    pad = request.url.path
    if pad == "/api/WetgevingDocument/Zoeken":
        return httpx.Response(200, json=ZOEKEN)
    if pad == f"/api/v2/WetgevingDocument/numac/{NUMAC}":
        return httpx.Response(200, json=DOCUMENT)
    if pad == f"/api/v2/WetgevingDocument/{DOC_ID}":
        return httpx.Response(200, json=DOCUMENT)
    if pad == f"/api/v2/WetgevingDocument/{DOC_ID}/VolledigDocument":
        return httpx.Response(200, json=VOLLEDIG)
    return httpx.Response(404)


def test_default_uit_geen_requests():
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("sta_fetch staat uit: er mag geen request vertrekken")

    adapter = _mock_adapter(handler)
    assert adapter.zoek("milieueffectrapportage") == []
    assert adapter.zoek_op_identifier(NUMAC) == []
    assert adapter.haal_norm(PORTAAL_URL) is None


def test_zoek_met_fetch_aan():
    def handler(request):
        assert request.url.path == "/api/WetgevingDocument/Zoeken"
        assert request.url.params.get("zoekTerm") == "milieueffectrapportage"
        assert request.url.params.get("take") == "3"
        return httpx.Response(200, json=ZOEKEN)

    adapter = _mock_adapter(handler, sta_fetch=True)
    normen = adapter.zoek("milieueffectrapportage", max_resultaten=3)
    assert len(normen) == 3
    assert normen[0].url == PORTAAL_URL


def test_zoek_cap_op_max_resultaten():
    adapter = _mock_adapter(_api_handler, sta_fetch=True)
    normen = adapter.zoek("milieueffectrapportage", max_resultaten=2)
    assert len(normen) == 2  # fixture geeft er 3; cap ook client-side


def test_zoek_lege_query():
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("lege query mag geen request opleveren")

    adapter = _mock_adapter(handler, sta_fetch=True)
    assert adapter.zoek("   ") == []


def test_zoek_op_identifier_numac():
    adapter = _mock_adapter(_api_handler, sta_fetch=True)
    normen = adapter.zoek_op_identifier(NUMAC)
    assert len(normen) == 1
    assert normen[0].nummer == NUMAC
    assert normen[0].type == "decreet"
    assert normen[0].url == PORTAAL_URL


def test_zoek_op_identifier_ongeldige_input():
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("ongeldige identifier mag geen request opleveren")

    adapter = _mock_adapter(handler, sta_fetch=True)
    assert adapter.zoek_op_identifier("32011L0092") == []
    assert adapter.zoek_op_identifier("dit is geen numac") == []
    assert adapter.zoek_op_identifier("") == []


def test_api_fout_geeft_lege_lijst():
    adapter = _mock_adapter(lambda request: httpx.Response(500), sta_fetch=True)
    assert adapter.zoek("milieueffectrapportage") == []
    assert adapter.zoek_op_identifier(NUMAC) == []
    assert adapter.haal_norm(PORTAAL_URL) is None


def test_haal_norm_portaal_url():
    adapter = _mock_adapter(_api_handler, sta_fetch=True)
    nt = adapter.haal_norm(PORTAAL_URL)
    assert nt is not None
    assert nt.norm.type == "decreet"
    assert nt.norm.nummer == NUMAC
    assert nt.tekst.startswith("Art. 1.")
    assert "gewestaangelegenheid" in nt.tekst


def test_haal_norm_api_url():
    adapter = _mock_adapter(_api_handler, sta_fetch=True)
    # ook de API-detail-URL's (v1 en v2) zijn aanvaardbare bron-URL's
    for url in (
        f"https://codex.opendata.api.vlaanderen.be/api/v2/WetgevingDocument/{DOC_ID}",
        f"https://codex.opendata.api.vlaanderen.be/api/WetgevingDocument/{DOC_ID}",
    ):
        nt = adapter.haal_norm(url)
        assert nt is not None
        assert "gewestaangelegenheid" in nt.tekst


def test_haal_norm_ongeldige_url():
    adapter = _mock_adapter(_api_handler, sta_fetch=True)
    assert adapter.haal_norm("https://example.com/Zoeken/Document.aspx?DID=1") is None
    assert adapter.haal_norm("https://codex.vlaanderen.be/Zoeken/Document.aspx") is None
    assert adapter.haal_norm("") is None


def test_haal_norm_zonder_inhoud_geeft_notitie():
    zonder_inhoud = dict(DOCUMENT, HeeftInhoud=False)

    def handler(request):
        if request.url.path == f"/api/v2/WetgevingDocument/{DOC_ID}":
            return httpx.Response(200, json=zonder_inhoud)
        raise AssertionError("VolledigDocument mag niet opgevraagd worden zonder inhoud")

    adapter = _mock_adapter(handler, sta_fetch=True)
    nt = adapter.haal_norm(PORTAAL_URL)
    assert nt is not None
    assert "HeeftInhoud" in nt.tekst  # eerlijke notitie, geen verzonnen tekst
    assert nt.norm.url in nt.tekst


def test_haal_norm_lege_tekst_geeft_notitie():
    def handler(request):
        if request.url.path == f"/api/v2/WetgevingDocument/{DOC_ID}":
            return httpx.Response(200, json=DOCUMENT)
        if request.url.path == f"/api/v2/WetgevingDocument/{DOC_ID}/VolledigDocument":
            return httpx.Response(200, json={"Inhoud": {"ArtikelVersies": []}})
        return httpx.Response(404)

    adapter = _mock_adapter(handler, sta_fetch=True)
    nt = adapter.haal_norm(PORTAAL_URL)
    assert nt is not None
    assert "raadpleeg de bron-URL" in nt.tekst


# ---------------------------------------------------------------------------------------
# Live smoke (optioneel)
# ---------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="alleen met RUN_LIVE=1")
def test_live_zoek():
    """Echte call naar de Codex-API. Vereist egress naar codex.opendata.api.vlaanderen.be."""
    adapter = CodexAdapter()
    adapter.sta_fetch = True
    try:
        normen = adapter.zoek("milieueffectrapportage", max_resultaten=3)
    finally:
        adapter.close()
    assert normen, "Geen treffer — check egress naar codex.opendata.api.vlaanderen.be"
    assert all(n.bron == "codex" for n in normen)
    assert all(
        n.url.startswith("https://codex.vlaanderen.be/Zoeken/Document.aspx?DID=")
        for n in normen
    )
