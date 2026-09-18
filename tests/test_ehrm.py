# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de EHRM-adapter (HUDOC).

Zelfde opzet als test_dbrc.py:

* Offline (default): pure parsers (fixture `hudoc_query.json`, ingekorte maar echte
  API-respons van 2026-08-09), plus geïsoleerde adapter-tests met httpx.MockTransport.
* Live (marker `live`): één echte call naar de HUDOC-query-API. Alleen met RUN_LIVE=1.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import httpx
import pytest

from rechtspraak_mcp.adapters.ehrm import (
    API_URL,
    EhrmAdapter,
    document_deeplink,
    normaliseer_appno,
    normaliseer_ehrm_ecli,
    parse_query_json,
)
from rechtspraak_mcp.schema import ZoekQuery

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "hudoc_query.json").read_text(encoding="utf-8")
)

LAMBERT_ECLI = "ECLI:CE:ECHR:2015:0605JUD004604314"


# ---------------------------------------------------------------------------------------
# Pure functies
# ---------------------------------------------------------------------------------------
def test_normaliseer_ehrm_ecli():
    assert normaliseer_ehrm_ecli(LAMBERT_ECLI) == LAMBERT_ECLI
    # whitespace en kleine letters worden genormaliseerd
    assert normaliseer_ehrm_ecli("  ecli:ce:echr:2015:0605jud004604314 ") == LAMBERT_ECLI
    # ook beslissingen (DEC) passen in het patroon
    assert normaliseer_ehrm_ecli("ECLI:CE:ECHR:2020:0101DEC001234567") is not None
    # geen EHRM-ECLI's
    assert normaliseer_ehrm_ecli("ECLI:BE:RVSCDE:2020:ARR.247.234") is None
    assert normaliseer_ehrm_ecli("ECLI:EU:C:2018:882") is None
    assert normaliseer_ehrm_ecli("onzin") is None
    assert normaliseer_ehrm_ecli("") is None


def test_normaliseer_appno():
    assert normaliseer_appno("46043/14") == "46043/14"
    assert normaliseer_appno("  46043/14  ") == "46043/14"
    assert normaliseer_appno("34068/21") == "34068/21"
    # geen zaaknummers
    assert normaliseer_appno("RvVb-A-1920-0284") is None
    assert normaliseer_appno(LAMBERT_ECLI) is None
    assert normaliseer_appno("46043/2014") is None  # jaartal is tweecijferig
    assert normaliseer_appno("") is None


def test_document_deeplink():
    assert document_deeplink("001-155352") == "https://hudoc.echr.coe.int/eng?i=001-155352"


def test_parse_query_json_fixture():
    """Fixture: 8 documenten (2 zaken) -> 2 unieke treffers, primair arrest gekozen."""
    treffers = parse_query_json(FIXTURE)
    assert len(treffers) == 2

    lambert = [t for t in treffers if t.ecli == LAMBERT_ECLI]
    assert len(lambert) == 1, "vertalingen/samenvattingen moeten naar 1 treffer dedupliceren"
    t = lambert[0]
    assert t.bron == "ehrm"
    assert t.instantie == "Europees Hof voor de Rechten van de Mens"
    # het Engelse origineel (HEJUD, itemid 001-155352) wint van HFJUD en vertalingen
    assert t.url == "https://hudoc.echr.coe.int/eng?i=001-155352"
    assert t.titel == "CASE OF LAMBERT AND OTHERS v. FRANCE"
    assert t.rolnummer == "46043/14"
    assert t.datum == date(2015, 6, 5)  # uit kpdate "2015-06-05T00:00:00"
    assert t.snippet and "Preliminary objection allowed" in t.snippet

    # tweede zaak (Greenpeace Nordic) blijft een eigen treffer
    greenpeace = [t for t in treffers if t.ecli == "ECLI:CE:ECHR:2025:1028JUD003406821"]
    assert len(greenpeace) == 1
    assert greenpeace[0].rolnummer == "34068/21"
    assert greenpeace[0].datum == date(2025, 10, 28)

    # de communicated-kennisgeving (HFCOM, 2014, zonder ECLI) is géén treffer
    assert all(t.datum != date(2014, 6, 24) for t in treffers)


