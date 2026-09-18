# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Wetgevingsadapter voor EU-richtlijnen, -verordeningen en -besluiten (EUR-Lex, via CELLAR).

Zelfde patroon als adapters/hvj.py (pure functies los van I/O, injecteerbare client). Dit
is de identifier-kant van het wetgevingsspoor; het zoeken op titelwoorden zit in de aparte
zoekmodule (wetgeving/eurlex_zoek.py) en wordt door het register/de server gekoppeld.

Toegang: via CELLAR, de open-data-dienst van het Publicatiebureau (zie cellar.py). Sinds
september 2026 zet EUR-Lex een botcontrole (AWS WAF) voor geautomatiseerde opvragingen, en
die omzeilen we niet. CELLAR levert per CELEX het opschrift (Nederlands, anders Engels), de
datum, de ELI en de Publicatieblad-verwijzing (SPARQL), en de oorspronkelijke — niet
geconsolideerde — tekst (content negotiation). De link die de gebruiker krijgt, blijft de
gewone EUR-Lex-pagina (``https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:32011L0092``),
in een browser leesbaar en het controleerbare bronadres. Hergebruik is vrij (Besluit
2011/833/EU); automatisch ophalen volgt niettemin het vaste opt-in-patroon (``sta_fetch``).

CELEX-formaat (sector 3 = wetgeving): ``3`` + jaar (4 cijfers) + documentletter +
volgnummer (4 cijfers, met voorloopnullen). Letters die deze adapter herkent:
``L`` (richtlijnen), ``R`` (verordeningen), ``D`` (besluiten en beschikkingen). Andere
sectoren (6 = rechtspraak, 0 = geconsolideerde versies) horen hier bewust niet thuis.

Nummerheuristiek en haar grenzen (eerlijk gedocumenteerd):

* Richtlijnen en besluiten/beschikkingen dragen het jaar VOORAAN ("2011/92/EU",
  "85/337/EEG", "Besluit 2011/833/EU"). Tweecijferige jaartallen worden als 19xx gelezen
  wanneer ze >= 52 zijn; 00-51 wordt NIET geraden (-> None).
* Verordeningen wisselden per 2015 van stijl: tot en met 2014 "nr. <volgnr>/<jaar>"
  ("nr. 1367/2006"), vanaf 2015 "<jaar>/<volgnr>" ("2016/679"). Detectie: het element dat
  op een plausibel jaartal lijkt, is het jaar; de oude lezing vereist een jaar <= 2014,
  de nieuwe een jaar >= 2015. Zijn beide lezingen mogelijk (bv. "2019/2010") dan geeft
  alleen een expliciete "nr." de doorslag (oude stijl); anders None — de server meldt de
  ambiguïteit. Is geen van beide lezingen mogelijk (bv. "2005/29": 2005 kan geen
  nieuwe-stijljaar zijn en 29 geen oud jaartal), dan eveneens None.
* Volgnummers passen in 4 cijfers (CELEX-eis); grotere nummers -> None.

Anti-hallucinatie: alle veldwaarden komen uit wat CELLAR teruggeeft of zijn een
gedocumenteerde herschrijving van het CELEX-nummer; zonder opschrift volgt None, nooit een
verzonnen norm.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import date

from .base import WetgevingAdapter
from ..cellar import Cellar, kies_titel, lees_datum, pb_vindplaats
from ..schema import Norm, NormTekst

BASE = "https://eur-lex.europa.eu"
#: Deeplink op CELEX-nummer: taalcode (NL/EN/FR/...) en CELEX worden ingevuld.
CELEX_URI_SJABLOON = BASE + "/legal-content/{taal}/TXT/?uri=CELEX:{celex}"
#: Prefixen waaraan een aanvaardbare bron-URL moet voldoen (haal_norm).
LEGAL_CONTENT_PREFIX = BASE + "/legal-content/"
ELI_PREFIX = BASE + "/eli/"

