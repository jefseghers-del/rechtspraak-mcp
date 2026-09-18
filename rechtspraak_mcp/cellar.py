# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Toegang tot EU-rechtspraak en -wetgeving via CELLAR, de open-data-dienst van het Publicatiebureau.

Waarom CELLAR en niet de EUR-Lex-pagina's: sinds september 2026 zet EUR-Lex een botcontrole
(AWS WAF-challenge) voor geautomatiseerde opvragingen, en die omzeilen we niet (zie
botcontrole.py). CELLAR is de machinetoegang die het Publicatiebureau zelf aanbiedt voor
dezelfde documenten, onder hetzelfde vrije hergebruik (Besluit 2011/833/EU).

Twee diensten (live verkend op 18 september 2026):

* SPARQL-endpoint ``https://publications.europa.eu/webapi/rdf/sparql`` met de CDM-ontologie:
  ECLI -> CELEX, datum en titel per taal (``cdm:case-law_ecli``, ``cdm:resource_legal_id_celex``,
  ``cdm:work_date_document``, ``cdm:expression_title``), ELI (``cdm:resource_legal_eli``) en de
  Publicatieblad-verwijzing (``cdm:work_id_document`` "oj:JOL_2012_026_R_..." en de datum van
  het Publicatieblad). Titels hebben een volledige-tekstindex (``bif:contains``), wat
  zoeken op woorden in de titel mogelijk maakt.
* Inhoud via content negotiation: ``https://publications.europa.eu/resource/celex/<CELEX>`` met
  ``Accept: text/html`` of ``application/xhtml+xml`` (recente documenten bestaan alleen als
  XHTML) en ``Accept-Language: nld`` verwijst (303) naar de Nederlandse taalversie.

De links die de gebruiker te zien krijgt, blijven de gewone EUR-Lex-pagina's: in een browser
zijn die gewoon leesbaar, en ze zijn het controleerbare bronadres.

