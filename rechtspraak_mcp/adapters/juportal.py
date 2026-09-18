# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Adapter voor Juportal (juportal.be), de federale openbare rechtspraakdatabank.

Concept-implementatie. Haalbaarheid: 🟠 oranje — zie docs/bronnenonderzoek.md, sectie 2.

TECHNISCHE VONDST (live geverifieerd op 2026-08-03): de ECLI-deeplink
``https://juportal.be/content/<ECLI>`` is — anders dan het zoekformulier — VOLLEDIG
server-rendered (PHP, geen JS-shell). De pagina bevat gestructureerde metadata (ECLI,
rolnummer, zaaknaam, kamer, rechtsgebied, invoerdatum), de datum in de fieldset-legend
("Vonnis/arrest van 30 oktober 2020"), één of meer samenvattingsfiches, de integrale
tekst van de beslissing en een PDF-link. Let op: de CSS-klassenamen zijn geobfusceerd
(prefix ``TUDUZTZH...``) en vermoedelijk niet stabiel; de parsers hieronder werken daarom
uitsluitend op labels en documentstructuur.

ROBOTS-VONDST (live gecontroleerd op 2026-08-03 op juportal.be ÉN juportal.just.fgov.be):

    User-agent: DG_JUSTICE_CRAWLER
    Allow: /
    User-agent: *
    Disallow: /