#: Structurele CELEX-vorm: sector (cijfer) + jaar + documentletter(s) + volgnummer.
_CELEX_VORM_RE = re.compile(r"^[0-9]\d{4}[A-Z]{1,2}\d{4}$")
#: Wetgevings-CELEX die deze adapter herkent: sector 3, letters L/R/D.
_CELEX_WETGEVING_RE = re.compile(r"^3(\d{4})([LRD])(\d{4})$")
#: Kale CELEX-invoer, optioneel met "CELEX:"-prefix.
_CELEX_INVOER_RE = re.compile(r"^(?:CELEX:)?\s*(3\d{4}[LRD]\d{4})$", re.IGNORECASE)
#: ELI-URL (eur-lex.europa.eu/eli/... of data.europa.eu/eli/...).
_ELI_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:eur-lex|data)\.europa\.eu/eli/"
    r"(dir|reg|dec)/(\d{4})/(\d+)(?:/|$|\?)",
    re.IGNORECASE,
)
#: Gangbare citeervorm: "Richtlijn 2011/92/EU", "Verordening (EG) nr. 1367/2006", ...
_CITEER_RE = re.compile(
    r"^(richtlijn|richtl\.?|verordening|verord\.?|besluit|beschikking)\s+"
    r"(?:\((?:EU|EG|EEG|Euratom)\)\s*)?"
    r"(nr\.\s*)?"
    r"(\d{1,4})/(\d{1,4})"
    r"(?:/(?:EU|EG|EEG|Euratom))?"
    r"\.?$",
    re.IGNORECASE,
)
#: Nummer (met eventuele gemeenschapsaanduiding) zoals het letterlijk in een opschrift staat.
_NUMMER_IN_OPSCHRIFT_RE = re.compile(
    r"^(?:richtlijn|verordening|besluit|beschikking)\s+"
    r"(?:\((?:EU|EG|EEG|Euratom)\)\s*)?(?:nr\.\s*)?"
    r"(\d{1,4}/\d{1,4}(?:/(?:EU|EG|EEG|Euratom))?)",
    re.IGNORECASE,
)
_TYPE_PER_LETTER = {"L": "richtlijn", "R": "verordening", "D": "besluit"}
_LETTER_PER_ELI_TYPE = {"dir": "L", "reg": "R", "dec": "D"}
_LETTER_PER_TYPEWOORD = {
    "richtlijn": "L", "richtl": "L", "richtl.": "L",
    "verordening": "R", "verord": "R", "verord.": "R",
    "besluit": "D", "beschikking": "D",
}

#: Vroegst plausibele jaartal voor EU-wetgeving (EGKS-verdrag in werking: 1952).
_JAAR_MIN = 1952
#: Jaar waarin verordeningen overschakelden op jaar-eerst-nummering.
_VERORDENING_NIEUWE_STIJL_VANAF = 2015

#: NL-maandnamen voor de datum in het opschrift ("van 13 december 2011").
_MAANDEN_NL = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}
_DATUM_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_MAANDEN_NL) + r")\s+(\d{4})", re.IGNORECASE
)


# ---------------------------------------------------------------------------------------
# Pure functies: CELEX-constructie en deeplinks (geen netwerk-I/O)
# ---------------------------------------------------------------------------------------
def _jaar_max() -> int:
    """Laatst plausibele jaartal voor een norm (klein beetje marge voor de jaarwissel)."""
    return date.today().year + 1


def _lees_jaar(element: str) -> int | None:
    """Lees een jaarelement (2 of 4 cijfers) uit een citeervorm; None als niet plausibel.

    Tweecijferig >= 52 wordt als 19xx gelezen ("85/337/EEG" -> 1985); 00-51 wordt bewust
    NIET geraden (gedocumenteerde grens van de heuristiek).
    """
    if len(element) == 4:
        jaar = int(element)
        return jaar if _JAAR_MIN <= jaar <= _jaar_max() else None
    if len(element) == 2 and int(element) >= 52:
        return 1900 + int(element)
    return None


def _bouw_celex(jaar: int, letter: str, volgnummer: str) -> str | None:
    """Zet jaar + letter + volgnummer om naar een CELEX (sector 3); None als het niet past."""
    nr = int(volgnummer)
    if not 1 <= nr <= 9999:
        return None
    return f"3{jaar}{letter}{nr:04d}"