def test_parse_query_json_vertaling_als_primair():
    """Zonder origineel arrest wint de best gerangschikte vertaling, met geschoonde titel."""
    data = {
        "resultcount": 2,
        "results": [
            {
                "columns": {
                    "doctype": "HJUDHRV",
                    "itemid": "001-165685",
                    "docname": (
                        "CASE OF LAMBERT AND OTHERS v. FRANCE - [Croatian Translation] "
                        "summary by the Republic of Croatia (Office of the Agent) "
                    ),
                    "appno": "46043/14",
                    "ecli": LAMBERT_ECLI,
                    "kpdate": "2015-06-05T00:00:00",
                    "conclusion": "",
                    "article": "2;2-1;34;35",
                }
            },
            {
                "columns": {
                    "doctype": "CLIN",
                    "itemid": "002-10758",
                    "docname": "Lambert and Others v. France [GC]",
                    "appno": "46043/14",
                    "ecli": "",
                    "kpdate": "2015-06-05T00:00:00",
                    "conclusion": "Preliminary objection allowed",
                    "article": "2",
                }
            },
        ],
    }
    treffers = parse_query_json(data)
    assert len(treffers) == 1
    assert treffers[0].titel == "CASE OF LAMBERT AND OTHERS v. FRANCE"  # suffix afgeknipt
    # zonder conclusion valt de snippet terug op de artikelen
    assert treffers[0].snippet == "Artikel(en): 2;2-1;34;35"


def test_parse_query_json_leeg():
    assert parse_query_json({}) == []
    assert parse_query_json({"resultcount": 0, "results": []}) == []


# ---------------------------------------------------------------------------------------
# Adapter met MockTransport (geen echt netwerk)
# ---------------------------------------------------------------------------------------
def _mock_adapter(handler, *, sta_fetch: bool = False) -> EhrmAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    adapter = EhrmAdapter(client=client, rate_limit_s=0.0)  # geen echte sleep in tests
    adapter.sta_fetch = sta_fetch
    return adapter


def _fixture_handler(request):
    assert request.url.path == "/app/query/results"
    return httpx.Response(200, json=FIXTURE)


def test_zoek_op_identifier_default_uit():
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("sta_fetch staat uit: er mag geen request vertrekken")

    adapter = _mock_adapter(handler)
    assert adapter.zoek_op_identifier("46043/14") == []
    assert adapter.zoek_op_identifier(LAMBERT_ECLI) == []


def test_zoek_default_uit():
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("sta_fetch staat uit: er mag geen request vertrekken")

    adapter = _mock_adapter(handler)
    assert adapter.zoek(ZoekQuery(query="euthanasie")) == []


def test_zoek_op_identifier_appno():
    def handler(request):
        assert request.url.path == "/app/query/results"
        assert '(appno:"46043/14")' in request.url.params.get("query", "")
        return httpx.Response(200, json=FIXTURE)

    adapter = _mock_adapter(handler, sta_fetch=True)
    treffers = adapter.zoek_op_identifier("46043/14")
    assert len(treffers) == 2  # fixture bevat 2 zaken; dedup over de vertalingen heen
    assert treffers[0].ecli == LAMBERT_ECLI


def test_zoek_op_identifier_ecli():
    def handler(request):
        assert f'(ecli:"{LAMBERT_ECLI}")' in request.url.params.get("query", "")
        return httpx.Response(200, json=FIXTURE)

    adapter = _mock_adapter(handler, sta_fetch=True)
    # kleine letters worden vóór de query genormaliseerd
    treffers = adapter.zoek_op_identifier(LAMBERT_ECLI.lower())
    assert treffers and treffers[0].url == "https://hudoc.echr.coe.int/eng?i=001-155352"


def test_zoek_op_identifier_ongeldige_input():
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("ongeldige identifier mag geen request opleveren")

    adapter = _mock_adapter(handler, sta_fetch=True)
    assert adapter.zoek_op_identifier("RvVb-A-1920-0284") == []
    assert adapter.zoek_op_identifier("dit is geen nummer") == []


def test_zoek_met_fetch_aan():
    def handler(request):
        q = request.url.params.get("query", "")
        assert "contentsitename=ECHR" in q  # portaal-basisfilter
        assert '(("climate change"))' in q  # vrije tekst als frase
        assert 'doctype="HEJUD"' in q  # beperkt tot originele arresten
        return httpx.Response(200, json=FIXTURE)

    adapter = _mock_adapter(handler, sta_fetch=True)
    treffers = adapter.zoek(ZoekQuery(query="climate change", max_resultaten=1))
    assert len(treffers) == 1  # max_resultaten gerespecteerd (fixture geeft er 2)


