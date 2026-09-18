# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Nep-CELLAR voor de tests: beantwoordt SPARQL- en tekstopvragingen uit vaste fixtures.

De fixtures zijn echte antwoorden van CELLAR, opgehaald op 18 september 2026:

* cellar_sparql_ecli_waddenzee.json   — ECLI:EU:C:2004:482 (C-127/02, Waddenzee)
* cellar_sparql_ecli_cassis.json      — ECLI:EU:C:1979:42 (120/78, Cassis de Dijon)
* cellar_sparql_celex_*.json          — metadata per CELEX (32011L0092, 32024R1991, 62002CJ0127)
* cellar_sparql_zoek_milieueffectbeoordeling.json — zoeken op titelwoord
* cellar_sparql_leeg.json             — geen resultaat
* cellar_hvj_*_nl.html, cellar_norm_32011L0092_nl.html — documenttekst (Nederlands)
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from rechtspraak_mcp.cellar import Cellar

FIXTURES = Path(__file__).parent / "fixtures"

SPARQL_PER_SLEUTEL = {
    '"ECLI:EU:C:2004:482"': "cellar_sparql_ecli_waddenzee.json",
    '"ECLI:EU:C:1979:42"': "cellar_sparql_ecli_cassis.json",
    '"32011L0092"': "cellar_sparql_celex_32011L0092.json",
    '"32024R1991"': "cellar_sparql_celex_32024R1991.json",
    '"62002CJ0127"': "cellar_sparql_celex_62002CJ0127.json",
    "'milieueffectbeoordeling'": "cellar_sparql_zoek_milieueffectbeoordeling.json",
}
TEKST_PER_CELEX = {
    "62002CJ0127": "cellar_hvj_waddenzee_nl.html",
    "61978CJ0120": "cellar_hvj_cassis_nl.html",
    "32011L0092": "cellar_norm_32011L0092_nl.html",
}


def lees(naam: str) -> str:
    return (FIXTURES / naam).read_text(encoding="utf-8")


def handler(verzoeken: list[httpx.Request] | None = None, *, alleen_engels: bool = False):
    """httpx-handler die CELLAR nabootst; legt de verzoeken vast in `verzoeken`."""

    def _h(request: httpx.Request) -> httpx.Response:
        if verzoeken is not None:
            verzoeken.append(request)
        if request.url.path == "/webapi/rdf/sparql":
            query = request.url.params.get("query", "")
            naam = next((f for k, f in SPARQL_PER_SLEUTEL.items() if k in query), "cellar_sparql_leeg.json")
            return httpx.Response(200, json=json.loads(lees(naam)))
        if request.url.path.startswith("/resource/celex/"):
            celex = request.url.path.rsplit("/", 1)[-1]
            taal = request.headers.get("accept-language", "")
            if celex in TEKST_PER_CELEX and (taal == "eng" if alleen_engels else taal == "nld"):
                return httpx.Response(200, text=lees(TEKST_PER_CELEX[celex]))
            return httpx.Response(404)
        return httpx.Response(404)

    return _h


def nep_cellar(verzoeken: list[httpx.Request] | None = None, **kwargs) -> Cellar:
    client = httpx.Client(transport=httpx.MockTransport(handler(verzoeken, **kwargs)), follow_redirects=True)
    return Cellar(client=client, rate_limit_s=0.0)


def cellar_met(handler_functie) -> Cellar:
    client = httpx.Client(transport=httpx.MockTransport(handler_functie), follow_redirects=True)
    return Cellar(client=client, rate_limit_s=0.0)
