# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de HvJ-adapter (via CELLAR).

* Offline (default): pure functies, en de adapter op een nep-CELLAR met echte
  CELLAR-antwoorden als fixtures (zie cellar_nep.py). Geen netwerk.
* Live (marker `live`): één echte opzoeking via CELLAR. Alleen met RUN_LIVE=1.
"""
from __future__ import annotations

import os
from datetime import date

import httpx
import pytest

from cellar_nep import cellar_met, nep_cellar
from rechtspraak_mcp.adapters.hvj import (
    HvjAdapter,
    celex_deeplink,
    content_deeplink,
    identifier_uit_url,
    instantie_voor_ecli,
    normaliseer_ecli_eu,
    treffer_uit_cellar,
)
from rechtspraak_mcp.schema import ZoekQuery
from rechtspraak_mcp.segmentatie import segmenteer

WADDENZEE = "ECLI:EU:C:2004:482"
WADDENZEE_URL = "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=ecli:ECLI:EU:C:2004:482"
CASSIS_URL = "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=ecli:ECLI:EU:C:1979:42"


# ---------------------------------------------------------------------------------------
# Pure functies: ECLI-normalisatie en deeplinks
# ---------------------------------------------------------------------------------------
def test_normaliseer_ecli_eu_varianten():
    assert normaliseer_ecli_eu("ECLI:EU:C:1979:42") == "ECLI:EU:C:1979:42"
    assert normaliseer_ecli_eu("ecli:eu:c:1979:42") == "ECLI:EU:C:1979:42"
    assert normaliseer_ecli_eu("  EU:T:2019:324  ") == "ECLI:EU:T:2019:324"
    assert normaliseer_ecli_eu("ECLI:EU:F:2010:2") == "ECLI:EU:F:2010:2"
    # geen EU-rechtspraak of ongeldig formaat -> None
    assert normaliseer_ecli_eu("ECLI:BE:RVSCDE:2020:ARR.247000") is None
    assert normaliseer_ecli_eu("ECLI:EU:X:1979:42") is None
    assert normaliseer_ecli_eu("C-120/78") is None
    assert normaliseer_ecli_eu("onzin") is None


def test_instantie_voor_ecli():
    assert instantie_voor_ecli("ECLI:EU:C:1979:42") == "Hof van Justitie"
    assert instantie_voor_ecli("ECLI:EU:T:2019:324") == "Gerecht"
    assert instantie_voor_ecli("ECLI:EU:F:2010:2") == "Gerecht voor ambtenarenzaken"
    assert instantie_voor_ecli("onzin") is None


def test_content_deeplink():
    assert content_deeplink("ECLI:EU:C:1979:42") == CASSIS_URL
    # taalcode instelbaar en genormaliseerd naar hoofdletters
    assert content_deeplink("eu:c:1979:42", taal="en") == (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=ecli:ECLI:EU:C:1979:42"
    )
    with pytest.raises(ValueError):
        content_deeplink("C-120/78")
    with pytest.raises(ValueError):
        content_deeplink("ECLI:NL:HR:2020:1")


def test_celex_deeplink():
    assert celex_deeplink("61978CJ0120") == (
        "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:61978CJ0120"
    )
    with pytest.raises(ValueError):
        celex_deeplink("   ")


# ---------------------------------------------------------------------------------------
# Pure functies op CELLAR-resultaten
# ---------------------------------------------------------------------------------------
def test_identifier_uit_url():
    assert identifier_uit_url(WADDENZEE_URL) == ("ecli", WADDENZEE)
    assert identifier_uit_url(
        "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:62002CJ0127"
    ) == ("celex", "62002CJ0127")
    assert identifier_uit_url("https://example.org/?uri=ecli:ECLI:EU:C:2004:482") is None
    assert identifier_uit_url("https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092") is None


def test_treffer_uit_cellar_waddenzee():
    rij = {
        "celex": "62002CJ0127",
        "datum": "2004-09-07",
        "titel_nl": "Arrest van het Hof (grote kamer) van 7 september 2004.#Landelijke Vereniging tot "
        "Behoud van de Waddenzee e.a. tegen Staatssecretaris.#Verzoek om een prejudiciële beslissing.#"
        "Richtlijn 92/43/EEG.#Zaak C-127/02.",
    }
    t = treffer_uit_cellar(rij, WADDENZEE, WADDENZEE_URL)
    assert t.instantie == "Hof van Justitie"
    assert t.titel.startswith("Arrest van het Hof (grote kamer) van 7 september 2004, Landelijke Vereniging")
    assert t.datum == date(2004, 9, 7)
    assert t.rolnummer == "C-127/02"
    assert t.url == WADDENZEE_URL


def test_treffer_uit_cellar_zonder_titel_geeft_none():
    assert treffer_uit_cellar({"celex": "62002CJ0127"}, WADDENZEE, WADDENZEE_URL) is None


def test_treffer_uit_cellar_engelse_titel_wordt_gemeld():
    rij = {"titel_en": "Order of the General Court of 8 May 2019.#A v B.#Environment.#Climate.#Case T-330/18."}
    t = treffer_uit_cellar(rij, "ECLI:EU:T:2019:324", "u")
    assert t.instantie == "Gerecht" and t.rolnummer == "T-330/18"
    assert t.datum == date(2019, 5, 8)
    assert "geen Nederlandse titel" in t.snippet


# ---------------------------------------------------------------------------------------
# Adapter met nep-CELLAR
# ---------------------------------------------------------------------------------------
def _adapter(**kwargs) -> HvjAdapter:
    a = HvjAdapter(cellar=nep_cellar(**kwargs))
    a.sta_fetch = True
    return a


def test_zoek_op_identifier_default_uit_geen_request():
    verzoeken: list[httpx.Request] = []
    adapter = HvjAdapter(cellar=nep_cellar(verzoeken))
    assert adapter.zoek_op_identifier(WADDENZEE) == []
    assert verzoeken == []


def test_zoek_op_identifier_waddenzee():
    [t] = _adapter().zoek_op_identifier("ecli:eu:c:2004:482")
    assert t.ecli == WADDENZEE
    assert t.rolnummer == "C-127/02"
    assert t.datum == date(2004, 9, 7)
    assert t.url == WADDENZEE_URL  # de controleerbare EUR-Lex-link, niet de CELLAR-URL


def test_zoek_op_identifier_onbekend_of_ongeldig():
    assert _adapter().zoek_op_identifier("ECLI:EU:C:2099:1") == []
    assert _adapter().zoek_op_identifier("C-127/02") == []
    assert _adapter().zoek_op_identifier("ECLI:BE:CASS:2020:1") == []


def test_zoek_vrije_tekst_nog_niet():
    assert _adapter().zoek(ZoekQuery(query="habitatrichtlijn")) == []


def test_haal_uitspraak_waddenzee_met_segmentatie():
    u = _adapter().haal_uitspraak(WADDENZEE_URL)
    assert u is not None and u.treffer.rolnummer == "C-127/02"
    assert "verklaart voor recht" in u.tekst
    s = segmenteer(u.tekst, bron="hvj")
    assert s.methode == "hvj-prejudiciele-vragen"
    assert s.beoordeling.startswith("De prejudiciële vragen")
    assert "Het juridisch kader" not in s.beoordeling


def test_haal_uitspraak_via_celex_link():
    u = _adapter().haal_uitspraak("https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:62002CJ0127")
    assert u is not None and u.treffer.ecli == WADDENZEE


def test_haal_uitspraak_zonder_nederlandse_tekst_meldt_engels():
    u = _adapter(alleen_engels=True).haal_uitspraak(WADDENZEE_URL)
    assert u.tekst.startswith("[Geen Nederlandse versie")


def test_haal_uitspraak_vreemde_url_en_default_uit():
    assert _adapter().haal_uitspraak("https://example.org/arrest") is None
    assert HvjAdapter(cellar=nep_cellar()).haal_uitspraak(WADDENZEE_URL) is None


def test_zoek_op_identifier_botcontrole_zet_de_vlag():
    adapter = HvjAdapter(cellar=cellar_met(lambda r: httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})))
    adapter.sta_fetch = True
    assert adapter.zoek_op_identifier(WADDENZEE) == []
    assert adapter.laatste_botcontrole is True


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("RUN_LIVE"), reason="live test; zet RUN_LIVE=1")
def test_live_zoek_op_identifier():
    adapter = HvjAdapter()
    adapter.sta_fetch = True
    try:
        treffers = adapter.zoek_op_identifier("ECLI:EU:C:1979:42")
    finally:
        adapter.close()
    assert treffers and treffers[0].rolnummer == "120/78"
