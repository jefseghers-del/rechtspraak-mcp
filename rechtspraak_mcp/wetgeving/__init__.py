# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Wetgevingsspoor: adapters voor wetgevingsbronnen (EUR-Lex; later Vlaamse Codex, Justel).

Tweede spoor naast de rechtspraakadapters (spec: docs/spec-gerichte-zoekfunctie.md en de
fasering beslist op 9 augustus 2026). Zelfde ontwerpprincipes: adapters gescheiden per bron,
normalisatie naar één schema (`Norm` in schema.py), anti-hallucinatie (alleen wat de bron
effectief teruggeeft, altijd een controleerbare URL), en automatisch ophalen achter een
bewuste opt-in (`sta_fetch`, via `RECHTSPRAAK_MCP_STA_FETCH=...,eurlex`).

Het register spiegelt adapters/__init__.py: verse instanties per aanroep, config per
aanroep toegepast, geen module-level cache. `maak_zoeker()` levert daarnaast de
zoeker op titelwoorden in EU-wetgeving (EurlexZoeker, via CELLAR) wanneer de eurlex-bron aan staat — het zoeken en
het identifier-ophalen delen zo dezelfde opt-in.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

from ..config import Config, lees_config, pas_toe
from .base import WetgevingAdapter
from .codex import CodexAdapter
from .eurlex import EurlexWetgevingAdapter
from .eurlex_zoek import EurlexZoeker
from .justel import JustelAdapter

__all__ = [
    "WetgevingAdapter",
    "EurlexWetgevingAdapter",
    "CodexAdapter",
    "JustelAdapter",
    "EurlexZoeker",
    "alle_wetgeving_adapters",
    "actieve_wetgeving_adapters",
    "maak_zoeker",
]


def alle_wetgeving_adapters(env: Mapping[str, str] | None = None) -> list[WetgevingAdapter]:
    """Maak verse wetgevingsadapter-instanties aan en pas de omgevingsconfiguratie toe."""
    config: Config = lees_config(os.environ if env is None else env)
    adapters: list[WetgevingAdapter] = [
        EurlexWetgevingAdapter(),
        CodexAdapter(),
        JustelAdapter(),
    ]
    for adapter in adapters:
        pas_toe(adapter, config)
    return adapters


def actieve_wetgeving_adapters(env: Mapping[str, str] | None = None) -> list[WetgevingAdapter]:
    """Enkel de wetgevingsadapters met `enabled = True`."""
    return [a for a in alle_wetgeving_adapters(env) if a.enabled]


def maak_zoeker(env: Mapping[str, str] | None = None) -> EurlexZoeker | None:
    """Geef de EUR-Lex-vrije-tekst-zoeker wanneer de eurlex-bron aan staat, anders None.

    Zelfde opt-in als het identifier-ophalen (`RECHTSPRAAK_MCP_STA_FETCH=...,eurlex`):
    één schakelaar per bron, geen aparte vlag voor het zoeken — EUR-Lex kent geen
    robots-beperking en vrij hergebruik, dus er is geen reden om beide te splitsen.
    """
    config = lees_config(os.environ if env is None else env)
    if "eurlex" not in config.sta_fetch:
        return None
    return EurlexZoeker()
