# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de Raad van State-adapter.

Twee soorten (patroon van test_dbrc.py):

* Offline (default): pure parser-/URL-logica op vaste fixtures, plus geïsoleerde
  adapter-tests met een httpx.MockTransport (geen echt netwerk).
* Live (marker `live`): één echte GET naar arr.php. Wordt overgeslagen tenzij
  `RUN_LIVE=1`. Let wel: robots.txt disallowt /arr.php (vondst 2026-08-03) — de
  live-test is een bewuste, eenmalige handmatige verificatie, geen crawling.

Fixtures (structuurgetrouw t.o.v. de echte arr.php-responsen van 2026-08-03):

* rvs_arrest_250123.pdf     — minimale PDF (zelfde openingsstructuur %PDF-1.4);
                              de echte respons was 116 kB `application/pdf` met
                              `Content-Disposition: inline; filename="250123.pdf"`.
* rvs_niet_gevonden.html    — letterlijke HTML-body bij een onbestaand nummer
                              (HTTP 200 + text/html!).
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from rechtspraak_mcp.adapters.raad_van_state import (
    RaadVanStateAdapter,
    arrest_deeplink,
    formatteer_arrestnummer,
    normaliseer_arrestnummer,
    parse_arrest_respons,
    zoek_deeplink,
)
from rechtspraak_mcp.schema import ZoekQuery

FIXTURES = Path(__file__).parent / "fixtures"
PDF_FIXTURE = (FIXTURES / "rvs_arrest_250123.pdf").read_bytes()
NIET_GEVONDEN_FIXTURE = (FIXTURES / "rvs_niet_gevonden.html").read_bytes()

ARR_URL_250123 = "https://www.raadvst-consetat.be/arr.php?nr=250123&l=nl"


# ---------------------------------------------------------------------------------------
# Pure functies (geen I/O)
# ---------------------------------------------------------------------------------------
def test_normaliseer_arrestnummer_varianten():
    assert normaliseer_arrestnummer("250.123") == "250123"
    assert normaliseer_arrestnummer("250123") == "250123"
    assert normaliseer_arrestnummer("nr. 250.123") == "250123"
    assert normaliseer_arrestnummer("nr 250123") == "250123"
    assert normaliseer_arrestnummer("RvS 250.123") == "250123"
    assert normaliseer_arrestnummer("  45.067 ") == "45067"  # ouder 5-cijferig nummer


def test_normaliseer_arrestnummer_ongeldig():
    assert normaliseer_arrestnummer("onzin") is None
    assert normaliseer_arrestnummer("") is None
    assert normaliseer_arrestnummer("12") is None  # te kort
    assert normaliseer_arrestnummer("1234567") is None  # te lang
    assert normaliseer_arrestnummer("RvVb-A-1920-0284") is None  # DBRC-nummer
    assert normaliseer_arrestnummer("ECLI:BE:RVSCE:2020:ARR.250123") is None  # ECLI


def test_formatteer_arrestnummer():
    assert formatteer_arrestnummer("250123") == "250.123"
    assert formatteer_arrestnummer("45067") == "45.067"


def test_arrest_deeplink():
    assert arrest_deeplink("250.123") == ARR_URL_250123
    assert arrest_deeplink("250123") == ARR_URL_250123
    with pytest.raises(ValueError):
        arrest_deeplink("geen nummer")


def test_zoek_deeplink():
    url = zoek_deeplink("stikstofdepositie")
    assert url.startswith("https://www.raadvst-consetat.be/?page=search&lang=nl")
    assert "q=stikstofdepositie" in url


def test_parse_arrest_respons_pdf():
    treffer = parse_arrest_respons("application/pdf", PDF_FIXTURE, "250123", ARR_URL_250123)
    assert treffer is not None
    assert treffer.bron == "raadvanstate"
    assert treffer.instantie == "Raad van State"
    assert treffer.rolnummer == "250.123"
    assert treffer.titel == "RvS-arrest nr. 250.123"
    assert treffer.url == ARR_URL_250123
    assert treffer.datum is None  # zit in de PDF; extractie is TODO


def test_parse_arrest_respons_pdf_zonder_content_type():
    # ook zonder (correct) Content-Type volstaat de %PDF-magic
    assert parse_arrest_respons("", PDF_FIXTURE, "250123", ARR_URL_250123) is not None


def test_parse_arrest_respons_niet_gevonden():
    # arr.php geeft óók HTTP 200 bij een onbestaand nummer, maar dan text/html:
    # dat mag nooit een Treffer opleveren (anti-hallucinatie).
    treffer = parse_arrest_respons(
        "text/html",
        NIET_GEVONDEN_FIXTURE,
        "999999",
        "https://www.raadvst-consetat.be/arr.php?nr=999999&l=nl",
    )
    assert treffer is None


