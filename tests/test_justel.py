# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de Justel-wetgevingsadapter (ejustice.just.fgov.be).

Twee soorten (zelfde opzet als test_juportal.py):

* Offline (default): pure numac-/ELI-logica en parsers op vaste fixtures
  (tests/fixtures/justel_eli_wet_depositogarantie.html — echte, ingekorte HTML van
  https://www.ejustice.just.fgov.be/eli/wet/2016/04/22/2016003166/justel, en
  tests/fixtures/justel_eli_help.html — de ELI-helppagina die ejustice bij een
  resultaatloze opzoeking toont; beide opgehaald 2026-08-09, ISO-8859-1), plus
  adaptertests met httpx.MockTransport (geen echt netwerk).
* Live (marker `live`): één echte GET naar ejustice.just.fgov.be. Wordt overgeslagen
  tenzij RUN_LIVE=1. Let op: robots.txt disallowt de /eli/-paden voor generieke bots —
  de live-test vergt dus een bewuste keuze (sta_fetch=True) en is enkel bedoeld als
  incidentele handmatige verificatie.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import httpx
import pytest

from rechtspraak_mcp.wetgeving.justel import (
    JustelAdapter,
    ZOEK_URL,
    decodeer_html,
    eli_deeplink,
    is_numac,
    parse_eli_pagina,
    parse_eli_url,
    parse_norm_tekst,
    zoek_deeplink,
)

NUMAC = "2016003166"
DATUM = date(2016, 4, 22)
ELI_URL = f"https://www.ejustice.just.fgov.be/eli/wet/2016/04/22/{NUMAC}/justel"

_FIXTURES = Path(__file__).parent / "fixtures"
# Bron is ISO-8859-1 (meta charset); bytes bewaren en via decodeer_html lezen,
# precies zoals de adapter dat met een echte respons doet.
FIXTURE_BYTES = (_FIXTURES / "justel_eli_wet_depositogarantie.html").read_bytes()
FIXTURE = decodeer_html(FIXTURE_BYTES)
HELP_BYTES = (_FIXTURES / "justel_eli_help.html").read_bytes()
HELP = decodeer_html(HELP_BYTES)


# ---------------------------------------------------------------------------------------
# Pure helpers: numac, deeplinks en ELI-URL-parsing
# ---------------------------------------------------------------------------------------
def test_is_numac():
    assert is_numac(NUMAC)
    assert is_numac(" 2016003166 ")  # trim
    assert is_numac("2016A03340")  # letter op positie 5 komt voor
    assert is_numac("2016a03340")  # hoofdletterongevoelig
    assert is_numac("1804032150")  # Burgerlijk Wetboek: oude jaartallen zijn plausibel
    # ongeldig
    assert not is_numac("2016")  # te kort
    assert not is_numac("20160031667")  # te lang
    assert not is_numac("A016003166")  # jaar geen 4 cijfers
    assert not is_numac("2016 03166")  # spatie
    assert not is_numac("9999003166")  # niet-plausibel jaar
    assert not is_numac("1492003166")  # voor 1789
    assert not is_numac("")


def test_eli_deeplink():
    assert eli_deeplink("wet", DATUM, NUMAC) == ELI_URL
    assert eli_deeplink("WET", DATUM, NUMAC) == ELI_URL  # type hoofdletterongevoelig
    # zero-padding van maand en dag
    assert (
        eli_deeplink("decreet", date(2014, 4, 25), "2014035516")
        == "https://www.ejustice.just.fgov.be/eli/decreet/2014/04/25/2014035516/justel"
    )
    # staatsblad-versie
    assert eli_deeplink("wet", DATUM, NUMAC, versie="staatsblad").endswith("/staatsblad")
    with pytest.raises(ValueError):
        eli_deeplink("kb", DATUM, NUMAC)  # geen geldig ELI-type
    with pytest.raises(ValueError):
        eli_deeplink("wet", DATUM, "onzin")  # geen numac
    with pytest.raises(ValueError):
        eli_deeplink("wet", DATUM, NUMAC, versie="pdf")  # geen geldige versie


def test_parse_eli_url():
    assert parse_eli_url(ELI_URL) == ("wet", DATUM, NUMAC)
    # zonder versie, met staatsblad-versie, http, zonder www, afsluitende slash
    assert parse_eli_url(ELI_URL.removesuffix("/justel")) == ("wet", DATUM, NUMAC)
    assert parse_eli_url(ELI_URL.replace("/justel", "/staatsblad")) == ("wet", DATUM, NUMAC)
    assert parse_eli_url(ELI_URL.replace("https://www.", "http://")) == ("wet", DATUM, NUMAC)
    assert parse_eli_url(ELI_URL + "/") == ("wet", DATUM, NUMAC)
    # ongeldig: lijst-URL zonder numac, vreemde host, vreemd type, onmogelijke datum,
    # cgi-pad, geen ELI
    assert parse_eli_url("https://www.ejustice.just.fgov.be/eli/wet/2016/04/22") is None
    assert parse_eli_url(f"https://evil.example/eli/wet/2016/04/22/{NUMAC}/justel") is None
    assert parse_eli_url(f"https://www.ejustice.just.fgov.be/eli/kb/2016/04/22/{NUMAC}") is None
    assert parse_eli_url(f"https://www.ejustice.just.fgov.be/eli/wet/2016/13/40/{NUMAC}") is None
    assert parse_eli_url("https://www.ejustice.just.fgov.be/cgi_loi/welcome.pl?language=nl") is None
    assert parse_eli_url("onzin") is None


