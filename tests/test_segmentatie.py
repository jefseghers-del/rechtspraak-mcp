# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor rechtspraak_mcp.segmentatie — geijkt op echte uitspraakteksten.

Fixtures (tests/fixtures/segmentatie_*.txt) zijn letterlijke teksten van echte
uitspraken, opgehaald via de bestaande adapters (op arresten rust geen auteursrecht,
artikel XI.172, § 2 WER); de EHRM-fixture is ingekort maar structuurgetrouw. Namen van
natuurlijke personen zijn gepseudonimiseerd (zie fixtures/README.md). Elke test
verifieert (a) waar de beoordeling begint/eindigt (letterlijke scharnierzinnen),
(b) dat partijenstandpunt-tekst er NIET in zit, en (c) methode en melding.
"""
from __future__ import annotations

import pathlib

from rechtspraak_mcp.segmentatie import Segmentatie, segmenteer

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _lees(naam: str) -> str:
    return (FIXTURES / naam).read_text(encoding="utf-8")


# ----------------------------------------------------------------------------------
# Grondwettelijk Hof — arrest nr. 100/2021 (ECLI:BE:GHCC:2021:ARR.100, via Juportal)
# ----------------------------------------------------------------------------------
class TestGrondwettelijkHof:
    def test_b_paragrafen(self):
        tekst = _lees("segmentatie_gwh_arr_100_2021.txt")
        s = segmenteer(tekst, bron="juportal", instantie="Grondwettelijk Hof")
        assert s.methode == "gwh-b-paragrafen"
        # Begin: onmiddellijk na de '-B-'-markering.
        assert s.beoordeling.startswith(
            "Ten aanzien van de in het geding zijnde bepaling"
        )
        # Einde: het dictum hoort erbij.
        assert "Om die redenen, het Hof zegt voor recht" in s.beoordeling
        # A-paragrafen (standpunten) zijn eruit.
        assert (
            "De eisende partij voor de verwijzende rechter herinnert eraan"
            not in s.beoordeling
        )
        assert "A-paragrafen" in s.melding

    def test_detectie_zonder_hint(self):
        tekst = _lees("segmentatie_gwh_arr_100_2021.txt")
        s = segmenteer(tekst)
        assert s.methode == "gwh-b-paragrafen"


# ----------------------------------------------------------------------------------
# Hof van Cassatie — ECLI:BE:CASS:2013:ARR.20130611.12 en ...:2020:ARR.20201030.1N.4
# ----------------------------------------------------------------------------------
class TestCassatie:
    def test_arrest_2013(self):
        tekst = _lees("segmentatie_cass_2013.txt")
        s = segmenteer(tekst, bron="juportal", instantie="Hof van Cassatie")
        assert s.methode == "cassatie-beslissing-kop"
        assert s.beoordeling.startswith("II. BESLISSING VAN HET HOF")
        assert "Verwerpt de cassatieberoepen." in s.beoordeling  # dictum
        # Rechtsplegingsrubriek (vóór de kop) is eruit.
        assert (
            "De eisers voeren in een memorie die aan dit arrest is gehecht"
            not in s.beoordeling
        )
        # De melding waarschuwt voor de middelsamenvattingen binnen de beslissing.
        assert "middel" in s.melding

    def test_arrest_2020_met_cassatiemiddelen_rubriek(self):
        tekst = _lees("segmentatie_cass_2020.txt")
        s = segmenteer(tekst, instantie="Hof van Cassatie")
        assert s.methode == "cassatie-beslissing-kop"
        assert s.beoordeling.startswith("III. BESLISSING VAN HET HOF")
        assert "Verwerpt het cassatieberoep." in s.beoordeling
        # De rubriek 'II. CASSATIEMIDDELEN' (partijtekst) is eruit.
        assert (
            "De eisers voeren in hun verzoekschrift dat aan dit arrest is gehecht"
            not in s.beoordeling
        )


# ----------------------------------------------------------------------------------
# RvVb — arrest RvVb-UDN-2526-0608 van 23 maart 2026 (PDF-tekst via pdfplumber)
# ----------------------------------------------------------------------------------
class TestRvVb:
    def test_beoordeling_en_dictum(self):
        tekst = _lees("segmentatie_rvvb_udn_2526_0608.txt")
        s = segmenteer(tekst, bron="dbrc")
        assert s.methode == "beoordeling-koppen"
        # Het beoordelingsblok begint bij de kop en behoudt die als scheidingsregel.
        assert "Beoordeling door de Raad" in s.beoordeling
        assert (
            "De verzoekende partij die vindt dat haar zaak uiterst dringend is"
            in s.beoordeling
        )
        # De sectie 'B. Ernstige middelen' (vaststelling van de Raad zelf, zonder
        # standpuntkop) blijft binnen het blok.
        assert (
            "Aangezien de Raad in het vorige onderdeel heeft vastgesteld" in s.beoordeling
        )
        # Dictum inbegrepen.
        assert (
            "De vordering tot schorsing bij uiterst dringende noodzakelijkheid wordt "
            "verworpen." in s.beoordeling
        )
        # Standpunt van de partijen is eruit.
        assert (
            "De duurtijd van een vernietigingsprocedure bij de RvVb bedraagt"
            not in s.beoordeling
        )
        assert "'Beoordeling door de Raad'" in s.melding
        assert "'V. Beslissing'" in s.melding


# ----------------------------------------------------------------------------------
# Raad van State — arrest nr. 226.824 van 20 maart 2014 (NL) en nr. 250.123 (FR)
# ----------------------------------------------------------------------------------
class TestRaadVanState:
    def test_meerdere_beoordelingsblokken(self):
        tekst = _lees("segmentatie_rvs_226824.txt")
        s = segmenteer(tekst, bron="raadvanstate")
        assert s.methode == "beoordeling-koppen"
        # Blok 1: beoordeling van de ontvankelijkheidsexceptie.
        assert "Enkel eerste verzoeker (hierna : verzoeker) beschikt" in s.beoordeling
        # Blok 2: beoordeling van het enig middel, tot en met de slotsom.
        assert "Het enig middel is gegrond." in s.beoordeling
        # Dictum ('BESLISSING') inbegrepen.
        assert "De Raad van State vernietigt het besluit" in s.beoordeling
        # Standpunten van de partijen zijn eruit.
        assert (
            "In een enig middel voert verzoeker de schending aan" not in s.beoordeling
        )
        assert (
            "De verwerende partij werpt op dat de tweede verzoekende partij"
            not in s.beoordeling
        )
        assert "'BESLISSING'" in s.melding

    def test_frans_arrest_niet_herkend(self):
        # Nr. 250.123 is Frans ('Objet du recours', 'PAR CES MOTIFS') zonder
        # standpunt/beoordeling-splitsing: eerlijk None, geen gok.
        tekst = _lees("segmentatie_rvs_250123_frans.txt")
        s = segmenteer(tekst, bron="raadvanstate")
        assert s.beoordeling is None
        assert s.methode is None
        assert "structuur niet herkend" in s.melding


# ----------------------------------------------------------------------------------
# EHRM — Lambert e.a. t. Frankrijk (HUDOC 001-155352, ingekorte bodytekst)
# ----------------------------------------------------------------------------------
class TestEhrm:
    def test_assessment_blokken_en_dictum(self):
        tekst = _lees("segmentatie_ehrm_lambert_ingekort.txt")
        s = segmenteer(tekst, bron="ehrm")
        assert s.methode == "ehrm-assessment-koppen"
        # Eerste assessment-blok (ontvankelijkheid/hoedanigheid).
        assert "Recapitulation of the principles" in s.beoordeling
        # Dictum inbegrepen, tot de slotregel.
        assert "FOR THESE REASONS, THE COURT" in s.beoordeling
        assert "Done in English and in French" in s.beoordeling
        # Partijenstandpunten ('The parties' submissions') zijn eruit.
        assert (
            "The Government observed that the applicants had not stated"
            not in s.beoordeling
        )
        # Het feitenrelaas is eruit (de namen in de fixture zijn gepseudonimiseerd).
        assert "V.L. sustained serious head injuries" in tekst
        assert "V.L. sustained serious head injuries" not in s.beoordeling
        # De separate opinion (na het dictum) is eruit.
        assert (
            "We regret that we have to dissociate ourselves" not in s.beoordeling
        )
        assert "separate opinions" in s.melding


# ----------------------------------------------------------------------------------
# HvJ / Gerecht — oud formaat (Cassis 1979, NL) en recent formaat (Carvalho 2019, EN)
# ----------------------------------------------------------------------------------
class TestHvj:
    def test_oud_formaat_rubrieken(self):
        tekst = _lees("segmentatie_hvj_cassis_1979.txt")
        s = segmenteer(tekst, bron="hvj")
        assert s.methode == "hvj-oude-rubrieken"
        assert s.beoordeling.startswith("Overwegingen van het arrest")
        assert "VERKLAART VOOR RECHT" in s.beoordeling  # dictum
        # De rubrieken 'Partijen' en 'Onderwerp' (vóór de overwegingen) zijn eruit;
        # de inhoudsopgave bovenaan mag het beginpunt niet vervroegen.
        assert "IN ZAAK 120/78" not in s.beoordeling
        assert (
            "OM EEN PREJUDICIELE BESLISSING INZAKE DE UITLEGGING" not in s.beoordeling
        )
        # De EUR-Lex-navigatieregel 'Top' is weggeknipt.
        assert not s.beoordeling.rstrip().endswith("Top")
        assert "zonder aparte kop" in s.melding

    def test_recent_formaat_findings(self):
        tekst = _lees("segmentatie_hvj_carvalho_2019.txt")
        s = segmenteer(tekst, instantie="Gerecht")
        assert s.methode == "hvj-recente-koppen"
        # Beide 'Findings of the Court'-blokken.
        assert "As indicated in paragraphs" in s.beoordeling
        assert (
            "It should be borne in mind, in the first place, that the remedy of an "
            "action for damages" in s.beoordeling
        )
        # Kosten en dictum inbegrepen.
        assert "hereby orders:" in s.beoordeling
        # Argumentenrubrieken van partijen zijn eruit.
        assert (
            "The Council contends that, notwithstanding the immense volume"
            not in s.beoordeling
        )
        assert (
            "The applicants also dispute the Parliament’s argument"
            not in s.beoordeling
        )
        assert "argumentenrubrieken" in s.melding


# ----------------------------------------------------------------------------------
# Randgevallen en de kop-op-eigen-regel-eis
# ----------------------------------------------------------------------------------
class TestRandgevallen:
    def test_lege_tekst(self):
        s = segmenteer("")
        assert s == Segmentatie(None, None, "lege tekst — niets te segmenteren.")

    def test_witruimte(self):
        s = segmenteer("   \n \n\t")
        assert s.beoordeling is None
        assert "lege tekst" in s.melding

    def test_onherkenbare_structuur(self):
        s = segmenteer("Dit is een tekst zonder enige herkenbare arreststructuur.")
        assert s.beoordeling is None
        assert s.methode is None
        assert "structuur niet herkend" in s.melding
        assert "integrale tekst" in s.melding

    def test_kop_niet_midden_in_zin(self):
        # 'beoordeling' en 'beslissing' midden in een lopende zin zijn géén koppen.
        tekst = (
            "De Raad stelt vast dat de beoordeling van het middel geen aparte rubriek "
            "vormt.\nVolgens de verzoekende partij is de beslissing onwettig omdat de "
            "beoordeling faalt.\nDe zaak wordt naar de rol verwezen."
        )
        s = segmenteer(tekst, bron="dbrc")
        assert s.beoordeling is None

    def test_kop_aan_regelbegin_maar_doorlopende_zin(self):
        # Een (afgebroken) regel die met 'beoordeling' begint maar een lopende zin
        # is, mag geen kop worden (kleine letter, lange staart).
        tekst = (
            "Standpunt van de partijen\n"
            "De verzoekende partij betoogt dat het besluit onwettig is en dat de\n"
            "beoordeling van de aanvraag door de vergunningverlenende overheid op een "
            "onzorgvuldige en dus onwettige wijze is gebeurd.\n"
        )
        s = segmenteer(tekst, bron="dbrc")
        assert s.beoordeling is None

    def test_kop_met_nummering_op_eigen_regel(self):
        tekst = "\n".join(
            [
                "Standpunt van de partijen",
                "De verzoekende partij betoogt dat het plan onwettig is.",
                "IV. Beoordeling",
                "De Raad stelt vast dat het middel gegrond is.",
                "V. Beslissing",
                "1. Het bestreden besluit wordt vernietigd.",
            ]
        )
        s = segmenteer(tekst, bron="dbrc")
        assert s.methode == "beoordeling-koppen"
        assert "IV. Beoordeling" in s.beoordeling
        assert "De Raad stelt vast dat het middel gegrond is." in s.beoordeling
        assert "Het bestreden besluit wordt vernietigd." in s.beoordeling
        assert "betoogt" not in s.beoordeling

    def test_halve_match_zonder_dictumkop(self):
        # Wel een 'Beoordeling'-kop, geen 'Beslissing'-kop: mag, mits de melding
        # dat zegt.
        tekst = "\n".join(
            [
                "Standpunt van de partijen",
                "De verzoekende partij betoogt dat het plan onwettig is.",
                "Beoordeling",
                "De Raad stelt vast dat het middel gegrond is.",
                "Het beroep wordt ingewilligd en de kosten volgen later.",
            ]
        )
        s = segmenteer(tekst, bron="dbrc")
        assert s.methode == "beoordeling-koppen"
        assert "De Raad stelt vast dat het middel gegrond is." in s.beoordeling
        assert "geen" in s.melding and "dictumkop" in s.melding


# ----------------------------------------------------------------------------------
# HvJ — prejudiciële arresten zoals CELLAR ze levert (NL): Waddenzee (2004), C-411/17 (2019)
# ----------------------------------------------------------------------------------
class TestHvjPrejudicieel:
    def _cellar(self, naam: str) -> str:
        from rechtspraak_mcp.cellar import html_naar_tekst

        return html_naar_tekst(_lees(naam))

    def test_recent_arrest_met_romeinse_koppen(self):
        tekst = self._cellar("cellar_hvj_c411_17_nl.html")
        s = segmenteer(tekst, bron="hvj")
        assert s.methode == "hvj-prejudiciele-vragen"
        assert s.beoordeling.startswith("III. Beantwoording van de prejudiciële vragen")
        # Toepasselijke bepalingen en hoofdgeding zijn eruit; kosten en dictum erin.
        assert "I. Toepasselijke bepalingen" not in s.beoordeling
        assert "II. Hoofdgeding en prejudiciële vragen" not in s.beoordeling
        assert "Het Hof (Grote kamer) verklaart voor recht:" in s.beoordeling
        assert "ondertekeningen" not in s.beoordeling

    def test_arrest_2004(self):
        s = segmenteer(self._cellar("cellar_hvj_waddenzee_nl.html"), bron="hvj")
        assert s.methode == "hvj-prejudiciele-vragen"
        assert "verklaart voor recht" in s.beoordeling
        assert "Het hoofdgeding en de prejudiciële vragen" not in s.beoordeling
