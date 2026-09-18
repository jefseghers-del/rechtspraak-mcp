# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Adapter voor het Hof van Justitie van de EU (en het Gerecht), via CELLAR.

Opzoeken op EU-ECLI en ophalen van de integrale tekst gebeurt via CELLAR, de
open-data-dienst van het Publicatiebureau (zie cellar.py): SPARQL geeft CELEX, datum en de
Nederlandse titel; de tekst komt via content negotiation op de CELEX-resource.

Waarom niet de EUR-Lex-pagina's: sinds september 2026 zet EUR-Lex een botcontrole (AWS WAF)
voor geautomatiseerde opvragingen, en die omzeilen we niet. De link die de gebruiker krijgt
(`Treffer.url`) blijft de gewone EUR-Lex-pagina: in een browser leesbaar en het
controleerbare bronadres. `haal_uitspraak` aanvaardt die EUR-Lex-link en haalt de tekst
via CELLAR op.

Hergebruik: EUR-Lex- en CELLAR-inhoud is vrij herbruikbaar (Besluit 2011/833/EU).
Automatisch ophalen volgt niettemin het vaste opt-in-patroon (`sta_fetch`); in de
Claude Desktop-bundel staat het standaard aan.

Titels in CELLAR hebben dezelfde segmenten als op EUR-Lex, gescheiden door "#":
[type + kamer + datum, partijen, procedure, onderwerp, "Zaak C-127/02."]. Van sommige
(vooral Gerecht-)beslissingen bestaat geen Nederlandse versie; dan volgt de Engelse, en
het antwoord zegt dat.

ECLI-formaat EU-rechtspraak: ``ECLI:EU:C:<jaar>:<nr>`` (Hof van Justitie),
``ECLI:EU:T:<jaar>:<nr>`` (Gerecht), ``ECLI:EU:F:<jaar>:<nr>`` (het vroegere Gerecht voor
ambtenarenzaken). De letter bepaalt de instantie.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import date

from .base import RechtspraakAdapter
from ..cellar import Cellar, kies_titel, lees_datum
from ..schema import Treffer, Uitspraak, ZoekQuery

BASE = "https://eur-lex.europa.eu"
#: Deeplink op ECLI: taalcode (NL/EN/FR/...) en volledige ECLI worden ingevuld.
ECLI_URI_SJABLOON = BASE + "/legal-content/{taal}/TXT/?uri=ecli:{ecli}"
#: Deeplink op CELEX-nummer (bv. 61978CJ0120), als alternatief aanknopingspunt.
CELEX_URI_SJABLOON = BASE + "/legal-content/{taal}/TXT/?uri=CELEX:{celex}"
#: Prefix waaraan elke aanvaardbare bron-URL moet voldoen (haal_uitspraak).
LEGAL_CONTENT_PREFIX = BASE + "/legal-content/"

_ECLI_EU_RE = re.compile(r"^(?:ECLI:)?EU:(C|T|F):(\d{4}):(\d+)$", re.IGNORECASE)
#: Zaaknummer in het laatste titelsegment: "Zaak C-411/17.", "Zaak 120/78.",
#: "Gevoegde zaken C-293/12 en C-594/12.", Engels "Case ...", Frans "Affaire ...".
_ZAAKNR_RE = re.compile(
    r"(?:Zaak|Zaken|Case|Cases|Affaires?)\s+((?:[CTF][-‑])?\d+/\d+)", re.IGNORECASE
)
#: Datum in het eerste titelsegment, bv. "van 29 juli 2019" of "of 8 May 2019".
_DATUM_RE = re.compile(r"(\d{1,2})\s+([A-Za-zéûäöü]+)\s+(\d{4})")

_INSTANTIE_PER_LETTER = {
    "C": "Hof van Justitie",
    "T": "Gerecht",
    "F": "Gerecht voor ambtenarenzaken",
}

#: Maandnamen in de drie proceduretalen (NL primair).
_MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "august": 8, "october": 10,
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
}

_MAX_SNIPPET = 400