Veiligheid: niets van de gebruikersinvoer gaat ongecontroleerd een SPARQL-query in. ECLI en
CELEX worden eerst op hun vaste vorm gecontroleerd; zoekwoorden worden beperkt tot letters,
cijfers en koppeltekens.
"""
from __future__ import annotations

import re
import time
from datetime import date

import httpx
from bs4 import BeautifulSoup

from . import user_agent
from .botcontrole import is_botcontrole

SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
RESOURCE_CELEX = "https://publications.europa.eu/resource/celex/{celex}"
USER_AGENT = user_agent("raadpleging via de CELLAR-open-data-diensten van het Publicatiebureau")
#: Geen robots-voorschrift voor de webapi; we houden een nette pauze aan.
RATE_LIMIT_S = 1.0
TIMEOUT_S = 30.0

_CDM = "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
_TAAL_URI = "http://publications.europa.eu/resource/authority/language/{code}"
_ECLI_EU_RE = re.compile(r"^ECLI:EU:[CTF]:\d{4}:\d+$")
_CELEX_RE = re.compile(r"^[0-9CE]\d{4}[A-Z]{1,2}\d{4}(?:\([0-9A-Z]+\))?$")
#: CELEX van een eindbeslissing (arrest, beschikking, conclusie) in sector 6: 62002CJ0127.
_CELEX_RECHTSPRAAK_RE = re.compile(r"^6\d{4}[A-Z]{2}\d{4}$")
_WOORD_RE = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+(?:-[0-9A-Za-zÀ-ÖØ-öø-ÿ]+)*")
#: Publicatieblad-identificatie in cdm:work_id_document.
_OJ_OUD_RE = re.compile(r"^oj:JO([LC])_(\d{4})_(\d{3})([A-Z]?)_(?:[A-Z]_(\d{4}))?")
_OJ_NIEUW_RE = re.compile(r"^oj:([LC])_(\d{4})(\d{5})$")


# ---------------------------------------------------------------------------------------
# Pure functies (geen netwerk-I/O)
# ---------------------------------------------------------------------------------------
def bindingen(resultaat: dict) -> list[dict[str, str]]:
    """Maak SPARQL-JSON-resultaten plat tot een lijst {variabele: waarde}."""
    rijen = []
    for b in resultaat.get("results", {}).get("bindings", []):
        rijen.append({k: v.get("value", "") for k, v in b.items()})
    return rijen


def _titels(var_werk: str) -> str:
    """OPTIONAL-blokken voor de Nederlandse en Engelse titel van een werk."""
    blokken = []
    for code, var in (("NLD", "titel_nl"), ("ENG", "titel_en")):
        blokken.append(
            f"  OPTIONAL {{ ?{var}_x cdm:expression_belongs_to_work ?{var_werk} ; "
            f"cdm:expression_uses_language <{_TAAL_URI.format(code=code)}> ; "
            f"cdm:expression_title ?{var} }}"
        )
    return "\n".join(blokken)


def query_arrest_op_ecli(ecli: str) -> str:
    if not _ECLI_EU_RE.match(ecli):
        raise ValueError(f"Geen genormaliseerde EU-ECLI: {ecli!r}")
    return (
        _CDM
        + "SELECT ?celex ?datum ?titel_nl ?titel_en WHERE {\n"
        + f'  ?werk cdm:case-law_ecli ?e . FILTER(STR(?e) = "{ecli}")\n'
        + "  ?werk cdm:resource_legal_id_celex ?celex .\n"
        + "  OPTIONAL { ?werk cdm:work_date_document ?datum }\n"
        + _titels("werk")
        + "\n} LIMIT 10"
    )


def query_werk_op_celex(celex: str) -> str:
    if not _CELEX_RE.match(celex):
        raise ValueError(f"Geen geldige CELEX-vorm: {celex!r}")
    return (
        _CDM
        + "SELECT ?datum ?titel_nl ?titel_en ?eli ?ecli ?oj_id ?oj_datum ?oj_akte_datum WHERE {\n"
        + f'  ?werk cdm:resource_legal_id_celex ?c . FILTER(STR(?c) = "{celex}")\n'
        + "  OPTIONAL { ?werk cdm:work_date_document ?datum }\n"
        + "  OPTIONAL { ?werk cdm:resource_legal_eli ?eli }\n"
        + "  OPTIONAL { ?werk cdm:case-law_ecli ?ecli }\n"
        + '  OPTIONAL { ?werk cdm:work_id_document ?oj_id . FILTER(STRSTARTS(STR(?oj_id), "oj:")) }\n'
        + "  OPTIONAL { ?werk cdm:resource_legal_published_in_official-journal ?pb .\n"
        + "             ?pb cdm:publication_general_date_publication ?oj_datum }\n"
        + "  OPTIONAL { ?werk cdm:official-journal-act_date_publication ?oj_akte_datum }\n"
        + _titels("werk")
        + "\n} LIMIT 10"
    )


def zoekwoorden(query: str) -> list[str]:
    """Veilige zoekwoorden uit vrije tekst: letters, cijfers en koppeltekens, minstens 3 tekens."""
    return [w for w in _WOORD_RE.findall(query) if len(w) >= 3][:8]


def query_zoek_wetgeving(woorden: list[str], max_resultaten: int) -> str:
    """Zoek EU-richtlijnen, -verordeningen en -besluiten met alle woorden in de NL-titel."""
    if not woorden:
        raise ValueError("Geen bruikbare zoekwoorden.")
    for w in woorden:
        if not _WOORD_RE.fullmatch(w):
            raise ValueError(f"Ongeldig zoekwoord: {w!r}")
    uitdrukking = " AND ".join(f"'{w}'" for w in woorden)
    limiet = max(1, min(int(max_resultaten), 100))
    return (
        _CDM
        + "SELECT DISTINCT ?celex ?datum ?titel_nl WHERE {\n"
        + "  ?expr cdm:expression_title ?titel_nl ;\n"
        + f"        cdm:expression_uses_language <{_TAAL_URI.format(code='NLD')}> ;\n"
        + "        cdm:expression_belongs_to_work ?werk .\n"
        + f'  ?titel_nl bif:contains "{uitdrukking}" .\n'
        + "  ?werk cdm:resource_legal_id_celex ?celex .\n"
        + '  FILTER(REGEX(STR(?celex), "^3[0-9]{4}[LRD][0-9]{4}$"))\n'
        + "  OPTIONAL { ?werk cdm:work_date_document ?datum }\n"
        + f"}} ORDER BY DESC(?datum) LIMIT {limiet}"
    )


def kies_titel(rij: dict[str, str]) -> tuple[str, str] | None:
    """(titel, taal): de Nederlandse titel, anders de Engelse; None als er geen is."""
    if rij.get("titel_nl"):
        return rij["titel_nl"], "nl"
    if rij.get("titel_en"):
        return rij["titel_en"], "en"
    return None


def lees_datum(waarde: str | None) -> date | None:
    if not waarde:
        return None
    try:
        return date.fromisoformat(waarde[:10])
    except ValueError:
        return None


_MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
            "september", "oktober", "november", "december"]


def pb_vindplaats(oj_id: str | None, oj_datum: str | None) -> str | None:
    """Vindplaats in het Publicatieblad in VENA-vorm (WG3): "Pb.L. 28 januari 2012, 1".

    De reeks (L/C) en de beginpagina komen uit de Publicatieblad-identificatie van CELLAR
    ("oj:JOL_2012_026_R_0001_01": reeks L, pagina 1); sinds oktober 2023 verschijnt elke
    akte afzonderlijk ("oj:L_202401991") en is er geen paginanummer. De datum is die van het
    Publicatieblad. Alleen uit wat CELLAR effectief meegeeft: zonder datum geen vindplaats
    (VENA vermeldt het nummer van het Publicatieblad niet, dus de datum is onmisbaar).
    """
    d = lees_datum(oj_datum)
    if not oj_id or d is None:
        return None
    datum = f"{d.day} {_MAANDEN[d.month - 1]} {d.year}"
    m = _OJ_OUD_RE.match(oj_id)
    if m:
        pagina = f", {int(m.group(5))}" if m.group(5) else ""
        return f"Pb.{m.group(1)}. {datum}{pagina}"
    m = _OJ_NIEUW_RE.match(oj_id)
    if m:
        return f"Pb.{m.group(1)}. {datum}"
    return None


_BLOKKEN = ["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "dt", "dd", "title"]


def html_naar_tekst(html: str) -> str:
    """Documenttekst uit de CELLAR-HTML: één regel per blok, zonder lege regels.

    Alleen blokelementen breken de regel af; inline-opmaak (span, em, a) blijft binnen de
    zin, zodat de tekst leest zoals het document en de segmentatie de koppen herkent.
    """
    soup = BeautifulSoup(html, "html.parser")
    for weg in soup(["script", "style", "head"]):
        weg.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for blok in soup.find_all(_BLOKKEN):
        blok.insert_before("\n")
        blok.insert_after("\n")
    for cel in soup.find_all("td"):
        cel.insert_after(" ")
    regels = [" ".join(r.split()) for r in soup.get_text("").split("\n")]
    return "\n".join(r for r in regels if r).strip()


def kies_rechtspraak_celex(rijen: list[dict[str, str]]) -> dict[str, str] | None:
    """Kies bij een ECLI de rij van de beslissing zelf (niet een samenvatting of mededeling)."""
    eigen = [r for r in rijen if _CELEX_RECHTSPRAAK_RE.match(r.get("celex", ""))]
    return (eigen or rijen or [None])[0]


# ---------------------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------------------
class Cellar:
    """Kleine CELLAR-client met nette identificatie en rate limiting (injecteerbare client)."""

    #: True wanneer de laatste opvraging op een botcontrole stuitte.
    laatste_botcontrole: bool = False

    def __init__(self, *, client: httpx.Client | None = None, rate_limit_s: float = RATE_LIMIT_S):
        self._eigen_client = client is None
        self._client = client or httpx.Client(
            timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )
        self._rate_limit_s = rate_limit_s
        self._laatste_request = 0.0

    def close(self) -> None:
        if self._eigen_client:
            self._client.close()

    def _wacht(self) -> None:
        verstreken = time.monotonic() - self._laatste_request
        if verstreken < self._rate_limit_s:
            time.sleep(self._rate_limit_s - verstreken)
        self._laatste_request = time.monotonic()

    def _get(self, url: str, **kwargs) -> httpx.Response | None:
        self.laatste_botcontrole = False
        self._wacht()
        kwargs["headers"] = {"User-Agent": USER_AGENT, **kwargs.get("headers", {})}
        try:
            r = self._client.get(url, **kwargs)
        except httpx.HTTPError:
            return None
        if is_botcontrole(r):
            self.laatste_botcontrole = True
            return None
        return r if r.status_code == 200 else None

    def sparql(self, query: str) -> list[dict[str, str]] | None:
        """Voer een SPARQL-query uit; None bij een fout (nooit een verzonnen resultaat)."""
        r = self._get(
            SPARQL_URL,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        if r is None:
            return None
        try:
            return bindingen(r.json())
        except ValueError:
            return None

    def arrest_op_ecli(self, ecli: str) -> dict[str, str] | None:
        rijen = self.sparql(query_arrest_op_ecli(ecli))
        return kies_rechtspraak_celex(rijen) if rijen else None

    def werk_op_celex(self, celex: str) -> dict[str, str] | None:
        rijen = self.sparql(query_werk_op_celex(celex))
        if not rijen:
            return None
        # Meerdere rijen door meerdere OPTIONAL-waarden: voeg samen, eerste waarde wint.
        samen: dict[str, str] = {}
        for rij in rijen:
            for k, v in rij.items():
                samen.setdefault(k, v)
        return samen

    def zoek_wetgeving(self, query: str, max_resultaten: int = 20) -> list[dict[str, str]] | None:
        woorden = zoekwoorden(query)
        if not woorden:
            return []
        return self.sparql(query_zoek_wetgeving(woorden, max_resultaten))

    def tekst(self, celex: str) -> tuple[str, str] | None:
        """(tekst, taal) van het document: Nederlands, anders Engels; None als geen van beide."""
        if not _CELEX_RE.match(celex):
            return None
        for taal, code in (("nl", "nld"), ("en", "eng")):
            r = self._get(
                RESOURCE_CELEX.format(celex=celex),
                headers={"Accept": "text/html, application/xhtml+xml;q=0.9", "Accept-Language": code},
            )
            if r is not None and r.text.strip():
                tekst = html_naar_tekst(r.text)
                if tekst:
                    return tekst, taal
            if self.laatste_botcontrole:
                return None
        return None