def test_zoek_deeplink():
    # De query wordt bewust niet in de URL verwerkt (geen geverifieerde GET-vorm);
    # het resultaat is altijd het handmatig te openen zoekformulier.
    assert zoek_deeplink("milieueffectrapportage") == ZOEK_URL
    assert zoek_deeplink() == ZOEK_URL
    assert "ejustice.just.fgov.be" in ZOEK_URL


def test_decodeer_html_iso_8859_1():
    # De fixture declareert ISO-8859-1; letters met diakrieten moeten kloppen.
    assert 'charset="iso-8859-1"' in FIXTURE.lower() or "iso-8859-1" in FIXTURE.lower()
    assert "Financiën" in FIXTURE
    # zonder declaratie: geldige UTF-8 blijft UTF-8, rauwe latin-1 valt netjes terug
    assert decodeer_html("Financiën".encode("utf-8")) == "Financiën"
    assert decodeer_html("Financiën".encode("iso-8859-1")) == "Financiën"


# ---------------------------------------------------------------------------------------
# Pure parsers op de fixtures
# ---------------------------------------------------------------------------------------
def test_parse_eli_pagina_fixture():
    norm = parse_eli_pagina(FIXTURE, ELI_URL)
    assert norm is not None
    assert norm.bron == "justel"
    assert norm.type == "wet"
    assert norm.nummer == NUMAC
    assert norm.datum == DATUM  # uit de opschriftprefix "22 APRIL 2016. - "
    # opschrift zonder datumprefix (zo verwacht de VENA-bouwer het)
    assert norm.opschrift.startswith("Wet tot omzetting van richtlijn 2014/49/EU")
    assert "depositogarantiestelsels" in norm.opschrift
    assert "22 APRIL 2016" not in norm.opschrift
    # vindplaats uit het metadatablok ("Publicatie: 12 mei 2016")
    assert norm.vindplaats == "BS 12 mei 2016"
    # canonieke ELI-link van de pagina zelf (a#link-text)
    assert norm.eli == ELI_URL
    assert norm.url == ELI_URL


def test_parse_eli_pagina_helppagina_geen_norm():
    # De ELI-helppagina (HTTP 200 bij een resultaatloze opzoeking) is geen norm.
    assert parse_eli_pagina(HELP, ELI_URL) is None


def test_parse_eli_pagina_onherkenbaar_geen_norm():
    assert parse_eli_pagina("<html><body>oeps</body></html>", ELI_URL) is None
    assert parse_eli_pagina("", ELI_URL) is None


def test_parse_norm_tekst_fixture():
    tekst = parse_norm_tekst(FIXTURE)
    assert tekst.startswith("HOOFDSTUK 1.")
    assert "Artikel 1. Deze wet regelt een aangelegenheid" in tekst
    assert "artikel 74 van de Grondwet" in tekst
    # slot van de tekst (hoofdstuk 6) staat er ook in
    assert "Deze wet treedt in werking" in tekst
    # ISO-8859-1-tekens overleven de extractie ("1°", "2°")
    assert "1° artikel 10" in tekst
    # navigatie-chrome, kop en metadata horen niet in de tekst
    assert "Tekst" != tekst.split("\n", 1)[0]
    assert "Link kopiëren" not in tekst
    assert "Inhoudstafel" not in tekst
    assert "Publicatie" not in tekst


def test_parse_norm_tekst_zonder_tekstblok():
    assert parse_norm_tekst(HELP) == ""
    assert parse_norm_tekst("<html><body><p>niets</p></body></html>") == ""


# ---------------------------------------------------------------------------------------
# Adapter met MockTransport (geen echt netwerk)
# ---------------------------------------------------------------------------------------
def _mock_adapter(handler) -> JustelAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    # rate_limit_s=0 -> geen echte sleep in tests
    return JustelAdapter(client=client, rate_limit_s=0.0)


def _verboden_handler(request):  # pragma: no cover - mag niet aangeroepen worden
    raise AssertionError(f"onverwacht request naar {request.url}: sta_fetch staat uit")


def _fixture_handler(request):
    assert str(request.url) == ELI_URL
    # rauwe ISO-8859-1-bytes, zoals de bron ze levert (decodering is aan de adapter)
    return httpx.Response(200, content=FIXTURE_BYTES, headers={"Content-Type": "text/html"})


