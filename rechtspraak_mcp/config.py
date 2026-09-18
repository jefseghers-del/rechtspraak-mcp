# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Configuratie via omgevingsvariabelen: bewust aanzetten van automatisch ophalen.

Waarom de defaults UIT staan
----------------------------
De adapters staan robots-conform standaard op "niet automatisch ophalen"
(``JuportalAdapter.sta_fetch = False``, ``RaadVanStateAdapter.sta_fetch = False``,
``DbrcAdapter.sta_zoek_scraping = False``). De robots-vondsten en gebruiksvoorwaarden per
bron staan gedocumenteerd in docs/bronnenonderzoek.md en in de moduledocstrings van de
adapters zelf. Aanzetten is een bewuste gebruikerskeuze, geen codewijziging: deze module
leest daarvoor drie omgevingsvariabelen en past ze toe op adapter-instanties, zonder de
klasse-defaults te wijzigen.

Omgevingsvariabelen
-------------------
``RECHTSPRAAK_MCP_STA_FETCH``
    Kommagescheiden broncodes, bv. ``"juportal,raadvanstate"``. Voor elke genoemde code
    wordt op de betrokken adapter-instantie ``sta_fetch = True`` gezet. Whitespace wordt
    getrimd, de vergelijking is hoofdletterongevoelig. Onbekende codes worden genegeerd
    maar verzameld in ``Config.onbekende_codes`` zodat de aanroeper kan waarschuwen.
    Bekende codes: ``juportal`` en ``raadvanstate``.

``RECHTSPRAAK_MCP_DBRC_ZOEK_SCRAPING``
    Waarheidswaarde (``"1"``, ``"true"`` of ``"ja"``, hoofdletterongevoelig) die
    ``DbrcAdapter.sta_zoek_scraping = True`` zet. Dit is BEWUST een aparte variabele:
    het DBRC-zoekendpoint (querystring ``search_api_fulltext``) is door robots.txt
    uitdrukkelijk verboden voor geautomatiseerde crawlers, en geautomatiseerd/breed
    hergebruik vergt voorafgaande schriftelijke toestemming van de DBRC. Zet deze
    variabele dus enkel aan wie zo'n DBRC-akkoord heeft. De DBRC-identifier-HEAD-probe
    (robots-conform) staat los hiervan en werkt altijd.

``RECHTSPRAAK_MCP_BROWSER_ZOEK``
    Kommagescheiden broncodes (zelfde parsing als ``RECHTSPRAAK_MCP_STA_FETCH``) waarvoor
    het browser-gedreven vrijetekstzoeken wordt ingeschakeld: een headless Chromium
    (Playwright) vult het zoekformulier van de bron in zoals een gebruiker dat doet.
    LET WEL: dit automatiseert een zoek-endpoint dat robots.txt afraadt. Dat is een
    richtlijn, geen technische afweer, en het inschakelen is een uitdrukkelijke keuze en
    verantwoordelijkheid van de gebruiker — zie docs/bronnen-gebruiksvoorwaarden.md en de
    moduledocstring van ``rechtspraak_mcp.browser_zoek``. Daarom staat het STANDAARD UIT
    en is Playwright een optionele dependency (``pip install 'rechtspraak-mcp[browser]'``).
    Geldige codes zijn de ``ONDERSTEUNDE_BRONNEN`` uit ``browser_zoek`` (momenteel enkel
    ``juportal``); andere codes worden genegeerd en verzameld in ``Config.onbekende_codes``.

De arrestendatabank-adapter blijft hoe dan ook uitgeschakeld (``enabled = False``);
deze module kan en mag die niet activeren.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from .browser_zoek import ONDERSTEUNDE_BRONNEN

#: Naam van de omgevingsvariabele met kommagescheiden broncodes voor ``sta_fetch``.
ENV_STA_FETCH = "RECHTSPRAAK_MCP_STA_FETCH"
#: Naam van de aparte omgevingsvariabele voor DBRC-zoek-scraping (vergt DBRC-akkoord).
ENV_DBRC_ZOEK_SCRAPING = "RECHTSPRAAK_MCP_DBRC_ZOEK_SCRAPING"
#: Naam van de omgevingsvariabele met kommagescheiden broncodes voor browser-zoeken (opt-in).
ENV_BROWSER_ZOEK = "RECHTSPRAAK_MCP_BROWSER_ZOEK"