def test_parse_arrest_respons_ongeldig_nummer():
    assert parse_arrest_respons("application/pdf", PDF_FIXTURE, "onzin", ARR_URL_250123) is None


# ---------------------------------------------------------------------------------------
# Adapter met MockTransport (geen echt netwerk)
# ---------------------------------------------------------------------------------------
def _mock_adapter(handler) -> RaadVanStateAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    # rate_limit_s=0 -> geen echte sleep in tests
    return RaadVanStateAdapter(client=client, rate_limit_s=0.0)


def _handler_verboden(request):  # pragma: no cover - mag niet aangeroepen worden
    raise AssertionError("Er mag geen request vertrekken zolang sta_fetch uit staat")


def test_vlag_uit_geen_requests():
    # standaard staat automatisch ophalen uit -> leeg resultaat, geen enkel request
    adapter = _mock_adapter(_handler_verboden)
    assert adapter.sta_fetch is False
    assert adapter.zoek_op_identifier("250.123") == []
    assert adapter.haal_uitspraak(ARR_URL_250123) is None
    assert adapter.zoek(ZoekQuery(query="stikstof")) == []


def test_zoek_altijd_leeg_ook_met_vlag_aan():
    # geen bruikbaar zoek-endpoint (JS-formulier + robots-disallow op page=caselaw)
    adapter = _mock_adapter(_handler_verboden)
    adapter.sta_fetch = True
    assert adapter.zoek(ZoekQuery(query="stikstof")) == []


def test_zoek_op_identifier_pdf_respons():
    def handler(request):
        assert request.url.path == "/arr.php"
        assert request.url.params.get("nr") == "250123"
        assert request.url.params.get("l") == "nl"
        return httpx.Response(
            200,
            headers={
                "content-type": "application/pdf",
                "content-disposition": 'inline; filename="250123.pdf"',
            },
            content=PDF_FIXTURE,
        )

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    treffers = adapter.zoek_op_identifier("250.123")
    assert len(treffers) == 1
    assert treffers[0].rolnummer == "250.123"
    assert treffers[0].url == ARR_URL_250123


def test_zoek_op_identifier_niet_gevonden():
    # geverifieerd randgeval: "niet gevonden" komt als HTTP 200 + text/html terug
    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "text/html"}, content=NIET_GEVONDEN_FIXTURE
        )

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier("999999") == []


def test_zoek_op_identifier_http_fout():
    adapter = _mock_adapter(lambda request: httpx.Response(500))
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier("250.123") == []


def test_zoek_op_identifier_ongeldig_nummer_geen_request():
    adapter = _mock_adapter(_handler_verboden)
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier("dit is geen nummer") == []
    assert adapter.zoek_op_identifier("RvVb-A-1920-0284") == []


def test_haal_uitspraak_pdf():
    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "application/pdf"}, content=PDF_FIXTURE
        )

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    uitspraak = adapter.haal_uitspraak(ARR_URL_250123)
    assert uitspraak is not None
    assert uitspraak.treffer.rolnummer == "250.123"
    # de fixture heeft een (minimale) tekstlaag; pdf_naar_tekst geeft die letterlijk terug
    assert "ARREST nr. 250.123" in uitspraak.tekst


def test_haal_uitspraak_niet_gevonden():
    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "text/html"}, content=NIET_GEVONDEN_FIXTURE
        )

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    assert adapter.haal_uitspraak("https://www.raadvst-consetat.be/arr.php?nr=999999&l=nl") is None


def test_haal_uitspraak_vreemde_url_geen_request():
    adapter = _mock_adapter(_handler_verboden)
    adapter.sta_fetch = True
    # geen arr.php-URL van de RvS -> geen request, None
    assert adapter.haal_uitspraak("https://voorbeeld.be/arr.php?nr=250123") is None
    assert adapter.haal_uitspraak("https://www.raadvst-consetat.be/index.php?nr=250123") is None
    assert adapter.haal_uitspraak("https://www.raadvst-consetat.be/arr.php?l=nl") is None


# ---------------------------------------------------------------------------------------
# Live smoke (optioneel)
# ---------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="alleen met RUN_LIVE=1")
def test_live_zoek_op_identifier():
    """Echte GET tegen arr.php. Vereist egress naar www.raadvst-consetat.be.

    Bewuste keuze: robots.txt disallowt /arr.php — dit is één handmatige
    verificatierequest (rate limit 10 s), geen crawling.
    """
    adapter = RaadVanStateAdapter()
    adapter.sta_fetch = True
    try:
        treffers = adapter.zoek_op_identifier("250.123")
    finally:
        adapter.close()
    assert treffers, "Geen treffer — check egress of arr.php-gedrag"
    assert treffers[0].url == ARR_URL_250123
