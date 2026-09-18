# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor rechtspraak_mcp/cellar.py: pure functies en de client met nep-CELLAR (geen netwerk).

Live-smoke achter RUN_LIVE=1.
"""
from __future__ import annotations

import os

import httpx
import pytest

from rechtspraak_mcp import cellar as C
from cellar_nep import cellar_met, lees, nep_cellar


# -- pure functies ---------------------------------------------------------------------------
def test_queries_weigeren_onveilige_invoer():
    with pytest.raises(ValueError):
        C.query_arrest_op_ecli('ECLI:EU:C:2004:482" } DROP')
    with pytest.raises(ValueError):
        C.query_werk_op_celex("32011L0092\"")
    with pytest.raises(ValueError):
        C.query_zoek_wetgeving(["milieu'"], 5)


def test_zoekwoorden_zijn_veilig_en_beperkt():
    assert C.zoekwoorden('habitats "; DROP } wilde-flora ok') == ["habitats", "DROP", "wilde-flora"]
    assert C.zoekwoorden("a b") == []


def test_query_zoek_wetgeving_vorm():
    q = C.query_zoek_wetgeving(["milieueffectbeoordeling", "projecten"], 500)
    assert "bif:contains \"'milieueffectbeoordeling' AND 'projecten'\"" in q
    assert "LIMIT 100" in q  # begrensd


@pytest.mark.parametrize(
    ("oj_id", "oj_datum", "verwacht"),
    [
        ("oj:JOL_2012_026_R_0001_01", "2012-01-28", "Pb.L. 28 januari 2012, 1"),
        ("oj:JOL_1992_206_R_0007_01", "1992-07-22", "Pb.L. 22 juli 1992, 7"),
        ("oj:JOC_2006_331_R_0009_01", "2006-12-30", "Pb.C. 30 december 2006, 9"),
        ("oj:L_202401991", "2024-07-29", "Pb.L. 29 juli 2024"),
        ("oj:JOL_2012_026_R_0001_01", None, None),  # zonder datum geen VENA-vindplaats
        (None, "2012-01-28", None),
        ("oj:iets-anders", None, None),
    ],
)
def test_pb_vindplaats(oj_id, oj_datum, verwacht):
    assert C.pb_vindplaats(oj_id, oj_datum) == verwacht


def test_html_naar_tekst_houdt_inline_opmaak_in_de_zin():
    html = "<html><head><title>x</title></head><body><p>Zaak <span>C‑127/02</span> en <em>meer</em></p><p>Tweede</p></body></html>"
    assert C.html_naar_tekst(html) == "Zaak C‑127/02 en meer\nTweede"


def test_kies_titel_en_rechtspraak_celex():
    assert C.kies_titel({"titel_nl": "NL", "titel_en": "EN"}) == ("NL", "nl")
    assert C.kies_titel({"titel_en": "EN"}) == ("EN", "en")
    assert C.kies_titel({}) is None
    rijen = [{"celex": "62002CJ0127(SUM)"}, {"celex": "62002CJ0127"}]
    assert C.kies_rechtspraak_celex(rijen)["celex"] == "62002CJ0127"


# -- client ----------------------------------------------------------------------------------
def test_arrest_op_ecli_via_sparql():
    verzoeken: list[httpx.Request] = []
    rij = nep_cellar(verzoeken).arrest_op_ecli("ECLI:EU:C:2004:482")
    assert rij["celex"] == "62002CJ0127"
    assert rij["datum"] == "2004-09-07"
    assert rij["titel_nl"].startswith("Arrest van het Hof (grote kamer) van 7 september 2004.#")
    assert verzoeken[0].headers["accept"] == "application/sparql-results+json"
    assert "rechtspraak-mcp/" in verzoeken[0].headers["user-agent"]


def test_onbekende_ecli_geeft_none():
    assert nep_cellar().arrest_op_ecli("ECLI:EU:C:2099:1") is None


def test_werk_op_celex():
    rij = nep_cellar().werk_op_celex("32011L0092")
    assert rij["eli"] == "http://data.europa.eu/eli/dir/2011/92/oj"
    assert C.pb_vindplaats(rij["oj_id"], rij["oj_datum"]) == "Pb.L. 28 januari 2012, 1"


def test_tekst_nederlands_en_terugval_op_engels():
    tekst, taal = nep_cellar().tekst("62002CJ0127")
    assert taal == "nl" and "Waddenzee" in tekst
    tekst, taal = nep_cellar(alleen_engels=True).tekst("62002CJ0127")
    assert taal == "en"
    assert nep_cellar().tekst("62099CJ0001") is None


def test_botcontrole_wordt_niet_omzeild():
    teller = {"n": 0}

    def h(request):
        teller["n"] += 1
        return httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})

    c = cellar_met(h)
    assert c.arrest_op_ecli("ECLI:EU:C:2004:482") is None
    assert c.laatste_botcontrole is True
    assert teller["n"] == 1


def test_serverfout_geeft_none():
    c = cellar_met(lambda request: httpx.Response(500))
    assert c.sparql(C.query_arrest_op_ecli("ECLI:EU:C:2004:482")) is None
    assert lees("cellar_sparql_leeg.json")  # fixture aanwezig


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("RUN_LIVE"), reason="live test; zet RUN_LIVE=1")
def test_live_waddenzee():
    c = C.Cellar()
    try:
        rij = c.arrest_op_ecli("ECLI:EU:C:2004:482")
        assert rij and rij["celex"] == "62002CJ0127"
        tekst, taal = c.tekst("62002CJ0127")
        assert taal == "nl" and "verklaart voor recht" in tekst
    finally:
        c.close()
