# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de PDF-tekstextractie (rechtspraak_mcp/pdf_tekst.py).

Volledig offline: extractie op de vaste fixture tests/fixtures/arrest_dummy.pdf
(twee pagina's neptekst mét tekstlaag; géén echte arresttekst i.v.m. auteursrecht),
robuustheid op corrupte invoer, en per adapter één integratietest via
httpx.MockTransport (patroon van test_dbrc.py / test_raad_van_state.py).
"""
from __future__ import annotations

from pathlib import Path

import httpx

from rechtspraak_mcp.adapters.dbrc import DbrcAdapter
from rechtspraak_mcp.adapters.raad_van_state import RaadVanStateAdapter
from rechtspraak_mcp.pdf_tekst import pdf_naar_tekst

FIXTURES = Path(__file__).parent / "fixtures"
DUMMY_PDF = (FIXTURES / "arrest_dummy.pdf").read_bytes()

DUMMY_REGEL = "RvVb-A-2223-0431 - dummy-arresttekst voor tests"


# ---------------------------------------------------------------------------------------
# pdf_naar_tekst (puur, geen I/O)
# ---------------------------------------------------------------------------------------
def test_pdf_naar_tekst_extraheert_beide_paginas():
    tekst = pdf_naar_tekst(DUMMY_PDF)
    assert tekst is not None
    assert DUMMY_REGEL in tekst
    assert "Tweede pagina van de dummy-fixture." in tekst
    # pagina's gescheiden door een lege regel; pagina 1 vóór pagina 2
    assert tekst.index(DUMMY_REGEL) < tekst.index("\n\nTweede pagina")


def test_pdf_naar_tekst_letterlijke_brontekst():
    # anti-hallucinatie: de geëxtraheerde regel is letterlijk de brontekst
    tekst = pdf_naar_tekst(DUMMY_PDF)
    assert any(regel == DUMMY_REGEL for regel in tekst.splitlines())


def test_pdf_naar_tekst_corrupte_pdf_geeft_none():
    assert pdf_naar_tekst(b"%PDF-1.4 garbage") is None


def test_pdf_naar_tekst_geen_pdf_geeft_none():
    assert pdf_naar_tekst(b"geen pdf") is None


def test_pdf_naar_tekst_lege_bytes_geeft_none():
    assert pdf_naar_tekst(b"") is None


# ---------------------------------------------------------------------------------------
# Adapter-integratie met MockTransport (geen echt netwerk)
# ---------------------------------------------------------------------------------------
def _pdf_handler(request):
    return httpx.Response(
        200, headers={"content-type": "application/pdf"}, content=DUMMY_PDF
    )


def test_dbrc_haal_uitspraak_extraheert_tekst():
    client = httpx.Client(transport=httpx.MockTransport(_pdf_handler), follow_redirects=True)
    adapter = DbrcAdapter(client=client, rate_limit_s=0.0)
    url = "https://www.dbrc.be/sites/default/files/2023-04/RVVB.A.2223.0431.pdf"
    uitspraak = adapter.haal_uitspraak(url)
    assert uitspraak is not None
    assert uitspraak.treffer.url == url
    assert DUMMY_REGEL in uitspraak.tekst
    assert "mislukte" not in uitspraak.tekst  # geen fallback-notitie bij geslaagde extractie


def test_rvs_haal_uitspraak_extraheert_tekst():
    client = httpx.Client(transport=httpx.MockTransport(_pdf_handler), follow_redirects=True)
    adapter = RaadVanStateAdapter(client=client, rate_limit_s=0.0)
    adapter.sta_fetch = True  # bewust aangezet voor de test (zie module-docstring adapter)
    uitspraak = adapter.haal_uitspraak("https://www.raadvst-consetat.be/arr.php?nr=250123&l=nl")
    assert uitspraak is not None
    assert uitspraak.treffer.rolnummer == "250.123"
    assert DUMMY_REGEL in uitspraak.tekst
    assert "mislukte" not in uitspraak.tekst


def test_dbrc_haal_uitspraak_fallback_bij_mislukte_extractie():
    # PDF-respons zonder leesbare inhoud -> eerlijke notitie, geen verzonnen tekst
    kapot = b"%PDF-1.4 garbage"

    def handler(request):
        return httpx.Response(
            200, headers={"content-type": "application/pdf"}, content=kapot
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    adapter = DbrcAdapter(client=client, rate_limit_s=0.0)
    uitspraak = adapter.haal_uitspraak(
        "https://www.dbrc.be/sites/default/files/2023-04/RVVB.A.2223.0431.pdf"
    )
    assert uitspraak is not None
    assert f"({len(kapot)} bytes)" in uitspraak.tekst
    assert "tekstextractie mislukte" in uitspraak.tekst
