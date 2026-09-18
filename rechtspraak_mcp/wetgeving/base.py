# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Basisinterface voor wetgevingsadapters (spiegel van adapters/base.py, maar voor normen).

Elke wetgevingsbron (EUR-Lex, Vlaamse Codex, Justel, ...) implementeert deze interface.
De adapter vertaalt een zoekopdracht of identifier naar het formaat van de bron en
normaliseert de respons naar het `Norm`-schema in schema.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..schema import Norm, NormTekst


class WetgevingAdapter(ABC):
    """Abstracte basisadapter voor wetgeving. Subklassen zetten `bron`, `naam`, `enabled`."""

    #: Technische broncode, bv. "eurlex". Komt in Norm.bron terecht.
    bron: str = ""
    #: Mensvriendelijke naam van de bron.
    naam: str = ""
    #: Of de adapter meedraait in de fan-out.
    enabled: bool = True
    #: Automatisch ophalen: bewuste opt-in per bron, consistent met het rechtspraakspoor.
    sta_fetch: bool = False

    @abstractmethod
    def zoek(self, query: str, *, max_resultaten: int = 20) -> list[Norm]:
        """Vrije-tekst/trefwoordzoekopdracht. Geeft genormaliseerde normen terug."""

    @abstractmethod
    def zoek_op_identifier(self, identifier: str) -> list[Norm]:
        """Zoek op CELEX, ELI, normnummer ('2011/92/EU') e.d. Meestal 0 of 1 norm."""

    @abstractmethod
    def haal_norm(self, url: str) -> NormTekst | None:
        """Haal de tekst van één norm op via de bron-URL."""
