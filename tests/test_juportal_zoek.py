# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor het Juportal-zoekresultatenparsen en het browser-gedreven zoekpad.

Volledig offline: de pure parser draait op een vaste fixture
(tests/fixtures/juportal_zoek_jachtdecreet.html — echte, gerenderde resultatenpagina van
https://juportal.be/zoekmachine/zoekresultaten voor de zoekterm "jachtdecreet",
opgehaald 2026-08-09 en ingekort tot de eerste 12 resultaatblokken), en de adapter
krijgt een nep-BrowserZoeker geïnjecteerd. Geen netwerk, geen Playwright.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from rechtspraak_mcp.adapters.juportal import (
    JuportalAdapter,
    is_cassatie_rolnummer,
    parse_juportal_zoekresultaten,
)
from rechtspraak_mcp.browser_zoek import BotdetectieError, ZoekError
from rechtspraak_mcp.schema import ZoekQuery

FIXTURE = (Path(__file__).parent / "fixtures" / "juportal_zoek_jachtdecreet.html").read_text()

EERSTE_ECLI = "ECLI:BE:RVSCE:2016:ARR.233.796"
EERSTE_URL = f"https://juportal.be/content/{EERSTE_ECLI}"


# ---------------------------------------------------------------------------------------
# Nep-BrowserZoekers (contract browser_zoek.BrowserZoeker; het `veld`-keyword kiest het
# formulierveld: "tekst" voor vrij zoeken, "rolnummer" voor het AR-pad)
# ---------------------------------------------------------------------------------------
class NepZoeker:
    """Geeft vaste HTML terug en registreert elke aanroep (bron, query, max, veld)."""

    def __init__(self, html: str = FIXTURE):
        self._html = html
        self.aanroepen: list[tuple[str, str, int, str]] = []

    def haal_zoekpagina_html(
        self, bron: str, query: str, *, max_resultaten: int = 20, veld: str = "tekst"
    ) -> str:
        self.aanroepen.append((bron, query, max_resultaten, veld))
        return self._html


class BotdetectieZoeker:
    """Simuleert een bot-challenge (CAPTCHA/Cloudflare): die wordt nooit omzeild."""

    def haal_zoekpagina_html(
        self, bron: str, query: str, *, max_resultaten: int = 20, veld: str = "tekst"
    ) -> str:
        raise BotdetectieError("bot-challenge gedetecteerd")


class KapotteZoeker:
    """Simuleert een render-/netwerkfout in de browser-aandrijving."""

    def haal_zoekpagina_html(
        self, bron: str, query: str, *, max_resultaten: int = 20, veld: str = "tekst"
    ) -> str:
        raise ZoekError("time-out bij het renderen")


# ---------------------------------------------------------------------------------------
# Pure parser op de fixture
# ---------------------------------------------------------------------------------------
def test_parse_zoekresultaten_fixture():
    treffers = parse_juportal_zoekresultaten(FIXTURE)
    assert len(treffers) == 12

    eerste = treffers[0]
    assert eerste.bron == "juportal"
    # zuivere ECLI: zonder /NL-taalsuffix en zonder ?HiLi=-query
    assert eerste.ecli == EERSTE_ECLI
    # url = canonieke content-deeplink, niet de sessiegebonden HiLi-URL
    assert eerste.url == EERSTE_URL
    assert eerste.instantie == "Raad van State"  # afgeleid uit RVSCE
    assert eerste.datum == date(2016, 2, 11)  # uit "Raad van State - 11 februari 2016 - ..."
    assert eerste.rolnummer == "A. 213337/VII-39195"
    assert "Raad van State - 11 februari 2016" in eerste.titel
    assert eerste.snippet is not None
    assert "Vernietiging bekendmaking" in eerste.snippet


def test_parse_zoekresultaten_urls_zonder_hili_of_taalsuffix():
    for t in parse_juportal_zoekresultaten(FIXTURE):
        assert "HiLi" not in t.url
        assert "?" not in t.url and "#" not in t.url
        assert not t.url.endswith("/NL")
        assert t.url == f"https://juportal.be/content/{t.ecli}"