def test_zoek_datumfilter_clientside():
    adapter = _mock_adapter(_fixture_handler, sta_fetch=True)
    treffers = adapter.zoek(ZoekQuery(query="x", datum_van=date(2020, 1, 1)))
    assert [t.rolnummer for t in treffers] == ["34068/21"]  # Lambert (2015) weggefilterd


def test_zoek_api_fout_geeft_lege_lijst():
    adapter = _mock_adapter(lambda request: httpx.Response(500), sta_fetch=True)
    assert adapter.zoek(ZoekQuery(query="x")) == []
    assert adapter.zoek_op_identifier("46043/14") == []


def test_haal_uitspraak_default_uit():
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("sta_fetch staat uit: er mag geen request vertrekken")

    adapter = _mock_adapter(handler)
    uitspraak = adapter.haal_uitspraak("https://hudoc.echr.coe.int/eng?i=001-155352")
    assert uitspraak is not None
    assert uitspraak.treffer.url == "https://hudoc.echr.coe.int/eng?i=001-155352"
    # eerlijke notitie, geen verzonnen tekst
    assert "raadpleeg de bron-URL" in uitspraak.tekst


def test_haal_uitspraak_met_fetch():
    body_html = (
        "<style>.s1 { font-size:12pt }</style>"
        "<p class='s1'>PROCEDURE</p><p>1. The case originated in an application "
        "(no. 46043/14) against the French Republic.</p>"
    )

    def handler(request):
        assert request.url.path == "/app/conversion/docx/html/body"
        assert request.url.params.get("library") == "ECHR"
        assert request.url.params.get("id") == "001-155352"
        return httpx.Response(200, text=body_html)

    adapter = _mock_adapter(handler, sta_fetch=True)
    uitspraak = adapter.haal_uitspraak("https://hudoc.echr.coe.int/eng?i=001-155352")
    assert uitspraak is not None
    assert "PROCEDURE" in uitspraak.tekst
    assert "46043/14" in uitspraak.tekst
    assert "font-size" not in uitspraak.tekst  # <style>-blok is gestript


def test_haal_uitspraak_ongeldige_url():
    adapter = _mock_adapter(lambda request: httpx.Response(200), sta_fetch=True)
    assert adapter.haal_uitspraak("https://example.com/eng?i=001-155352") is None
    assert adapter.haal_uitspraak("https://www.dbrc.be/sites/default/files/x.pdf") is None
    assert adapter.haal_uitspraak("") is None


def test_haal_uitspraak_http_fout_geeft_notitie():
    adapter = _mock_adapter(lambda request: httpx.Response(500), sta_fetch=True)
    uitspraak = adapter.haal_uitspraak("https://hudoc.echr.coe.int/eng?i=001-155352")
    assert uitspraak is not None
    assert "raadpleeg de bron-URL" in uitspraak.tekst


# ---------------------------------------------------------------------------------------
# Live smoke (optioneel)
# ---------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="alleen met RUN_LIVE=1")
def test_live_zoek_op_identifier():
    """Echte call naar de HUDOC-query-API. Vereist egress naar hudoc.echr.coe.int."""
    adapter = EhrmAdapter(rate_limit_s=5.0)
    adapter.sta_fetch = True
    try:
        treffers = adapter.zoek_op_identifier("46043/14")
    finally:
        adapter.close()
    assert treffers, "Geen treffer — check egress naar hudoc.echr.coe.int"
    assert any(t.ecli == LAMBERT_ECLI for t in treffers)
    assert all(t.url.startswith("https://hudoc.echr.coe.int/eng?i=") for t in treffers)


def test_hudoc_botcontrole_stopt_meteen_en_zet_de_vlag():
    # Cloudflare-challenge (403 + cf-mitigated): niet opnieuw proberen, wel melden.
    teller = {"n": 0}

    def handler(request):
        teller["n"] += 1
        return httpx.Response(403, headers={"cf-mitigated": "challenge"}, text="Just a moment...")

    adapter = _mock_adapter(handler)
    adapter.sta_fetch = True
    assert adapter.zoek(ZoekQuery(query="climate change")) == []
    assert teller["n"] == 1
    assert adapter.laatste_botcontrole is True


def test_server_meldt_hudoc_botcontrole():
    from rechtspraak_mcp.server import _leg_lege_identifier_uit

    r = _leg_lege_identifier_uit("53600/20", botcontrole=True)
    assert "HUDOC" in r.melding and "botcontrole" in r.melding
