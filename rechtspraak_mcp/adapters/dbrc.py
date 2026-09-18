# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Adapter voor DBRC / Vlaamse bestuursrechtscolleges (dbrc.be).

Concept-implementatie (geen productiecode). Haalbaarheid: 🟢 groen — zie
docs/bronnenonderzoek.md. Server-rendered (Paddle/Drupal), geen JS nodig.

BELANGRIJKE ROBOTS-VONDST (live gecontroleerd op 2026-07-25 via https://www.dbrc.be/robots.txt):

    User-agent: *
    Crawl-Delay: 10
    ...
    Disallow: /*?*search_api_fulltext*
    Disallow: /*f%5B0%5D*

De zoek- en facet-endpoints (querystring `search_api_fulltext` en facet `f[0]`) zijn dus
UITDRUKKELIJK verboden voor geautomatiseerde crawlers. De directe PDF's onder
`/sites/default/files/...` zijn NIET disallowed. Gevolg voor het ontwerp:

* `zoek_op_identifier` resolvt de PDF-URL via een HEAD-probe op `/sites/default/files/`
  (robots-conform). Dit hergebruikt het bewezen patroon uit
  `src/overzicht_iioa/source_lookup.py` van de hoofdrepo.
* `zoek` (vrije tekst) kan technisch enkel via het `search_api_fulltext`-endpoint, dat door
  robots.txt verboden is. Daarom staat automatische zoek-scraping STANDAARD UIT
  (`sta_zoek_scraping = False`): `zoek` geeft dan een lege lijst terug. Wie een DBRC-akkoord
  heeft (zie disclaimer: hergebruik voor commerciële/brede doeleinden vereist voorafgaande
  schriftelijke toestemming) kan de vlag aanzetten; de scraper respecteert dan Crawl-Delay 10s.
  `zoek_deeplink()` geeft altijd een handmatig te openen zoek-URL terug zonder te crawlen.

Juridisch: arresten zijn "vrij beschikbaar voor raadpleging"; commercieel/breed gedeeld
hergebruik vereist voorafgaande schriftelijke DBRC-toestemming. Houd nette rate limiting en
bronidentificatie aan en link steeds terug naar de bron-PDF.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

from .base import RechtspraakAdapter
from ..pdf_tekst import pdf_naar_tekst
from ..schema import Treffer, Uitspraak, ZoekQuery
from .. import user_agent

BASE = "https://www.dbrc.be"
ZOEK_URL = f"{BASE}/rechtspraak"
PDF_BASE = f"{BASE}/sites/default/files"
SEARCH_PARAM = "search_api_fulltext"

#: Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt.
USER_AGENT = user_agent("raadpleging DBRC-arresten op nummer")
#: robots.txt schrijft Crawl-Delay: 10 voor. We respecteren dat tussen opeenvolgende requests.
CRAWL_DELAY_S = 10.0
#: Korte timeouts, zoals gevraagd.
TIMEOUT_S = 10.0
#: Wandkloktijdbudget voor één `zoek_op_identifier`. Het volledige maandvenster is tot 26
#: HEAD-probes; met Crawl-Delay 10 s loopt dat op tot ~260 s, ruim voorbij de time-out van
#: een MCP-client — die breekt de oproep dan af zonder uitleg. Binnen het budget een
#: eerlijk "niet gevonden" mét de raad om een uitspraakdatum mee te geven is bruikbaarder.
#: De crawl-delay zelf blijft onaangeroerd: we doen minder requests, niet snellere.
TIJDSBUDGET_S = 40.0

# --- Naamgeving arresten -------------------------------------------------------------------
# PDF-bestandsnaam: <COLLEGE>.<TYPE>.<WERKJAAR>.<NUMMER>[_<n>].pdf
#   bv. RVVB.UDN.2526.0627.pdf  ·  RVVB.A.1920.0284_0.pdf
# Arrestnummer (zoals in de bijsluiter): "RvVb-A-1920-0284", "RvVb-UDN-2526-0627".
# WERKJAAR is het token zoals het in het arrestnummer staat (bv. "1920" = werkjaar 2019-2020,
# "2526" = 2025-2026); het wordt LETTERLIJK in de bestandsnaam overgenomen.

_COLLEGE_CANON = {  # genormaliseerde sleutel -> bestandsnaam-prefix
    "rvvb": "RVVB",
    "hhc": "HHC",
    "rstvb": "RSTVB",
    "rverkb": "RVERKB",
}
_COLLEGE_DISPLAY = {  # bestandsnaam-prefix -> arrestnummer-weergave
    "RVVB": "RvVb",
    "HHC": "HHC",
    "RSTVB": "R.Stvb",
    "RVERKB": "R.Verkb",
}
_COLLEGE_INSTANTIE = {
    "RVVB": "Raad voor Vergunningsbetwistingen",
    "HHC": "Handhavingscollege",
    "RSTVB": "Raad voor betwistingen inzake studievoortgangsbeslissingen",
    "RVERKB": "Raad voor Verkiezingsbetwistingen",
}

# Arrestnummer, bv. "RvVb-A-1920-0284" of "R.Verkb-A-2021-0003".
_ARRESTNR_RE = re.compile(
    r"^\s*(RvVb|HHC|R\.?Stvb|R\.?Verkb)[-. ]([A-Za-z]+)[-. ](\d{3,4})[-. ](\d{2,4})\s*$",
    re.IGNORECASE,
)
# Bestandsnaam (evt. zonder .pdf), bv. "RVVB.A.1920.0284_0".
_FILENAME_RE = re.compile(
    r"(RVVB|HHC|RSTVB|RVERKB)\.([A-Za-z]+)\.(\d{3,4})\.(\d{2,4})(_\d+)?",
    re.IGNORECASE,
)


class ArrestId:
    """Ontlede identifier: college-prefix, proceduretype, werkjaar-token en nummer."""

    __slots__ = ("college", "type", "werkjaar", "nummer")

    def __init__(self, college: str, type_: str, werkjaar: str, nummer: str):
        self.college = college  # bestandsnaam-prefix, bv. "RVVB"
        self.type = type_.upper()  # bv. "A", "S", "UDN"
        self.werkjaar = werkjaar  # letterlijk token, bv. "1920" of "2526"
        self.nummer = nummer.zfill(4)

    @property
    def basename(self) -> str:
        """Bestandsnaam zonder extensie/suffix, bv. 'RVVB.A.1920.0284'."""
        return f"{self.college}.{self.type}.{self.werkjaar}.{self.nummer}"

    @property
    def arrestnummer(self) -> str:
        """Weergave zoals in de bijsluiter, bv. 'RvVb-A-1920-0284'."""
        return f"{_COLLEGE_DISPLAY[self.college]}-{self.type}-{self.werkjaar}-{self.nummer}"

    @property
    def instantie(self) -> str:
        return _COLLEGE_INSTANTIE[self.college]


def parse_arrestnummer(identifier: str) -> ArrestId | None:
    """Parse een arrest-/rolnummer zoals 'RvVb-A-1920-0284' naar een ArrestId, of None."""
    m = _ARRESTNR_RE.match(identifier)
    if not m:
        return None
    college_key = m.group(1).replace(".", "").lower()
    college = _COLLEGE_CANON.get(college_key)
    if not college:
        return None
    return ArrestId(college, m.group(2), m.group(3), m.group(4))


def parse_filename(href_of_naam: str) -> ArrestId | None:
    """Parse een PDF-bestandsnaam/URL zoals '.../RVVB.A.1920.0284_0.pdf' naar een ArrestId."""
    m = _FILENAME_RE.search(href_of_naam)
    if not m:
        return None
    return ArrestId(m.group(1).upper(), m.group(2), m.group(3), m.group(4))


def zoek_deeplink(query: str) -> str:
    """Bouw een handmatig te openen zoek-URL (crawlt NIET; robots verbiedt automatisch ophalen)."""
    return f"{ZOEK_URL}?{urllib.parse.urlencode({SEARCH_PARAM: query})}"


def parse_zoekresultaten(html: str) -> list[Treffer]:
    """Puur: parse de HTML van een /rechtspraak-resultatenpagina naar Treffers.

    De resultatenlijst toont per arrest enkel een PDF-link (bestandsnaam + grootte); er is
    geen datum of samenvatting in de lijst (bevestigd in de DBRC-bijsluiter). We normaliseren
    wat de bron effectief toont: bron, instantie, arrestnummer als titel/rolnummer en de
    PDF-URL. Deze functie doet géén netwerk-I/O en is los te testen.
    """
    soup = BeautifulSoup(html, "html.parser")
    treffers: list[Treffer] = []
    gezien: set[str] = set()
    for a in soup.select('a[href$=".pdf"]'):
        href = a.get("href") or ""
        if "/sites/default/files/" not in href:
            continue
        aid = parse_filename(href)
        if aid is None:  # bv. de toegankelijkheidsverklaring.pdf in de footer
            continue
        url = href if href.startswith("http") else urllib.parse.urljoin(BASE, href)
        if url in gezien:
            continue
        gezien.add(url)
        grootte = (a.get_text() or "").strip()
        treffers.append(
            Treffer(
                bron="dbrc",
                instantie=aid.instantie,
                titel=aid.arrestnummer,
                datum=None,  # niet aanwezig in de overzichtslijst
                ecli=None,
                rolnummer=aid.arrestnummer,
                snippet=grootte or None,
                url=url,
            )
        )
    return treffers


def _pdf_kandidaten(aid: ArrestId, anchor: date | None, venster_maanden: int = 12) -> list[str]:
    """Bouw kandidaat-PDF-URL's (verschillende publicatiemaanden + optioneel _0-suffix).

    Hergebruikt het patroon uit src/overzicht_iioa/source_lookup.py: de publicatiemaand
    (YYYY-MM in het pad) is niet exact voorspelbaar, dus we proberen een venster van maanden.
    Zonder datum ankeren we op september van het werkjaar (start van het werkjaar).

    `venster_maanden` bepaalt hoeveel maanden vooruit we proberen. Groter = meer kans op laat
    gepubliceerde arresten, maar (met Crawl-Delay 10s) trager. Zie [BEPERKING] in
    zoek_op_identifier.

    Volgorde: eerst alle maanden met de kale bestandsnaam, pas daarna dezelfde maanden met
    `_0`. Dat is bewust NIET geïnterleaved: de kale naam is verreweg het gewone geval, en
    interleaven verdubbelt dan het aantal probes (live gemeten op RvVb-A-2425-0744: 10 →
    19 pogingen, met Crawl-Delay 10 s goed voor anderhalve minuut extra). Een arrest mét
    `_0`-suffix betaalt in ruil een volledig tweede venster; dat is de zeldzame kant.
    """
    if anchor is None:
        anchor = _werkjaar_start(aid.werkjaar)
    maanden: list[date] = [_verschuif_maand(anchor, i) for i in range(-1, venster_maanden)]
    urls: list[str] = []
    seen: set[str] = set()
    for suffix in ("", "_0"):
        for d in maanden:
            ym = f"{d.year:04d}-{d.month:02d}"
            url = f"{PDF_BASE}/{ym}/{aid.basename}{suffix}.pdf"
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def _werkjaar_start(werkjaar: str) -> date:
    """Leid de startdatum (1 sep) van het werkjaar af uit een token als '2526' of '1920'."""
    try:
        if len(werkjaar) == 4:
            startjaar = 2000 + int(werkjaar[:2])
        else:
            startjaar = int(werkjaar)
    except ValueError:
        startjaar = date.today().year
    return date(startjaar, 9, 1)


def _verschuif_maand(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    return date(y, m % 12 + 1, 1)


class DbrcAdapter(RechtspraakAdapter):
    bron = "dbrc"
    instantie = "Vlaamse bestuursrechtscolleges (RvVb/HHC/RStvb/RVerkb)"
    enabled = True

    #: Automatisch scrapen van het zoek-endpoint staat UIT: robots.txt verbiedt
    #: `search_api_fulltext`/facet-URL's voor crawlers. Enkel aanzetten met DBRC-akkoord.
    sta_zoek_scraping: bool = False

    #: True wanneer de laatste `zoek_op_identifier` het maandvenster niet heeft kunnen
    #: aflopen binnen het tijdsbudget. Dan is "niets gevonden" géén uitspraak over het
    #: bestaan van het arrest, en moet de server dat eerlijk melden.
    laatste_zoektocht_afgebroken: bool = False

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        rate_limit_s: float = CRAWL_DELAY_S,
        tijdsbudget_s: float = TIJDSBUDGET_S,
    ):
        self._eigen_client = client is None
        self._client = client or httpx.Client(
            timeout=TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._rate_limit_s = rate_limit_s
        self._tijdsbudget_s = tijdsbudget_s
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
        """Vrije-tekstzoekopdracht.

        Standaard UIT wegens robots.txt (`Disallow: /*?*search_api_fulltext*`). Geeft dan een
        lege lijst terug. Met `sta_zoek_scraping = True` (enkel bij DBRC-akkoord) wordt het
        zoek-endpoint respectvol opgehaald en geparset.
        """
        if not self.sta_zoek_scraping:
            return []
        params = {SEARCH_PARAM: query.query, "sort_bef_combine": "name_DESC"}
        self._wacht()
        try:
            r = self._client.get(ZOEK_URL, params=params)
            r.raise_for_status()
        except httpx.HTTPError:
            return []
        treffers = parse_zoekresultaten(r.text)
        return treffers[: query.max_resultaten]

    def zoek_op_identifier(
        self,
        identifier: str,
        datum: date | None = None,
        venster_maanden: int = 12,
        tijdsbudget_s: float | None = None,
    ) -> list[Treffer]:
        """Zoek een arrest op arrest-/rolnummer en resolve de directe PDF-URL.

        Robots-conform: probeert enkel `/sites/default/files/`-PDF's via HEAD (niet disallowed).
        Werkt betrouwbaar voor arresten die binnen ~1 jaar na het werkjaar (of na `datum`)
        gepubliceerd zijn. Laat-gepubliceerde arresten (soms >1,5 jaar later — bv.
        RvVb-A-1920-0284 werd pas in 2021-08 gepubliceerd) vallen buiten het standaardvenster
        en worden dan niet gevonden zonder de (robots-verboden) zoekfunctie. Verhoog
        `venster_maanden` of geef `datum` mee om de trefkans te vergroten. [BEPERKING]

        TIJDSBUDGET: het volledige venster afproberen duurt met Crawl-Delay 10 s tot ~260 s;
        een MCP-client is dan allang in time-out. Daarom stoppen we na `tijdsbudget_s`
        (`None` = de instelling van deze instantie, default `TIJDSBUDGET_S`; `math.inf` =
        geen begrenzing) en zetten we `laatste_zoektocht_afgebroken`, zodat de
        aanroeper het verschil kan uitleggen tussen "bestaat niet" en "niet binnen de tijd
        gevonden". Met een `datum` is de eerste of tweede probe meestal raak en speelt het
        budget geen rol. `tijdsbudget_s=None` schakelt de begrenzing uit (voor batchgebruik
        buiten een MCP-client: geef `tijdsbudget_s=math.inf`).

        ECLI wordt (nog) niet ondersteund: de DBRC-PDF-naamgeving is niet uit een ECLI af te
        leiden en de ECLI-zoekfunctie loopt via het verboden zoek-endpoint. [TE VERIFIËREN]
        """
        self.laatste_zoektocht_afgebroken = False
        aid = parse_arrestnummer(identifier) or parse_filename(identifier)
        if aid is None:
            return []
        budget = self._tijdsbudget_s if tijdsbudget_s is None else tijdsbudget_s
        start = time.monotonic()
        for i, url in enumerate(_pdf_kandidaten(aid, anchor=datum, venster_maanden=venster_maanden)):
            # De eerste probe loopt altijd; daarna stoppen we zodra de volgende probe —
            # crawl-delay inbegrepen — het budget zou overschrijden.
            if i and time.monotonic() - start + self._rate_limit_s > budget:
                self.laatste_zoektocht_afgebroken = True
                break
            self._wacht()
            if self._bestaat(url):
                return [
                    Treffer(
                        bron="dbrc",
                        instantie=aid.instantie,
                        titel=aid.arrestnummer,
                        datum=None,
                        ecli=None,
                        rolnummer=aid.arrestnummer,
                        snippet=None,
                        url=url,
                    )
                ]
        return []

    def haal_uitspraak(self, url: str) -> Uitspraak | None:
        """Haal de arrest-PDF op via de bron-URL en extraheer de tekstlaag (pdfplumber).

        Anti-hallucinatie: `Uitspraak.tekst` is letterlijk wat uit de PDF-tekstlaag
        komt (pdf_naar_tekst). Lukt de extractie niet (corrupte of gescande PDF),
        dan volgt een eerlijke notitie met verwijzing naar de bron-URL — nooit een
        verzonnen of aangevulde arresttekst.
        """
        if not url.startswith(f"{PDF_BASE}/"):
            return None
        aid = parse_filename(url)
        self._wacht()
        try:
            r = self._client.get(url)
            r.raise_for_status()
        except httpx.HTTPError:
            return None
        treffer = Treffer(
            bron="dbrc",
            instantie=aid.instantie if aid else self.instantie,
            titel=aid.arrestnummer if aid else url.rsplit("/", 1)[-1],
            rolnummer=aid.arrestnummer if aid else None,
            url=url,
        )
        tekst = pdf_naar_tekst(r.content)
        if tekst is None:
            tekst = (
                f"[PDF opgehaald ({len(r.content)} bytes), maar tekstextractie mislukte — "
                f"raadpleeg de bron-URL rechtstreeks.]"
            )
        return Uitspraak(treffer=treffer, tekst=tekst)

    # -- intern ----------------------------------------------------------------------------
    def _bestaat(self, url: str) -> bool:
        try:
            r = self._client.head(url)
            return r.status_code == 200
        except httpx.HTTPError:
            return False