# ---------------------------------------------------------------------------------------
# Pure functies (geen netwerk-I/O)
# ---------------------------------------------------------------------------------------
def normaliseer_ecli_eu(s: str) -> str | None:
    """Normaliseer een EU-ECLI naar 'ECLI:EU:C:1979:42', of None bij ongeldig formaat.

    Aanvaardt hoofdletterongevoelige invoer en een weggelaten 'ECLI:'-prefix
    (bv. 'eu:c:1979:42'). Alleen de EU-rechtscolleges C (Hof van Justitie), T (Gerecht)
    en F (Gerecht voor ambtenarenzaken) worden herkend.
    """
    m = _ECLI_EU_RE.match(s.strip())
    if not m:
        return None
    letter = m.group(1).upper()
    jaar = m.group(2)
    nummer = m.group(3).lstrip("0") or "0"
    return f"ECLI:EU:{letter}:{jaar}:{nummer}"


def instantie_voor_ecli(ecli: str) -> str | None:
    """Leid de instantienaam af uit de ECLI-letter (C/T/F), of None bij ongeldige ECLI."""
    genormaliseerd = normaliseer_ecli_eu(ecli)
    if genormaliseerd is None:
        return None
    return _INSTANTIE_PER_LETTER[genormaliseerd.split(":")[2]]


def content_deeplink(ecli: str, taal: str = "NL") -> str:
    """Bouw de EUR-Lex-deeplink voor een EU-ECLI (crawlt niet).

    Heft ValueError op bij een ongeldige EU-ECLI, zodat er nooit een deeplink naar een
    onbestaand of niet-EU-document wordt geconstrueerd.
    """
    genormaliseerd = normaliseer_ecli_eu(ecli)
    if genormaliseerd is None:
        raise ValueError(f"Geen geldige EU-ECLI (verwacht ECLI:EU:C|T|F:<jaar>:<nr>): {ecli!r}")
    return ECLI_URI_SJABLOON.format(taal=taal.upper(), ecli=genormaliseerd)


def celex_deeplink(celex: str, taal: str = "NL") -> str:
    """Bouw de EUR-Lex-deeplink voor een CELEX-nummer, bv. '61978CJ0120' (crawlt niet)."""
    celex = celex.strip()
    if not celex:
        raise ValueError("Leeg CELEX-nummer.")
    return CELEX_URI_SJABLOON.format(taal=taal.upper(), celex=celex)


def _parse_datum(segment: str) -> date | None:
    """Parse de uitspraakdatum uit het eerste titelsegment; None als niet herkenbaar."""
    m = _DATUM_RE.search(segment)
    if not m:
        return None
    maand = _MAANDEN.get(m.group(2).lower())
    if maand is None:
        return None
    try:
        return date(int(m.group(3)), maand, int(m.group(1)))
    except ValueError:
        return None


def identifier_uit_url(url: str) -> tuple[str, str] | None:
    """Haal ("ecli", ECLI) of ("celex", CELEX) uit een EUR-Lex-legal-content-URL, anders None."""
    if not url.startswith(LEGAL_CONTENT_PREFIX):
        return None
    uri = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("uri", [""])[0]
    soort, _, waarde = uri.partition(":")
    if soort.lower() == "ecli":
        ecli = normaliseer_ecli_eu(waarde)
        return ("ecli", ecli) if ecli else None
    if soort.upper() == "CELEX" and re.fullmatch(r"6\d{4}[A-Z]{2}\d{4}", waarde.strip().upper()):
        return ("celex", waarde.strip().upper())
    return None


def treffer_uit_cellar(rij: dict[str, str], ecli: str, url: str) -> Treffer | None:
    """Puur: bouw een Treffer uit een CELLAR-resultaatrij (titel, datum, CELEX).

    Anti-hallucinatie: zonder titel geen treffer. Alle velden komen uit wat CELLAR
    teruggaf; de datum bij voorkeur uit de metadata, anders uit het eerste titelsegment.
    """
    gekozen = kies_titel(rij)
    if gekozen is None:
        return None
    volledige_titel, taal = gekozen
    segmenten = [s.strip() for s in volledige_titel.split("#") if s.strip()]
    if not segmenten:
        return None
    # Segment 0 = type + kamer + datum; segment 1 = partijen; laatste = "Zaak ...".
    titel = segmenten[0].rstrip(".")
    if len(segmenten) > 1:
        titel = f"{titel}, {segmenten[1].rstrip('.')}"
    zaak = _ZAAKNR_RE.search(" ".join(segmenten))
    rolnummer = zaak.group(1).replace("‑", "-") if zaak else None
    midden = segmenten[2:-1] if len(segmenten) > 3 else []
    snippet = " ".join(midden)[:_MAX_SNIPPET] or None
    if taal != "nl" and snippet:
        snippet = f"[geen Nederlandse titel in CELLAR; Engelse titel] {snippet}"
    return Treffer(
        bron="hvj",
        instantie=_INSTANTIE_PER_LETTER[ecli.split(":")[2]],
        titel=titel,
        datum=lees_datum(rij.get("datum")) or _parse_datum(segmenten[0]),
        ecli=ecli,
        rolnummer=rolnummer,
        snippet=snippet,
        url=url,
    )


