# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Wetgevingsadapter voor Justel (ejustice.just.fgov.be, Belgische federale databank).

Concept-implementatie naar het patroon van adapters/juportal.py (robots-restrictieve
bron): pure deeplink-bouwers en parsers los van I/O, injecteerbare httpx.Client, nette
rate limiting (10 s), identificeerbare User-Agent, en automatisch ophalen STANDAARD UIT.

ROBOTS-VONDST (live gecontroleerd op 2026-08-09 op www.ejustice.just.fgov.be/robots.txt):
voor ``User-agent: *`` zijn o.m. disallowed: ``/eli/``, ``/eli_cgi/``, ``/cgi_loi/``,
``/cgi_wet/``, ``/loi/``, ``/wet/``, ``/mopdf/`` — alle wetgevingspaden dus. Gevolg
(consistent met Juportal en RvS): ``sta_fetch = False`` standaard; met de vlag uit geven
``zoek_op_identifier`` en ``haal_norm`` een leeg resultaat terug en wordt er niets
opgehaald. De pure deeplink-bouwers (``eli_deeplink``, ``zoek_deeplink``) blijven altijd
bruikbaar, zodat de gebruiker de URL handmatig kan openen.

JURIDISCHE DUIDING: op officiële akten van de overheid rust geen auteursrecht
(artikel XI.172, § 2 WER) en de gebruiksvoorwaarden van de FOD Justitie zijn ruim (zie
docs/bronnen-gebruiksvoorwaarden.md). Het robots-verbod is dus een technisch signaal van
de beheerder, geen hergebruiksverbod; wie ``sta_fetch`` bewust aanzet (incidentele
raadpleging van individuele ELI's) maakt die afweging zelf. Deze adapter blijft dan nog
steeds netjes: herkenbare User-Agent met contact, 10 s tussen requests, korte timeouts.

ELI-STRUCTUUR (vastgesteld op 2026-08-09 via de officiële ELI-helppagina die ejustice
zelf toont bij een resultaatloze ELI-opzoeking, plus twee verificatie-fetches):

* Vorm: ``https://www.ejustice.just.fgov.be/eli/<DT>/<JJJJ>/<MM>/<DD>/<numac>/<versie>``.
* Geldige documenttypes ``<DT>`` volgens de helppagina: GRONDWET, WET (federaal),
  DECREET (regionaal/communautair, vanaf 1972), ORDONNANTIE (Brussel, vanaf 1990) en
  BESLUIT (secundaire wetgeving: KB's, besluiten van regeringen, MB's). Kleine letters
  werken (live bevestigd voor ``wet`` en ``decreet``).
* De unieke identificatiecode is het numac: 10 tekens, beginnend met het jaar van
  indiening ter publicatie, gevolgd door het werknummer. De helppagina zegt "10 cijfers",
  maar er bestaan numac's met een hoofdletter op positie 5 (bv. ``2016A03340``); die
  aanvaarden we dus ook.
* Versies: ``staatsblad`` (originele tekstversie BS, met link naar de publicatie-PDF) en
  ``justel`` (officieuze geconsolideerde versie). Zonder versie toont de pagina alleen de
  titel; zonder numac een lijst per datum.
* Een onbekende of onvolledige combinatie geeft GEEN 404 maar HTTP 200 met de
  ELI-helppagina ("Sorry, de opzoeking ... heeft geen resultaat opgeleverd");
  ``parse_eli_pagina`` herkent dat en geeft dan None terug (anti-hallucinatie).

SERVER-RENDERED op de ``/justel``-versie (live geverifieerd 2026-08-09 op
``/eli/wet/2016/04/22/2016003166/justel``, zie tests/fixtures/justel_eli_wet_*.html):

* het numac in ``span.tag`` en het opschrift mét datumprefix ("22 APRIL 2016. - Wet
  tot omzetting van ...") in ``p.list-item--title``;
* een metadatablok (``div.plain-text``) met label→waarde-paren: Bron (departement),
  Publicatie (BS-datum), Nummer (numac), bladzijde, Dossiernummer, Inwerkingtreding,
  en links naar gewijzigde teksten;
* de inhoudstafel (``h2#inhoud``), de INTEGRALE geconsolideerde tekst (``h2#text``),
  parlementaire werkzaamheden, handtekening en aanhef — alles server-rendered HTML
  (geen JS-shell); de pagina is ISO-8859-1-gecodeerd (meta charset);
* de canonieke ELI-link (``a#link-text``) en een link naar de BS-publicatie-PDF
  (``/mopdf/...``, eveneens robots-disallowed).

BEPERKING numac-zonder-ELI: uit een kaal numac alleen valt de ELI-URL niet af te leiden
(type en afkondigingsdatum ontbreken) en de omweg loopt via de disallowde
``/cgi_loi/``-zoekfunctie. ``zoek_op_identifier`` geeft bij een kaal numac daarom [] terug;
de server kan de gebruiker naar ``zoek_deeplink()`` verwijzen. Vrije-tekstzoeken idem:
het Justel-zoekformulier is een formulier op een disallowed pad — ``zoek`` geeft altijd
[] en ``zoek_deeplink()`` levert de handmatig te openen formulierpagina.
"""
from __future__ import annotations

import re
import time
from datetime import date

import httpx
from bs4 import BeautifulSoup, Tag

from .base import WetgevingAdapter
from ..schema import Norm, NormTekst
from .. import user_agent

BASE = "https://www.ejustice.just.fgov.be"
#: ELI-deeplink: type/jaar/maand/dag/numac/versie (zie moduledocstring).
ELI_SJABLOON = BASE + "/eli/{type}/{jjjj:04d}/{mm:02d}/{dd:02d}/{numac}/{versie}"
#: Publiek zoekformulier van de Justel-databank (menulink op de ELI-pagina zelf,
#: vastgesteld 2026-08-09). Handmatig te openen; het pad is robots-disallowed voor bots.
ZOEK_URL = BASE + "/cgi_loi/welcome.pl?language=nl"

#: Geldige ELI-documenttypes volgens de officiële helppagina (2026-08-09).
ELI_TYPES = ("grondwet", "wet", "decreet", "ordonnantie", "besluit")
#: Geldige tekstversies in het laatste ELI-segment.
ELI_VERSIES = ("justel", "staatsblad")

#: Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt.
USER_AGENT = user_agent("incidentele raadpleging met expliciete gebruikersvlag")
#: Conservatieve rate limit tussen opeenvolgende requests (zelfde keuze als Juportal/DBRC).
CRAWL_DELAY_S = 10.0
#: Korte timeouts.
TIMEOUT_S = 10.0

#: Vroegst plausibele numac-jaar (oudste Justel-teksten: Burgerlijk Wetboek, 1804).
_NUMAC_JAAR_MIN = 1789

# Numac: 4-cijferig jaar + 6 tekens werknummer; positie 5 mag een hoofdletter zijn
# (bv. 2016A03340). Zie de moduledocstring.
_NUMAC_RE = re.compile(r"^\d{4}[0-9A-Z]\d{5}$")

# ELI-URL van ejustice, met volledige datum en numac (identificeert precies één norm);
# lijst-URL's zonder numac vallen er bewust buiten. Versie optioneel.
_ELI_URL_RE = re.compile(
    r"^https?://(?:www\.)?ejustice\.just\.fgov\.be/eli/"
    r"(?P<type>[a-z]+)/(?P<jjjj>\d{4})/(?P<mm>\d{1,2})/(?P<dd>\d{1,2})/"
    r"(?P<numac>[0-9A-Za-z]{10})"
    r"(?:/(?P<versie>justel|staatsblad))?/?$",
    re.IGNORECASE,
)

#: NL-maandnamen voor de datumprefix van het opschrift ("22 APRIL 2016. - Wet ...").
_MAANDEN_NL = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}
_OPSCHRIFT_DATUM_RE = re.compile(
    r"^(\d{1,2})\s+(" + "|".join(_MAANDEN_NL) + r")\s+(\d{4})\s*\.?\s*[-–]\s*",
    re.IGNORECASE,
)

# Aard van de norm zoals het opschrift ze zelf noemt (rijker dan het ELI-type: het
# ELI-type 'besluit' dekt zowel KB's als MB's als regeringsbesluiten). Langste eerst;
# \b voorkomt dat "Wetboek ..." als "wet" wordt gelezen. Geen match -> ELI-type uit
# de URL (anti-hallucinatie: we raden niet).
_AARD_IN_OPSCHRIFT_RE = re.compile(
    r"^(besluit van de vlaamse regering|koninklijk besluit|ministerieel besluit|"
    r"bijzondere wet|grondwet|wet|decreet|ordonnantie|besluit)\b",
    re.IGNORECASE,
)

#: Herkenning van de ELI-helppagina (HTTP 200 zonder resultaat, zie moduledocstring).
#: parse_eli_pagina heeft de marker niet nodig (geen numac/opschrift -> None), maar de
#: server kan er desgewenst "geen resultaat" mee onderscheiden van een structuurwijziging.
HELPPAGINA_MARKER = "heeft geen resultaat opgeleverd"


# ---------------------------------------------------------------------------------------
# Pure functies: numac, deeplinks en ELI-URL-parsing (geen netwerk-I/O)
# ---------------------------------------------------------------------------------------
def is_numac(s: str) -> bool:
    """Herken een numac (uniek publicatienummer BS): 10 tekens, jaar + werknummer.

    Vorm: 4-cijferig jaar (plausibel: 1789 t.e.m. volgend jaar) + 6 tekens werknummer,
    waarvan het eerste teken een cijfer of een hoofdletter mag zijn (bv. '2016003166',
    '2016A03340'). Hoofdletterongevoelig, trimt witruimte. Puur, geen I/O.
    """
    kandidaat = s.strip().upper()
    if not _NUMAC_RE.match(kandidaat):
        return False
    return _NUMAC_JAAR_MIN <= int(kandidaat[:4]) <= date.today().year + 1


def eli_deeplink(type_: str, datum: date, numac: str, *, versie: str = "justel") -> str:
    """Bouw de ELI-deeplink voor één norm. Puur: doet GEEN netwerkverkeer.

    ``type_`` moet een geldig ELI-documenttype zijn (zie :data:`ELI_TYPES`), ``datum``
    de afkondigingsdatum, ``numac`` een geldig numac en ``versie`` 'justel'
    (geconsolideerd, standaard) of 'staatsblad' (originele BS-tekst). ValueError bij
    ongeldige invoer. Bedoeld om de gebruiker een handmatig te openen URL te geven,
    ook wanneer automatisch ophalen uit staat (robots.txt).
    """
    type_norm = type_.strip().lower()
    if type_norm not in ELI_TYPES:
        raise ValueError(f"Geen geldig ELI-documenttype: {type_!r} (geldig: {ELI_TYPES})")
    if not is_numac(numac):
        raise ValueError(f"Geen geldig numac: {numac!r}")
    if versie not in ELI_VERSIES:
        raise ValueError(f"Geen geldige ELI-versie: {versie!r} (geldig: {ELI_VERSIES})")
    return ELI_SJABLOON.format(
        type=type_norm, jjjj=datum.year, mm=datum.month, dd=datum.day,
        numac=numac.strip().upper(), versie=versie,
    )


def parse_eli_url(url: str) -> tuple[str, date, str] | None:
    """Puur: lees (type, datum, numac) uit een ejustice-ELI-URL, of None.

    Aanvaardt http(s), met of zonder www, met of zonder versiesegment
    (justel/staatsblad). Lijst-URL's zonder numac, andere hosts, ongeldige types,
    onmogelijke datums en misvormde numacs geven None. Puur, geen I/O.
    """
    m = _ELI_URL_RE.match(url.strip())
    if m is None:
        return None
    type_norm = m.group("type").lower()
    if type_norm not in ELI_TYPES:
        return None
    numac = m.group("numac").upper()
    if not is_numac(numac):
        return None
    try:
        datum = date(int(m.group("jjjj")), int(m.group("mm")), int(m.group("dd")))
    except ValueError:
        return None
    return (type_norm, datum, numac)


def zoek_deeplink(query: str = "") -> str:
    """Handmatig te openen URL van het publieke Justel-zoekformulier. Puur, geen I/O.

    De zoekfunctie zelf loopt via het robots-disallowde ``/cgi_loi/``-pad en er is geen
    geverifieerde GET-vorm om zoektermen in de URL mee te geven; de ``query``-parameter
    wordt daarom bewust NIET in de URL verwerkt (de gebruiker typt de termen zelf in het
    formulier). De parameter bestaat alleen voor API-symmetrie met andere bronnen.
    """
    del query  # bewust ongebruikt, zie docstring
    return ZOEK_URL


# ---------------------------------------------------------------------------------------
# Pure parsers (geen netwerk-I/O)
# ---------------------------------------------------------------------------------------
def decodeer_html(inhoud: bytes) -> str:
    """Decodeer een ejustice-respons naar tekst op basis van de meta-charset.

    De ELI-pagina's declareren ISO-8859-1 in een meta-tag (en niet altijd in de
    HTTP-header); we sniffen daarom de eerste 2048 bytes. Zonder herkenbare declaratie:
    eerst UTF-8 proberen, dan ISO-8859-1 (dat nooit faalt). Puur, geen I/O.
    """
    kop = inhoud[:2048].decode("ascii", errors="ignore").lower()
    if "iso-8859-1" in kop or "latin-1" in kop or "latin1" in kop:
        return inhoud.decode("iso-8859-1", errors="replace")
    try:
        return inhoud.decode("utf-8")
    except UnicodeDecodeError:
        return inhoud.decode("iso-8859-1", errors="replace")


def _tekst(node: Tag | None) -> str:
    """Genormaliseerde tekst van een node: witruimte (ook nbsp) samengevouwen, of ''."""
    if node is None:
        return ""
    return re.sub(r"[\s\xa0]+", " ", node.get_text(" ", strip=True)).strip()


def _metadata_blok(soup: BeautifulSoup) -> dict[str, str]:
    """Label→waarde-paren uit het metadatablok (p-elementen met een strong-label).

    Vorm op de pagina: ``<p><strong>Publicatie: </strong>12 mei 2016</p>``. Labels
    worden ontdaan van dubbelepunt en witruimte; lege waarden worden overgeslagen.
    """
    velden: dict[str, str] = {}
    for p in soup.find_all("p"):
        strong = p.find("strong")
        if strong is None:
            continue
        label = _tekst(strong).rstrip(":").strip()
        waarde = _tekst(p).removeprefix(_tekst(strong)).strip()
        if label and waarde and label not in velden:
            velden[label] = waarde
    return velden


def _parse_opschrift(ruw: str) -> tuple[str, date | None]:
    """Splits het opschrift in (opschrift zonder datumprefix, datum).

    De bron toont "22 APRIL 2016. - Wet tot omzetting van ..."; de datum gaat naar
    ``Norm.datum`` en de rest is het opschrift (zo verwacht de VENA-bouwer het:
    aard + datum + opschrift). Zonder herkenbare prefix blijft het opschrift integraal
    en is de datum None.
    """
    m = _OPSCHRIFT_DATUM_RE.match(ruw)
    if m is None:
        return ruw, None
    try:
        datum = date(int(m.group(3)), _MAANDEN_NL[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return ruw, None
    return ruw[m.end():].strip() or ruw, datum


def parse_eli_pagina(html: str, url: str) -> Norm | None:
    """Puur: parse de Justel-versie van een ELI-pagina naar één Norm, of None.

    Herkenbaarheidscriterium (anti-hallucinatie): de pagina moet een geldig numac
    (``span.tag``) én een opschrift (``p.list-item--title``) dragen. De ELI-helppagina
    (HTTP 200 bij een resultaatloze opzoeking), lege pagina's en foutpagina's vallen
    daar buiten -> None. Veldkeuzes:

    * ``opschrift``/``datum``: uit ``p.list-item--title``, met de datumprefix
      ("22 APRIL 2016. - ") afgesplitst naar ``datum``;
    * ``type``: de aard zoals het opschrift ze zelf noemt (bv. "koninklijk besluit"),
      anders het ELI-type uit de URL — er wordt niet geraden;
    * ``nummer``: het numac; ``eli``: de canonieke ELI-link van de pagina
      (``a#link-text``), anders de meegegeven URL indien die een ELI-URL is;
    * ``vindplaats``: "BS <Publicatie-datum>" uit het metadatablok, indien aanwezig.

    Geen netwerk-I/O; los te testen op een fixture.
    """
    soup = BeautifulSoup(html, "html.parser")

    numac_node = soup.find("span", class_="tag")
    numac = _tekst(numac_node).upper() if numac_node else ""
    if not is_numac(numac):
        return None
    titel_node = soup.find("p", class_="list-item--title")
    ruw_opschrift = _tekst(titel_node)
    if not ruw_opschrift:
        return None

    opschrift, datum = _parse_opschrift(ruw_opschrift)

    uit_url = parse_eli_url(url)
    if datum is None and uit_url is not None:
        datum = uit_url[1]

    m_aard = _AARD_IN_OPSCHRIFT_RE.match(opschrift)
    if m_aard:
        type_ = m_aard.group(1).lower()
    elif uit_url is not None:
        type_ = uit_url[0]
    else:
        type_ = None

    velden = _metadata_blok(soup)
    publicatie = velden.get("Publicatie")
    vindplaats = f"BS {publicatie}" if publicatie else None

    eli_node = soup.find("a", id="link-text")
    eli = None
    if isinstance(eli_node, Tag) and eli_node.get("href"):
        eli = str(eli_node["href"]).strip()
    if eli is None and uit_url is not None:
        eli = url

    return Norm(
        bron="justel",
        type=type_,
        nummer=numac,
        opschrift=opschrift,
        datum=datum,
        eli=eli,
        vindplaats=vindplaats,
        url=url,
    )


def parse_norm_tekst(html: str) -> str:
    """Puur: extraheer de geconsolideerde tekst uit het 'Tekst'-blok (``h2#text``).

    Neemt de inhoud van de omvattende box, zonder de kop zelf; ``<br>``'s worden
    regeleinden en witruimte wordt per regel genormaliseerd. Geeft '' terug wanneer het
    blok ontbreekt (bv. helppagina) — de aanroeper beslist dan over een eerlijke notitie.

    Let op: de kop draagt in de bron TWEE id-attributen (``id="text"`` én
    ``id="list-link-3"``, invalide HTML); parsers verschillen in welke ze bewaren.
    We zoeken daarom op beide sporen: het id én de letterlijke koptekst "Tekst".
    """
    soup = BeautifulSoup(html, "html.parser")
    kop = soup.find("h2", id="text") or next(
        (h for h in soup.find_all("h2") if _tekst(h) == "Tekst"), None
    )
    if kop is None:
        return ""
    box = kop.find_parent("div")
    if box is None:
        return ""
    kop.extract()
    for br in box.find_all("br"):
        br.replace_with("\n")
    regels = [re.sub(r"[\s\xa0]+", " ", r).strip() for r in box.get_text().split("\n")]
    return "\n".join(r for r in regels if r).strip()


# ---------------------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------------------
class JustelAdapter(WetgevingAdapter):
    bron = "justel"
    naam = "Justel (Belgische wetgeving, FOD Justitie)"
    enabled = True

    #: Automatisch ophalen staat STANDAARD UIT: robots.txt van www.ejustice.just.fgov.be
    #: disallowt alle wetgevingspaden voor generieke bots (gecontroleerd 2026-08-09, zie
    #: moduledocstring — daar ook de juridische duiding: het robots-verbod is een
    #: technisch signaal, geen hergebruiksverbod; de afweging is aan de gebruiker).
    #: Met de vlag uit geeft de adapter lege resultaten en verzint hij géén normen;
    #: eli_deeplink() en zoek_deeplink() blijven bruikbaar voor handmatige raadpleging.
    sta_fetch: bool = False

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        rate_limit_s: float = CRAWL_DELAY_S,
    ):
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
    def zoek(self, query: str, *, max_resultaten: int = 20) -> list[Norm]:
        """Vrije-tekstzoeken is bij Justel niet geautomatiseerd — geeft altijd [] terug.

        Het zoekformulier loopt via het robots-disallowde ``/cgi_loi/``-pad en er is
        geen geverifieerde GET-zoek-URL; automatiseren zou bovendien formulier-/
        sessieverkeer vergen. De server kan de gebruiker naar ``zoek_deeplink()``
        verwijzen: die levert de handmatig te openen formulierpagina (anti-hallucinatie:
        een geconstrueerde link is geen treffer).
        """
        return []

    def zoek_op_identifier(self, identifier: str) -> list[Norm]:
        """Zoek één norm op een volledige ejustice-ELI-URL; een kaal numac kan niet.

        * ELI-URL (``/eli/<type>/<jjjj>/<mm>/<dd>/<numac>[/versie]``): met
          ``sta_fetch = True`` wordt de geconsolideerde ``/justel``-versie opgehaald en
          geparset (alleen die versie is structureel geverifieerd; andere versies worden
          naar de justel-versie genormaliseerd). Met de vlag uit (standaard, robots.txt):
          [] — er wordt géén onbevestigde deeplink als Norm teruggegeven.
        * Kaal numac: uit het numac alleen valt de ELI-URL niet te construeren (type en
          afkondigingsdatum ontbreken) en de omweg loopt via de disallowde zoekfunctie —
          resultaat [], óók met de vlag aan; de server meldt dit en kan naar
          ``zoek_deeplink()`` verwijzen.
        * Al het andere: [].
        """
        onderdelen = parse_eli_url(identifier)
        if onderdelen is None:
            return []
        if not self.sta_fetch:
            return []
        type_, datum, numac = onderdelen
        url = eli_deeplink(type_, datum, numac)
        html = self._get(url)
        if html is None:
            return []
        norm = parse_eli_pagina(html, url)
        return [norm] if norm is not None else []

    def haal_norm(self, url: str) -> NormTekst | None:
        """Haal de geconsolideerde tekst van één norm op via een ejustice-ELI-URL.

        Aanvaardt uitsluitend ELI-URL's die precies één norm identificeren (zie
        ``parse_eli_url``); andere URL's — ook de robots-disallowde ``/cgi_loi/``- en
        ``/mopdf/``-paden — worden zonder request geweigerd. Vereist ``sta_fetch = True``
        (standaard uit, robots.txt). Er wordt altijd de ``/justel``-versie opgehaald: die
        draagt de integrale geconsolideerde tekst server-rendered (vastgesteld
        2026-08-09). Ontbreekt het tekstblok toch, dan volgt een eerlijke notitie met de
        bron-URL — nooit een verzonnen of aangevulde normtekst.
        """
        onderdelen = parse_eli_url(url)
        if onderdelen is None:
            return None
        if not self.sta_fetch:
            return None
        type_, datum, numac = onderdelen
        justel_url = eli_deeplink(type_, datum, numac)
        html = self._get(justel_url)
        if html is None:
            return None
        norm = parse_eli_pagina(html, justel_url)
        if norm is None:
            return None
        tekst = parse_norm_tekst(html)
        if not tekst:
            tekst = (
                "[Pagina opgehaald, maar geen 'Tekst'-blok aangetroffen; raadpleeg de "
                f"bron-URL rechtstreeks: {justel_url}]"
            )
        return NormTekst(norm=norm, tekst=tekst)

    # -- intern ----------------------------------------------------------------------------
    def _get(self, url: str) -> str | None:
        """GET met rate limiting; decodeert zelf (meta-charset, zie decodeer_html)."""
        self._wacht()
        try:
            r = self._client.get(url)
            r.raise_for_status()
        except httpx.HTTPError:
            return None
        return decodeer_html(r.content)
