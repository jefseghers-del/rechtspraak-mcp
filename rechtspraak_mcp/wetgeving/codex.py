# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Wetgevingsadapter voor de Vlaamse Codex (geconsolideerde Vlaamse wetgeving).

Bron: de officiële "Vlaamse Codex Open Data API" van de Vlaamse overheid,
https://codex.opendata.api.vlaanderen.be — een JSON-REST-API die uitdrukkelijk voor
hergebruik is opengesteld (open data; geen robots-kwestie zoals bij de
rechtspraakbronnen). OpenAPI-spec op ``/swagger/docs/v1``. Automatisch ophalen staat
niettemin STANDAARD UIT (``sta_fetch = False``), conform het consistente
opt-in-patroon van dit project; de pure deeplink-bouwer (`document_deeplink`) blijft
altijd bruikbaar.

GEVERIFIEERDE ENDPOINTS EN VELDENSETS (live, 9 augustus 2026):

* ``GET /api/WetgevingDocument/Zoeken?zoekTerm=<q>&skip=<n>&take=<n>`` ->
  ``{"GevondenDocumenten", "GevondenArtikelen", "ResultatenLijst": [{"Id", "Datum",
  "Opschrift", "HeeftInhoud", "BSDatum", "Versies"}], "Skip", "Take", "SearchString"}``.
  Let op: het zoekresultaat bevat GEEN ``WetgevingDocumentType`` en GEEN numac; het
  ``Opschrift`` begint hier wel letterlijk met het typewoord ("Decreet tot ...",
  "Besluit van de Vlaamse Regering tot ...").
* ``GET /api/v2/WetgevingDocument/{id}`` en ``GET /api/v2/WetgevingDocument/numac/{numac}``
  (beide v2, live geverifieerd; dezelfde veldenset) -> ``{"Id", "Opschrift" (ZONDER
  typewoord: "tot wijziging van ..."), "WetgevingDocumentType" ("Decreet", ...),
  "Datum", "BSDatum", "BSPagina", "StartDatum", "EindDatum", "Numac" (integer!),
  "KbNummer", "IsFederaal", "HeeftInhoud", "Commentaar", "Opmerkingen", "MetaData",
  "Link"}``.
* ``GET /api/v2/WetgevingDocument/{id}/VolledigDocument?datum=&geannoteerd=`` ->
  ``{"Info", "Document" (zelfde veldenset als het detail), "Inhoudstafel", "Inhoud":
  {"Artikelen", "ArtikelVersies": [{"ArtikelVersie": {"Tekst", "ArtikelNummer",
  "ArtikelType", "StartDatum", "EindDatum", ...}}], "ToekomstigeArtikelVersies",
  "Hoofdstukken", "HoofdstukVersies", ...}}`` — de geldende geconsolideerde
  artikelsgewijze tekst, met via ``datum=`` ook historische versies (nu niet gebruikt).

MENSVRIENDELIJKE DEEPLINK (live geverifieerd, 9 augustus 2026):

* ``https://codex.vlaanderen.be/Zoeken/Document.aspx?DID=<id>&param=inhoud`` — HTTP 200;
  dit is het URL-patroon dat het Codex-portaal zelf in zijn eigen links hanteert (in de
  paginabron o.a. ``Document.aspx?DID={0}&param=inhoud`` en een canonieke verwijzing
  naar precies deze vorm). De documentinhoud wordt er client-side geladen (DNN-portaal),
  maar de link opent voor een mens het juiste document.
* ``https://codex.vlaanderen.be/doc/document/<id>`` bestaat ook, maar redirect naar de
  kale API-JSON (``/api/WetgevingDocument/<id>``) en is dus NIET mensvriendelijk.

Uitbreidingsmogelijkheden (bewust nog niet gebruikt): de API biedt ook Thema-,
Trefwoord- en Artikel-endpoints (o.a. ``/api/WetgevingDocument/{id}/Themas`` en
``.../Trefwoorden``) en per document een ``Structuur``-endpoint.