# ---------------------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------------------
class HvjAdapter(RechtspraakAdapter):
    bron = "hvj"
    instantie = "Hof van Justitie van de Europese Unie"
    enabled = True

    #: Automatisch ophalen volgt het vaste opt-in-patroon; EUR-Lex/CELLAR kent geen
    #: robots-blokkering en vrij hergebruik (Besluit 2011/833/EU).
    sta_fetch: bool = False
    #: True wanneer de laatste opvraging op een botcontrole stuitte (zie botcontrole.py).
    laatste_botcontrole: bool = False

    def __init__(self, *, cellar: Cellar | None = None, taal: str = "NL"):
        self._eigen_cellar = cellar is None
        self._cellar = cellar or Cellar()
        self.taal = taal.upper()

    def close(self) -> None:
        if self._eigen_cellar:
            self._cellar.close()

    # -- publieke API ----------------------------------------------------------------------
    def zoek(self, query: ZoekQuery) -> list[Treffer]:
        """Vrije-tekstzoeken in EU-rechtspraak: nog niet geïmplementeerd — geeft altijd [] terug.

        Gerichte opzoekingen op ECLI (zoek_op_identifier) werken wel.
        """
        return []

    def zoek_op_identifier(self, identifier: str, datum: date | None = None) -> list[Treffer]:
        """Zoek een arrest of beschikking op EU-ECLI via CELLAR.

        Geeft [] terug bij een niet-EU- of ongeldige ECLI, wanneer `sta_fetch` uit staat, of
        wanneer CELLAR niets teruggeeft. `datum` speelt hier geen rol.
        """
        ecli = normaliseer_ecli_eu(identifier)
        if ecli is None or not self.sta_fetch:
            return []
        rij = self._cellar.arrest_op_ecli(ecli)
        self.laatste_botcontrole = self._cellar.laatste_botcontrole
        if rij is None:
            return []
        treffer = treffer_uit_cellar(rij, ecli, content_deeplink(ecli, self.taal))
        return [treffer] if treffer is not None else []

    def haal_uitspraak(self, url: str) -> Uitspraak | None:
        """Haal de integrale tekst van één uitspraak op, via een EUR-Lex-link (ECLI of CELEX).

        Anti-hallucinatie: `Uitspraak.tekst` is letterlijk de tekst die CELLAR levert. Is er
        geen Nederlandse versie, dan de Engelse, met een notitie vooraan; is er geen tekst,
        dan None.
        """
        if not self.sta_fetch:
            return None
        gevonden = identifier_uit_url(url)
        if gevonden is None:
            return None
        soort, waarde = gevonden
        if soort == "ecli":
            ecli = waarde
            rij = self._cellar.arrest_op_ecli(ecli)
        else:
            rij = self._cellar.werk_op_celex(waarde)
            ecli = normaliseer_ecli_eu((rij or {}).get("ecli", ""))
            if rij is not None:
                rij.setdefault("celex", waarde)
        self.laatste_botcontrole = self._cellar.laatste_botcontrole
        if rij is None or ecli is None:
            return None
        treffer = treffer_uit_cellar(rij, ecli, url)
        if treffer is None:
            return None
        opgehaald = self._cellar.tekst(rij["celex"])
        self.laatste_botcontrole = self._cellar.laatste_botcontrole
        if opgehaald is None:
            return None
        tekst, taal = opgehaald
        if taal != "nl":
            tekst = (
                "[Geen Nederlandse versie van deze tekst beschikbaar in CELLAR; hieronder de "
                f"Engelse versie. Bron: {url}]\n\n" + tekst
            )
        return Uitspraak(treffer=treffer, tekst=tekst)
