# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor het zoeken op titelwoorden in EU-wetgeving (wetgeving/eurlex_zoek.py, via CELLAR)."""
from __future__ import annotations

import os
from datetime import date

import httpx
import pytest

from cellar_nep import cellar_met, nep_cellar
from rechtspraak_mcp.wetgeving.eurlex_zoek import EurlexZoeker, norm_uit_zoekrij


def test_norm_uit_zoekrij():
    n = norm_uit_zoekrij({"celex": "32014L0052", "datum": "2014-04-16", "titel_nl": "Richtlijn 2014/52/EU van ..."})
    assert (n.type, n.nummer, n.datum) == ("richtlijn", "2014/52/EU", date(2014, 4, 16))
    assert n.url.endswith("uri=CELEX:32014L0052")
    assert norm_uit_zoekrij({"celex": "62002CJ0127", "titel_nl": "Arrest"}) is None
    assert norm_uit_zoekrij({"celex": "32014L0052"}) is None


def test_zoeker_vindt_de_mer_richtlijnen():
    verzoeken: list[httpx.Request] = []
    normen = EurlexZoeker(cellar=nep_cellar(verzoeken)).zoek("milieueffectbeoordeling", max_resultaten=5)
    assert [n.celex for n in normen] == ["32014L0052", "32011L0092"]
    assert "bif:contains" in verzoeken[0].url.params["query"]


def test_zoeker_lege_of_onbruikbare_query_geen_request():
    verzoeken: list[httpx.Request] = []
    z = EurlexZoeker(cellar=nep_cellar(verzoeken))
    assert z.zoek("   ") == []
    assert z.zoek("a b") == []
    assert verzoeken == []


def test_zoeker_serverfout_geeft_lege_lijst():
    assert EurlexZoeker(cellar=cellar_met(lambda r: httpx.Response(500))).zoek("habitats") == []


def test_zoeker_botcontrole_zet_de_vlag():
    z = EurlexZoeker(cellar=cellar_met(lambda r: httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})))
    assert z.zoek("habitats") == []
    assert z.laatste_botcontrole is True


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("RUN_LIVE"), reason="live test; zet RUN_LIVE=1")
def test_live_zoek():
    z = EurlexZoeker()
    try:
        normen = z.zoek("natuurherstel", max_resultaten=5)
    finally:
        z.close()
    assert any(n.celex == "32024R1991" for n in normen)