def test_parse_zoekresultaten_instantie_afleiding():
    treffers = parse_juportal_zoekresultaten(FIXTURE)
    per_ecli = {t.ecli: t for t in treffers}
    assert per_ecli["ECLI:BE:RVSCE:2016:ARR.233.796"].instantie == "Raad van State"
    cass = per_ecli["ECLI:BE:CASS:2000:ARR.20000615.9"]
    assert cass.instantie == "Hof van Cassatie"
    assert cass.datum == date(2000, 6, 15)
    assert cass.rolnummer == "C.96.0451.N"
    assert per_ecli["ECLI:BE:GHCC:2007:ARR.044"].instantie == "Grondwettelijk Hof"


def test_parse_zoekresultaten_dedup_op_ecli():
    # elke uitspraak heeft in de fixture meerdere links (hoofdlink, #text, #notice1;
    # ECLI:BE:CASS:2004:ARR.20040920.6 zelfs #notice1 t.e.m. #notice3) -> exact 1 treffer
    treffers = parse_juportal_zoekresultaten(FIXTURE)
    eclis = [t.ecli for t in treffers]
    assert len(eclis) == len(set(eclis))
    assert eclis.count("ECLI:BE:CASS:2004:ARR.20040920.6") == 1
    # volgorde = documentvolgorde (eerste twee resultaten van de pagina)
    assert eclis[0] == EERSTE_ECLI
    assert eclis[1] == "ECLI:BE:RVSCE:2025:ARR.264.818"


def test_parse_zoekresultaten_dedup_synthetisch():
    html = (
        '<table><tr><td>'
        '<a href="/content/ECLI:BE:CASS:2020:ARR.1/NL?HiLi=xyz">ECLI:BE:CASS:2020:ARR.1</a>'
        '</td></tr><tr><td>'
        '<a href="/content/ECLI:BE:CASS:2020:ARR.1/NL?HiLi=xyz#text">Tekst</a>'
        '</td></tr></table>'
    )
    treffers = parse_juportal_zoekresultaten(html)
    assert len(treffers) == 1
    t = treffers[0]
    assert t.ecli == "ECLI:BE:CASS:2020:ARR.1"
    assert t.url == "https://juportal.be/content/ECLI:BE:CASS:2020:ARR.1"
    # geen metadataregel of fiche in de buurt -> titel valt terug op de ECLI, rest leeg
    assert t.titel == "ECLI:BE:CASS:2020:ARR.1"
    assert t.datum is None and t.rolnummer is None and t.snippet is None


def test_parse_zoekresultaten_lege_pagina():
    # geen resultaatlinks -> lege lijst, geen verzonnen treffers
    assert parse_juportal_zoekresultaten("") == []
    assert parse_juportal_zoekresultaten("<html><body><p>0 resultaten</p></body></html>") == []


# ---------------------------------------------------------------------------------------
# Cassatie-rolnummerherkenning (AR)
# ---------------------------------------------------------------------------------------
def test_is_cassatie_rolnummer():
    assert is_cassatie_rolnummer("P.20.0693.N")
    assert is_cassatie_rolnummer("C.19.0132.N")
    assert is_cassatie_rolnummer("F.08.0035.F")
    assert is_cassatie_rolnummer("  c.19.0132.n ")  # trim + hoofdletterongevoelig
    # geen rolnummers: ECLI's, RvVb- en RvS-nummers, afwijkende cijferblokken
    assert not is_cassatie_rolnummer("ECLI:BE:CASS:2020:ARR.20201030.1N.4")
    assert not is_cassatie_rolnummer("RvVb-A-1920-0284")
    assert not is_cassatie_rolnummer("A. 213337/VII-39195")
    assert not is_cassatie_rolnummer("44/2007")
    assert not is_cassatie_rolnummer("C.19.132.N")  # volgnummer geen 4 cijfers
    assert not is_cassatie_rolnummer("")


