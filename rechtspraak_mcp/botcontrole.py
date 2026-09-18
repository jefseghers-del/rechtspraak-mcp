# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Herkennen van botcontroles in HTTP-antwoorden, zodat de adapters meteen stoppen.

Harde regel van het project: botcontroles worden nooit omzeild. Een adapter die zo'n
controle krijgt, probeert het niet opnieuw en geeft niets terug; de server meldt dan eerlijk
waarom er niets is opgehaald (dat zegt niets over het bestaan van het document).

Vondsten van 18 september 2026:

* EUR-Lex antwoordt op geautomatiseerde opvragingen met HTTP 202, een lege body en de header
  ``x-amzn-waf-action: challenge`` (AWS WAF). Dat 202-antwoord werd eerder gelezen als
  "pagina wordt nog gegenereerd" en opnieuw geprobeerd; met die header is het een
  botcontrole. EU-rechtspraak en -wetgeving lopen daarom via CELLAR (cellar.py).
* HUDOC (Cloudflare) toont met tussenpozen een challenge (HTTP 403,
  ``cf-mitigated: challenge``).
"""
from __future__ import annotations

import httpx


def melding_botcontrole(bron: str) -> str:
    """Eerlijke uitleg voor de gebruiker wanneer een bron een botcontrole toonde."""
    return (
        f"{bron} vroeg bij deze opvraging een botcontrole. De connector omzeilt zulke "
        "controles niet en probeert het ook niet opnieuw; er is daarom niets opgehaald, en "
        "dat zegt niets over het bestaan van het document. Probeer het later opnieuw, of "
        "open de link hieronder zelf in de browser."
    )


MELDING_EURLEX = melding_botcontrole("EUR-Lex (via CELLAR)")
MELDING_HUDOC = melding_botcontrole("HUDOC (EHRM)")


def is_botcontrole(r: httpx.Response) -> bool:
    """Is dit antwoord een botcontrole (challenge) in plaats van inhoud?"""
    waf = r.headers.get("x-amzn-waf-action", "").lower()
    return waf in ("challenge", "captcha", "block") or r.headers.get("cf-mitigated", "").lower() == "challenge"