def identifier_naar_celex(s: str) -> str | None:
    """Puur: zet een gangbare citeervorm om naar een wetgevings-CELEX, of None.

    Aanvaardt (hoofdletterongevoelig):

    * kale CELEX ("32011L0092", ook met "CELEX:"-prefix) — alleen sector 3 met L/R/D;
    * "Richtlijn 2011/92/EU", "Richtl. 2014/52/EU", "richtlijn 85/337/EEG";
    * "Verordening (EU) 2016/679", "Verordening (EG) nr. 1367/2006";
    * "Besluit 2011/833/EU", "Beschikking 97/81/EG";
    * ELI-URL's (eur-lex.europa.eu/eli/dir/2011/92/... of data.europa.eu/eli/...).

    Nummerheuristiek en grenzen: zie de moduledocstring. Bij een ambigue verordening
    (beide leesrichtingen mogelijk, geen "nr.") of een niet-plausibel jaartal volgt None;
    de melding aan de gebruiker is aan de server.
    """
    s = s.strip()
    if not s:
        return None

    m = _CELEX_INVOER_RE.match(s)
    if m:
        return m.group(1).upper()

    m = _ELI_URL_RE.match(s)
    if m:
        letter = _LETTER_PER_ELI_TYPE[m.group(1).lower()]
        jaar = _lees_jaar(m.group(2))
        if jaar is None:
            return None
        return _bouw_celex(jaar, letter, m.group(3))

    m = _CITEER_RE.match(s)
    if m:
        letter = _LETTER_PER_TYPEWOORD[m.group(1).lower()]
        heeft_nr = m.group(2) is not None
        a, b = m.group(3), m.group(4)
        if letter in ("L", "D"):
            # Richtlijnen en besluiten/beschikkingen: het jaar staat altijd vooraan.
            jaar = _lees_jaar(a)
            if jaar is None:
                return None
            return _bouw_celex(jaar, letter, b)
        # Verordeningen: oude stijl volgnr/jaar (t.e.m. 2014) vs. nieuwe stijl jaar/volgnr
        # (vanaf 2015). Beide lezingen expliciet toetsen; alleen een eenduidige lezing telt.
        nieuw_jaar = _lees_jaar(a) if len(a) == 4 else None
        if nieuw_jaar is not None and nieuw_jaar < _VERORDENING_NIEUWE_STIJL_VANAF:
            nieuw_jaar = None  # jaar-eerst bestaat pas sinds 2015
        oud_jaar = _lees_jaar(b)
        if oud_jaar is not None and oud_jaar >= _VERORDENING_NIEUWE_STIJL_VANAF:
            oud_jaar = None  # volgnr/jaar bestaat niet meer sinds 2015
        if nieuw_jaar is not None and oud_jaar is not None:
            if heeft_nr:
                # "nr." is de oude citeerstijl — dat geeft de doorslag.
                return _bouw_celex(oud_jaar, "R", a)
            return None  # ambigu, bv. "Verordening 2019/2010" — melding aan de server
        if nieuw_jaar is not None:
            return _bouw_celex(nieuw_jaar, "R", b)
        if oud_jaar is not None:
            return _bouw_celex(oud_jaar, "R", a)
        return None  # geen van beide lezingen plausibel, bv. "Verordening 2005/29"

    return None


def celex_naar_nummer_en_type(celex: str) -> tuple[str, str] | None:
    """Puur: leid (type, nummer) af uit een wetgevings-CELEX, bv. ("richtlijn", "2011/92").

    Herschrijft het CELEX-nummer naar de gangbare citeervorm: richtlijnen en besluiten
    jaar-eerst (pre-2000 tweecijferig: 31985L0337 -> "85/337"), verordeningen volgens hun
    stijlperiode (32006R1367 -> "1367/2006", 32016R0679 -> "2016/679"). None bij een
    CELEX die geen sector-3-wetgeving (L/R/D) is.
    """
    celex = celex.strip().upper().removeprefix("CELEX:")
    m = _CELEX_WETGEVING_RE.match(celex)
    if not m:
        return None
    jaar = int(m.group(1))
    letter = m.group(2)
    volgnr = int(m.group(3))
    if letter == "R" and jaar < _VERORDENING_NIEUWE_STIJL_VANAF:
        nummer = f"{volgnr}/{jaar}"
    elif letter == "R":
        nummer = f"{jaar}/{volgnr}"
    elif jaar < 2000:
        nummer = f"{jaar % 100}/{volgnr}"
    else:
        nummer = f"{jaar}/{volgnr}"
    return (_TYPE_PER_LETTER[letter], nummer)


def content_deeplink(celex: str, taal: str = "NL") -> str:
    """Bouw de EUR-Lex-deeplink voor een CELEX-nummer (crawlt niet).

    Aanvaardt een optionele "CELEX:"-prefix en valideert de structurele CELEX-vorm
    (sector + jaar + letter(s) + viercijferig volgnummer), zodat er nooit een deeplink
    naar een misvormd nummer wordt geconstrueerd. ValueError bij een ongeldige vorm.
    """
    celex = celex.strip().upper().removeprefix("CELEX:").strip()
    if not _CELEX_VORM_RE.match(celex):
        raise ValueError(
            f"Geen geldige CELEX-vorm (verwacht sector+jaar+letter(s)+volgnummer): {celex!r}"
        )
    return CELEX_URI_SJABLOON.format(taal=taal.upper(), celex=celex)