# ---------------------------------------------------------------------------------------
# Adapter met geïnjecteerde nep-BrowserZoeker
# ---------------------------------------------------------------------------------------
def test_zoek_standaard_uit_ook_met_zoeker():
    zoeker = NepZoeker()
    adapter = JuportalAdapter(zoeker=zoeker)
    assert adapter.browser_zoek_aan is False
    assert adapter.zoek(ZoekQuery(query="jachtdecreet")) == []
    assert zoeker.aanroepen == []  # de zoeker wordt niet eens aangesproken


def test_zoek_zonder_zoeker_ook_met_vlag_aan():
    adapter = JuportalAdapter()
    adapter.browser_zoek_aan = True
    assert adapter.zoek(ZoekQuery(query="jachtdecreet")) == []


def test_zoek_met_vlag_en_zoeker():
    zoeker = NepZoeker()
    adapter = JuportalAdapter(zoeker=zoeker)
    adapter.browser_zoek_aan = True
    treffers = adapter.zoek(ZoekQuery(query="jachtdecreet"))
    assert len(treffers) == 12
    assert treffers[0].ecli == EERSTE_ECLI
    assert treffers[0].url == EERSTE_URL
    assert zoeker.aanroepen == [("juportal", "jachtdecreet", 20, "tekst")]


def test_zoek_respecteert_max_resultaten():
    adapter = JuportalAdapter(zoeker=NepZoeker())
    adapter.browser_zoek_aan = True
    treffers = adapter.zoek(ZoekQuery(query="jachtdecreet", max_resultaten=3))
    assert len(treffers) == 3
    assert treffers[0].ecli == EERSTE_ECLI


def test_zoek_botdetectie_geeft_leeg_resultaat():
    adapter = JuportalAdapter(zoeker=BotdetectieZoeker())
    adapter.browser_zoek_aan = True
    assert adapter.zoek(ZoekQuery(query="jachtdecreet")) == []


def test_zoek_zoekfout_geeft_leeg_resultaat():
    adapter = JuportalAdapter(zoeker=KapotteZoeker())
    adapter.browser_zoek_aan = True
    assert adapter.zoek(ZoekQuery(query="jachtdecreet")) == []


def test_zoek_op_identifier_rolnummer_via_zoeker():
    zoeker = NepZoeker()
    adapter = JuportalAdapter(zoeker=zoeker)
    adapter.browser_zoek_aan = True
    treffers = adapter.zoek_op_identifier("P.20.0693.N")
    assert treffers  # de nepzoeker geeft de fixture terug; de treffers komen dááruit
    assert treffers[0].ecli == EERSTE_ECLI
    assert zoeker.aanroepen == [("juportal", "P.20.0693.N", 20, "rolnummer")]


def test_zoek_op_identifier_rolnummer_standaard_uit():
    zoeker = NepZoeker()
    adapter = JuportalAdapter(zoeker=zoeker)
    assert adapter.zoek_op_identifier("P.20.0693.N") == []
    assert zoeker.aanroepen == []


def test_zoek_op_identifier_rolnummer_botdetectie_valt_terug_op_leeg():
    adapter = JuportalAdapter(zoeker=BotdetectieZoeker())
    adapter.browser_zoek_aan = True
    assert adapter.zoek_op_identifier("P.20.0693.N") == []


def test_zoek_op_identifier_ecli_pad_raakt_zoeker_niet():
    # het bestaande ECLI-pad blijft ongewijzigd: sta_fetch uit -> [] zonder browser-zoek
    zoeker = NepZoeker()
    adapter = JuportalAdapter(zoeker=zoeker)
    adapter.browser_zoek_aan = True
    assert adapter.sta_fetch is False
    assert adapter.zoek_op_identifier("ECLI:BE:CASS:2020:ARR.20201030.1N.4") == []
    assert zoeker.aanroepen == []


def test_zoek_op_identifier_onherkenbare_identifier_blijft_leeg():
    zoeker = NepZoeker()
    adapter = JuportalAdapter(zoeker=zoeker)
    adapter.browser_zoek_aan = True
    assert adapter.zoek_op_identifier("onzin") == []
    assert adapter.zoek_op_identifier("RvVb-A-1920-0284") == []
    assert zoeker.aanroepen == []
