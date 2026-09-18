# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""BE-rechtspraak: MCP-connector voor Belgische en Europese rechtspraak en wetgeving.

Eén bron voor versie, repository-URL, User-Agent, disclaimer en privacyverklaring. README,
handleiding, manifest, serverinstructies en tool-antwoorden nemen deze teksten over. Wijzig
ze hier, niet op de afzonderlijke plaatsen (tests bewaken dat ze overal aanwezig blijven).
"""

__all__ = ["__version__", "REPO_URL", "user_agent", "DISCLAIMER", "DISCLAIMER_KORT", "PRIVACY"]
__version__ = "0.1.0"

REPO_URL = "https://github.com/jefseghers-del/rechtspraak-mcp"


def user_agent(doel: str) -> str:
    """Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt."""
    return f"rechtspraak-mcp/{__version__} ({doel}; +{REPO_URL})"


DISCLAIMER_KORT = (
    "Betaversie, geen product — zonder enige garantie en zonder aansprakelijkheid; geen juridisch "
    "advies. De gebruiker is zelf verantwoordelijk voor de controle en het gebruik van de resultaten."
)

DISCLAIMER = (
    "Betaversie — geen product, geen garantie, geen aansprakelijkheid. Deze software is een experimenteel "
    "hulpmiddel in ontwikkeling, geen commercieel product of dienst. Ze wordt kosteloos aangeboden zoals ze "
    "is, zonder enige uitdrukkelijke of stilzwijgende garantie, onder meer over juistheid, volledigheid, "
    "actualiteit of geschiktheid voor een bepaald doel. De resultaten zijn een geautomatiseerde opvraging van "
    "publieke rechtspraak- en wetgevingsbronnen; ze zijn geen juridisch advies en vervangen geen raadpleging "
    "van de officiële bron of een eigen juridische analyse. Een zoektreffer of fragment kan aanslaan op wat "
    "een partij aanvoert in plaats van op het oordeel van het rechtscollege: citeer alleen na controle in de "
    "officiële bron. Nul treffers betekent niet dat een uitspraak of norm niet bestaat. De gebruiker is zelf "
    "volledig verantwoordelijk voor het controleren van de resultaten en voor elk gebruik dat ervan wordt "
    "gemaakt, ook voor het naleven van de gebruiksvoorwaarden van de geraadpleegde bronnen. De auteur is niet "
    "aansprakelijk voor schade die voortvloeit uit het gebruik van de software of de resultaten."
)

PRIVACY = (
    "De connector bewaart geen uitspraken, wetteksten of zoekopdrachten: er is geen cache en geen "
    "geschiedenis, en niets van de opgevraagde inhoud wordt naar schijf geschreven. Opvragingen gaan "
    "rechtstreeks van de eigen computer naar de bron; er is geen tussenserver van de auteur. Uitspraken "
    "kunnen persoonsgegevens bevatten zoals de bron ze publiceert; wat de gebruiker daarmee doet, valt onder "
    "diens eigen verantwoordelijkheid. De connector schrijft alleen technische meldingen naar het logbestand "
    "van Claude Desktop, geen inhoud van uitspraken."
)
