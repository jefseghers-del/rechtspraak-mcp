# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Adapter voor het Europees Hof voor de Rechten van de Mens (HUDOC).

Concept-implementatie naar het DBRC-patroon (injecteerbare client, rate limiting,
pure parsers los van I/O). Bron: de publieke JSON-zoek-API van HUDOC zelf
(`/app/query/results`), live geverifieerd op 9 augustus 2026. HUDOC publiceert geen
robots.txt; het gaat om de eigen data-API van het EHRM met vrij herbruikbare
rechtspraak. Automatisch ophalen staat niettemin standaard UIT (`sta_fetch = False`),
conform de voorzichtige standaard van dit project; de pure deeplink-bouwer
(`document_deeplink`) blijft altijd bruikbaar.

GEVERIFIEERDE QUERYVORMEN (2026-08-09, live tegen hudoc.echr.coe.int):

* Op zaaknummer:  ``(appno:"46043/14")``
* Op ECLI:        ``(ecli:"ECLI:CE:ECHR:2015:0605JUD004604314")``
* Vrije tekst (de vorm die het HUDOC-portaal zelf hanteert)::

      contentsitename=ECHR AND (NOT (doctype=PR OR doctype=HFCOMOLD OR
      doctype=HECOMOLD)) AND (("<tekst>")) AND ((doctype="HEJUD") OR (doctype="HFJUD"))

  De variant ``contents:"..."`` gaf 0 resultaten en wordt dus NIET gebruikt.
* Documenttekst: ``/app/conversion/docx/html/body?library=ECHR&id=<itemid>`` geeft de
  integrale documenttekst als HTML (met ingebedde <style>-blokken) terug.

DOCTYPES EN KEUZE VAN HET PRIMAIRE DOCUMENT (waargenomen in de live respons):