Anti-hallucinatie: alle veldwaarden komen letterlijk uit de API-respons. Twee
gedocumenteerde herschrijvingen: (1) het normtype is bij zoekresultaten een prefixlezing
van het opschrift (gesloten lijstje typewoorden; onherkenbaar -> None), omdat het
zoekendpoint het type niet meegeeft; (2) bij het documentdetail wordt het typewoord
(``WetgevingDocumentType``) vóór het kale opschrift geplakt zodat het opschrift op
zichzelf leesbaar is ("Decreet tot wijziging van ..."). Bij een onherkenbare respons
volgt None/[], nooit een verzonnen norm.
"""
from __future__ import annotations

import re
import time
from datetime import date

import httpx

from .base import WetgevingAdapter
from ..schema import Norm, NormTekst
from .. import user_agent

API_BASE = "https://codex.opendata.api.vlaanderen.be"
ZOEK_URL = API_BASE + "/api/WetgevingDocument/Zoeken"
#: Documentdetail (v2 verkozen; live geverifieerd, zelfde veldenset als het numac-pad).
DOCUMENT_URL_SJABLOON = API_BASE + "/api/v2/WetgevingDocument/{id}"
NUMAC_URL_SJABLOON = API_BASE + "/api/v2/WetgevingDocument/numac/{numac}"
VOLLEDIG_URL_SJABLOON = API_BASE + "/api/v2/WetgevingDocument/{id}/VolledigDocument"
#: Mensvriendelijke deeplink naar het Codex-portaal (patroon van het portaal zelf).
PORTAAL_URL_SJABLOON = "https://codex.vlaanderen.be/Zoeken/Document.aspx?DID={id}&param=inhoud"

#: Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt.
USER_AGENT = user_agent("raadpleging via de Vlaamse Codex Open Data API")
#: Pauze tussen requests: 2 s volstaat voor een open-data-API (korter dan bij scraping).
RATE_LIMIT_S = 2.0
TIMEOUT_S = 15.0

INSTANTIE_BRON = "codex"

#: Numac-vorm zoals waargenomen in de API (integerveld ``Numac``, bv. 2026002345):
#: 10 cijfers, waarvan de eerste vier het jaartal van de BS-publicatie vormen.
_NUMAC_RE = re.compile(r"^\d{10}$")
#: Vroegst plausibele numac-jaartal (numac-nummering dekt ook oudere, heropgenomen
#: teksten; ruime ondergrens zodat we niets onterecht afwijzen).
_NUMAC_JAAR_MIN = 1800

#: Gesloten lijstje typewoorden waarmee een Codex-opschrift kan beginnen (prefixlezing
#: voor zoekresultaten; langste eerst zodat "besluit van de vlaamse regering" wint van
#: "besluit"). Onherkenbaar -> type None, nooit geraden.
_TYPE_PREFIXEN = (
    "besluit van de vlaamse regering",
    "bijzondere wet",
    "koninklijk besluit",
    "ministerieel besluit",
    "samenwerkingsakkoord",
    "gecoördineerd decreet",
    "omzendbrief",
    "beschikking",
    "decreet",
    "besluit",
    "verdrag",
    "wet",
)

#: URL-vormen waaruit haal_norm een document-Id kan halen: de portaaldeeplink
#: (DID-parameter, hoofdletterongevoelig) en de API-detail-URL's (v1 en v2).
_PORTAAL_URL_RE = re.compile(
    r"^https?://codex\.vlaanderen\.be/Zoeken/Document\.aspx\?.*\bDID=(\d+)",
    re.IGNORECASE,
)
_API_URL_RE = re.compile(
    r"^https?://codex\.opendata\.api\.vlaanderen\.be/api/(?:v2/)?WetgevingDocument/(\d+)"
    r"(?:/|\?|$)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------------------
# Pure functies (geen netwerk-I/O)
# ---------------------------------------------------------------------------------------
def is_numac(s: str) -> bool:
    """Puur: is deze string een plausibele numac (bv. "2014035564")?

    Vorm zoals waargenomen in de API: exact 10 cijfers, beginnend met een plausibel
    jaartal (de eerste vier cijfers). De API levert de numac als integer (2026002345);
    aanroepen gebeurt met de stringvorm.
    """
    s = (s or "").strip()
    if not _NUMAC_RE.match(s):
        return False
    jaar = int(s[:4])
    return _NUMAC_JAAR_MIN <= jaar <= date.today().year + 1


def document_deeplink(document_id: int) -> str:
    """Bouw de mensvriendelijke portaaldeeplink voor één Codex-document-Id (crawlt niet)."""
    return PORTAAL_URL_SJABLOON.format(id=document_id)


def _parse_datum(iso: str | None) -> date | None:
    """Parse "2026-03-06T00:00:00Z" (of zonder Z) naar een date; None bij onbruikbaar."""
    try:
        return date.fromisoformat((iso or "")[:10])
    except ValueError:
        return None


def _vindplaats_uit_bsdatum(bsdatum: str | None) -> str | None:
    """Bouw "BS <d.m.jjjj>" uit het BSDatum-veld, of None als dat ontbreekt."""
    d = _parse_datum(bsdatum)
    if d is None:
        return None
    return f"BS {d.day}.{d.month}.{d.year}"


def _type_uit_opschrift(opschrift: str) -> str | None:
    """Prefixlezing van het typewoord in een Zoeken-opschrift (gesloten lijstje).

    Het zoekendpoint geeft geen ``WetgevingDocumentType`` mee; het opschrift begint er
    wel letterlijk mee ("Decreet tot ...", "Besluit van de Vlaamse Regering tot ...").
    Onherkenbaar begin -> None (nooit geraden).
    """
    laag = opschrift.lower()
    for prefix in _TYPE_PREFIXEN:
        if laag.startswith(prefix + " "):
            return prefix
    return None


def parse_zoekrespons(data: dict) -> list[Norm]:
    """Puur: normaliseer een /Zoeken-respons naar Normen (veldenset: moduledocstring).

    Elk resultaat behoudt een controleerbare bron-URL (de portaaldeeplink op het Id).
    Het type is een prefixlezing van het opschrift (gedocumenteerde herschrijving);
    numac zit niet in het zoekresultaat, dus ``nummer`` blijft hier None — het
    documentdetail (parse_document) vult dat wel in. Resultaten zonder Id of opschrift
    worden overgeslagen (geen controleerbare link resp. geen benoembare norm).
    """
    normen: list[Norm] = []
    for resultaat in data.get("ResultatenLijst") or []:
        document_id = resultaat.get("Id")
        opschrift = (resultaat.get("Opschrift") or "").strip()
        if not isinstance(document_id, int) or not opschrift:
            continue
        normen.append(
            Norm(
                bron=INSTANTIE_BRON,
                type=_type_uit_opschrift(opschrift),
                opschrift=opschrift,
                datum=_parse_datum(resultaat.get("Datum")),
                vindplaats=_vindplaats_uit_bsdatum(resultaat.get("BSDatum")),
                url=document_deeplink(document_id),
            )
        )
    return normen


def parse_document(data: dict) -> Norm | None:
    """Puur: normaliseer een documentdetail (v2, ook het numac-pad) naar een Norm.

    Herkenbaarheidscriterium (anti-hallucinatie): een integer ``Id`` en een niet-leeg
    ``Opschrift``; anders None. Het detail-opschrift mist het typewoord ("tot wijziging
    van ..."); dat wordt — gedocumenteerde herschrijving — vooraan bijgeplakt uit
    ``WetgevingDocumentType`` zodat het opschrift op zichzelf leesbaar is. ``type``
    is het lowercase ``WetgevingDocumentType``; ``nummer`` de numac (integerveld,
    als string).
    """
    document_id = data.get("Id")
    opschrift = (data.get("Opschrift") or "").strip()
    if not isinstance(document_id, int) or not opschrift:
        return None
    type_ruw = (data.get("WetgevingDocumentType") or "").strip()
    if type_ruw and not opschrift.lower().startswith(type_ruw.lower()):
        opschrift = f"{type_ruw} {opschrift}"
    numac = data.get("Numac")
    return Norm(
        bron=INSTANTIE_BRON,
        type=type_ruw.lower() or None,
        nummer=str(numac) if numac else None,
        opschrift=opschrift,
        datum=_parse_datum(data.get("Datum")),
        vindplaats=_vindplaats_uit_bsdatum(data.get("BSDatum")),
        url=document_deeplink(document_id),
    )


def parse_volledig_document(data: dict) -> str:
    """Puur: zet een VolledigDocument-respons om naar artikelsgewijze platte tekst.

    Neemt de geldende ``ArtikelVersies`` uit ``Inhoud`` in de volgorde van de bron en
    rendert per artikel "Art. <ArtikelNummer>" gevolgd door de letterlijke ``Tekst``.
    Toekomstige versies en hoofdstukstructuur blijven bewust buiten beschouwing
    (het portaal toont dezelfde geldende tekst). Geeft "" terug wanneer er geen
    inhoud is — de aanroeper beslist dan over een eerlijke notitie.
    """
    inhoud = data.get("Inhoud") or {}
    blokken: list[str] = []
    for wrapper in inhoud.get("ArtikelVersies") or []:
        versie = (wrapper or {}).get("ArtikelVersie") or {}
        tekst = (versie.get("Tekst") or "").strip()
        if not tekst:
            continue
        nummer = (versie.get("ArtikelNummer") or "").strip()
        kop = f"Art. {nummer}" if nummer else "Art."
        blokken.append(f"{kop}\n{tekst}")
    return "\n\n".join(blokken)


def _document_id_uit_url(url: str) -> int | None:
    """Haal het document-Id uit een portaaldeeplink of API-detail-URL; anders None."""
    for patroon in (_PORTAAL_URL_RE, _API_URL_RE):
        m = patroon.match(url or "")
        if m:
            return int(m.group(1))
    return None


# ---------------------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------------------
class CodexAdapter(WetgevingAdapter):
    bron = INSTANTIE_BRON
    naam = "Vlaamse Codex (Vlaamse wetgeving)"
    enabled = True

    #: Automatisch ophalen staat standaard UIT, conform het consistente opt-in-patroon
    #: van dit project. De Vlaamse Codex Open Data API is uitdrukkelijk voor hergebruik
    #: opengesteld (open data van de Vlaamse overheid); aanzetten is dus juridisch
    #: onproblematisch. Wie de vlag aanzet krijgt nette rate limiting (RATE_LIMIT_S)
    #: en een identificeerbare User-Agent.
    sta_fetch: bool = False

    def __init__(self, *, client: httpx.Client | None = None, rate_limit_s: float = RATE_LIMIT_S):
        self._eigen_client = client is None
        self._client = client or httpx.Client(
            timeout=TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
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
        """Vrije-tekst-/trefwoordzoeken via /api/WetgevingDocument/Zoeken.

        Geeft [] terug wanneer `sta_fetch` uit staat (standaard), bij een lege query of
        bij een API-fout. Het resultaat bevat uitsluitend wat de API effectief teruggaf
        (anti-hallucinatie), gecapt op `max_resultaten`.
        """
        if not self.sta_fetch:
            return []
        zoekterm = (query or "").strip()
        if not zoekterm:
            return []
        data = self._haal_json(
            ZOEK_URL, params={"zoekTerm": zoekterm, "skip": "0", "take": str(max_resultaten)}
        )
        if data is None:
            return []
        return parse_zoekrespons(data)[:max_resultaten]

    def zoek_op_identifier(self, identifier: str) -> list[Norm]:
        """Zoek op numac (10 cijfers, bv. "2014035564") via het v2-numac-pad.

        Andere identifiervormen (ELI, CELEX, citeervormen) horen bij andere bronnen en
        geven hier [] terug. Geeft ook [] wanneer `sta_fetch` uit staat (standaard),
        of wanneer de API het nummer niet kent.
        """
        numac = (identifier or "").strip()
        if not is_numac(numac):
            return []
        if not self.sta_fetch:
            return []
        data = self._haal_json(NUMAC_URL_SJABLOON.format(numac=numac))
        if data is None:
            return []
        norm = parse_document(data)
        return [norm] if norm is not None else []

    def haal_norm(self, url: str) -> NormTekst | None:
        """Haal de geldende geconsolideerde tekst van één document op.

        Aanvaardt de portaaldeeplink (Document.aspx?DID=<id>) én de API-detail-URL's
        (v1/v2) en vereist `sta_fetch = True`. Werkwijze: documentdetail (v2) voor de
        metadata, dan VolledigDocument voor de artikelsgewijze tekst. Anti-hallucinatie:
        de tekst is letterlijk wat de API teruggeeft; bij ``HeeftInhoud = false`` of een
        lege tekst volgt een eerlijke notitie met de bron-URL — nooit verzonnen tekst.
        Historische versies (``datum=``-parameter van VolledigDocument) zijn een
        uitbreidingsmogelijkheid en worden nu niet opgevraagd.
        """
        document_id = _document_id_uit_url(url)
        if document_id is None:
            return None
        if not self.sta_fetch:
            return None
        detail = self._haal_json(DOCUMENT_URL_SJABLOON.format(id=document_id))
        if detail is None:
            return None
        norm = parse_document(detail)
        if norm is None:
            return None
        if not detail.get("HeeftInhoud"):
            return NormTekst(
                norm=norm,
                tekst=(
                    "[De Codex-API meldt voor dit document geen raadpleegbare inhoud "
                    f"(HeeftInhoud = false); raadpleeg de bron-URL rechtstreeks: {norm.url}]"
                ),
            )
        volledig = self._haal_json(VOLLEDIG_URL_SJABLOON.format(id=document_id))
        tekst = parse_volledig_document(volledig) if volledig is not None else ""
        if not tekst:
            tekst = (
                "[Documentdetail opgehaald, maar de volledige tekst kwam leeg terug; "
                f"raadpleeg de bron-URL rechtstreeks: {norm.url}]"
            )
        return NormTekst(norm=norm, tekst=tekst)

    # -- intern ----------------------------------------------------------------------------
    def _haal_json(self, url: str, *, params: dict[str, str] | None = None) -> dict | None:
        """GET met rate limiting; None bij een HTTP-fout of onleesbare JSON."""
        self._wacht()
        try:
            r = self._client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            return None
        return data if isinstance(data, dict) else None