def test_fetch_staat_standaard_uit_geen_enkel_request():
    # robots.txt disallowt de wetgevingspaden -> standaard geen netwerk, lege resultaten
    adapter = _mock_adapter(_verboden_handler)
    assert adapter.sta_fetch is False
    assert adapter.zoek("omgevingsvergunning") == []
    assert adapter.zoek_op_identifier(ELI_URL) == []
    assert adapter.haal_norm(ELI_URL) is None


def test_zoek_altijd_leeg_ook_met_vlag_aan():
    # vrije-tekstzoeken loopt via het disallowde cgi-pad en is niet geautomatiseerd
    adapter = _mock_adapter(_verboden_handler)
    adapter.sta_fetch = True
    assert adapter.zoek("depositogarantie") == []


def test_zoek_op_identifier_eli_url_met_vlag_aan():
    adapter = _mock_adapter(_fixture_handler)
    adapter.sta_fetch = True
    normen = adapter.zoek_op_identifier(ELI_URL)
    assert len(normen) == 1
    n = normen[0]
    assert n.bron == "justel"
    assert n.type == "wet"
    assert n.nummer == NUMAC
    assert n.datum == DATUM
    assert n.vindplaats == "BS 12 mei 2016"
    assert n.url == ELI_URL


def test_zoek_op_identifier_normaliseert_naar_justel_versie():
    # staatsblad- of versieloze ELI-URL -> de structureel geverifieerde justel-versie
    adapter = _mock_adapter(_fixture_handler)
    adapter.sta_fetch = True
    for variant in (ELI_URL.replace("/justel", "/staatsblad"), ELI_URL.removesuffix("/justel")):
        normen = adapter.zoek_op_identifier(variant)
        assert len(normen) == 1
        assert normen[0].url == ELI_URL


def test_zoek_op_identifier_kaal_numac_geen_request():
    # gedocumenteerde beperking: zonder type en afkondigingsdatum geen ELI-URL, en de
    # omweg loopt via de disallowde zoekfunctie -> [], ook met de vlag aan
    adapter = _mock_adapter(_verboden_handler)
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier(NUMAC) == []
    assert adapter.zoek_op_identifier("2016A03340") == []
    assert adapter.zoek_op_identifier("onzin") == []


def test_zoek_op_identifier_http_fout():
    adapter = _mock_adapter(lambda request: httpx.Response(404))
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier(ELI_URL) == []


def test_zoek_op_identifier_helppagina_geen_verzonnen_norm():
    # HTTP 200 met de helppagina ("geen resultaat") -> geen norm
    adapter = _mock_adapter(
        lambda request: httpx.Response(200, content=HELP_BYTES, headers={"Content-Type": "text/html"})
    )
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier(ELI_URL) == []


def test_haal_norm_met_vlag_aan():
    adapter = _mock_adapter(_fixture_handler)
    adapter.sta_fetch = True
    resultaat = adapter.haal_norm(ELI_URL)
    assert resultaat is not None
    assert resultaat.norm.nummer == NUMAC
    assert resultaat.norm.type == "wet"
    assert "Artikel 1. Deze wet regelt een aangelegenheid" in resultaat.tekst
    assert "1° artikel 10" in resultaat.tekst  # ISO-8859-1 correct gedecodeerd ("°")


def test_haal_norm_weigert_vreemde_urls_geen_request():
    adapter = _mock_adapter(_verboden_handler)
    adapter.sta_fetch = True
    # geen ejustice-ELI-URL's: cgi-paden, PDF's, lijst-URL's, andere hosts
    assert adapter.haal_norm("https://www.ejustice.just.fgov.be/cgi_loi/welcome.pl?language=nl") is None
    assert adapter.haal_norm("https://www.ejustice.just.fgov.be/mopdf/2016/05/12_1.pdf") is None
    assert adapter.haal_norm("https://www.ejustice.just.fgov.be/eli/wet/2016/04/22") is None
    assert adapter.haal_norm(f"https://evil.example/eli/wet/2016/04/22/{NUMAC}/justel") is None
    assert adapter.haal_norm("https://eur-lex.europa.eu/eli/dir/2011/92/oj/nld") is None


def test_haal_norm_http_fout():
    adapter = _mock_adapter(lambda request: httpx.Response(500))
    adapter.sta_fetch = True
    assert adapter.haal_norm(ELI_URL) is None


# ---------------------------------------------------------------------------------------
# Live smoke (optioneel)
# ---------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="alleen met RUN_LIVE=1")
def test_live_zoek_op_identifier():
    """Eén echte GET tegen ejustice.just.fgov.be (bewuste keuze: sta_fetch=True)."""
    adapter = JustelAdapter(rate_limit_s=1.0)
    adapter.sta_fetch = True
    try:
        normen = adapter.zoek_op_identifier(ELI_URL)
    finally:
        adapter.close()
    assert normen, "Geen norm — check egress of gewijzigde paginastructuur"
    assert normen[0].nummer == NUMAC
    assert normen[0].url == ELI_URL