Eén zaak levert in HUDOC vele documenten op (Lambert e.a. t. Frankrijk: 33 stuks).
Waargenomen doctypes: ``HEJUD`` (Engels origineel arrest), ``HFJUD`` (Frans origineel
arrest), ``HJUD<TAAL>`` (niet-officiële vertalingen, bv. HJUDHRV/HJUDSWE), ``CLIN``/
``CLINF`` (samenvattingen uit de Case-Law Information Notes, zonder eigen ECLI) en
``HECOM``/``HFCOM`` (communicated cases, procedurele kennisgeving zonder ECLI).
Keuze (zie `_doctype_rang`): per zaak/uitspraak kiezen we het best gerangschikte
document — Engels origineel vóór Frans origineel vóór vertalingen. Groepen die enkel
uit samenvattingen of communicated-kennisgevingen bestaan worden niet als treffer
teruggegeven: het zijn geen uitspraken (het arrest zelf zit al in de lijst zodra het
bestaat). Deduplicatie gebeurt per zaak/uitspraak: op ECLI waar aanwezig; documenten
zonder ECLI (samenvattingen) hangen we via (zaaknummer, datum) aan dezelfde uitspraak.
"""
from __future__ import annotations

import re
import time
from datetime import date

import httpx
from bs4 import BeautifulSoup

from .base import RechtspraakAdapter
from ..schema import Treffer, Uitspraak, ZoekQuery
from .. import user_agent
from ..botcontrole import is_botcontrole

#: JSON-zoek-API van HUDOC (live geverifieerd).
API_URL = "https://hudoc.echr.coe.int/app/query/results"
#: Mensvriendelijke deeplink naar één document.
DOCUMENT_URL_SJABLOON = "https://hudoc.echr.coe.int/eng?i={itemid}"
#: Endpoint dat de integrale documenttekst als HTML teruggeeft (live geverifieerd).
BODY_URL = "https://hudoc.echr.coe.int/app/conversion/docx/html/body"

#: Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt.
USER_AGENT = user_agent("raadpleging EHRM-rechtspraak via de publieke HUDOC-API")
#: Conservatieve pauze tussen opeenvolgende requests (HUDOC schrijft niets voor).
RATE_LIMIT_S = 5.0
TIMEOUT_S = 15.0
#: Vaste select-lijst voor de query-API (alle velden live geverifieerd).
SELECT_VELDEN = (
    "itemid,docname,appno,ecli,kpdate,doctype,importance,originatingbody,article,conclusion"
)
#: Basisfilter van het HUDOC-portaal zelf (sluit persberichten en verouderde
#: communicated-documenten uit).
_BASISFILTER = (
    'contentsitename=ECHR AND (NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD))'
)
#: Hoeveel documenten we per API-call opvragen: ruim, omdat één zaak veel
#: vertalingen/samenvattingen kan opleveren die na deduplicatie wegvallen.
_API_LENGTH = 50

# EHRM-ECLI, bv. "ECLI:CE:ECHR:2015:0605JUD004604314"
# (jaar : MMDD + documenttype (JUD/DEC/...) + cijferreeks uit het zaaknummer).
_ECLI_RE = re.compile(r"^\s*(ECLI:CE:ECHR:\d{4}:\d{4}[A-Z]{2,6}\d+)\s*$", re.IGNORECASE)
# Zaaknummer (application number), bv. "46043/14".
_APPNO_RE = re.compile(r"^\s*(\d{1,6}/\d{2})\s*$")
# Document-deeplink, bv. "https://hudoc.echr.coe.int/eng?i=001-155352".
_DEEPLINK_RE = re.compile(
    r"^https?://hudoc\.echr\.coe\.int/[a-z]{3}\?i=([0-9]{3}-[0-9]+)$"
)
# Oudere deeplink-vorm met itemid in het URL-fragment, bv.
# 'https://hudoc.echr.coe.int/eng#{"itemid":["001-155352"]}' (evt. percent-gecodeerd).
_ITEMID_FRAGMENT_RE = re.compile(r"itemid[^0-9]*([0-9]{3}-[0-9]+)")

INSTANTIE = "Europees Hof voor de Rechten van de Mens"


# ------------------------------------------------------------------------------------
# Pure functies (geen I/O)
# ------------------------------------------------------------------------------------
def normaliseer_ehrm_ecli(s: str) -> str | None:
    """Normaliseer een EHRM-ECLI naar hoofdletters, of None als het er geen is."""
    m = _ECLI_RE.match(s or "")
    return m.group(1).upper() if m else None


def normaliseer_appno(s: str) -> str | None:
    """Normaliseer een EHRM-zaaknummer (application number) zoals '46043/14', of None."""
    m = _APPNO_RE.match(s or "")
    return m.group(1) if m else None


def document_deeplink(itemid: str) -> str:
    """Bouw de mensvriendelijke HUDOC-deeplink voor één document-itemid."""
    return DOCUMENT_URL_SJABLOON.format(itemid=itemid)


def _doctype_rang(doctype: str) -> int:
    """Rangschik doctypes: hoe lager, hoe primairder het document voor de uitspraak.

    Live waargenomen: HEJUD/HFJUD (originele arresten EN/FR), HJUD<TAAL>
    (vertalingen), CLIN/CLINF (samenvattingen), HFCOM (communicated). HEDEC/HFDEC
    (originele beslissingen) volgen hetzelfde naamschema en worden via de
    prefixregels meegenomen. [TE VERIFIËREN: HEDEC/HFDEC niet live waargenomen]
    """
    if doctype == "HEJUD":
        return 0  # Engels origineel arrest
    if doctype == "HFJUD":
        return 1  # Frans origineel arrest
    if doctype in ("HEDEC", "HFDEC"):
        return 2  # originele beslissing (ontvankelijkheid e.d.)
    if doctype.startswith("HJUD"):
        return 3  # vertaling van een arrest
    if doctype.startswith("HDEC"):
        return 4  # vertaling van een beslissing
    return 9  # samenvattingen (CLIN/CLINF), communicated (HECOM/HFCOM), overige


#: Documenten met een rang boven deze drempel zijn geen uitspraak(vertaling) en
#: leveren nooit zelfstandig een treffer op.
_MAX_RANG_UITSPRAAK = 4


def _schoon_titel(docname: str) -> str:
    """Knip het vertaalsuffix (' - [Croatian Translation] ...') van een docname af."""
    return docname.split(" - [", 1)[0].strip()


def _parse_datum(kpdate: str) -> date | None:
    """Parse '2015-06-05T00:00:00' naar een date, of None bij een onbruikbare waarde."""
    try:
        return date.fromisoformat((kpdate or "")[:10])
    except ValueError:
        return None


def parse_query_json(data: dict) -> list[Treffer]:
    """Puur: normaliseer een JSON-respons van de query-API naar unieke Treffers.

    Per zaak/uitspraak (gededupliceerd op ECLI; documenten zonder ECLI via
    (zaaknummer, datum) aan dezelfde uitspraak gekoppeld) geven we één treffer
    terug: het primaire document volgens `_doctype_rang`. Groepen zonder
    uitspraakdocument (enkel samenvatting/communicated) vallen weg — zie de
    module-docstring. De volgorde van de bron (sortering van de API) blijft
    behouden. Deze functie doet géén netwerk-I/O en is los te testen.
    """
    resultaten = data.get("results") or []
    groepen: dict[object, list[dict]] = {}  # zaak-sleutel -> kolommen-dicts
    ecli_zaken: set[tuple[str, str]] = set()  # (appno, datum-iso) van ECLI-groepen
    for resultaat in resultaten:
        kolommen = resultaat.get("columns") or {}
        itemid = (kolommen.get("itemid") or "").strip()
        if not itemid:
            continue  # zonder itemid is er geen controleerbare bron-URL
        ecli = (kolommen.get("ecli") or "").strip()
        appno = (kolommen.get("appno") or "").strip()
        datum_iso = (kolommen.get("kpdate") or "")[:10]
        if ecli:
            sleutel: object = ecli
            ecli_zaken.add((appno, datum_iso))
        elif appno:
            sleutel = (appno, datum_iso)
        else:
            sleutel = itemid
        groepen.setdefault(sleutel, []).append(kolommen)

    treffers: list[Treffer] = []
    for sleutel, docs in groepen.items():
        if isinstance(sleutel, tuple) and sleutel in ecli_zaken:
            # Samenvattingen e.d. zonder ECLI horen bij een uitspraak die al met
            # haar ECLI in de lijst zit: geen aparte treffer.
            continue
        primair = min(docs, key=lambda k: _doctype_rang((k.get("doctype") or "").strip()))
        if _doctype_rang((primair.get("doctype") or "").strip()) > _MAX_RANG_UITSPRAAK:
            continue  # geen uitspraakdocument in deze groep
        ecli = (primair.get("ecli") or "").strip() or None
        appno = (primair.get("appno") or "").strip() or None
        snippet = (primair.get("conclusion") or "").strip()
        if not snippet:
            artikelen = (primair.get("article") or "").strip()
            snippet = f"Artikel(en): {artikelen}" if artikelen else ""
        treffers.append(
            Treffer(
                bron="ehrm",
                instantie=INSTANTIE,
                titel=_schoon_titel(primair.get("docname") or "") or primair["itemid"],
                datum=_parse_datum(primair.get("kpdate") or ""),
                ecli=ecli,
                rolnummer=appno,
                snippet=snippet or None,
                url=document_deeplink(primair["itemid"]),
            )
        )
    return treffers


def _itemid_uit_url(url: str) -> str | None:
    """Haal de itemid uit een HUDOC-document-URL, of None bij een vreemde URL."""
    m = _DEEPLINK_RE.match(url or "")
    if m:
        return m.group(1)
    if (url or "").startswith("https://hudoc.echr.coe.int/"):
        m = _ITEMID_FRAGMENT_RE.search(url)
        if m:
            return m.group(1)
    return None


def _html_naar_tekst(html: str) -> str:
    """Puur: strip het body-endpoint-HTML (incl. <style>-blokken) naar kale tekst."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "script"]):
        tag.decompose()
    tekst = soup.get_text("\n")
    regels = [regel.strip() for regel in tekst.splitlines()]
    return "\n".join(regel for regel in regels if regel)


