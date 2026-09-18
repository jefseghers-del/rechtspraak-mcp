# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de VENA-verwijzingsformatter (rechtspraak_mcp/verwijzing.py).

Puur, geen netwerk. Verwacht gedrag: VENA-voetnootvorm (docs/verwijsregels.md) —
instantie afgekort + datum (maand voluit) + nr./AR + eventueel ECLI + bron-URL,
zonder punt op het einde, en uitsluitend opgebouwd uit velden die effectief in de
treffer zitten (anti-hallucinatie).
"""
from __future__ import annotations

from datetime import date

from rechtspraak_mcp.schema import Treffer
from rechtspraak_mcp.verwijzing import vena_verwijzing


def _treffer(**kwargs) -> Treffer:
    basis = dict(
        bron="dbrc",
        instantie="Raad voor Vergunningsbetwistingen",
        titel="RvVb-A-2223-0431",
        url="https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf",
    )
    basis.update(kwargs)
    return Treffer(**basis)


def test_rvvb_met_datum_en_nummer_met_prefix():
    t = _treffer(datum=date(2023, 1, 17), rolnummer="RvVb-A-2223-0431")
    v = vena_verwijzing(t)
    assert v == (
        "RvVb 17 januari 2023, nr. RvVb-A-2223-0431, "
        "https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf"
    )
    # RvVb-nummer steeds mét prefix, en geen punt op het einde (VENA-voetnootvorm)
    assert "nr. RvVb-" in v
    assert not v.endswith(".pdf.")


def test_dbrc_zonder_datum_laat_datum_weg():
    t = _treffer(rolnummer="RvVb-UDN-2526-0608")
    v = vena_verwijzing(t)
    assert v.startswith("RvVb, nr. RvVb-UDN-2526-0608, ")


def test_cassatie_gebruikt_ar_en_ecli():
    t = _treffer(
        bron="juportal",
        instantie="Hof van Cassatie",
        datum=date(2020, 10, 30),
        ecli="ECLI:BE:CASS:2020:ARR.20201030.1N.4",
        rolnummer="C.19.0123.N",
        url="https://juportal.be/content/ECLI:BE:CASS:2020:ARR.20201030.1N.4",
    )
    v = vena_verwijzing(t)
    assert v == (
        "Cass. 30 oktober 2020, AR C.19.0123.N, ECLI:BE:CASS:2020:ARR.20201030.1N.4, "
        "https://juportal.be/content/ECLI:BE:CASS:2020:ARR.20201030.1N.4"
    )


def test_raad_van_state_nummer_met_duizendtallenpunt():
    t = _treffer(
        bron="raadvanstate",
        instantie="Raad van State",
        rolnummer="250.123",
        url="https://www.raadvst-consetat.be/arr.php?nr=250123&l=nl",
    )
    v = vena_verwijzing(t)
    assert v == "RvS, nr. 250.123, https://www.raadvst-consetat.be/arr.php?nr=250123&l=nl"


def test_onbekende_instantie_blijft_voluit():
    t = _treffer(instantie="Vredegerecht kanton Gent", datum=date(2024, 5, 1))
    v = vena_verwijzing(t)
    assert v.startswith("Vredegerecht kanton Gent 1 mei 2024, ")


def test_zonder_identificerende_elementen_geen_verwijzing():
    # geen datum, rolnummer of ECLI -> niets verantwoords te citeren
    assert vena_verwijzing(_treffer()) is None


# ---------------------------------------------------------------------------------------
# Wetgeving (vena_verwijzing_norm)
# ---------------------------------------------------------------------------------------
from rechtspraak_mcp.schema import Norm
from rechtspraak_mcp.verwijzing import vena_verwijzing_norm


def _norm(**kwargs) -> Norm:
    basis = dict(
        bron="eurlex",
        type="richtlijn",
        nummer="2011/92/EU",
        opschrift=(
            "Richtlijn 2011/92/EU van het Europees Parlement en de Raad van 13 december "
            "2011 betreffende de milieueffectbeoordeling van bepaalde openbare en "
            "particuliere projecten"
        ),
        url="https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092",
    )
    basis.update(kwargs)
    return Norm(**basis)


def test_norm_richtlijn_canonieke_vena_vorm():
    v = vena_verwijzing_norm(_norm(datum=date(2011, 12, 13), vindplaats="PB L 26 van 28.1.2012"))
    assert v == (
        "Richtl.EP en Raad 2011/92/EU, 13 december 2011 betreffende de "
        "milieueffectbeoordeling van bepaalde openbare en particuliere projecten, "
        "PB L 26 van 28.1.2012, "
        "https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092"
    )


def test_norm_verordening_commissie_zonder_vindplaats():
    v = vena_verwijzing_norm(
        _norm(
            type="verordening",
            nummer="2016/679",
            opschrift="Verordening (EU) 2016/679 van het Europees Parlement en de Raad van 27 april 2016 betreffende de bescherming van natuurlijke personen",
            datum=date(2016, 4, 27),
            vindplaats=None,
        )
    )
    assert v.startswith("Verord.EP en Raad 2016/679, 27 april 2016 betreffende de bescherming")
    assert v.endswith("uri=CELEX:32011L0092")  # url uit _norm-basis


def test_norm_zonder_datum_valt_terug_op_kop_en_url():
    v = vena_verwijzing_norm(_norm(datum=None))
    assert v.startswith("Richtl.EP en Raad 2011/92/EU betreffende de milieueffectbeoordeling")


def test_norm_zonder_nummer_en_celex_geeft_none():
    assert vena_verwijzing_norm(_norm(nummer=None, celex=None)) is None


def test_belgische_norm_decreet_met_bs():
    v = vena_verwijzing_norm(
        _norm(
            bron="codex",
            type="decreet",
            nummer=None,
            celex=None,
            opschrift="Decreet betreffende de omgevingsvergunning",
            datum=date(2014, 4, 25),
            vindplaats="BS 23 oktober 2014",
            url="https://codex.vlaanderen.be/x",
        )
    )
    assert v == (
        "Decreet 25 april 2014 betreffende de omgevingsvergunning, BS 23 oktober 2014, "
        "https://codex.vlaanderen.be/x"
    )


def test_belgische_norm_bvr_afkorting():
    v = vena_verwijzing_norm(
        _norm(
            bron="codex",
            type="besluit van de vlaamse regering",
            nummer=None,
            celex=None,
            opschrift="Besluit van de Vlaamse Regering tot uitvoering van het decreet",
            datum=date(2021, 5, 7),
            vindplaats=None,
            url="https://codex.vlaanderen.be/y",
        )
    )
    assert v.startswith("Besl.Vl.Reg. 7 mei 2021 tot uitvoering van het decreet, ")


def test_belgische_norm_zonder_opschrift_geeft_none():
    assert (
        vena_verwijzing_norm(
            _norm(bron="justel", type="wet", nummer="2016A03340", celex=None, opschrift="", datum=None)
        )
        is None
    )


def test_conclusie_openbaar_ministerie_is_geen_arrest():
    # Een conclusie van het OM mag niet als uitspraak van het Hof verschijnen (VENA:
    # "Concl. FAMILIENAAM I. bij Cass. ..."); de naam levert de bron niet, dus "OM".
    t = Treffer(
        bron="juportal",
        instantie="Hof van Cassatie",
        titel="Hof van Cassatie, conclusie van het openbaar ministerie van 04 juni 2012",
        datum=date(2012, 6, 4),
        ecli="ECLI:BE:CASS:2012:CONC.20120604.4",
        rolnummer="C.10.0672.N",
        url="https://juportal.be/content/ECLI:BE:CASS:2012:CONC.20120604.4",
    )
    assert vena_verwijzing(t).startswith("Concl. OM bij Cass. 4 juni 2012, AR C.10.0672.N, ")


def test_arrest_blijft_arrest():
    t = Treffer(
        bron="juportal",
        instantie="Hof van Cassatie",
        titel="Hof van Cassatie, vonnis/arrest van 5 december 2016",
        datum=date(2016, 12, 5),
        ecli="ECLI:BE:CASS:2016:ARR.20161205.2",
        rolnummer="C.16.0150.N",
        url="https://juportal.be/content/ECLI:BE:CASS:2016:ARR.20161205.2",
    )
    assert vena_verwijzing(t).startswith("Cass. 5 december 2016, AR C.16.0150.N, ")
