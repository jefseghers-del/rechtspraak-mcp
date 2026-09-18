# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Zoeken in EU-wetgeving op woorden in het opschrift, via CELLAR.

Vroeger zocht deze module op de EUR-Lex-zoekpagina (search.html). Sinds september 2026 zet
EUR-Lex daar een botcontrole (AWS WAF) voor, en die omzeilen we niet. CELLAR, de
open-data-dienst van het Publicatiebureau, heeft een volledige-tekstindex op de titels
(SPARQL met ``bif:contains``). Daarmee zoekt deze module in de Nederlandse opschriften van
richtlijnen, verordeningen en besluiten (CELEX sector 3, letters L/R/D).

Beperking, eerlijk gemeld aan de gebruiker: er wordt in het opschrift gezocht, niet in de
volledige tekst. Een zoekwoord moet dus in de titel staan ("milieueffectbeoordeling",
"natuurherstel", "habitats"). Alle woorden moeten voorkomen; woorden van minder dan drie
tekens worden genegeerd. Resultaten staan van nieuw naar oud.

Anti-hallucinatie: alleen wat CELLAR teruggeeft; bij een fout een lege lijst.
"""
from __future__ import annotations

from ..cellar import Cellar, lees_datum
from ..schema import Norm
from .eurlex import _NUMMER_IN_OPSCHRIFT_RE, celex_naar_nummer_en_type, content_deeplink

#: Uitleg die de server meegeeft bij vrij zoeken in EU-wetgeving.
BEPERKING = (
    "EU-wetgeving is doorzocht op woorden in het opschrift (niet in de volledige tekst), "
    "via CELLAR."
)


def norm_uit_zoekrij(rij: dict[str, str]) -> Norm | None:
    """Puur: Norm uit een zoekresultaatrij (CELEX, datum, NL-opschrift)."""
    celex = rij.get("celex", "")
    afgeleid = celex_naar_nummer_en_type(celex)
    opschrift = " ".join((rij.get("titel_nl") or "").split())
    if afgeleid is None or not opschrift:
        return None
    type_, celex_nummer = afgeleid
    m_nr = _NUMMER_IN_OPSCHRIFT_RE.match(opschrift)
    return Norm(
        bron="eurlex",
        type=type_,
        nummer=m_nr.group(1) if m_nr else celex_nummer,
        opschrift=opschrift,
        datum=lees_datum(rij.get("datum")),
        celex=celex,
        eli=None,  # niet opgevraagd in de zoekquery; haal de norm op voor ELI en PB
        vindplaats=None,
        url=content_deeplink(celex),
    )


class EurlexZoeker:
    """Zoeker op titelwoorden in EU-wetgeving (CELLAR). Injecteerbare client voor tests.

    Geen sta_fetch-gate hier: die zit in het register (maak_zoeker) dat deze module aankoppelt.
    """

    #: True wanneer de laatste opvraging op een botcontrole stuitte (zie botcontrole.py).
    laatste_botcontrole: bool = False

    def __init__(self, *, cellar: Cellar | None = None):
        self._eigen_cellar = cellar is None
        self._cellar = cellar or Cellar()

    def close(self) -> None:
        if self._eigen_cellar:
            self._cellar.close()

    def zoek(self, query: str, max_resultaten: int = 20) -> list[Norm]:
        """Zoek normen waarvan het Nederlandse opschrift alle zoekwoorden bevat."""
        if not query.strip() or max_resultaten < 1:
            return []
        rijen = self._cellar.zoek_wetgeving(query, max_resultaten)
        self.laatste_botcontrole = self._cellar.laatste_botcontrole
        normen: list[Norm] = []
        gezien: set[str] = set()
        for rij in rijen or []:
            norm = norm_uit_zoekrij(rij)
            if norm is not None and norm.celex not in gezien:
                gezien.add(norm.celex)
                normen.append(norm)
        return normen[:max_resultaten]
