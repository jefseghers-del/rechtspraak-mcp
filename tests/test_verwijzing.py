# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de VENA-verwijzingsformatter (rechtspraak_mcp/verwijzing.py).

Puur, geen netwerk. Maatstaf: de voorbeelden op vena.be (nagekeken op 18 september 2026):
RS1 (rechtspraak), RS2 (conclusies), WG2 (interne normen), WG3 (Europese normen), de
afkortingenlijsten en algemene regel 5 (elke voetnoot eindigt met een punt). Waar een
test een VENA-voorbeeld letterlijk nabouwt, staat dat erbij.
"""
from __future__ import annotations

from datetime import date

from rechtspraak_mcp.schema import Norm, Treffer
from rechtspraak_mcp.verwijzing import vena_verwijzing, vena_verwijzing_norm


def _treffer(**kwargs) -> Treffer:
    basis = dict(
        bron="dbrc",
        instantie="Raad voor Vergunningsbetwistingen",
        titel="RvVb-A-2223-0431",
        url="https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf",
    )
    basis.update(kwargs)
    return Treffer(**basis)


# -- RS1: rechtspraak ------------------------------------------------------------------------
def test_vena_voorbeeld_cassatie():
    # vena.be RS1: "Cass. 2 maart 2021, P.20.1057.N, ECLI:BE:CASS:2021:ARR.20210302.2N.22."
    t = _treffer(
        bron="juportal", instantie="Hof van Cassatie", datum=date(2021, 3, 2),
        rolnummer="P.20.1057.N", ecli="ECLI:BE:CASS:2021:ARR.20210302.2N.22",
        url="https://juportal.be/content/ECLI:BE:CASS:2021:ARR.20210302.2N.22",
    )
    assert vena_verwijzing(t) == "Cass. 2 maart 2021, P.20.1057.N, ECLI:BE:CASS:2021:ARR.20210302.2N.22."


def test_vena_voorbeeld_hof_van_justitie():
    # vena.be RS1: "HvJ 20 februari 1979, C-120/78, ECLI:EU:C:1979:42, 'Cassis de Dijon'" —
    # de partijnaam levert de bron niet; die vult de gebruiker aan.
    t = _treffer(
        bron="hvj", instantie="Hof van Justitie", datum=date(1979, 2, 20), rolnummer="C-120/78",
        ecli="ECLI:EU:C:1979:42", url="https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=ecli:ECLI:EU:C:1979:42",
    )
    assert vena_verwijzing(t) == "HvJ 20 februari 1979, C-120/78, ECLI:EU:C:1979:42."


def test_vena_voorbeeld_ehrm_en_gerecht():
    # vena.be RS1: "EHRM 18 juli 2023, 49255/22, ECLI:CE:ECHR:2023:0718JUD004925522"
    t = _treffer(
        bron="ehrm", instantie="Europees Hof voor de Rechten van de Mens", datum=date(2023, 7, 18),
        rolnummer="49255/22", ecli="ECLI:CE:ECHR:2023:0718JUD004925522", url="https://hudoc.echr.coe.int/",
    )
    assert vena_verwijzing(t) == "EHRM 18 juli 2023, 49255/22, ECLI:CE:ECHR:2023:0718JUD004925522."
    g = _treffer(bron="hvj", instantie="Gerecht", datum=date(2019, 5, 8), rolnummer="T-330/18",
                 ecli="ECLI:EU:T:2019:324", url="u")
    assert vena_verwijzing(g).startswith("Ger.EU 8 mei 2019, T-330/18, ")  # VENA-afkorting Ger.EU


def test_vena_voorbeeld_raad_van_state_nummer_uit_ecli():
    # vena.be RS1: "RvS 26 maart 2024, 259.259, ECLI:BE:RVSCE:2024:ARR.259.259." — Juportal
    # geeft bij RvS het rolnummer; het arrestnummer staat letterlijk in de ECLI.
    t = _treffer(
        bron="juportal", instantie="Raad van State", datum=date(2024, 3, 26),
        rolnummer="A. 240000/XV-1234", ecli="ECLI:BE:RVSCE:2024:ARR.259.259", url="u",
    )
    assert vena_verwijzing(t) == "RvS 26 maart 2024, 259.259, ECLI:BE:RVSCE:2024:ARR.259.259."


def test_raad_van_state_zonder_ecli_houdt_de_url():
    # Bewuste afwijking van VENA-regel 10.1: URL wanneer er geen ECLI of ELI is, ook bij een
    # veelgebruikte databank, met het oog op verificatie. Naast een ECLI komt geen URL.
    t = _treffer(bron="raadvanstate", instantie="Raad van State", titel="RvS-arrest nr. 250.123",
                 rolnummer="250.123", url="https://www.raadvst-consetat.be/arr.php?nr=250123&l=nl")
    assert vena_verwijzing(t) == "RvS, 250.123, https://www.raadvst-consetat.be/arr.php?nr=250123&l=nl."


def test_rvvb_met_prefix_en_url():
    t = _treffer(datum=date(2023, 1, 17), rolnummer="RvVb-A-2223-0431")
    v = vena_verwijzing(t)
    assert v == (
        "RvVb 17 januari 2023, RvVb-A-2223-0431, "
        "https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf."
    )


def test_dbrc_zonder_datum_laat_datum_weg():
    v = vena_verwijzing(_treffer(rolnummer="RvVb-UDN-2526-0608"))
    assert v.startswith("RvVb, RvVb-UDN-2526-0608, ")
    assert v.endswith(".")


def test_vlaamse_bestuursrechtscolleges_vena_afkortingen():
    t = _treffer(instantie="Raad voor Verkiezingsbetwistingen", rolnummer="R.Verkb-A-2425-0001")
    assert vena_verwijzing(t).startswith("R.Verkb., ")


def test_onbekende_instantie_voluit():
    t = _treffer(instantie="Vredegerecht kanton Gent", datum=date(2024, 5, 1), rolnummer="24A123")
    assert vena_verwijzing(t).startswith("Vredegerecht kanton Gent 1 mei 2024, 24A123, ")


def test_zonder_identificerend_element_none():
    assert vena_verwijzing(_treffer()) is None


# -- RS2: conclusies -------------------------------------------------------------------------
def test_conclusie_openbaar_ministerie_rs2():
    # vena.be RS2: "LECLERCQ J.F., 'Conclusie bij Cass. 6 juni 2014, C.10.0482.F',
    # ECLI:BE:CASS:2014:CONC.20140606.4." — de naam levert de bron niet: invulveld.
    t = _treffer(
        bron="juportal", instantie="Hof van Cassatie",
        titel="Hof van Cassatie, conclusie van het openbaar ministerie van 06 juni 2014",
        datum=date(2014, 6, 6), rolnummer="C.10.0482.F", ecli="ECLI:BE:CASS:2014:CONC.20140606.4", url="u",
    )
    assert vena_verwijzing(t) == (
        "[FAMILIENAAM I.], 'Conclusie bij Cass. 6 juni 2014, C.10.0482.F', ECLI:BE:CASS:2014:CONC.20140606.4."
    )


# -- WG3: Europese normen --------------------------------------------------------------------
def _norm(**kwargs) -> Norm:
    basis = dict(
        bron="eurlex",
        type="richtlijn",
        nummer="2011/92/EU",
        opschrift=(
            "Richtlijn 2011/92/EU van het Europees Parlement en de Raad van 13 december "
            "2011 betreffende de milieueffectbeoordeling van bepaalde openbare en "
            "particuliere projecten (codificatie) Voor de EER relevante tekst"
        ),
        url="https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092",
    )
    basis.update(kwargs)
    return Norm(**basis)


def test_eu_richtlijn_vena_wg3():
    # vena.be WG3: opschrift voluit (aard niet afgekort), "Pb.L. <datum>, <pagina>", ELI.
    n = _norm(datum=date(2011, 12, 13), vindplaats="Pb.L. 28 januari 2012, 1",
              eli="http://data.europa.eu/eli/dir/2011/92/oj")
    assert vena_verwijzing_norm(n) == (
        "Richtlijn 2011/92/EU van het Europees Parlement en de Raad van 13 december 2011 betreffende "
        "de milieueffectbeoordeling van bepaalde openbare en particuliere projecten (codificatie), "
        "Pb.L. 28 januari 2012, 1, http://data.europa.eu/eli/dir/2011/92/oj."
    )


def test_eu_norm_zonder_eli_valt_terug_op_url():
    v = vena_verwijzing_norm(_norm())
    assert v.endswith("uri=CELEX:32011L0092.")
    assert "Voor de EER relevante tekst" not in v


def test_eu_norm_zonder_opschrift_none():
    assert vena_verwijzing_norm(_norm(opschrift="  ")) is None


# -- WG2: interne normen ---------------------------------------------------------------------
def _be(**kwargs) -> Norm:
    basis = dict(bron="codex", url="https://codex.vlaanderen.be/Zoeken/Document.aspx?DID=1")
    basis.update(kwargs)
    return Norm(**basis)


def test_vena_voorbeeld_vlaams_decreet():
    # vena.be WG2: "Decr.Vl. 4 april 2014 betreffende de organisatie en de rechtspleging van
    # sommige Vlaamse bestuursrechtscolleges, BS 1 oktober 2014, <ELI>."
    n = _be(type="decreet", datum=date(2014, 4, 4), vindplaats="BS 1 oktober 2014",
            opschrift="Decreet betreffende de organisatie en de rechtspleging van sommige Vlaamse bestuursrechtscolleges",
            eli="https://www.ejustice.just.fgov.be/eli/decreet/2014/04/04/2014035564/justel")
    assert vena_verwijzing_norm(n) == (
        "Decr.Vl. 4 april 2014 betreffende de organisatie en de rechtspleging van sommige Vlaamse "
        "bestuursrechtscolleges, BS 1 oktober 2014, "
        "https://www.ejustice.just.fgov.be/eli/decreet/2014/04/04/2014035564/justel."
    )


def test_vena_voorbeeld_wet_via_justel():
    # vena.be WG2: "Wet 30 juli 2018 betreffende de bescherming van natuurlijke personen ...,
    # BS 5 september 2018, <ELI>."
    n = _be(bron="justel", type="wet", datum=date(2018, 7, 30), vindplaats="BS 5 september 2018",
            opschrift="Wet betreffende de bescherming van natuurlijke personen met betrekking tot de verwerking van persoonsgegevens",
            eli="https://www.ejustice.just.fgov.be/eli/wet/2018/07/30/2018040581/justel")
    assert vena_verwijzing_norm(n).startswith("Wet 30 juli 2018 betreffende de bescherming van natuurlijke personen")
    assert vena_verwijzing_norm(n).endswith(", BS 5 september 2018, https://www.ejustice.just.fgov.be/eli/wet/2018/07/30/2018040581/justel.")


def test_besluit_vlaamse_regering_en_kb_afkortingen():
    bvr = _be(type="besluit van de vlaamse regering", datum=date(2021, 5, 7),
              opschrift="Besluit van de Vlaamse Regering tot uitvoering van het decreet", vindplaats="BS 1 juni 2021")
    assert vena_verwijzing_norm(bvr) == (
        "B.Vl.Reg. 7 mei 2021 tot uitvoering van het decreet, BS 1 juni 2021, "
        "https://codex.vlaanderen.be/Zoeken/Document.aspx?DID=1."
    )
    kb = _be(bron="justel", type="koninklijk besluit", datum=date(1999, 3, 18),
             opschrift="Koninklijk besluit betreffende de medische hulpmiddelen", vindplaats="BS 14 april 1999")
    assert vena_verwijzing_norm(kb).startswith("KB 18 maart 1999 betreffende de medische hulpmiddelen, BS 14 april 1999, ")


def test_decreet_via_justel_zonder_orgaan():
    n = _be(bron="justel", type="decreet", datum=date(2020, 1, 1), opschrift="Decreet over iets")
    assert vena_verwijzing_norm(n).startswith("Decr. 1 januari 2020 over iets, https://")


def test_vena_voorbeeld_grondwettelijk_hof_nummer_uit_ecli():
    # vena.be RS1: "GwH 4 juni 2020, 81/2020, ECLI:BE:GHCC:2020:ARR.081."
    t = _treffer(bron="juportal", instantie="Grondwettelijk Hof (Arbitragehof)", datum=date(2020, 6, 4),
                 ecli="ECLI:BE:GHCC:2020:ARR.081", url="u")
    assert vena_verwijzing(t) == "GwH 4 juni 2020, 81/2020, ECLI:BE:GHCC:2020:ARR.081."


def test_verzamelnaam_juportal_wordt_rechtscollege_of_invulveld():
    hvb = _treffer(bron="juportal", instantie="Hof van beroep Antwerpen", datum=date(2005, 11, 9),
                   ecli="ECLI:BE:HBANT:2005:ARR.20051109.5", url="u")
    assert vena_verwijzing(hvb) == "HvB Antwerpen 9 november 2005, ECLI:BE:HBANT:2005:ARR.20051109.5."
    rb = _treffer(bron="juportal", instantie="Juportal (federale rechtspraak)", datum=date(2026, 1, 29),
                  ecli="ECLI:BE:ORANT:2026:JUG.20260129.1", url="u")
    assert vena_verwijzing(rb).startswith("[rechtscollege] 29 januari 2026, ")


def test_codex_norm_zonder_eli_krijgt_de_codex_link():
    # Bewuste afwijking van VENA-regel 10.1: zonder ELI de bron-URL, met het oog op verificatie.
    n = _be(type="decreet", datum=date(2014, 4, 25), vindplaats="BS 23 oktober 2014",
            opschrift="Decreet betreffende de omgevingsvergunning")
    assert vena_verwijzing_norm(n) == (
        "Decr.Vl. 25 april 2014 betreffende de omgevingsvergunning, BS 23 oktober 2014, "
        "https://codex.vlaanderen.be/Zoeken/Document.aspx?DID=1."
    )