#: Broncodes waarvoor ``sta_fetch`` via ``RECHTSPRAAK_MCP_STA_FETCH`` gezet kan worden.
#: ``hvj`` (Hof van Justitie EU, via EUR-Lex) en ``ehrm`` (via de HUDOC-API) zijn open
#: bronnen (geen robots-beperking, vrij hergebruik), maar volgen consistent hetzelfde
#: opt-in-patroon: standaard geen netwerk tot de gebruiker ze aanzet.
BEKENDE_FETCH_CODES = frozenset({"juportal", "raadvanstate", "hvj", "ehrm", "eurlex", "codex", "justel"})

#: Broncodes waarvoor browser-zoeken bestaat (bron van waarheid: ``browser_zoek``-module).
BEKENDE_BROWSER_ZOEK_CODES = frozenset(ONDERSTEUNDE_BRONNEN)

#: Waarden die als "waar" gelden voor ``RECHTSPRAAK_MCP_DBRC_ZOEK_SCRAPING``.
_WAAR = frozenset({"1", "true", "ja"})


@dataclass(frozen=True)
class Config:
    """Geparste configuratie uit de omgevingsvariabelen.

    Attributen:
        sta_fetch: broncodes (genormaliseerd, lowercase) waarvoor de gebruiker
            automatisch ophalen bewust heeft aangezet.
        dbrc_zoek_scraping: True enkel wanneer de gebruiker de aparte DBRC-variabele
            heeft aangezet (vergt een DBRC-akkoord, zie moduledocstring).
        browser_zoek: broncodes (genormaliseerd, lowercase) waarvoor de gebruiker het
            browser-gedreven zoeken bewust heeft aangezet (opt-in, zie moduledocstring).
        onbekende_codes: codes uit ``RECHTSPRAAK_MCP_STA_FETCH`` of
            ``RECHTSPRAAK_MCP_BROWSER_ZOEK`` die niet herkend of niet ondersteund
            werden; genegeerd, maar bewaard zodat de aanroeper kan waarschuwen.
    """

    sta_fetch: frozenset[str] = field(default_factory=frozenset)
    dbrc_zoek_scraping: bool = False
    browser_zoek: frozenset[str] = field(default_factory=frozenset)
    onbekende_codes: frozenset[str] = field(default_factory=frozenset)


def lees_config(env: Mapping[str, str] | None = None) -> Config:
    """Lees de configuratie uit ``env`` (default: ``os.environ``).

    Puur en injecteerbaar: tests geven een eigen mapping mee en zijn zo onafhankelijk
    van de echte procesomgeving.
    """
    if env is None:
        env = os.environ

    fetch_gevraagd = _parse_codes(env.get(ENV_STA_FETCH, ""))
    browser_gevraagd = _parse_codes(env.get(ENV_BROWSER_ZOEK, ""))

    dbrc_waarde = env.get(ENV_DBRC_ZOEK_SCRAPING, "").strip().lower()

    return Config(
        sta_fetch=frozenset(fetch_gevraagd & BEKENDE_FETCH_CODES),
        dbrc_zoek_scraping=dbrc_waarde in _WAAR,
        browser_zoek=frozenset(browser_gevraagd & BEKENDE_BROWSER_ZOEK_CODES),
        onbekende_codes=frozenset(
            (fetch_gevraagd - BEKENDE_FETCH_CODES)
            | (browser_gevraagd - BEKENDE_BROWSER_ZOEK_CODES)
        ),
    )


def _parse_codes(ruw: str) -> set[str]:
    """Parse een kommagescheiden codelijst: trim, lowercase, lege stukken weg."""
    return {stuk.strip().lower() for stuk in ruw.split(",") if stuk.strip()}


def pas_toe(adapter, config: Config) -> None:
    """Pas ``config`` toe op één adapter-instantie.

    Zet uitsluitend instantie-attributen (de klasse-defaults blijven False):

    * ``sta_fetch = True`` op adapters wier ``bron`` in ``config.sta_fetch`` zit;
    * ``sta_zoek_scraping = True`` op de DBRC-adapter wanneer
      ``config.dbrc_zoek_scraping`` waar is.

    Zet nooit iets op False en raakt ``enabled`` niet aan: uitgeschakelde adapters
    (arrestendatabank) blijven uitgeschakeld.
    """
    bron = getattr(adapter, "bron", "")
    if bron in config.sta_fetch and hasattr(adapter, "sta_fetch"):
        adapter.sta_fetch = True
    if bron == "dbrc" and config.dbrc_zoek_scraping and hasattr(adapter, "sta_zoek_scraping"):
        adapter.sta_zoek_scraping = True
