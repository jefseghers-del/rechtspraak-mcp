# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Adapter voor de Raad van State (raadvst-consetat.be).

Concept-implementatie (geen productiecode). Haalbaarheid: 🟠 oranje — zie
docs/bronnenonderzoek.md, sectie 3. Deeplink per arrestnummer via `arr.php`; het
zoekformulier draait op JavaScript en heeft geen bruikbare querystring-API.

BELANGRIJKE ROBOTS-VONDST (live gecontroleerd op 2026-08-03 via
https://www.raadvst-consetat.be/robots.txt):

    User-agent: *
    Disallow: /arr.php
    Disallow: /Arresten/   (en /arresten/, /Arrets/, /arrets/, /Beschikkingen/,
                            /beschikkingen/, /Ordonnances/, /ordonnances/, /Cass/,
                            /cass/, /dbx/, /dbx_dev/)
    Disallow: /*page=caselaw*   (en page=job, page=hearing)
    Crawl-delay: 10

Het deeplink-endpoint `arr.php?nr=<NUMMER>&l=nl` is dus UITDRUKKELIJK disallowed voor
geautomatiseerde crawlers. Gevolg voor het ontwerp (consistent met het DBRC-precedent in
`dbrc.py`):

* Automatisch ophalen staat STANDAARD UIT (`sta_fetch = False`). Met de vlag uit geven
  `zoek` en `zoek_op_identifier` een lege lijst en `haal_uitspraak` None terug
  (anti-hallucinatie: we geven geen onbevestigde deeplink als Treffer terug).
* De pure functies `arrest_deeplink()` en `zoek_deeplink()` bouwen enkel URL's, zonder
  enige netwerk-I/O, voor handmatige raadpleging door de gebruiker.
* Wie de vlag bewust aanzet (eigen verantwoordelijkheid; robots.txt-vondst hierboven)
  krijgt nette requests: identificeerbare User-Agent, rate limiting die de
  Crawl-delay van 10 s respecteert, korte timeouts, en een injecteerbare
  `httpx.Client` (voor tests met MockTransport).

VERIFICATIE-VONDST arr.php (eenmalige handmatige controle op 2026-08-03, twee requests
met 10 s tussenpauze en identificeerbare User-Agent — géén crawling):

* Bestaand nummer (`arr.php?nr=250123&l=nl`): HTTP 200 met `Content-Type:
  application/pdf` en `Content-Disposition: inline; filename="250123.pdf"` — de
  integrale arrest-PDF (met tekstlaag) wordt rechtstreeks teruggegeven; geen
  HTML-detailpagina, geen redirect. De "lege body" uit het eerdere bronnenonderzoek
  trad hier niet op.
* Onbestaand nummer (`arr.php?nr=999999&l=nl`): eveneens HTTP 200, maar met
  `Content-Type: text/html` en de boodschap "Het arrest <b>999999</b> is niet
  toegankelijk, of bestaat niet."

[BEPERKING] "Gevonden" versus "niet gevonden" is dus uitsluitend te onderscheiden via
het Content-Type (pdf vs. html), niet via de statuscode. De parser hieronder hanteert
dat criterium. Alleen `l=nl` is geverifieerd; `l=fr` e.d. zijn [TE VERIFIËREN].

[TE VERIFIËREN] Eigen gebruiksvoorwaarden/copyright-pagina van de RvS zijn niet
uitgelezen (geen aparte crawl gedaan).

Vrije-tekstzoeken (`zoek`) blijft onbeschikbaar: het zoekformulier is JavaScript zonder
eenvoudige querystring-API én de `page=caselaw`-URL's zijn robots-disallowed. `zoek`
geeft daarom altijd een lege lijst terug, ook met de vlag aan.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from datetime import date

import httpx

from .base import RechtspraakAdapter
from ..pdf_tekst import pdf_naar_tekst
from ..schema import Treffer, Uitspraak, ZoekQuery
from .. import user_agent

BASE = "https://www.raadvst-consetat.be"
ARR_PATH = "/arr.php"
ARR_URL = f"{BASE}{ARR_PATH}"
ZOEK_URL = f"{BASE}/?page=search&lang=nl"

#: Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt.
USER_AGENT = user_agent("incidentele raadpleging met expliciete gebruikersvlag")
#: robots.txt schrijft Crawl-delay: 10 voor. We respecteren dat tussen opeenvolgende requests.
CRAWL_DELAY_S = 10.0
#: Korte timeouts, zoals gevraagd.
TIMEOUT_S = 10.0

# --- Arrestnummers -------------------------------------------------------------------------
# RvS-arrestnummers zijn doorlopend genummerd sinds 1948; de online beschikbare arresten
# (vanaf 1994) hebben 5-6 cijfers (bv. 250.123, actueel ± 260.000). Gangbare schrijfwijzen:
# met duizendtallenpunt ("250.123") of aaneengeschreven ("250123"), soms met "nr."-prefix.
# VASTSTELLING (verificatie 2026-08-03): arr.php verwacht het nummer ZONDER punt
# (`nr=250123`); wij normaliseren beide schrijfwijzen naar cijfers-zonder-punt.
_ARRESTNR_RE = re.compile(
    r"^\s*(?:RvS[\s.\-]*)?(?:nr\.?\s*)?(\d{1,3}(?:\.\d{3})+|\d{3,6})\s*$",
    re.IGNORECASE,
)

#: HTML-boodschap van arr.php bij een onbestaand/afgeschermd nummer (geverifieerd 2026-08-03).
_NIET_GEVONDEN_MARKER = "is niet toegankelijk, of bestaat niet"


def normaliseer_arrestnummer(identifier: str) -> str | None:
    """Normaliseer een RvS-arrestnummer naar het cijfers-zonder-punt-formaat van arr.php.

    Aanvaardt '250.123', '250123', 'nr. 250.123', 'RvS 250.123', ... Geeft None terug voor
    alles wat geen plausibel arrestnummer is (bv. ECLI's, DBRC-nummers, vrije tekst).
    """
    m = _ARRESTNR_RE.match(identifier or "")
    if not m:
        return None
    cijfers = m.group(1).replace(".", "")
    if not 3 <= len(cijfers) <= 6:
        return None
    return cijfers


def formatteer_arrestnummer(cijfers: str) -> str:
    """Weergave met duizendtallenpunt zoals in de RvS-praktijk, bv. '250123' -> '250.123'."""
    return f"{int(cijfers):,}".replace(",", ".")


def arrest_deeplink(nr: str, taal: str = "nl") -> str:
    """Bouw de deeplink naar één arrest (pure functie, GEEN netwerk-I/O).

    Alleen `taal='nl'` is geverifieerd; andere taalcodes worden doorgegeven maar zijn
    [TE VERIFIËREN]. Heft ValueError op bij een ongeldig nummer.
    """
    cijfers = normaliseer_arrestnummer(nr)
    if cijfers is None:
        raise ValueError(f"Geen geldig RvS-arrestnummer: {nr!r}")
    return f"{ARR_URL}?{urllib.parse.urlencode({'nr': cijfers, 'l': taal})}"


def zoek_deeplink(query: str) -> str:
    """Bouw een handmatig te openen URL naar het (JS-)zoekformulier (GEEN netwerk-I/O).

    Patroon uit het bronnenonderzoek: `?page=search&lang=nl`; de `q`-parameter volgt de
    bestaande repo-aanpak (source_lookup.py) en is [TE VERIFIËREN] als voorinvulling.
    """
    return f"{ZOEK_URL}&{urllib.parse.urlencode({'q': query})}"


def parse_arrest_respons(
    content_type: str, inhoud: bytes, nr: str, url: str
) -> Treffer | None:
    """Puur: classificeer een arr.php-respons en normaliseer naar een Treffer, of None.

    Geverifieerd gedrag van arr.php (2026-08-03): een bestaand arrest komt terug als
    HTTP 200 + `application/pdf` (integrale arrest-PDF); een onbestaand/afgeschermd
    nummer als HTTP 200 + `text/html` met een foutboodschap. We beschouwen de respons
    dus enkel als treffer wanneer het effectief een PDF is (Content-Type of
    %PDF-magic). Titel/datum zitten in de PDF zelf en vergen tekstextractie
    (pdfplumber, TODO) — we normaliseren wat de bron zonder extractie aantoonbaar
    teruggeeft: bron, instantie, arrestnummer en de controleerbare deeplink.
    Deze functie doet géén netwerk-I/O en is los te testen.
    """
    cijfers = normaliseer_arrestnummer(nr)
    if cijfers is None:
        return None
    is_pdf = "application/pdf" in (content_type or "").lower() or inhoud.startswith(b"%PDF")
    if not is_pdf:
        return None
    weergave = formatteer_arrestnummer(cijfers)
    return Treffer(
        bron="raadvanstate",
        instantie="Raad van State",
        titel=f"RvS-arrest nr. {weergave}",
        datum=None,  # zit in de PDF; extractie is TODO
        ecli=None,  # niet afleidbaar zonder tekstextractie [TE VERIFIËREN]
        rolnummer=weergave,
        snippet=None,
        url=url,
    )


def _nr_uit_url(url: str) -> str | None:
    """Haal de nr-parameter uit een arr.php-URL (www/non-www/fgov-varianten toegelaten)."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if not host.endswith(("raadvst-consetat.be", "raadvst-consetat.fgov.be")):
        return None
    if parts.path != ARR_PATH:
        return None
    nr = urllib.parse.parse_qs(parts.query).get("nr", [None])[0]
    return normaliseer_arrestnummer(nr) if nr else None


class RaadVanStateAdapter(RechtspraakAdapter):
    bron = "raadvanstate"
    instantie = "Raad van State"
    enabled = True

    #: Automatisch ophalen van arr.php staat UIT: robots.txt disallowt /arr.php
    #: uitdrukkelijk (vondst 2026-08-03, zie module-docstring). Alleen bewust aanzetten;
    #: de adapter respecteert dan Crawl-delay 10 s en identificeert zichzelf netjes.
    sta_fetch: bool = False

    def __init__(self, *, client: httpx.Client | None = None, rate_limit_s: float = CRAWL_DELAY_S):
        self._eigen_client = client is None
        self._client = client or httpx.Client(
            timeout=TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._rate_limit_s = rate_limit_s
        self._laatste_request: float = 0.0

    # -- rate limiting ---------------------------------------------------------------------
    def _wacht(self) -> None:
        verstreken = time.monotonic() - self._laatste_request
        if verstreken < self._rate_limit_s:
            time.sleep(self._rate_limit_s - verstreken)
        self._laatste_request = time.monotonic()

    def close(self) -> None:
        if self._eigen_client:
            self._client.close()

    # -- publieke API ----------------------------------------------------------------------
    def zoek(self, query: ZoekQuery) -> list[Treffer]:
        """Vrije-tekstzoekopdracht — NIET beschikbaar voor de RvS.

        Het zoekformulier is JavaScript zonder eenvoudige querystring-API en de
        `page=caselaw`-resultaat-URL's zijn robots-disallowed. Geeft daarom altijd een
        lege lijst terug, ook met `sta_fetch = True` (anti-hallucinatie: we verzinnen
        geen treffers). Gebruik `zoek_deeplink()` voor een handmatig te openen zoek-URL.
        """
        return []

    def zoek_op_identifier(self, identifier: str, datum: date | None = None) -> list[Treffer]:
        """Zoek een arrest op RvS-arrestnummer via de arr.php-deeplink.

        Standaard UIT wegens robots.txt (`Disallow: /arr.php`, vondst 2026-08-03): geeft
        dan een lege lijst terug zonder enige netwerkrequest — een onbevestigde deeplink
        geven we niet als Treffer terug. Met `sta_fetch = True` wordt arr.php éénmaal
        opgehaald (GET; een statuscode volstaat niet, want ook "niet gevonden" komt als
        HTTP 200 terug — het onderscheid zit in het Content-Type, zie module-docstring)
        en alleen bij een bevestigde, inhoudsdragende PDF-respons volgt een Treffer.

        ECLI wordt niet ondersteund: uit een ECLI is het arr.php-nummer niet af te
        leiden zonder de (onbeschikbare) zoekfunctie.
        """
        if not self.sta_fetch:
            return []
        cijfers = normaliseer_arrestnummer(identifier)
        if cijfers is None:
            return []
        url = arrest_deeplink(cijfers)
        self._wacht()
        try:
            r = self._client.get(url)
            r.raise_for_status()
        except httpx.HTTPError:
            return []
        treffer = parse_arrest_respons(
            r.headers.get("content-type", ""), r.content, cijfers, url
        )
        return [treffer] if treffer else []

    def haal_uitspraak(self, url: str) -> Uitspraak | None:
        """Haal de arrest-PDF op via de arr.php-deeplink en extraheer de tekstlaag.

        Standaard UIT wegens robots.txt (zie module-docstring): geeft dan None terug
        zonder netwerkrequest. Met `sta_fetch = True` wordt de PDF opgehaald en de
        tekstlaag geëxtraheerd met pdfplumber (de arr.php-PDF's hebben een tekstlaag).
        Anti-hallucinatie: `Uitspraak.tekst` is letterlijk wat uit de PDF komt; lukt
        de extractie niet, dan volgt een eerlijke notitie met verwijzing naar de
        bron-URL — nooit een verzonnen of aangevulde arresttekst.
        """
        if not self.sta_fetch:
            return None
        cijfers = _nr_uit_url(url)
        if cijfers is None:
            return None
        self._wacht()
        try:
            r = self._client.get(url)
            r.raise_for_status()
        except httpx.HTTPError:
            return None
        treffer = parse_arrest_respons(
            r.headers.get("content-type", ""), r.content, cijfers, url
        )
        if treffer is None:
            return None
        tekst = pdf_naar_tekst(r.content)
        if tekst is None:
            tekst = (
                f"[PDF opgehaald ({len(r.content)} bytes), maar tekstextractie mislukte — "
                f"raadpleeg de bron-URL rechtstreeks.]"
            )
        return Uitspraak(treffer=treffer, tekst=tekst)
