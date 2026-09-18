# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Basisinterface voor bronadapters.

Elke bron (DBRC, Juportal, Raad van State, ...) implementeert deze interface. De adapter
vertaalt een genormaliseerde ZoekQuery naar het formaat van de bron en normaliseert de
respons terug naar het interne Treffer-schema. Zo blijft de brongebonden logica gescheiden
(spec, punt 5: "adapters gescheiden houden").

Een adapter voert nog GEEN echte scraping uit in deze scaffold. De methodes geven een lege
lijst of None terug met een duidelijke TODO, of heffen NotImplementedError op.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..schema import Treffer, Uitspraak, ZoekQuery


class RechtspraakAdapter(ABC):
    """Abstracte basisadapter. Subklassen zetten `bron`, `instantie` en `enabled`."""

    #: Technische broncode, bv. "dbrc". Komt in Treffer.bron terecht.
    bron: str = ""
    #: Mensvriendelijke naam van het rechtscollege.
    instantie: str = ""
    #: Of de adapter meedraait in de fan-out. Zet False bij juridische/technische blokkering.
    enabled: bool = True

    @abstractmethod
    def zoek(self, query: ZoekQuery) -> list[Treffer]:
        """Vrije-tekst/trefwoordzoekopdracht. Geeft genormaliseerde treffers terug."""

    @abstractmethod
    def zoek_op_identifier(self, identifier: str, datum: date | None = None) -> list[Treffer]:
        """Zoek op ECLI of rol-/arrestnummer. Meestal 0 of 1 treffer.

        `datum` is de (bij benadering) gekende uitspraakdatum. Bronnen die een identifier
        direct naar een URL vertalen (Juportal, RvS, HvJ, EHRM) hebben die niet nodig en
        negeren ze; de DBRC-adapter moet de publicatiemaand raden en gebruikt ze als anker,
        wat het aantal HEAD-probes — en dus de wachttijd — drastisch terugbrengt.
        """

    @abstractmethod
    def haal_uitspraak(self, url: str) -> Uitspraak | None:
        """Haal de volledige (of verkorte) tekst van één uitspraak op via de bron-URL."""
