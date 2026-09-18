# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""VENA-voetnootverwijzingen opbouwen uit een Treffer.

Volgt de VENA-verwijsregels (vena.be) in voetnootvorm, zoals samengevat in
docs/verwijsregels.md. Canonieke volgorde voor
rechtspraak: instantie (afgekort) + datum + rolnummer/"nr." + eventueel ECLI + vindplaats.

Anti-hallucinatie: de verwijzing wordt uitsluitend opgebouwd uit velden die de bron
effectief teruggaf. Ontbrekende elementen (bv. de datum bij een DBRC-treffer uit de
overzichtslijst) worden weggelaten, nooit aangevuld of geraden. Het resultaat is dus een
VOORSTEL dat de gebruiker vóór gebruik in een processtuk verifieert via de bron-URL.
"""
from __future__ import annotations

import re
from datetime import date

from .schema import Norm, Treffer

#: VENA-afkortingen per instantie zoals de adapters die aanleveren. Onbekende instanties
#: worden niet afgekort maar voluit overgenomen (liever voluit dan een verzonnen afkorting).
_INSTANTIE_AFK = {
    "Hof van Cassatie": "Cass.",
    "Grondwettelijk Hof": "GwH",
    "Raad van State": "RvS",
    "Raad voor Vergunningsbetwistingen": "RvVb",
    "Handhavingscollege": "HHC",
    "Raad voor betwistingen inzake studievoortgangsbeslissingen": "RStvb",
    "Raad voor Verkiezingsbetwistingen": "RVerkb",
    # Europese rechtscolleges (VENA: HvJ, Ger. voor het Gerecht, EHRM).
    "Hof van Justitie van de Europese Unie": "HvJ",
    "Hof van Justitie": "HvJ",
    "Gerecht van de Europese Unie": "Ger.",
    "Gerecht": "Ger.",
    "Europees Hof voor de Rechten van de Mens": "EHRM",
}

_MAANDEN_NL = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def _datum_voluit(d: date) -> str:
    """Datum met de maand voluit, bv. '30 oktober 2020' (VENA)."""
    return f"{d.day} {_MAANDEN_NL[d.month - 1]} {d.year}"


def is_conclusie(treffer: Treffer) -> bool:
    """Is de treffer een conclusie van het openbaar ministerie (geen uitspraak)?

    Herkend aan het documenttype in de ECLI (``...:CONC.<datum>...``) of aan de titel die
    Juportal meegeeft ("conclusie van het openbaar ministerie").
    """
    if treffer.ecli and ":CONC." in treffer.ecli.upper():
        return True
    return "conclusie van het openbaar ministerie" in (treffer.titel or "").lower()


def vena_verwijzing(treffer: Treffer) -> str | None:
    """Bouw een VENA-voetnootverwijzing (voorstel) uit één treffer, of None.

    Geeft None terug wanneer de treffer geen enkel identificerend element bevat
    (geen datum, rolnummer of ECLI) — dan valt er niets verantwoords te citeren.
    De voetnoot eindigt zonder punt (VENA); RvVb-nummers behouden hun volledige
    prefix (bv. 'nr. RvVb-A-2223-0431', nooit 'nr. A-2223-0431'); bij het Hof van
    Cassatie wordt het rolnummer als 'AR' vermeld.
    """
    if not (treffer.datum or treffer.rolnummer or treffer.ecli):
        return None
    afk = _INSTANTIE_AFK.get(treffer.instantie, treffer.instantie)
    kop = f"{afk} {_datum_voluit(treffer.datum)}" if treffer.datum else afk
    if is_conclusie(treffer):
        # Een conclusie van het openbaar ministerie is geen uitspraak van het Hof. VENA:
        # "Concl. FAMILIENAAM I. bij Cass. <datum>, ..." — de naam van de magistraat levert
        # de bron niet mee, dus die blijft aan de gebruiker. [TE VERIFIËREN: VENA RS2]
        kop = f"Concl. OM bij {kop}"
    delen = [kop]
    if treffer.rolnummer:
        label = "AR" if afk == "Cass." else "nr."
        delen.append(f"{label} {treffer.rolnummer}")
    if treffer.ecli:
        delen.append(treffer.ecli)
    delen.append(treffer.url)
    return ", ".join(delen)


# -------------------------------------------------------------------------------------------
# Wetgeving (tweede spoor): VENA-vorm voor normen
# -------------------------------------------------------------------------------------------

#: VENA-afkortingen per normtype (EU-vormen; interne normen behouden hun aard voluit).
_NORMTYPE_AFK = {
    "richtlijn": "Richtl.",
    "verordening": "Verord.",
    "besluit": "Besl.",
    "beschikking": "Besch.",
}

#: Belgische normtypes -> VENA-weergave in de kop (aard + datum + opschrift + BS).
#: Wat niet in deze lijst staat, wordt met de aard voluit weergegeven (VENA §4 laat dat toe).
_BELGISCH_TYPE_AFK = {
    "wet": "Wet",
    "decreet": "Decreet",
    "ordonnantie": "Ordonnantie",
    "koninklijk besluit": "KB",
    "ministerieel besluit": "MB",
    "besluit van de vlaamse regering": "Besl.Vl.Reg.",
    "grondwet": "Gw.",
}

#: Broncodes waarvoor de Belgische wetgevingsvorm geldt (aard + datum + opschrift + BS).
_BELGISCHE_BRONNEN = frozenset({"codex", "justel"})

#: Prefix van een Belgisch opschrift dat de aard herhaalt ("Decreet tot wijziging van ...",
#: "Besluit van de Vlaamse Regering houdende ..."): we knippen de aard weg zodat ze niet
#: dubbel in de verwijzing belandt; opschriften die meteen met "houdende"/"betreffende"/
#: "tot" beginnen, blijven onaangeroerd.
_BELGISCH_PREFIX_RE = re.compile(
    r"^\s*(?:wet|decreet|ordonnantie|grondwet|(?:koninklijk|ministerieel)\s+besluit|"
    r"besluit(?:\s+van\s+de\s+vlaamse\s+regering)?)\s+"
    r"(?:van\s+\d{1,2}\s+\w+\s+\d{4}\s+)?",
    re.IGNORECASE,
)

#: Instellingen zoals ze in het opschrift voorkomen -> VENA-weergave in de kop.
_INSTELLINGEN = (
    ("Europees Parlement en de Raad", "EP en Raad"),
    ("Europees Parlement en van de Raad", "EP en Raad"),
    ("van de Raad", "Raad"),
    ("van de Commissie", "Comm."),
)

# Standaardprefix van een EU-opschrift: "Richtlijn 2011/92/EU van het Europees Parlement en
# de Raad van 13 december 2011 betreffende ..." -> we knippen alles t.e.m. de datum weg om
# het "betreffende ..."-deel over te houden.
_OPSCHRIFT_PREFIX_RE = re.compile(
    r"^\s*\S+\s+(?:\([A-Z]{2,4}\)\s+)?(?:nr\.\s+)?\S+\s+van\s+.*?"
    r"van\s+\d{1,2}\s+\w+\s+\d{4}\s*",
    re.IGNORECASE | re.DOTALL,
)


def vena_verwijzing_norm(norm: Norm) -> str | None:
    """Bouw een VENA-verwijzing (voorstel) voor één norm, of None.

    Volgt de wetgevingsvorm uit docs/verwijsregels.md: aard van de norm (afgekort voor
    EU-vormen: Richtl./Verord./Besl.) + instelling(en) + nummer, datum met de maand voluit,
    de rest van het opschrift, vindplaats en bron-URL. Uitsluitend opgebouwd uit velden die
    de bron effectief teruggaf; ontbrekende elementen worden weggelaten. Geen punt op het
    einde (voetnootvorm).
    """
    if norm.bron in _BELGISCHE_BRONNEN:
        return _vena_belgische_norm(norm)
    if not (norm.nummer or norm.celex):
        return None
    afk = _NORMTYPE_AFK.get((norm.type or "").lower())
    instelling = ""
    for zoekterm, weergave in _INSTELLINGEN:
        if zoekterm in norm.opschrift:
            instelling = weergave
            break
    if afk:
        kop = f"{afk}{instelling} {norm.nummer or norm.celex}"
    else:
        kop = f"{(norm.type or 'Norm').capitalize()} {norm.nummer or norm.celex}"
    delen = [kop]
    rest = _OPSCHRIFT_PREFIX_RE.sub("", norm.opschrift).strip().rstrip(".")
    if norm.datum:
        if rest and rest != norm.opschrift.strip():
            delen[0] = f"{kop}, {_datum_voluit(norm.datum)} {rest}"
        else:
            delen[0] = f"{kop}, {_datum_voluit(norm.datum)}"
    elif rest and rest != norm.opschrift.strip():
        delen[0] = f"{kop} {rest}"
    if norm.vindplaats:
        delen.append(norm.vindplaats)
    delen.append(norm.url)
    return ", ".join(delen)


def _vena_belgische_norm(norm: Norm) -> str | None:
    """VENA-vorm voor Belgische normen: aard + datum (maand voluit) + opschrift + BS.

    Voorbeeldvorm (verwijsregels §4): "Decreet 25 april 2014 betreffende de
    omgevingsvergunning, BS 23 oktober 2014". De aard wordt afgekort volgens de gangbare
    praktijk (KB/MB/Besl.Vl.Reg.); onbekende aarden blijven voluit. Zonder datum én zonder
    opschrift valt er niets verantwoords te citeren -> None.
    """
    if not norm.opschrift:
        return None
    type_laag = (norm.type or "").strip().lower()
    afk = _BELGISCH_TYPE_AFK.get(type_laag, (norm.type or "").strip() or None)
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
    delen = [kop]
    if norm.vindplaats:
        delen.append(norm.vindplaats)
    delen.append(norm.url)
    return ", ".join(delen)
