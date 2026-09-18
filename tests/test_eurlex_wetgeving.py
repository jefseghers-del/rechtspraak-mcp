# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de wetgevingsadapter voor EU-wetgeving (rechtspraak_mcp/wetgeving/eurlex.py).

Pure functies (CELEX-herkenning, citeervorm), en de adapter op een nep-CELLAR met echte
CELLAR-antwoorden als fixtures (cellar_nep.py). Eén live-smoke achter RUN_LIVE=1.
"""
from __future__ import annotations

import os
from datetime import date

import httpx
import pytest

from cellar_nep import nep_cellar
from rechtspraak_mcp.wetgeving.eurlex import (
    EurlexWetgevingAdapter,
    celex_naar_nummer_en_type,
    celex_uit_url,
    content_deeplink,
    identifier_naar_celex,
    norm_uit_cellar,
)

MEB_URL = "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092"


# ---------------------------------------------------------------------------------------
# identifier_naar_celex — alle gedocumenteerde citeervormen
# ---------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("invoer", "celex"),
    [
        ("32011L0092", "32011L0092"),
        ("CELEX:32011L0092", "32011L0092"),
        ("celex:32016r0679", "32016R0679"),
        ("Richtlijn 2011/92/EU", "32011L0092"),
        ("Richtl. 2014/52/EU", "32014L0052"),
        ("richtlijn 85/337/EEG", "31985L0337"),
        ("Verordening (EU) 2016/679", "32016R0679"),
        ("Verordening (EG) nr. 1367/2006", "32006R1367"),
        ("Besluit 2011/833/EU", "32011D0833"),
        ("Beschikking 97/81/EG", "31997D0081"),
        ("https://eur-lex.europa.eu/eli/dir/2011/92/oj", "32011L0092"),
        ("http://data.europa.eu/eli/reg/2016/679/oj", "32016R0679"),
    ],
)
def test_identifier_naar_celex_geldig(invoer, celex):
    assert identifier_naar_celex(invoer) == celex


@pytest.mark.parametrize(
    "invoer",
    [
        "",
        "zomaar tekst",
        "ECLI:EU:C:1979:42",  # rechtspraak, geen wetgeving
        "RvVb-A-2223-0431",
        "Verordening 2019/2010",  # ambigu: beide leesrichtingen mogelijk, geen "nr."
        "Verordening 2005/29",  # geen van beide lezingen plausibel
        "Richtlijn 05/33/EG",  # tweecijferig jaar < 52 wordt niet geraden
    ],
)
def test_identifier_naar_celex_ongeldig_of_ambigu(invoer):
    assert identifier_naar_celex(invoer) is None


def test_celex_naar_nummer_en_type():
    assert celex_naar_nummer_en_type("32011L0092") == ("richtlijn", "2011/92")
    assert celex_naar_nummer_en_type("31985L0337") == ("richtlijn", "85/337")
    assert celex_naar_nummer_en_type("32006R1367") == ("verordening", "1367/2006")
    assert celex_naar_nummer_en_type("32016R0679") == ("verordening", "2016/679")
    assert celex_naar_nummer_en_type("32011D0833") == ("besluit", "2011/833")
    assert celex_naar_nummer_en_type("62014CJ0050") is None  # sector 6 = rechtspraak


def test_content_deeplink():
    assert (
        content_deeplink("32011L0092")
        == "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092"
    )
    assert "/EN/" in content_deeplink("CELEX:32011L0092", taal="en")
    with pytest.raises(ValueError):
        content_deeplink("onzin")


# ---------------------------------------------------------------------------------------
# Pure functies op CELLAR-resultaten
# ---------------------------------------------------------------------------------------
def test_celex_uit_url():
    assert celex_uit_url(MEB_URL) == "32011L0092"
    assert celex_uit_url("https://eur-lex.europa.eu/eli/dir/2011/92/oj") == "32011L0092"
    assert celex_uit_url("http://data.europa.eu/eli/reg/2016/679/oj") == "32016R0679"
    assert celex_uit_url("https://example.org/?uri=CELEX:32011L0092") is None


def test_norm_uit_cellar_richtlijn():
    rij = {
        "datum": "2011-12-13",
        "titel_nl": "Richtlijn 2011/92/EU van het Europees Parlement en de Raad van 13 december 2011 "
        "betreffende de milieueffectbeoordeling van bepaalde openbare en particuliere projecten",
        "eli": "http://data.europa.eu/eli/dir/2011/92/oj",
        "oj_id": "oj:JOL_2012_026_R_0001_01",
        "oj_datum": "2012-01-28",
    }
    n = norm_uit_cellar(rij, "32011L0092", MEB_URL)
    assert (n.type, n.nummer) == ("richtlijn", "2011/92/EU")
    assert n.datum == date(2011, 12, 13)
    assert n.vindplaats == "Pb.L. 28 januari 2012, 1"
    assert n.eli == "http://data.europa.eu/eli/dir/2011/92/oj"


def test_norm_uit_cellar_zonder_titel_of_geen_wetgeving():
    assert norm_uit_cellar({"datum": "2011-12-13"}, "32011L0092", MEB_URL) is None
    assert norm_uit_cellar({"titel_nl": "x"}, "62002CJ0127", MEB_URL) is None


# ---------------------------------------------------------------------------------------
# Adapter met nep-CELLAR
# ---------------------------------------------------------------------------------------
def _adapter(**kwargs) -> EurlexWetgevingAdapter:
    a = EurlexWetgevingAdapter(cellar=nep_cellar(**kwargs))
    a.sta_fetch = True
    return a


def test_zoek_op_identifier_fetch_uit_geen_request():
    verzoeken: list[httpx.Request] = []
    adapter = EurlexWetgevingAdapter(cellar=nep_cellar(verzoeken))
    assert adapter.zoek_op_identifier("Richtlijn 2011/92/EU") == []
    assert verzoeken == []


def test_zoek_op_identifier_meb_richtlijn():
    [n] = _adapter().zoek_op_identifier("Richtlijn 2011/92/EU")
    assert n.celex == "32011L0092" and n.nummer == "2011/92/EU"
    assert n.vindplaats == "Pb.L. 28 januari 2012, 1"
    assert n.url == MEB_URL


def test_zoek_op_identifier_natuurherstelverordening_nieuw_publicatieblad():
    # "Verordening (EU) 2024/1991" is bewust ambigu (1991 kan een jaartal zijn): via de CELEX.
    assert identifier_naar_celex("Verordening (EU) 2024/1991") is None
    [n] = _adapter().zoek_op_identifier("32024R1991")
    assert n.celex == "32024R1991" and n.type == "verordening"
    assert n.vindplaats == "Pb.L. 29 juli 2024"  # akte-per-akte: geen pagina


def test_zoek_op_identifier_onherkenbaar():
    assert _adapter().zoek_op_identifier("zomaar tekst") == []


def test_haal_norm_geeft_tekst():
    nt = _adapter().haal_norm(MEB_URL)
    assert nt is not None and nt.norm.celex == "32011L0092"
    assert "milieueffectbeoordeling" in nt.tekst.lower()


def test_haal_norm_weigert_vreemde_url():
    assert _adapter().haal_norm("https://example.org/richtlijn") is None


def test_zoek_geeft_altijd_leeg():
    assert _adapter().zoek("milieueffectbeoordeling") == []


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("RUN_LIVE"), reason="live test; zet RUN_LIVE=1")
def test_live_meb_richtlijn():
    adapter = EurlexWetgevingAdapter()
    adapter.sta_fetch = True
    try:
        normen = adapter.zoek_op_identifier("Richtlijn 2011/92/EU")
    finally:
        adapter.close()
    assert normen and normen[0].vindplaats == "Pb.L. 28 januari 2012, 1"