# ------------------------------------------------------------------------------------
# Adapter
# ------------------------------------------------------------------------------------
class EhrmAdapter(RechtspraakAdapter):
    bron = "ehrm"
    instantie = INSTANTIE
    enabled = True

    #: Automatisch ophalen staat standaard UIT (voorzichtige projectstandaard).
    #: HUDOC is de publieke data-API van het EHRM zelf (geen robots.txt, vrij
    #: herbruikbare rechtspraak); wie de vlag aanzet krijgt nette rate limiting
    #: (RATE_LIMIT_S) en een identificeerbare User-Agent.
    sta_fetch: bool = False

    #: True wanneer de laatste opvraging op een botcontrole stuitte (zie botcontrole.py).
    laatste_botcontrole: bool = False

    def __init__(self, *, client: httpx.Client | None = None, rate_limit_s: float = RATE_LIMIT_S):
        self._eigen_client = client is None
        self._client = client or httpx.Client(
            timeout=TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._rate_limit_s = rate_limit_s
        self._laatste_request: float = 0.0

    # -- rate limiting ---------------------------------------------------------------
    def _wacht(self) -> None:
        verstreken = time.monotonic() - self._laatste_request
        if verstreken < self._rate_limit_s:
            time.sleep(self._rate_limit_s - verstreken)
        self._laatste_request = time.monotonic()

    def close(self) -> None:
        if self._eigen_client:
            self._client.close()

    # -- publieke API ----------------------------------------------------------------
    def zoek(self, query: ZoekQuery) -> list[Treffer]:
        """Vrije-tekstzoekopdracht via de query-API (portaal-queryvorm, geverifieerd).

        De zoektekst gaat als exacte frase in de queryvorm van het HUDOC-portaal,
        beperkt tot originele arresten (HEJUD/HFJUD) — beslissingen en vertalingen
        worden bij vrije tekst dus niet doorzocht [BEPERKING]. Datumfilters uit de
        ZoekQuery passen we na het parsen client-side toe (een server-side
        kpdate-filter is niet geverifieerd). Standaard staat `sta_fetch` uit en
        volgt een lege lijst.
        """
        if not self.sta_fetch:
            return []
        tekst = re.sub(r'["\\]', " ", query.query or "").strip()
        if not tekst:
            return []
        api_query = (
            f'{_BASISFILTER} AND (("{tekst}")) '
            f'AND ((doctype="HEJUD") OR (doctype="HFJUD"))'
        )
        data = self._query_api(api_query)
        if data is None:
            return []
        treffers = parse_query_json(data)
        if query.datum_van is not None:
            treffers = [t for t in treffers if t.datum is not None and t.datum >= query.datum_van]
        if query.datum_tot is not None:
            treffers = [t for t in treffers if t.datum is not None and t.datum <= query.datum_tot]
        return treffers[: query.max_resultaten]

    def zoek_op_identifier(self, identifier: str, datum: date | None = None) -> list[Treffer]:
        """Zoek op EHRM-ECLI of zaaknummer (application number, bv. '46043/14').

        De API geeft per zaak vele documenten terug (vertalingen, samenvattingen);
        `parse_query_json` dedupliceert en kiest het primaire arrest. Meerdere
        uitspraken in dezelfde zaak (bv. arrest ten gronde + billijke genoegdoening)
        behouden elk hun eigen treffer via hun eigen ECLI. Standaard staat
        `sta_fetch` uit en volgt een lege lijst.
        """
        ecli = normaliseer_ehrm_ecli(identifier)
        appno = None if ecli else normaliseer_appno(identifier)
        if ecli is None and appno is None:
            return []
        if not self.sta_fetch:
            return []
        if ecli:
            api_query = f'(ecli:"{ecli}")'
        else:
            api_query = f'(appno:"{appno}")'
        data = self._query_api(api_query)
        if data is None:
            return []
        return parse_query_json(data)

    def haal_uitspraak(self, url: str) -> Uitspraak | None:
        """Haal de documenttekst op via het HUDOC-body-endpoint (geverifieerd).

        Aanvaardt enkel HUDOC-document-URL's; andere URL's geven None. Met
        `sta_fetch` uit, of wanneer het ophalen/strippen mislukt, volgt een
        Uitspraak met een eerlijke notitie dat de integrale tekst via de bron-URL
        te raadplegen is — nooit verzonnen of aangevulde tekst. De treffer bevat
        enkel wat uit de URL zelf af te leiden valt (itemid); metadata zoals titel
        en datum vergt een aparte zoekopdracht via zoek_op_identifier.
        """
        itemid = _itemid_uit_url(url)
        if itemid is None:
            return None
        treffer = Treffer(
            bron="ehrm",
            instantie=INSTANTIE,
            titel=f"HUDOC-document {itemid}",
            url=document_deeplink(itemid),
        )
        notitie = (
            f"[Integrale tekst niet automatisch opgehaald — raadpleeg de bron-URL "
            f"{treffer.url} rechtstreeks.]"
        )
        if not self.sta_fetch:
            return Uitspraak(treffer=treffer, tekst=notitie)
        self._wacht()
        self.laatste_botcontrole = False
        try:
            r = self._client.get(BODY_URL, params={"library": "ECHR", "id": itemid})
            if is_botcontrole(r):
                # Cloudflare-challenge: nooit omzeilen, ook niet door opnieuw te proberen.
                self.laatste_botcontrole = True
                return Uitspraak(treffer=treffer, tekst=notitie)
            r.raise_for_status()
        except httpx.HTTPError:
            return Uitspraak(treffer=treffer, tekst=notitie)
        tekst = _html_naar_tekst(r.text)
        if not tekst:
            return Uitspraak(treffer=treffer, tekst=notitie)
        return Uitspraak(treffer=treffer, tekst=tekst)

    # -- intern ----------------------------------------------------------------------
    def _query_api(self, api_query: str) -> dict | None:
        """Bevraag de query-API met de vaste select/sortering; None bij een fout."""
        params = {
            "query": api_query,
            "select": SELECT_VELDEN,
            "sort": "kpdate Descending",
            "start": "0",
            "length": str(_API_LENGTH),
        }
        self._wacht()
        self.laatste_botcontrole = False
        try:
            r = self._client.get(API_URL, params=params)
            if is_botcontrole(r):
                # Cloudflare-challenge: nooit omzeilen, ook niet door opnieuw te proberen.
                self.laatste_botcontrole = True
                return None
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError):
            return None