# ---------------------------------------------------------------------------------------
# Pure functies op CELLAR-resultaten (geen netwerk-I/O)
# ---------------------------------------------------------------------------------------
def _parse_datum(opschrift: str) -> date | None:
    """Parse de normdatum uit het opschrift (NL-maandnamen); None als niet herkenbaar."""
    m = _DATUM_RE.search(opschrift)
    if not m:
        return None
    try:
        return date(int(m.group(3)), _MAANDEN_NL[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def celex_uit_url(url: str) -> str | None:
    """Wetgevings-CELEX uit een EUR-Lex-link (legal-content met uri=CELEX:..., of een ELI-URL)."""
    if url.startswith(LEGAL_CONTENT_PREFIX):
        uri = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("uri", [""])[0]
        return identifier_naar_celex(uri)
    if url.startswith(ELI_PREFIX) or url.startswith(("http://data.europa.eu/eli/", "https://data.europa.eu/eli/")):
        return identifier_naar_celex(url)
    return None


def norm_uit_cellar(rij: dict[str, str], celex: str, url: str) -> Norm | None:
    """Puur: bouw een Norm uit de CELLAR-metadata van één wetgevingsdocument.

    Opschrift, datum, ELI en Publicatieblad komen uit CELLAR; type en (bij een afwijkend
    opschrift) nummer zijn een gedocumenteerde herschrijving van het CELEX-nummer.
    """
    afgeleid = celex_naar_nummer_en_type(celex)
    gekozen = kies_titel(rij)
    if afgeleid is None or gekozen is None:
        return None
    type_, celex_nummer = afgeleid
    opschrift = " ".join(gekozen[0].replace("#", " ").split())
    m_nr = _NUMMER_IN_OPSCHRIFT_RE.match(opschrift)
    return Norm(
        bron="eurlex",
        type=type_,
        nummer=m_nr.group(1) if m_nr else celex_nummer,
        opschrift=opschrift,
        datum=lees_datum(rij.get("datum")) or _parse_datum(opschrift),
        celex=celex,
        eli=rij.get("eli") or None,
        vindplaats=pb_vindplaats(rij.get("oj_id"), rij.get("oj_datum")),
        url=url,
    )


# ---------------------------------------------------------------------------------------
class EurlexWetgevingAdapter(WetgevingAdapter):
    bron = "eurlex"
    naam = "EUR-Lex (EU-wetgeving, via CELLAR)"
    enabled = True

    #: Automatisch ophalen volgt het vaste opt-in-patroon; vrij hergebruik (Besluit 2011/833/EU).
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
    def zoek(self, query: str, *, max_resultaten: int = 20) -> list[Norm]:
        """Zoeken op woorden zit in de aparte zoekmodule (wetgeving/eurlex_zoek.py) — hier altijd []."""
        return []

    def zoek_op_identifier(self, identifier: str) -> list[Norm]:
        """Zoek een norm op CELEX, citeervorm of ELI via CELLAR.

        Geeft [] terug bij een niet-herkende of ambigue identifier (zie de heuristiek in
        de moduledocstring), wanneer `sta_fetch` uit staat, of wanneer CELLAR niets
        teruggeeft.
        """
        celex = identifier_naar_celex(identifier)
        if celex is None or not self.sta_fetch:
            return []
        rij = self._cellar.werk_op_celex(celex)
        self.laatste_botcontrole = self._cellar.laatste_botcontrole
        if rij is None:
            return []
        norm = norm_uit_cellar(rij, celex, content_deeplink(celex, self.taal))
        return [norm] if norm is not None else []

    def haal_norm(self, url: str) -> NormTekst | None:
        """Haal de (oorspronkelijke, niet geconsolideerde) tekst van één norm op.

        Aanvaardt EUR-Lex-links (legal-content met CELEX, of ELI). Anti-hallucinatie: de
        tekst is letterlijk wat CELLAR levert; zonder Nederlandse versie de Engelse, met een
        notitie vooraan; zonder tekst None.
        """
        if not self.sta_fetch:
            return None
        celex = celex_uit_url(url)
        if celex is None:
            return None
        rij = self._cellar.werk_op_celex(celex)
        self.laatste_botcontrole = self._cellar.laatste_botcontrole
        if rij is None:
            return None
        norm = norm_uit_cellar(rij, celex, url)
        if norm is None:
            return None
        opgehaald = self._cellar.tekst(celex)
        self.laatste_botcontrole = self._cellar.laatste_botcontrole
        if opgehaald is None:
            return None
        tekst, taal = opgehaald
        if taal != "nl":
            tekst = (
                "[Geen Nederlandse versie van deze tekst beschikbaar in CELLAR; hieronder de "
                f"Engelse versie. Bron: {url}]\n\n" + tekst
            )
        return NormTekst(norm=norm, tekst=tekst)
