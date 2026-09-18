# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Stub-adapter voor de Arrestendatabank (arrestendatabank.be).

Haalbaarheid: 🔴 ROOD (zie docs/bronnenonderzoek.md). Technisch scraperbaar, MAAR de
gebruiksvoorwaarden (disclaimer) verbieden UITDRUKKELIJK bulk-download, systematisch
verzamelen, integratie in andere toepassingen/databanken en commercieel hergebruik. De
bron beroept zich op auteursrecht (Wet 30 juni 1994) én databankbescherming (Wet 31 aug 1998).

DAAROM: deze adapter staat standaard UITGESCHAKELD (enabled = False) en mag NIET worden
geïmplementeerd zonder voorafgaande overeenkomst met het agentschap Justitie en Handhaving.
Contact: info.arrestendatabank@vlaanderen.be.
"""
from __future__ import annotations

from datetime import date

from .base import RechtspraakAdapter
from ..schema import Treffer, Uitspraak, ZoekQuery

_BLOKKADE = (
    "Arrestendatabank: geautomatiseerd hergebruik is contractueel verboden. "
    "Adapter uitgeschakeld tot er een overeenkomst is. Zie docs/bronnenonderzoek.md."
)


class ArrestendatabankAdapter(RechtspraakAdapter):
    bron = "arrestendatabank"
    instantie = "Arrestendatabank Vlaams Handhavingsbeleid"
    enabled = False  # bewust uit: zie module-docstring en _BLOKKADE

    def zoek(self, query: ZoekQuery) -> list[Treffer]:
        # TODO: NIET implementeren zonder overeenkomst.
        return []

    def zoek_op_identifier(self, identifier: str, datum: date | None = None) -> list[Treffer]:
        return []

    def haal_uitspraak(self, url: str) -> Uitspraak | None:
        raise NotImplementedError(_BLOKKADE)