Alles is dus verboden voor generieke bots; alleen de eigen justitie-crawler mag (er staan
wel publieke sitemaps onder https://juportal.just.fgov.be/JUPORTAsitemap/...). Gevolg voor
het ontwerp (consistent met het DBRC-precedent in dbrc.py): automatisch ophalen staat
STANDAARD UIT via ``sta_fetch = False``. Met de vlag uit geven ``zoek``,
``zoek_op_identifier`` en ``haal_uitspraak`` een lege lijst / None terug — anti-hallucinatie:
we geven géén onbevestigde deeplink als Treffer terug, want dan zouden we een treffer
suggereren die niet effectief van de bron komt. De pure functie ``content_deeplink()``
bouwt wel altijd de URL (zonder netwerk), zodat de gebruiker die handmatig kan openen.

Wie de vlag bewust aanzet (eigen keuze en verantwoordelijkheid van de gebruiker, bv. voor
incidentele raadpleging van individuele ECLI's) krijgt nette requests: identificeerbare
User-Agent met contactvermelding, conservatieve rate limiting (10 s, zoals bij DBRC),
korte timeouts en een injecteerbare httpx.Client (voor MockTransport in tests).

JURIDISCH: de gebruiksvoorwaarden van FOD Justitie zijn gunstig (onvoorwaardelijk
hergebruik, ook commercieel; zie bronnenonderzoek). MAAR: de HTML van de content-pagina
zelf bevat een copyrightvermelding "Copyright (c) 2017-2026 FOD Justitie - alle rechten
voorbehouden. Elke reproductie, zelfs gedeeltelijk, is verboden." en de eigen
Juportal-disclaimer (juportal.be/home/disclaimer) blijft [TE VERIFIËREN]. Link daarom
steeds terug naar de bron-URL en vermeld bron en datum.

ZOEKRESULTATEN (live vastgesteld op 2026-08-09): de resultatenpagina
(``/zoekmachine/zoekresultaten``) wordt door de JS-front-end gerenderd tot een gewone
HTML-tabel. Per uitspraak staan er meerdere links ``a[href*='/content/ECLI...']`` (de
hoofdlink plus ``#text``- en ``#notice``-ankers), met in de href een ``/NL``-taalsuffix
en een sessiegebonden ``?HiLi=``-highlightparameter. Naast de hoofdlink staat een
metadataregel "Instantie - datum - rolnummer"; bij het ``#notice1``-anker staat de
samenvatting van Fiche 1. ``parse_juportal_zoekresultaten()`` parseert die structuur
puur (zonder I/O); de HTML zelf komt — opt-in — van een geïnjecteerde ``BrowserZoeker``
(zie ``browser_zoek.py``), want een gewone HTTP-fetch rendert de SPA niet.
"""
from __future__ import annotations

import re
import time
from datetime import date
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup, Tag

from .base import RechtspraakAdapter
from ..schema import Treffer, Uitspraak, ZoekQuery
from .. import user_agent

if TYPE_CHECKING:  # enkel voor type-hints: geen runtime-koppeling met browser_zoek
    from ..browser_zoek import BrowserZoeker

BASE = "https://juportal.be"
CONTENT_URL = f"{BASE}/content/{{ecli}}"
ZOEK_URL = f"{BASE}/zoekmachine/zoekformulier"

#: Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt.
USER_AGENT = user_agent("incidentele raadpleging met expliciete gebruikersvlag")
#: Conservatieve rate limit tussen opeenvolgende requests (zelfde keuze als DBRC).
CRAWL_DELAY_S = 10.0
#: Korte timeouts.
TIMEOUT_S = 10.0

# ECLI-formaat: ECLI:BE:<instantiecode>:<jaar>:<volgnummer>
# bv. ECLI:BE:CASS:2020:ARR.20201030.1N.4 — het volgnummer mag punten bevatten.
_ECLI_RE = re.compile(r"^ECLI:BE:[A-Z][A-Z0-9]{0,6}:\d{4}:[A-Z0-9][A-Z0-9.\-]{0,30}$")

# Content-URL zoals wij die bouwen of zoals Juportal ze linkt (evt. met /NL of /FR-suffix).
_CONTENT_URL_RE = re.compile(
    r"^https://(?:juportal\.be|juportal\.just\.fgov\.be)/content/"
    r"(?P<ecli>ECLI:BE:[^/]+)(?:/(?P<taal>[A-Z]{2}))?$"
)

# Datum in de fieldset-legend, bv. "Vonnis/arrest van 30 oktober 2020".
_LEGEND_DATUM_RE = re.compile(r"van\s+(\d{1,2})\s+([a-zéû]+)\s+(\d{4})", re.IGNORECASE)
_MAANDEN_NL = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}

# -- zoekresultatenpagina (zoekmachine/zoekresultaten) ------------------------------------
# ECLI in een resultaat-href, bv. /content/ECLI:BE:RVSCE:2016:ARR.233.796/NL?HiLi=...#text
# — stopt vóór het /NL-taalsuffix, de HiLi-query en het fragment.
_ZOEK_HREF_RE = re.compile(r"/content/(?P<ecli>ECLI:BE:[^/?#]+)")

# Metadataregel naast de hoofdlink: "Hof van Cassatie - 15 juni 2000 - C.96.0451.N" of
# "Raad van State - 11 februari 2016 - A. 213337/VII-39195".
_RESULTAAT_REGEL_RE = re.compile(
    r"^(?P<instantie>.+?)\s+-\s+(?P<dag>\d{1,2})\s+(?P<maand>[a-zéû]+)\s+(?P<jaar>\d{4})"
    r"\s+-\s+(?P<rolnummer>.+)$",
    re.IGNORECASE,
)

# Cassatie-rolnummer (AR): letter, punt, 2 cijfers, punt, 4 cijfers, punt, taalletter.
_CASSATIE_ROLNUMMER_RE = re.compile(r"^[A-Z]\.\d{2}\.\d{4}\.[A-Z]$")

#: Instantienaam per ECLI-instantiecode. Alleen wat vaststaat; onbekende codes vallen
#: terug op de generieke Juportal-noemer (anti-hallucinatie: niets erbij verzinnen).
_INSTANTIE_PER_ECLI_CODE = {
    "CASS": "Hof van Cassatie",
    "GHCC": "Grondwettelijk Hof",
    "RVSCE": "Raad van State",
    # Hoven van beroep (Nederlandstalige en Franstalige codes), vastgesteld in Juportal-resultaten.
    "HBANT": "Hof van beroep Antwerpen",
    "HBGNT": "Hof van beroep Gent",
    "HBBRL": "Hof van beroep Brussel",
    "CABRL": "Hof van beroep Brussel",
    "CALIE": "Hof van beroep Luik",
    "CAMON": "Hof van beroep Bergen",
}


def normaliseer_ecli(identifier: str) -> str | None:
    """Normaliseer een ECLI-string (trim + hoofdletters) en valideer het formaat.

    Geeft de genormaliseerde ECLI terug, of None wanneer de input geen geldige
    Belgische ECLI is (``ECLI:BE:<code>:<jaar>:<rest>``). Puur, geen I/O.
    """
    kandidaat = identifier.strip().upper()
    if _ECLI_RE.match(kandidaat):
        return kandidaat
    return None


def content_deeplink(ecli: str) -> str:
    """Bouw de stabiele content-deeplink voor een ECLI. Puur: doet GEEN netwerkverkeer.

    Bedoeld om de gebruiker een handmatig te openen URL te geven, ook wanneer
    automatisch ophalen uit staat (robots.txt). Heft ValueError op bij een ongeldige ECLI.
    """
    genorm = normaliseer_ecli(ecli)
    if genorm is None:
        raise ValueError(f"Geen geldige Belgische ECLI: {ecli!r}")
    return CONTENT_URL.format(ecli=genorm)


def _tekst(node: Tag | None) -> str:
    """Genormaliseerde tekst van een node: whitespace samengevouwen, of ''."""
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _metadata_tabel(soup: BeautifulSoup) -> dict[str, str]:
    """Lees de label→waarde-rijen van de metadatatabel (labels eindigen op ':')."""
    velden: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        cellen = tr.find_all("td")
        if len(cellen) != 2:
            continue
        label = _tekst(cellen[0]).rstrip(":").strip()
        waarde = _tekst(cellen[1])
        if label and waarde and label not in velden:
            velden[label] = waarde
    return velden


def _parse_legend_datum(soup: BeautifulSoup) -> tuple[str | None, date | None]:
    """Vind de eerste legend met een datum ("Vonnis/arrest van 30 oktober 2020").

    Geeft (legendtekst, datum) terug; datum is None wanneer de maand niet herkend wordt
    (we parsen de NL-versie van de pagina; Nederlandse maandnamen).
    """
    for legend in soup.find_all("legend"):
        tekst = _tekst(legend)
        m = _LEGEND_DATUM_RE.search(tekst)
        if not m:
            continue
        maand = _MAANDEN_NL.get(m.group(2).lower())
        if maand is None:
            return tekst, None
        try:
            return tekst, date(int(m.group(3)), maand, int(m.group(1)))
        except ValueError:
            return tekst, None
    return None, None


def _fiche_samenvatting(soup: BeautifulSoup) -> str | None:
    """Tekst van de eerste samenvattingsfiche (fieldset met legend 'Fiche ...'), of None."""
    for fieldset in soup.find_all("fieldset"):
        legend = fieldset.find("legend")
        if legend is None or not _tekst(legend).startswith("Fiche"):
            continue
        div = fieldset.find("div")
        samenvatting = _tekst(div)
        if samenvatting:
            return samenvatting
    return None


def parse_content_pagina(html: str, url: str) -> Treffer | None:
    """Puur: parse de HTML van een /content/<ECLI>-pagina naar één Treffer.

    Geeft None terug wanneer de pagina geen herkenbare uitspraak bevat (bv. een lege
    of foutpagina) — anti-hallucinatie: zonder ECLI in de respons geen treffer. Werkt
    uitsluitend op labels/structuur, niet op de (geobfusceerde, wellicht instabiele)
    CSS-klassenamen. Geen netwerk-I/O; los te testen op een fixture.
    """
    soup = BeautifulSoup(html, "html.parser")
    velden = _metadata_tabel(soup)

    ecli = normaliseer_ecli(velden.get("ECLI nr", ""))
    if ecli is None:
        # Terugval: de <title> van de pagina is de ECLI.
        ecli = normaliseer_ecli(_tekst(soup.find("title")))
    if ecli is None:
        return None

    # Instantie zoals de bron ze zelf vermeldt (meta author, bv. "Hof van Cassatie").
    instantie = ""
    meta_author = soup.find("meta", attrs={"name": "author"})
    if isinstance(meta_author, Tag):
        instantie = re.sub(r"\s+", " ", str(meta_author.get("content") or "")).strip()
    if not instantie:
        instantie = "Juportal (federale rechtspraak)"

    legend_tekst, datum = _parse_legend_datum(soup)
    zaak = velden.get("Zaak")
    if legend_tekst and zaak:
        titel = f"{instantie}, {legend_tekst.lower()} — {zaak}"
    elif legend_tekst:
        titel = f"{instantie}, {legend_tekst.lower()}"
    else:
        titel = ecli

    return Treffer(
        bron="juportal",
        instantie=instantie,
        titel=titel,
        datum=datum,
        ecli=ecli,
        rolnummer=velden.get("Rolnummer"),
        snippet=_fiche_samenvatting(soup),
        url=url,
    )


def parse_uitspraak_tekst(html: str) -> str:
    """Puur: extraheer de integrale tekst uit de fieldset 'Tekst van de beslissing'.

    Geeft de alinea's als regels terug (één per <p>), of '' wanneer de fieldset ontbreekt.
    De PDF-link onder de tekst (buiten de tekst-div) wordt niet meegenomen.
    """
    soup = BeautifulSoup(html, "html.parser")
    for fieldset in soup.find_all("fieldset"):
        legend = fieldset.find("legend")
        if legend is None or "Tekst van de beslissing" not in _tekst(legend):
            continue
        div = fieldset.find("div")
        if div is None:
            return ""
        alineas = [_tekst(p) for p in div.find_all("p")]
        return "\n".join(a for a in alineas if a)
    return ""


def is_cassatie_rolnummer(identifier: str) -> bool:
    """Herken een rolnummer (AR) van het Hof van Cassatie, bv. 'P.20.0693.N'.

    Patroon: zaakletter, punt, twee cijfers (jaar), punt, vier cijfers (volgnummer),
    punt, taalletter (N/F) — bv. C.19.0132.N of F.08.0035.F. Hoofdletterongevoelig.
    Puur, geen I/O.
    """
    return _CASSATIE_ROLNUMMER_RE.match(identifier.strip().upper()) is not None


def _instantie_uit_ecli(ecli: str) -> str:
    """Leid de instantienaam af uit de ECLI-instantiecode (bv. RVSCE -> Raad van State).

    Onbekende codes vallen terug op de generieke noemer 'Juportal (federale rechtspraak)'.
    """
    delen = ecli.split(":")
    code = delen[2] if len(delen) > 2 else ""
    return _INSTANTIE_PER_ECLI_CODE.get(code, "Juportal (federale rechtspraak)")


def _resultaat_metadataregel(hoofdlink: Tag) -> str | None:
    """De metadataregel ('Instantie - datum - rolnummer') in de cel van de hoofdlink.

    De regel staat in een <span> naast (niet binnen) de <a>; de span mét de ECLI-
    highlight zit binnen de <a> en wordt dus overgeslagen. Klassenamen zijn
    geobfusceerd en worden bewust niet gebruikt. Geeft None wanneer er niets staat.
    """
    td = hoofdlink.find_parent("td")
    if td is None:
        return None
    for span in td.find_all("span"):
        if span.find_parent("a") is not None:
            continue
        tekst = _tekst(span)
        if tekst:
            return tekst
    return None


def _resultaat_fichetekst(fichelink: Tag) -> str | None:
    """De samenvatting van de fiche naast een '#notice'-anker (zelfde tabelrij).

    Neemt de tekst van de overige cellen in de rij (de cel met het anker zelf niet).
    Geeft None wanneer er geen tekst staat — anti-hallucinatie: geen lege snippet
    opdikken.
    """
    tr = fichelink.find_parent("tr")
    if tr is None:
        return None
    eigen_td = fichelink.find_parent("td")
    delen = []
    for td in tr.find_all("td"):
        if td is eigen_td:
            continue
        tekst = _tekst(td)
        if tekst:
            delen.append(tekst)
    samenvatting = " ".join(delen).strip()
    return samenvatting or None


def parse_juportal_zoekresultaten(html: str) -> list[Treffer]:
    """Puur: parse de gerenderde resultatenpagina (zoekmachine/zoekresultaten) naar Treffers.

    Structuur (live vastgesteld 2026-08-09, zie moduledocstring): per uitspraak meerdere
    ``a[href*='/content/ECLI...']``-links (hoofdlink + ``#text``/``#notice``-ankers).
    Er wordt GEDEDUPLICEERD per ECLI, in documentvolgorde. Per unieke uitspraak:

    * ``ecli``: zuiver, zonder ``/NL``-taalsuffix en zonder ``?HiLi=``-query;
    * ``url``: de canonieke content-deeplink (níet de sessiegebonden HiLi-URL);
    * ``instantie``: afgeleid uit de ECLI-instantiecode (:data:`_INSTANTIE_PER_ECLI_CODE`);
    * ``titel``: de metadataregel zoals de bron die toont ('Instantie - datum -
      rolnummer'), of de ECLI wanneer die regel ontbreekt;
    * ``datum``/``rolnummer``: uit die metadataregel, alléén wanneer die volledig en
      herkenbaar parseert (Nederlandse maandnamen) — anders None;
    * ``snippet``: de samenvatting van de eerste fiche (``#notice1``), of None.

    Geen netwerk-I/O; los te testen op een fixture. Een pagina zonder resultaatlinks
    geeft een lege lijst — er wordt niets verzonnen.
    """
    soup = BeautifulSoup(html, "html.parser")
    volgorde: list[str] = []
    per_ecli: dict[str, dict[str, str | None]] = {}

    for a in soup.find_all("a", href=True):
        m = _ZOEK_HREF_RE.search(str(a["href"]))
        if m is None:
            continue
        ecli = normaliseer_ecli(m.group("ecli"))
        if ecli is None:
            continue
        href = str(a["href"])
        fragment = href.split("#", 1)[1] if "#" in href else ""
        if ecli not in per_ecli:
            volgorde.append(ecli)
            per_ecli[ecli] = {"regel": None, "snippet": None}
        gegevens = per_ecli[ecli]
        if not fragment and gegevens["regel"] is None:
            gegevens["regel"] = _resultaat_metadataregel(a)
        elif fragment.startswith("notice") and gegevens["snippet"] is None:
            gegevens["snippet"] = _resultaat_fichetekst(a)

    treffers: list[Treffer] = []
    for ecli in volgorde:
        gegevens = per_ecli[ecli]
        regel = gegevens["regel"]
        datum: date | None = None
        rolnummer: str | None = None
        if regel:
            m = _RESULTAAT_REGEL_RE.match(regel)
            if m:
                maand = _MAANDEN_NL.get(m.group("maand").lower())
                if maand is not None:
                    try:
                        datum = date(int(m.group("jaar")), maand, int(m.group("dag")))
                    except ValueError:
                        datum = None
                rolnummer = m.group("rolnummer").strip() or None
        treffers.append(
            Treffer(
                bron="juportal",
                instantie=_instantie_uit_ecli(ecli),
                titel=regel or ecli,
                datum=datum,
                ecli=ecli,
                rolnummer=rolnummer,
                snippet=gegevens["snippet"],
                url=content_deeplink(ecli),
            )
        )
    return treffers


class JuportalAdapter(RechtspraakAdapter):
    bron = "juportal"
    instantie = "Juportal (federale rechtspraak)"
    enabled = True

    #: Automatisch ophalen staat STANDAARD UIT: robots.txt van juportal.be en
    #: juportal.just.fgov.be disallowt alles voor generieke bots (gecontroleerd 2026-08-03,
    #: zie moduledocstring). Alleen bewust aanzetten; de adapter geeft anders lege
    #: resultaten terug en verzint géén treffers. Gebruik content_deeplink() voor een
    #: handmatig te openen URL.
    sta_fetch: bool = False

    #: Browser-gedreven vrij zoeken (opt-in, zie browser_zoek.py) staat STANDAARD UIT.
    #: Alleen met deze vlag aan ÉN een via de constructor geïnjecteerde BrowserZoeker
    #: doet ``zoek`` (en het rolnummerpad van ``zoek_op_identifier``) iets. Bot-
    #: challenges worden nooit omzeild: BotdetectieError geeft een leeg resultaat.
    browser_zoek_aan: bool = False

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        rate_limit_s: float = CRAWL_DELAY_S,
        zoeker: BrowserZoeker | None = None,
    ):
        self._eigen_client = client is None
        self._client = client or httpx.Client(
            timeout=TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._rate_limit_s = rate_limit_s
        self._laatste_request: float = 0.0
        self._zoeker = zoeker

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
        """Vrije-tekstzoekopdracht via de opt-in browser-aandrijving (browser_zoek.py).

        Werkt UITSLUITEND wanneer ``browser_zoek_aan`` aanstaat ÉN er een
        ``BrowserZoeker`` via de constructor is geïnjecteerd; anders (standaard) is het
        resultaat [] — het zoekformulier is een JS-front-end die een gewone HTTP-fetch
        niet rendert, en robots.txt raadt de zoek-endpoints af (bewuste gebruikerskeuze,
        zie browser_zoek.py). Bot-challenges worden nooit omzeild: bij
        ``BotdetectieError`` (of een andere ``ZoekError``) is het resultaat eveneens []
        — er worden géén treffers verzonnen.
        """
        if not (self.browser_zoek_aan and self._zoeker is not None):
            return []
        html = self._browser_zoek_html(
            query.query, max_resultaten=query.max_resultaten, veld="tekst"
        )
        if html is None:
            return []
        return parse_juportal_zoekresultaten(html)[: query.max_resultaten]

    def zoek_op_identifier(self, identifier: str, datum: date | None = None) -> list[Treffer]:
        """Zoek één uitspraak op ECLI (content-deeplink) of op Cassatie-rolnummer (AR).

        ECLI-pad (ongewijzigd): valideert eerst het ECLI-formaat
        (``ECLI:BE:<code>:<jaar>:<rest>``). Met ``sta_fetch = False`` (standaard, wegens
        robots.txt) wordt er niets opgehaald en is het resultaat [] — er wordt géén
        onbevestigde deeplink als Treffer teruggegeven. Met de vlag aan wordt de
        content-pagina net opgehaald en naar één Treffer geparset.

        Rolnummerpad (nieuw): een Cassatie-rolnummer zoals ``P.20.0693.N`` is geen ECLI
        en heeft dus geen deeplink; het wordt — enkel met ``browser_zoek_aan`` aan én
        een geïnjecteerde ``BrowserZoeker`` — via het zoekformulier (veld 'rolnummer')
        opgezocht en uit de resultatenpagina geparset. Browser-fouten (botdetectie,
        renderfout) vallen terug op het bestaande gedrag: [].
        """
        ecli = normaliseer_ecli(identifier)
        if ecli is not None:
            if not self.sta_fetch:
                return []
            url = content_deeplink(ecli)
            html = self._get(url)
            if html is None:
                return []
            treffer = parse_content_pagina(html, url)
            return [treffer] if treffer is not None else []
        if is_cassatie_rolnummer(identifier) and self.browser_zoek_aan and self._zoeker is not None:
            zoek_html = self._browser_zoek_html(
                identifier.strip().upper(), max_resultaten=20, veld="rolnummer"
            )
            if zoek_html is not None:
                return parse_juportal_zoekresultaten(zoek_html)
        return []

    def haal_uitspraak(self, url: str) -> Uitspraak | None:
        """Haal de integrale tekst van één uitspraak op via de content-URL.

        Accepteert uitsluitend Juportal-content-URL's
        (``https://juportal.be/content/<ECLI>[/NL|/FR]``). Met ``sta_fetch = False``
        (standaard, wegens robots.txt) wordt er niets opgehaald en is het resultaat None.
        """
        if not _CONTENT_URL_RE.match(url):
            return None
        if not self.sta_fetch:
            return None
        html = self._get(url)
        if html is None:
            return None
        treffer = parse_content_pagina(html, url)
        if treffer is None:
            return None
        tekst = parse_uitspraak_tekst(html)
        if not tekst:
            tekst = (
                "[Geen tekstblok 'Tekst van de beslissing' aangetroffen op de content-pagina; "
                "raadpleeg de bron-URL rechtstreeks.]"
            )
        return Uitspraak(treffer=treffer, tekst=tekst)

    # -- intern ----------------------------------------------------------------------------
    def _browser_zoek_html(self, zoekterm: str, *, max_resultaten: int, veld: str) -> str | None:
        """Gerenderde resultaten-HTML via de geïnjecteerde BrowserZoeker, of None bij fout.

        Het ``veld``-keyword ("tekst"/"rolnummer") kiest het formulierveld waarin de
        zoekterm wordt ingevuld. De fouttypes worden lokaal geïmporteerd zodat er geen
        harde koppeling (of importcyclus) tussen de adapter en browser_zoek ontstaat.
        Bot-challenges worden nooit omzeild: elke ZoekError geeft eerlijk None terug.
        """
        if self._zoeker is None:
            return None
        from ..browser_zoek import BotdetectieError, ZoekError

        try:
            return self._zoeker.haal_zoekpagina_html(
                "juportal", zoekterm, max_resultaten=max_resultaten, veld=veld
            )
        except (BotdetectieError, ZoekError):
            return None

    def _get(self, url: str) -> str | None:
        self._wacht()
        try:
            r = self._client.get(url)
            r.raise_for_status()
        except httpx.HTTPError:
            return None
        return r.text
