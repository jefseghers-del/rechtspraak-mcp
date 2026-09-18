# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""VENA-voetnootverwijzingen opbouwen uit een Treffer of een Norm.

Volgt de VENA-verwijsregels van vena.be (nagekeken op 18 september 2026), samengevat in
docs/verwijsregels.md:

* RS1 rechtspraak: ``instantie (afgekort) + datum, nummer, ECLI, URL.`` — het nummer zonder
  "AR" of "nr." (dat laatste is bij VENA facultatief), bv.
  ``Cass. 2 maart 2021, P.20.1057.N, ECLI:BE:CASS:2021:ARR.20210302.2N.22.``
* RS2 conclusie OM of advocaat-generaal: ``FAMILIENAAM I., 'Conclusie bij Cass. <datum>,
  <nummer>', ECLI.``
* WG2 interne normen: ``aard (afgekort, met orgaan) + datum + rest van het opschrift, BS
  <datum voluit>, ELI.``, bv. ``Decr.Vl. 4 april 2014 betreffende ..., BS 1 oktober 2014.``
* WG3 Europese normen: het opschrift voluit (aard niet afgekort), ``Pb.L. <datum voluit>,
  <pagina>, ELI.``
* Afkortingen van rechtscolleges en normen volgens de VENA-lijsten; elke voetnoot eindigt
  met een punt (algemene regel 5); een URL alleen als er geen ECLI of ELI is (regel 10:
  alleen minder bekende URL's).

Anti-hallucinatie: de verwijzing wordt uitsluitend opgebouwd uit velden die de bron
effectief teruggaf. Ontbrekende elementen (partijnaam, tijdschriftvindplaats, de naam van
de magistraat bij een conclusie, de datum bij een DBRC-treffer) worden weggelaten of als
invulveld tussen vierkante haken gemarkeerd, nooit aangevuld of geraden. Het resultaat is
een VOORSTEL dat de gebruiker vóór gebruik verifieert via de bron-URL (veld `url`).
"""
from __future__ import annotations

import re
from datetime import date

from .schema import Norm, Treffer

#: VENA-afkortingen van rechtscolleges (vena.be, Afkortingen: rechtscolleges). Onbekende
#: instanties worden voluit overgenomen (liever voluit dan een verzonnen afkorting).
_INSTANTIE_AFK = {
    "Hof van Cassatie": "Cass.",
    "Grondwettelijk Hof": "GwH",
    "Grondwettelijk Hof (Arbitragehof)": "GwH",
    "Arbitragehof": "Arbitragehof",
    "Raad van State": "RvS",
    "Raad voor Vergunningsbetwistingen": "RvVb",
    "Handhavingscollege": "HHC",
    "Raad voor betwistingen inzake studievoortgangsbeslissingen": "R.Stvb.",
    "Raad voor Verkiezingsbetwistingen": "R.Verkb.",
    "Hof van Justitie van de Europese Unie": "HvJ",
    "Hof van Justitie": "HvJ",
    "Gerecht van de Europese Unie": "Ger.EU",
    "Gerecht": "Ger.EU",
    "Gerecht voor ambtenarenzaken": "Ger.Ambt.EU",
    "Europees Hof voor de Rechten van de Mens": "EHRM",
}

_MAANDEN_NL = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]

#: RvS-arrestnummer in de ECLI (ECLI:BE:RVSCE:2016:ARR.233.796 -> "233.796"). Juportal geeft
#: bij RvS-arresten het rolnummer (A. 213337/VII-39195) als rolnummer; het arrestnummer
#: staat letterlijk in de ECLI die de bron teruggaf, dus dat is geen gok.
_RVS_ECLI_NR_RE = re.compile(r"^ECLI:BE:RVSC[ED]:\d{4}:ARR\.(\d{1,3}\.\d{3})$", re.IGNORECASE)
#: GwH-arrestnummer in de ECLI (ECLI:BE:GHCC:2020:ARR.081 -> "81/2020", zoals VENA het schrijft).
_GWH_ECLI_NR_RE = re.compile(r"^ECLI:BE:GHCC:(\d{4}):ARR\.0*(\d+)$", re.IGNORECASE)
#: VENA: "HvB Gent" voor een hof van beroep.
_HVB_RE = re.compile(r"^Hof van beroep (?:te |van )?(\S.*)$", re.IGNORECASE)
#: Verzamelnaam die de Juportal-zoekresultaten soms als instantie geven: geen rechtscollege.
_GENERIEKE_INSTANTIES = {"Juportal (federale rechtspraak)"}


def _datum_voluit(d: date) -> str:
    """Datum met de maand voluit, bv. '30 oktober 2020' (VENA)."""
    return f"{d.day} {_MAANDEN_NL[d.month - 1]} {d.year}"


def _met_punt(delen: list[str]) -> str:
    """Onderdelen gescheiden door komma's; de voetnoot eindigt met een punt (VENA regel 5)."""
    tekst = ", ".join(d for d in delen if d)
    return tekst if tekst.endswith(".") else tekst + "."


# -------------------------------------------------------------------------------------------
# Rechtspraak (RS1) en conclusies (RS2)
# -------------------------------------------------------------------------------------------
def is_conclusie(treffer: Treffer) -> bool:
    """Is de treffer een conclusie van het openbaar ministerie (geen uitspraak)?

    Herkend aan het documenttype in de ECLI (``...:CONC.<datum>...``) of aan de titel die
    Juportal meegeeft ("conclusie van het openbaar ministerie").
    """
    if treffer.ecli and ":CONC." in treffer.ecli.upper():
        return True
    return "conclusie van het openbaar ministerie" in (treffer.titel or "").lower()


def _nummer(treffer: Treffer) -> str | None:
    if treffer.ecli:
        m = _RVS_ECLI_NR_RE.match(treffer.ecli)
        if m:
            return m.group(1)
        m = _GWH_ECLI_NR_RE.match(treffer.ecli)
        if m:
            return f"{m.group(2)}/{m.group(1)}"
    return treffer.rolnummer


def _instantie(treffer: Treffer) -> str:
    """VENA-afkorting van het rechtscollege; bij een verzamelnaam een invulveld (nooit geraden)."""
    if treffer.instantie in _GENERIEKE_INSTANTIES:
        return "[rechtscollege]"
    m = _HVB_RE.match(treffer.instantie)
    if m:
        return f"HvB {m.group(1)}"
    return _INSTANTIE_AFK.get(treffer.instantie, treffer.instantie)


def vena_verwijzing(treffer: Treffer) -> str | None:
    """Bouw een VENA-voetnootverwijzing (voorstel) uit één treffer, of None.

    RS1: ``instantie + datum, nummer, ECLI, URL.`` De URL alleen wanneer er geen ECLI is
    (bv. DBRC-arresten). Bij een conclusie van het openbaar ministerie de RS2-vorm met een
    invulveld voor de naam van de magistraat, die de bron niet meegeeft. None wanneer de
    treffer geen enkel identificerend element bevat (geen datum, nummer of ECLI).
    """
    if not (treffer.datum or treffer.rolnummer or treffer.ecli):
        return None
    afk = _instantie(treffer)
    kop = f"{afk} {_datum_voluit(treffer.datum)}" if treffer.datum else afk
    nummer = _nummer(treffer)
    if is_conclusie(treffer):
        titel = f"Conclusie bij {kop}" + (f", {nummer}" if nummer else "")
        return _met_punt(["[FAMILIENAAM I.]", f"'{titel}'", treffer.ecli or treffer.url])
    delen = [kop, nummer, treffer.ecli]
    if not treffer.ecli:
        delen.append(treffer.url)
    return _met_punt(delen)


# -------------------------------------------------------------------------------------------
# Wetgeving: WG3 (Europese normen) en WG2 (interne normen)
# -------------------------------------------------------------------------------------------
#: VENA-afkortingen van de aard van interne normen (vena.be, Afkortingen: wetgeving). De
#: Vlaamse Codex bevat Vlaamse regelgeving, dus een decreet uit de Codex is een Vlaams
#: decreet (Decr.Vl.); bij Justel is het orgaan niet af te leiden en blijft het "Decr.".
_BELGISCH_TYPE_AFK = {
    "wet": "Wet",
    "decreet": "Decr.",
    "ordonnantie": "Ord.Br.",
    "koninklijk besluit": "KB",
    "ministerieel besluit": "MB",
    "besluit van de vlaamse regering": "B.Vl.Reg.",
    "besluit": "B.",
    "omzendbrief": "Omz.",
    "grondwet": "Gw.",
}
_BELGISCH_TYPE_AFK_CODEX = {"decreet": "Decr.Vl."}

#: Broncodes waarvoor de Belgische wetgevingsvorm geldt.
_BELGISCHE_BRONNEN = frozenset({"codex", "justel"})

#: Prefix van een Belgisch opschrift dat de aard (en eventueel de datum) herhaalt: die knippen
#: we weg zodat ze niet dubbel in de verwijzing belandt.
_BELGISCH_PREFIX_RE = re.compile(
    r"^\s*(?:wet|decreet|ordonnantie|grondwet|omzendbrief|(?:koninklijk|ministerieel)\s+besluit|"
    r"besluit(?:\s+van\s+de\s+vlaamse\s+regering)?)\s+"
    r"(?:van\s+\d{1,2}\s+\w+\s+\d{4}\s+)?",
    re.IGNORECASE,
)

#: Staartje dat CELLAR/EUR-Lex aan EU-opschriften hangt maar geen deel van het opschrift is.
_EER_RE = re.compile(r"\s*\(?\s*Voor de EER relevante tekst\s*\)?\s*\.?\s*$", re.IGNORECASE)


def vena_verwijzing_norm(norm: Norm) -> str | None:
    """Bouw een VENA-verwijzing (voorstel) voor één norm, of None.

    EU-normen (WG3): het opschrift voluit zoals de bron het geeft (aard niet afgekort),
    vindplaats in het Publicatieblad (``Pb.L. <datum>, <pagina>``) en de ELI. Belgische
    normen (WG2): zie ``_vena_belgische_norm``. Uitsluitend opgebouwd uit velden die de bron
    effectief teruggaf; ontbrekende elementen worden weggelaten.
    """
    if norm.bron in _BELGISCHE_BRONNEN:
        return _vena_belgische_norm(norm)
    opschrift = _EER_RE.sub("", " ".join(norm.opschrift.split())).rstrip(" .")
    if not opschrift:
        return None
    return _met_punt([opschrift, norm.vindplaats, norm.eli or norm.url])


def _vena_belgische_norm(norm: Norm) -> str | None:
    """WG2: aard (afgekort, met orgaan) + datum + rest van het opschrift, BS <datum>, ELI.

    Voorbeeld (vena.be, WG2): ``Decr.Vl. 4 april 2014 betreffende de organisatie en de
    rechtspleging van sommige Vlaamse bestuursrechtscolleges, BS 1 oktober 2014.`` Onbekende
    aarden blijven voluit. Zonder opschrift valt er niets verantwoords te citeren -> None.
    """
    if not norm.opschrift:
        return None
    type_laag = (norm.type or "").strip().lower()
    afk = (_BELGISCH_TYPE_AFK_CODEX if norm.bron == "codex" else {}).get(type_laag) or (
        _BELGISCH_TYPE_AFK.get(type_laag, (norm.type or "").strip().capitalize() or None)
    )
    rest = _BELGISCH_PREFIX_RE.sub("", norm.opschrift).strip().rstrip(".")
    if not rest:
        rest = norm.opschrift.strip().rstrip(".")
    if afk and norm.datum:
        kop = f"{afk} {_datum_voluit(norm.datum)} {rest}"
    elif afk:
        kop = f"{afk} {rest}"
    elif norm.datum:
        kop = f"{rest} ({_datum_voluit(norm.datum)})"
    else:
        return None
    return _met_punt([kop, norm.vindplaats, norm.eli])
