# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de Juportal-adapter.

Twee soorten (zelfde opzet als test_dbrc.py):

* Offline (default): pure parser- en URL-logica op een vaste fixture
  (tests/fixtures/juportal_content_cass.html — echte, licht geanonimiseerde HTML van
  https://juportal.be/content/ECLI:BE:CASS:2020:ARR.20201030.1N.4, opgehaald 2026-08-03),
  plus adaptertests met httpx.MockTransport (geen echt netwerk).
* Live (marker `live`): één echte GET naar juportal.be. Wordt overgeslagen tenzij
  RUN_LIVE=1. Let op: robots.txt van juportal.be disallowt alles voor generieke bots —
  de live-test vergt dus ook een bewuste keuze (sta_fetch=True) en is enkel bedoeld als
  incidentele handmatige verificatie.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import httpx
import pytest

from rechtspraak_mcp.adapters.juportal import (
    JuportalAdapter,
    content_deeplink,
    normaliseer_ecli,
    parse_content_pagina,
    parse_uitspraak_tekst,
)
from rechtspraak_mcp.schema import ZoekQuery

ECLI = "ECLI:BE:CASS:2020:ARR.20201030.1N.4"
CONTENT_URL = f"https://juportal.be/content/{ECLI}"
FIXTURE = (Path(__file__).parent / "fixtures" / "juportal_content_cass.html").read_text()


# ---------------------------------------------------------------------------------------
# Pure helpers: ECLI-validatie en deeplink
# ---------------------------------------------------------------------------------------
def test_normaliseer_ecli():
    assert normaliseer_ecli(ECLI) == ECLI
    # trim + hoofdletters
    assert normaliseer_ecli("  ecli:be:cass:2020:arr.20201030.1n.4 ") == ECLI
    assert normaliseer_ecli("ECLI:BE:GHCC:2024:ARR.001") == "ECLI:BE:GHCC:2024:ARR.001"
    # ongeldig
    assert normaliseer_ecli("ECLI:NL:HR:2020:123") is None  # geen BE
    assert normaliseer_ecli("ECLI:BE:CASS:20:ARR.1") is None  # jaar geen 4 cijfers
    assert normaliseer_ecli("RvVb-A-1920-0284") is None
    assert normaliseer_ecli("onzin") is None
    assert normaliseer_ecli("") is None


def test_content_deeplink():
    assert content_deeplink(ECLI) == CONTENT_URL
    assert content_deeplink("ecli:be:cass:2020:arr.20201030.1n.4") == CONTENT_URL
    with pytest.raises(ValueError):
        content_deeplink("dit is geen ecli")


# ---------------------------------------------------------------------------------------
# Pure parsers op de fixture
# ---------------------------------------------------------------------------------------
def test_parse_content_pagina_fixture():
    treffer = parse_content_pagina(FIXTURE, CONTENT_URL)
    assert treffer is not None
    assert treffer.bron == "juportal"
    assert treffer.ecli == ECLI
    assert treffer.instantie == "Hof van Cassatie"
    assert treffer.rolnummer == "C.20.0061.N"
    assert treffer.datum == date(2020, 10, 30)  # uit "Vonnis/arrest van 30 oktober 2020"
    assert treffer.url == CONTENT_URL
    # titel bevat instantie, datum-legend en zaaknaam zoals de bron ze toont
    assert "Hof van Cassatie" in treffer.titel
    assert "30 oktober 2020" in treffer.titel
    assert "G. contra Niko" in treffer.titel
    # snippet = samenvatting van Fiche 1
    assert treffer.snippet is not None
    assert "exceptie van niet-uitvoering" in treffer.snippet


def test_parse_content_pagina_zonder_uitspraak():
    # lege pagina / JS-shell / foutpagina -> None, geen verzonnen treffer
    assert parse_content_pagina("<html><head></head><body></body></html>", CONTENT_URL) is None
    assert parse_content_pagina("", CONTENT_URL) is None


def test_parse_uitspraak_tekst_fixture():
    tekst = parse_uitspraak_tekst(FIXTURE)
    assert tekst.startswith("Nr. C.20.0061.N")
    assert "Verwerpt het cassatieberoep." in tekst
    assert "openbare rechtszitting van 30 oktober 2020" in tekst
    # navigatie-chrome en PDF-link horen niet in de tekst
    assert "Print deze pagina" not in tekst
    assert "PDF document" not in tekst


def test_parse_uitspraak_tekst_zonder_tekstblok():
    assert parse_uitspraak_tekst("<html><body><p>niets</p></body></html>") == ""


# ---------------------------------------------------------------------------------------
# Adapter met MockTransport (geen echt netwerk)
# ---------------------------------------------------------------------------------------
def _mock_adapter(handler) -> JuportalAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    # rate_limit_s=0 -> geen echte sleep in tests
    return JuportalAdapter(client=client, rate_limit_s=0.0)


def _verboden_handler(request):  # pragma: no cover - mag niet aangeroepen worden
    raise AssertionError(f"onverwacht request naar {request.url}: sta_fetch staat uit")


def test_fetch_staat_standaard_uit_geen_enkel_request():
    # robots.txt disallowt alles -> standaard geen netwerk en lege resultaten
    adapter = _mock_adapter(_verboden_handler)
    assert adapter.sta_fetch is False
    assert adapter.zoek(ZoekQuery(query="exceptie van niet-uitvoering")) == []
    assert adapter.zoek_op_identifier(ECLI) == []
    assert adapter.haal_uitspraak(CONTENT_URL) is None


def test_zoek_altijd_leeg_ook_met_vlag_aan():
    # zoek is niet geïmplementeerd (JSON-endpoint achter de SPA niet onderzocht)
    adapter = _mock_adapter(_verboden_handler)
    adapter.sta_fetch = True
    assert adapter.zoek(ZoekQuery(query="cassatie")) == []


def test_zoek_op_identifier_met_vlag_aan():
    def handler(request):
        assert str(request.url) == CONTENT_URL
        return httpx.Response(200, text=FIXTURE)

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    treffers = adapter.zoek_op_identifier(ECLI)
    assert len(treffers) == 1
    t = treffers[0]
    assert t.bron == "juportal"
    assert t.ecli == ECLI
    assert t.rolnummer == "C.20.0061.N"
    assert t.datum == date(2020, 10, 30)
    assert t.url == CONTENT_URL


def test_zoek_op_identifier_ongeldige_ecli_geen_request():
    adapter = _mock_adapter(_verboden_handler)
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier("RvVb-A-1920-0284") == []
    assert adapter.zoek_op_identifier("onzin") == []


def test_zoek_op_identifier_http_fout():
    adapter = _mock_adapter(lambda request: httpx.Response(404))
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier(ECLI) == []


def test_zoek_op_identifier_onbruikbare_respons_geen_treffer():
    # 200 maar zonder herkenbare uitspraak (bv. foutpagina) -> geen verzonnen treffer
    adapter = _mock_adapter(lambda request: httpx.Response(200, text="<html><body>oeps</body></html>"))
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier(ECLI) == []


def test_haal_uitspraak_met_vlag_aan():
    def handler(request):
        assert str(request.url) == CONTENT_URL
        return httpx.Response(200, text=FIXTURE)

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    uitspraak = adapter.haal_uitspraak(CONTENT_URL)
    assert uitspraak is not None
    assert uitspraak.treffer.ecli == ECLI
    assert uitspraak.treffer.instantie == "Hof van Cassatie"
    assert "Verwerpt het cassatieberoep." in uitspraak.tekst


def test_haal_uitspraak_accepteert_taalsuffix():
    url_nl = f"{CONTENT_URL}/NL"

    def handler(request):
        assert str(request.url) == url_nl
        return httpx.Response(200, text=FIXTURE)

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    uitspraak = adapter.haal_uitspraak(url_nl)
    assert uitspraak is not None
    assert uitspraak.treffer.url == url_nl


def test_haal_uitspraak_weigert_vreemde_urls_geen_request():
    adapter = _mock_adapter(_verboden_handler)
    adapter.sta_fetch = True
    assert adapter.haal_uitspraak("https://www.dbrc.be/sites/default/files/x.pdf") is None
    assert adapter.haal_uitspraak("https://juportal.be/zoekmachine/zoekformulier") is None
    assert adapter.haal_uitspraak("https://evil.example/content/" + ECLI) is None


def test_haal_uitspraak_http_fout():
    adapter = _mock_adapter(lambda request: httpx.Response(500))
    adapter.sta_fetch = True
    assert adapter.haal_uitspraak(CONTENT_URL) is None


# ---------------------------------------------------------------------------------------
# Live smoke (optioneel)
# ---------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="alleen met RUN_LIVE=1")
def test_live_zoek_op_identifier():
    """Eén echte GET tegen juportal.be (bewuste keuze: sta_fetch=True). Vereist egress."""
    adapter = JuportalAdapter(rate_limit_s=1.0)
    adapter.sta_fetch = True
    try:
        treffers = adapter.zoek_op_identifier(ECLI)
    finally:
        adapter.close()
    assert treffers, "Geen treffer — check egress of gewijzigde paginastructuur"
    assert treffers[0].ecli == ECLI
    assert treffers[0].url == CONTENT_URL
