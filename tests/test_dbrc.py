# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de DBRC-adapter.

Twee soorten:

* Offline (default): parser- en URL-logica, plus geïsoleerde adapter-tests met een
  httpx.MockTransport (geen echt netwerk). Draaien overal, ook in een afgeschermde sandbox.
* Live (marker `live`): één echte HEAD-request naar dbrc.be om de PDF-URL te bevestigen.
  Wordt overgeslagen tenzij `RUN_LIVE=1`. In een sandbox met egress-allowlist zal deze
  falen/oversgeslagen worden — dat is verwacht (zie het rapport).

Draaien:
    pip install httpx beautifulsoup4 pydantic pytest
    PYTHONPATH=.. python -m pytest -v            # offline
    RUN_LIVE=1 PYTHONPATH=.. python -m pytest -v -m live   # ook live
"""
from __future__ import annotations

import math
import os
from datetime import date
from pathlib import Path

import httpx
import pytest

from rechtspraak_mcp.adapters.dbrc import (
    DbrcAdapter,
    _pdf_kandidaten,
    parse_arrestnummer,
    parse_filename,
    parse_zoekresultaten,
    zoek_deeplink,
)
from rechtspraak_mcp.schema import ZoekQuery

FIXTURE = (Path(__file__).parent / "fixtures" / "dbrc_zoekresultaten.html").read_text()


# ---------------------------------------------------------------------------------------
# Pure parsers
# ---------------------------------------------------------------------------------------
def test_parse_arrestnummer_varianten():
    aid = parse_arrestnummer("RvVb-A-1920-0284")
    assert aid is not None
    assert aid.college == "RVVB"
    assert aid.type == "A"
    assert aid.werkjaar == "1920"
    assert aid.nummer == "0284"
    assert aid.basename == "RVVB.A.1920.0284"
    assert aid.arrestnummer == "RvVb-A-1920-0284"
    assert aid.instantie == "Raad voor Vergunningsbetwistingen"

    assert parse_arrestnummer("RvVb-UDN-2526-0627").basename == "RVVB.UDN.2526.0627"
    assert parse_arrestnummer("HHC-A-2324-0012").college == "HHC"
    assert parse_arrestnummer("R.Verkb-A-2021-0003").college == "RVERKB"
    assert parse_arrestnummer("onzin") is None


def test_parse_filename():
    aid = parse_filename("https://www.dbrc.be/sites/default/files/2021-08/RVVB.A.1920.0284_0.pdf")
    assert aid is not None
    assert aid.basename == "RVVB.A.1920.0284"
    assert aid.arrestnummer == "RvVb-A-1920-0284"
    # footer-PDF is geen arrest
    assert parse_filename("/sites/default/files/2022-03/toegankelijkheidsverklaring.pdf") is None


def test_zoek_deeplink():
    url = zoek_deeplink("zonevreemde woning")
    assert url.startswith("https://www.dbrc.be/rechtspraak?")
    assert "search_api_fulltext=zonevreemde+woning" in url


def test_parse_zoekresultaten_fixture():
    treffers = parse_zoekresultaten(FIXTURE)
    # 3 echte arresten; de toegankelijkheidsverklaring is uitgefilterd
    assert len(treffers) == 3
    eerste = treffers[0]
    assert eerste.bron == "dbrc"
    assert eerste.rolnummer == "RvVb-UDN-2526-0608"
    assert eerste.instantie == "Raad voor Vergunningsbetwistingen"
    assert eerste.url.endswith("/2026-04/RVVB.UDN.2526.0608.pdf")
    assert eerste.datum is None  # niet aanwezig in de overzichtslijst
    # HHC-rij correct genormaliseerd
    hhc = [t for t in treffers if t.rolnummer == "HHC-A-2324-0012"]
    assert hhc and hhc[0].instantie == "Handhavingscollege"


# ---------------------------------------------------------------------------------------
# Adapter met MockTransport (geen echt netwerk)
# ---------------------------------------------------------------------------------------
def _mock_adapter(handler) -> DbrcAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    # rate_limit_s=0 -> geen echte sleep in tests
    return DbrcAdapter(client=client, rate_limit_s=0.0)


def test_zoek_uit_wegens_robots():
    # standaard staat scraping uit -> lege lijst, geen enkel request
    def handler(request):  # pragma: no cover - mag niet aangeroepen worden
        raise AssertionError("zoek() mag het verboden endpoint niet aanroepen als scraping uit staat")

    adapter = _mock_adapter(handler)
    assert adapter.zoek(ZoekQuery(query="test")) == []


def test_zoek_met_scraping_aan():
    def handler(request):
        assert request.url.path == "/rechtspraak"
        assert request.url.params.get("search_api_fulltext") == "zonevreemde woning"
        return httpx.Response(200, text=FIXTURE)

    adapter = _mock_adapter(handler)
    adapter.sta_zoek_scraping = True
    treffers = adapter.zoek(ZoekQuery(query="zonevreemde woning", max_resultaten=2))
    assert len(treffers) == 2  # max_resultaten gerespecteerd
    assert treffers[0].bron == "dbrc"


def test_zoek_op_identifier_head_probe():
    # recent arrest -> publicatiemaand valt binnen het standaard maandvenster
    goede_url = "https://www.dbrc.be/sites/default/files/2026-04/RVVB.UDN.2526.0608.pdf"

    def handler(request):
        # alleen de juiste PDF-URL bestaat; al de rest 404
        if request.method == "HEAD" and str(request.url) == goede_url:
            return httpx.Response(200)
        return httpx.Response(404)

    adapter = _mock_adapter(handler)
    treffers = adapter.zoek_op_identifier("RvVb-UDN-2526-0608")
    assert len(treffers) == 1
    assert treffers[0].url == goede_url
    assert treffers[0].rolnummer == "RvVb-UDN-2526-0608"


def test_zoek_op_identifier_late_publicatie_buiten_venster():
    # RvVb-A-1920-0284 werd pas 2021-08 gepubliceerd: buiten het standaardvenster -> niet
    # gevonden (gedocumenteerde [BEPERKING]). Met datum-anker of ruim venster lukt het wel.
    goede_url = "https://www.dbrc.be/sites/default/files/2021-08/RVVB.A.1920.0284_0.pdf"

    def handler(request):
        if request.method == "HEAD" and str(request.url) == goede_url:
            return httpx.Response(200)
        return httpx.Response(404)

    adapter = _mock_adapter(handler)
    # standaardvenster -> niet gevonden
    assert adapter.zoek_op_identifier("RvVb-A-1920-0284") == []
    # met datum-anker (uitspraak 16 juli 2019 -> publicatie ~2 jaar later) toch gevonden
    treffers = adapter.zoek_op_identifier(
        "RvVb-A-1920-0284", datum=date(2019, 7, 16), venster_maanden=30
    )
    assert len(treffers) == 1
    assert treffers[0].url == goede_url


def test_zoek_op_identifier_niet_gevonden():
    adapter = _mock_adapter(lambda request: httpx.Response(404))
    assert adapter.zoek_op_identifier("RvVb-A-2526-9999") == []


def test_zoek_op_identifier_ongeldige_input():
    adapter = _mock_adapter(lambda request: httpx.Response(200))
    assert adapter.zoek_op_identifier("dit is geen nummer") == []


# ---------------------------------------------------------------------------------------
# Live smoke (optioneel)
# ---------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="alleen met RUN_LIVE=1")
def test_live_zoek_op_identifier():
    """Echte HEAD tegen dbrc.be. Vereist egress naar www.dbrc.be."""
    adapter = DbrcAdapter(rate_limit_s=1.0)
    try:
        # recent UDN-arrest: publicatiemaand valt binnen het standaardvenster
        treffers = adapter.zoek_op_identifier("RvVb-UDN-2526-0608")
    finally:
        adapter.close()
    assert treffers, "Geen treffer — check egress/robots of publicatiemaand-venster"
    assert treffers[0].url.endswith("RVVB.UDN.2526.0608.pdf")


# ---------------------------------------------------------------------------------------
# Kandidaatvolgorde en tijdsbudget
# ---------------------------------------------------------------------------------------
def test_kandidaten_eerst_alle_maanden_zonder_suffix():
    # Bewust niet geïnterleaved: de kale bestandsnaam is het gewone geval, dus die maanden
    # gaan eerst. Interleaven verdubbelde het aantal probes voor gewone arresten (live
    # gemeten op RvVb-A-2425-0744: 10 -> 19 pogingen à 10 s).
    aid = parse_arrestnummer("RvVb-A-2425-0744")
    urls = _pdf_kandidaten(aid, anchor=date(2025, 4, 1), venster_maanden=2)
    assert urls == [
        "https://www.dbrc.be/sites/default/files/2025-03/RVVB.A.2425.0744.pdf",
        "https://www.dbrc.be/sites/default/files/2025-04/RVVB.A.2425.0744.pdf",
        "https://www.dbrc.be/sites/default/files/2025-05/RVVB.A.2425.0744.pdf",
        "https://www.dbrc.be/sites/default/files/2025-03/RVVB.A.2425.0744_0.pdf",
        "https://www.dbrc.be/sites/default/files/2025-04/RVVB.A.2425.0744_0.pdf",
        "https://www.dbrc.be/sites/default/files/2025-05/RVVB.A.2425.0744_0.pdf",
    ]


def test_zoek_op_identifier_stopt_op_tijdsbudget():
    # Alles 404: zonder budget zou de adapter het hele venster afgaan. Met een budget van 0
    # loopt enkel de eerste probe, en meldt de vlag dat er is afgebroken — zodat de server
    # "niet gevonden" niet als "bestaat niet" presenteert.
    pogingen: list[str] = []

    def handler(request):
        pogingen.append(str(request.url))
        return httpx.Response(404)

    adapter = _mock_adapter(handler)
    assert adapter.zoek_op_identifier("RvVb-A-2526-0001", tijdsbudget_s=0.0) == []
    assert len(pogingen) == 1
    assert adapter.laatste_zoektocht_afgebroken is True


def test_zoek_op_identifier_zonder_budget_gaat_het_venster_af():
    pogingen: list[str] = []

    def handler(request):
        pogingen.append(str(request.url))
        return httpx.Response(404)

    adapter = _mock_adapter(handler)
    assert adapter.zoek_op_identifier("RvVb-A-2526-0001", tijdsbudget_s=math.inf) == []
    assert len(pogingen) == len(
        _pdf_kandidaten(parse_arrestnummer("RvVb-A-2526-0001"), anchor=None)
    )
    assert adapter.laatste_zoektocht_afgebroken is False


def test_treffer_binnen_budget_zet_de_vlag_niet():
    goede_url = "https://www.dbrc.be/sites/default/files/2026-04/RVVB.UDN.2526.0608.pdf"

    def handler(request):
        return httpx.Response(200 if str(request.url) == goede_url else 404)

    adapter = _mock_adapter(handler)
    treffers = adapter.zoek_op_identifier("RvVb-UDN-2526-0608", datum=date(2026, 4, 15))
    assert len(treffers) == 1 and treffers[0].url == goede_url
    assert adapter.laatste_zoektocht_afgebroken is False
