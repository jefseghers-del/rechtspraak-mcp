# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Adapterregister.

`alle_adapters()` geeft alle bekende adapters terug; `actieve_adapters()` enkel die met
`enabled = True`. De server fant zoekopdrachten uit over de actieve adapters.

Bij elke aanroep van `alle_adapters()` wordt de omgevingsconfiguratie
(zie `rechtspraak_mcp.config`) vers gelezen en toegepast op de nieuwe instanties:
zo kan de gebruiker automatisch ophalen per bron bewust aanzetten via
omgevingsvariabelen, zonder dat de robots-conforme klasse-defaults wijzigen.
Er is bewust geen module-level cache, zodat tests met env-injectie of monkeypatch
deterministisch blijven.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping

from ..browser_zoek import PlaywrightZoeker
from ..config import Config, lees_config, pas_toe
from .arrestendatabank import ArrestendatabankAdapter
from .base import RechtspraakAdapter
from .dbrc import DbrcAdapter
from .ehrm import EhrmAdapter
from .hvj import HvjAdapter
from .juportal import JuportalAdapter
from .raad_van_state import RaadVanStateAdapter

__all__ = [
    "RechtspraakAdapter",
    "DbrcAdapter",
    "JuportalAdapter",
    "RaadVanStateAdapter",
    "HvjAdapter",
    "EhrmAdapter",
    "ArrestendatabankAdapter",
    "alle_adapters",
    "actieve_adapters",
]

logger = logging.getLogger(__name__)


def alle_adapters(env: Mapping[str, str] | None = None) -> list[RechtspraakAdapter]:
    """Maak verse adapter-instanties aan en pas de omgevingsconfiguratie toe.

    `env` is injecteerbaar voor tests; default is `os.environ`. Onbekende codes in
    `RECHTSPRAAK_MCP_STA_FETCH` worden genegeerd, met een waarschuwing in de log.
    """
    config: Config = lees_config(os.environ if env is None else env)
    if config.onbekende_codes:
        logger.warning(
            "Onbekende/niet-ondersteunde broncode(s) in RECHTSPRAAK_MCP_STA_FETCH of "
            "RECHTSPRAAK_MCP_BROWSER_ZOEK genegeerd: %s",
            ", ".join(sorted(config.onbekende_codes)),
        )
    adapters: list[RechtspraakAdapter] = [
        DbrcAdapter(),
        RaadVanStateAdapter(),
        JuportalAdapter(),
        HvjAdapter(),
        EhrmAdapter(),
        ArrestendatabankAdapter(),
    ]
    for adapter in adapters:
        pas_toe(adapter, config)
    if config.browser_zoek:
        # ÉÉN gedeelde zoeker voor alle browser-zoek-adapters: zo geldt de rate limit over
        # de bronnen heen. Constructie is veilig zonder playwright (lazy import in de
        # methode); pas een effectieve zoekopdracht geeft dan een ZoekError met hint.
        zoeker = PlaywrightZoeker()
        for adapter in adapters:
            if getattr(adapter, "bron", "") in config.browser_zoek:
                _injecteer_zoeker(adapter, zoeker)
    return adapters


def _injecteer_zoeker(adapter: RechtspraakAdapter, zoeker: PlaywrightZoeker) -> None:
    """Injecteer de gedeelde browser-zoeker in één adapter-instantie.

    Contract met de adapters (nu: JuportalAdapter): de zoeker leeft in het attribuut
    ``_zoeker`` en ``browser_zoek_aan = True`` schakelt het browser-zoekpad in. We zetten
    beide als instantie-attributen ná constructie — dat is robuust ongeacht of de adapter
    (al) een ``zoeker=``-constructorkeyword aanbiedt, en laat de robots-conforme
    klasse-defaults ongemoeid.
    """
    adapter._zoeker = zoeker
    adapter.browser_zoek_aan = True


def actieve_adapters(env: Mapping[str, str] | None = None) -> list[RechtspraakAdapter]:
    """Enkel de adapters met `enabled = True` (de arrestendatabank valt er dus uit)."""
    return [a for a in alle_adapters(env) if a.enabled]
