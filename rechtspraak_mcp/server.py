# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""MCP-server BE-rechtspraak: Belgische en Europese rechtspraak en wetgeving.

Tools:
  - zoek_rechtspraak      : vrije tekst/trefwoorden over de actieve bronnen
  - zoek_op_identifier    : ECLI, arrest-, rol- of zaaknummer
  - haal_uitspraak        : tekst van één uitspraak via bron-URL, met het beoordelende deel
  - zoek_wetgeving        : EU- en Belgische wetgeving op identifier of vrije tekst
  - haal_norm             : tekst van één norm via bron-URL

De tools fannen uit over de actieve adapters (adapters/__init__.py, wetgeving/__init__.py)
en geven genormaliseerde schema's terug (schema.py), telkens met een controleerbare bron-URL
en een voorstel van VENA-verwijzing.

Anti-hallucinatie (spec, punt 4): de tools geven enkel terug wat een adapter effectief van de
bron ontvangt. Bronnen die standaard uit staan, leveren niets; de respons legt dat dan uit.

Lokaal draaien (stdio):  python -m rechtspraak_mcp.server
"""
from __future__ import annotations

import os
import urllib.parse
from datetime import date

from mcp.server.mcpserver import MCPServer

import re

from . import DISCLAIMER, PRIVACY, REPO_URL, __version__
from .adapters import actieve_adapters
from .adapters import dbrc as _dbrc
from .adapters import ehrm as _ehrm
from .adapters import hvj as _hvj
from .adapters import juportal as _juportal
from .adapters import raad_van_state as _rvs
from .botcontrole import MELDING_EURLEX, MELDING_HUDOC
from .schema import Norm, NormTekst, Treffer, Uitspraak, WetgevingRespons, ZoekQuery, ZoekRespons
from .segmentatie import segmenteer
from .verwijzing import vena_verwijzing, vena_verwijzing_norm
from .wetgeving import actieve_wetgeving_adapters, maak_zoeker
from .wetgeving import codex as _codex
from .wetgeving import eurlex as _eurlex
from .wetgeving import eurlex_zoek as _eurlex_zoek
from .wetgeving import justel as _justel

INSTRUCTIES = (
    DISCLAIMER + "\n\n" + PRIVACY + "\n\n"
    "Aanwijzing voor het model: vermeld bij elk inhoudelijk resultaat van deze server kort dat het om een "
    "betaversie gaat, zonder garantie of aansprakelijkheid en zonder juridisch advies, en dat de gebruiker "
    "zelf verantwoordelijk blijft voor controle en gebruik. Geef alleen terug wat de tools opleveren en vul "
    "nooit rechtspraak of citaten aan die niet uit een tool-respons komen; vermeld bij elke uitspraak de "
    "bron-URL. Citeer alleen uit het veld `beoordeling` (het beoordelende deel), nooit uit wat partijen "
    "aanvoeren. Nul treffers betekent niet dat een uitspraak of norm niet bestaat."
)

mcp = MCPServer(
    "be-rechtspraak",
    title="BE-rechtspraak (beta)",
    description=(
        "Belgische en Europese rechtspraak en wetgeving met controleerbare bron-URL's. "
        "Betaversie, geen product, zonder garantie of aansprakelijkheid."
    ),
    instructions=INSTRUCTIES,
    website_url=REPO_URL,
    version=__version__,
)

def _schakelaar_uit(titel: str, code: str) -> str:
    """Uitleg bij een bron die standaard uit staat: waar de gebruiker ze aanzet."""
    return (
        "het automatisch ophalen staat uit. In Claude Desktop: Instellingen → Extensies → "
        f"BE-rechtspraak → Configureren, schakelaar '{titel}' (lees eerst de toelichting over "
        f"robots.txt en de eigen verantwoordelijkheid); buiten Claude Desktop: "
        f"RECHTSPRAAK_MCP_STA_FETCH={code}."
    )


# Rolnummer Hof van Cassatie (AR), bv. "P.12.1389.N", "C.20.0061.N", "F.08.0035.F".
_CASS_AR_RE = re.compile(r"^\s*(?:AR\s+)?[A-Za-z]\.\s?\d{2}\.\d{4}\.[A-Za-z]\s*$")


def _met_verwijzing(treffers: list[Treffer]) -> list[Treffer]:
    """Vul per treffer het voorstel van VENA-voetnootverwijzing in (docs/verwijsregels.md)."""
    for t in treffers:
        if t.verwijzing is None:
            t.verwijzing = vena_verwijzing(t)
    return treffers


@mcp.tool()
def zoek_rechtspraak(
    query: str,
    instanties: list[str] | None = None,
    datum_van: date | None = None,
    datum_tot: date | None = None,
    max_resultaten: int = 20,
) -> ZoekRespons:
    """Doorzoek Belgische rechtspraakbronnen op vrije tekst of trefwoorden.

    BELANGRIJK: vrijetekstzoeken vereist de opt-in browser-zoekadapter (Juportal), die
    STANDAARD UIT staat — geautomatiseerd doorzoeken wordt door robots.txt afgeraden, dus
    inschakelen is een bewuste keuze (`RECHTSPRAAK_MCP_BROWSER_ZOEK=juportal`; zie
    docs/bronnen-gebruiksvoorwaarden.md). Staat de vlag uit, dan geeft deze tool een lege
    lijst met uitleg in `melding` en per bron een handmatige zoeklink; staat ze aan, dan
    komen er echte treffers van Juportal (via een renderende browser). Voor een concreet
    arrest werkt `zoek_op_identifier` (ECLI of arrestnummer) hoe dan ook.

    LET OP BIJ CITEREN: de zoekmachines van de bronnen doorzoeken het HELE document,
    dus een treffer (of snippet) kan aanslaan op wat een PARTIJ aanvoert in plaats van
    op het oordeel van het rechtscollege. Onderbouw nooit een stelling op basis van een
    zoektreffer alleen: haal de uitspraak op met `haal_uitspraak` en citeer uitsluitend
    uit het veld `beoordeling` (het gesegmenteerde beoordelende deel).

    Args:
        query: Zoektekst of trefwoorden.
        instanties: Optionele filter op broncodes (bv. ["dbrc"]). None = alle actieve bronnen.
        datum_van: Ondergrens uitspraakdatum (optioneel).
        datum_tot: Bovengrens uitspraakdatum (optioneel).
        max_resultaten: Max. treffers per bron (1-100).

    Returns:
        ZoekRespons: treffers (enkel wat de bron effectief leverde), melding en
        handmatige zoeklinks. Presenteer handmatige links nooit als gevonden rechtspraak.
    """
    q = ZoekQuery(
        query=query,
        instanties=instanties,
        datum_van=datum_van,
        datum_tot=datum_tot,
        max_resultaten=max_resultaten,
    )
    adapters = [
        a
        for a in actieve_adapters()
        if not q.instanties or a.bron in q.instanties
    ]
    treffers: list[Treffer] = []
    for adapter in adapters:
        treffers.extend(adapter.zoek(q))
    melding = None
    if not treffers:
        # Vrij zoeken bestaat via twee paden: de browser-zoekadapter (Juportal) en de
        # HUDOC-API van het EHRM (gewone sta_fetch). Alleen als geen van beide actief is,
        # is "staat uit" de juiste uitleg.
        zoekpad_actief = any(
            getattr(a, "browser_zoek_aan", False)
            or (a.bron == "ehrm" and getattr(a, "sta_fetch", False))
            for a in adapters
        )
        if any(getattr(a, "laatste_botcontrole", False) for a in adapters):
            melding = MELDING_HUDOC
        elif zoekpad_actief:
            melding = (
                "Geen treffers. Er staat wel een vrij-zoekpad aan, dus de bron(nen) vonden "
                "niets voor deze zoekterm (of een bron toonde een bot-challenge, die bewust "
                "niet wordt omzeild). Probeer andere trefwoorden of open de handmatige "
                "zoeklinks hieronder."
            )
        else:
            melding = (
                "Vrijetekstzoeken staat uit: het vereist de schakelaar 'EHRM ophalen en "
                "doorzoeken (HUDOC)' en/of 'Vrij zoeken op Juportal (browser)' in Claude Desktop "
                "(buiten Claude Desktop: RECHTSPRAAK_MCP_STA_FETCH=ehrm, "
                "RECHTSPRAAK_MCP_BROWSER_ZOEK=juportal). Zonder die vlaggen geeft deze tool geen "
                "treffers — dat is ontworpen gedrag, geen storing. Gebruik zoek_op_identifier "
                "met een ECLI of arrestnummer, of open de handmatige zoeklinks hieronder."
            )
    return ZoekRespons(
        treffers=_met_verwijzing(treffers),
        melding=melding,
        handmatige_links={
            "dbrc (zoekpagina)": _dbrc.zoek_deeplink(query),
            "raadvanstate (zoekformulier)": _rvs.zoek_deeplink(query),
            "juportal (zoekformulier, query zelf invullen)": _juportal.ZOEK_URL,
        },
    )


@mcp.tool()
def zoek_op_identifier(
    identifier: str,
    instanties: list[str] | None = None,
    datum: date | None = None,
) -> ZoekRespons:
    """Zoek een uitspraak op ECLI of arrestnummer.

    Ondersteunde formaten:
      - ECLI (Juportal), bv. "ECLI:BE:CASS:2020:ARR.20201030.1N.4"
      - DBRC-arrestnummer, bv. "RvVb-A-2425-0744", "RvVb-UDN-2526-0608", "HHC-A-2324-0012"
      - RvS-arrestnummer, bv. "250.123" of "250123"

    GEEF BIJ DBRC-NUMMERS DE UITSPRAAKDATUM MEE als je die kent. De DBRC publiceert haar
    PDF's onder een publicatiemaand die niet uit het arrestnummer af te leiden is; zonder
    datum moet de adapter maand na maand proberen, met de voorgeschreven wachttijd van
    10 s per poging. Met `datum` is het meestal de eerste of tweede poging. Zonder datum
    stopt de zoektocht na een tijdsbudget en zegt `melding` dat expliciet — "niet gevonden"
    betekent dan niet "bestaat niet". Voor ECLI's en RvS-nummers speelt `datum` geen rol.

    NIET ondersteund: rolnummers van het Hof van Cassatie (AR, bv. "P.12.1389.N") — die
    zijn zonder de (robots-geblokkeerde) zoekfunctie niet naar een ECLI om te zetten. De
    respons legt dat dan uit in `melding`, met een handmatige zoeklink.

    Args:
        identifier: ECLI of arrestnummer (zie formaten hierboven).
        instanties: Optionele filter op broncodes. None = alle actieve bronnen.
        datum: Gekende (of benaderende) uitspraakdatum. Alleen van tel voor DBRC-nummers,
            waar ze de zoektocht naar de publicatiemaand verankert.

    Returns:
        ZoekRespons: meestal 0 of 1 treffer per bron; bij 0 treffers legt `melding` uit
        waarom, en bevat `handmatige_links` eventueel een zelf te openen (onbevestigde)
        deeplink. Presenteer die nooit als gevonden rechtspraak.
    """
    adapters = [
        a for a in actieve_adapters() if not instanties or a.bron in instanties
    ]
    treffers: list[Treffer] = []
    for adapter in adapters:
        treffers.extend(adapter.zoek_op_identifier(identifier, datum=datum))
    if treffers:
        return ZoekRespons(treffers=_met_verwijzing(treffers))
    # Onderscheid "bestaat niet" van "niet binnen het tijdsbudget afgezocht": alleen de
    # DBRC-adapter kan afbreken, en dan mag de melding geen negatieve zekerheid suggereren.
    afgebroken = any(getattr(a, "laatste_zoektocht_afgebroken", False) for a in adapters)
    botcontrole = any(getattr(a, "laatste_botcontrole", False) for a in adapters)
    return _leg_lege_identifier_uit(
        identifier, datum=datum, afgebroken=afgebroken, botcontrole=botcontrole
    )


def _leg_lege_identifier_uit(
    identifier: str,
    datum: date | None = None,
    afgebroken: bool = False,
    botcontrole: bool = False,
) -> ZoekRespons:
    """Bouw een eerlijke uitleg + handmatige links wanneer een identifier niets opleverde."""
    links: dict[str, str] = {}
    ecli = _juportal.normaliseer_ecli(identifier)
    if _CASS_AR_RE.match(identifier):
        melding = (
            f"'{identifier.strip()}' is een rolnummer van het Hof van Cassatie (AR). Dat "
            "kan niet automatisch naar een ECLI worden omgezet: de Juportal-zoekfunctie "
            "is robots-geblokkeerd. Zoek de ECLI handmatig via het Juportal-zoekformulier "
            "en geef die aan deze tool."
        )
        links["juportal (zoekformulier)"] = _juportal.ZOEK_URL
    elif _hvj.normaliseer_ecli_eu(identifier) is not None:
        eu_ecli = _hvj.normaliseer_ecli_eu(identifier)
        adapter = next((a for a in actieve_adapters() if a.bron == "hvj"), None)
        if botcontrole:
            melding = MELDING_EURLEX
        elif adapter is not None and not getattr(adapter, "sta_fetch", True):
            melding = "Geldige EU-ECLI, maar bij EUR-Lex " + _schakelaar_uit(
                "Hof van Justitie EU ophalen (EUR-Lex)", "hvj"
            )
        else:
            melding = (
                "Geldige EU-ECLI, maar EUR-Lex gaf geen herkenbaar arrest terug (onbestaande "
                "ECLI, tijdelijke storing, of een paginavorm die de parser niet herkent). "
                "Controleer via de deeplink hieronder."
            )
        links["eurlex (onbevestigde deeplink)"] = _hvj.content_deeplink(eu_ecli)
    elif (
        _ehrm.normaliseer_ehrm_ecli(identifier) is not None
        or _ehrm.normaliseer_appno(identifier) is not None
    ):
        adapter = next((a for a in actieve_adapters() if a.bron == "ehrm"), None)
        if botcontrole:
            melding = MELDING_HUDOC
        elif adapter is not None and not getattr(adapter, "sta_fetch", True):
            melding = "Herkend als EHRM-ECLI of verzoekschriftnummer, maar bij HUDOC " + (
                _schakelaar_uit("EHRM ophalen en doorzoeken (HUDOC)", "ehrm")
            )
        else:
            melding = (
                "Herkend als EHRM-ECLI of verzoekschriftnummer, maar HUDOC gaf geen arrest of "
                "beslissing terug. Controleer het nummer, of zoek zelf op hudoc.echr.coe.int."
            )
        links["hudoc (zoekpagina)"] = "https://hudoc.echr.coe.int/"
    elif ecli is not None:
        adapter = next((a for a in actieve_adapters() if a.bron == "juportal"), None)
        if adapter is not None and not getattr(adapter, "sta_fetch", True):
            melding = (
                "Geldige ECLI, maar bij Juportal "
                + _schakelaar_uit("Juportal automatisch ophalen", "juportal")
                + " De deeplink hieronder kan handmatig geopend worden."
            )
        else:
            melding = (
                "Geldige ECLI, maar de Juportal-pagina leverde geen herkenbare uitspraak "
                "op (onbestaande ECLI, of een paginavorm die de parser niet herkent — in "
                "dat laatste geval: meld de ECLI, dan wordt de parser bijgestuurd). "
                "Controleer via de deeplink hieronder."
            )
        links["juportal (onbevestigde deeplink)"] = _juportal.content_deeplink(ecli)
    elif _rvs.normaliseer_arrestnummer(identifier) is not None and _dbrc.parse_arrestnummer(
        identifier
    ) is None:
        nr = _rvs.normaliseer_arrestnummer(identifier)
        adapter = next((a for a in actieve_adapters() if a.bron == "raadvanstate"), None)
        if adapter is not None and not getattr(adapter, "sta_fetch", True):
            melding = (
                "Herkend als RvS-arrestnummer, maar bij de Raad van State "
                + _schakelaar_uit("Raad van State automatisch ophalen", "raadvanstate")
                + " De deeplink hieronder kan handmatig geopend worden."
            )
        else:
            melding = (
                "Herkend als RvS-arrestnummer, maar arr.php gaf geen arrest terug "
                "(onbestaand of niet toegankelijk nummer). Controleer via de deeplink."
            )
        links["raadvanstate (onbevestigde deeplink)"] = _rvs.arrest_deeplink(nr)
    elif _dbrc.parse_arrestnummer(identifier) is not None:
        if afgebroken:
            melding = (
                "Herkend als DBRC-arrestnummer, maar de zoektocht naar de publicatiemaand "
                "is op het tijdsbudget gestopt vóór het volledige venster was afgezocht. "
                "Dit zegt dus NIETS over het bestaan van het arrest. De DBRC publiceert "
                "haar PDF's onder een publicatiemaand die niet uit het nummer af te leiden "
                "is, en robots.txt schrijft 10 s tussen twee pogingen voor. Roep deze tool "
                "opnieuw op met de uitspraakdatum in `datum` — dan is het meestal de eerste "
                "of tweede poging — of open de zoeklink hieronder."
            )
        elif datum is not None:
            melding = (
                "Herkend als DBRC-arrestnummer, maar rond de opgegeven datum staat geen PDF "
                "op de verwachte plaats. Controleer de uitspraakdatum, of open de zoeklink "
                "hieronder: laat gepubliceerde arresten vallen buiten het venster."
            )
        else:
            melding = (
                "Herkend als DBRC-arrestnummer, maar geen PDF gevonden binnen het "
                "publicatiemaand-venster (laat gepubliceerde arresten vallen daarbuiten; een "
                "uitspraakdatum in `datum` meegeven vergroot de trefkans aanzienlijk). De "
                "zoeklink hieronder toont het arrest op de DBRC-site."
            )
        links["dbrc (zoekpagina met nummer)"] = _dbrc.zoek_deeplink(identifier.strip())
    else:
        melding = (
            f"'{identifier.strip()}' is niet herkend. Ondersteund: ECLI "
            "(ECLI:BE:...), DBRC-arrestnummers (RvVb/HHC/R.Stvb/R.Verkb-...-JJJJ-NNNN) en "
            "RvS-arrestnummers (bv. 250.123). Cassatie-rolnummers (bv. P.12.1389.N) "
            "kunnen niet worden opgezocht; zoek daarvoor eerst de ECLI via Juportal."
        )
        links["juportal (zoekformulier)"] = _juportal.ZOEK_URL
    return ZoekRespons(treffers=[], melding=melding, handmatige_links=links)


@mcp.tool()
def haal_uitspraak(url: str, bron: str) -> Uitspraak | None:
    """Haal de volledige (of verkorte) tekst van één uitspraak op via de bron-URL.

    BELANGRIJK VOOR CITEREN: het veld `beoordeling` bevat uitsluitend de eigen
    beoordeling van het rechtscollege (het enige deel dat stellingen kan onderbouwen);
    `tekst` bevat het hele document, dus óók de standpunten van partijen — die mogen
    nooit als oordeel worden gepresenteerd. Citeer daarom uit `beoordeling`. Is
    `beoordeling` None, dan is de structuur niet betrouwbaar herkend (zie
    `segmentatie`): gebruik dan de integrale tekst en controleer zelf welk deel het
    oordeel is — zeg dat er ook bij.

    Args:
        url: Deeplink naar het brondocument (afkomstig uit een eerdere treffer).
        bron: Broncode van de adapter die de URL kan verwerken (bv. "dbrc").

    Returns:
        De uitspraak met tekst, of None als de bron niets teruggeeft.
    """
    for adapter in actieve_adapters():
        if adapter.bron == bron:
            uitspraak = adapter.haal_uitspraak(url)
            if uitspraak is not None:
                _met_verwijzing([uitspraak.treffer])
                _met_beoordeling(uitspraak)
            return uitspraak
    return None


def _met_beoordeling(uitspraak: Uitspraak) -> Uitspraak:
    """Segmenteer de uitspraaktekst en vul het beoordelende deel in (nooit geraden).

    De kern-eis uit docs/spec-gerichte-zoekfunctie.md §1: alleen de eigen beoordeling van
    het rechtscollege onderbouwt stellingen. Dit gebeurt ALTIJD — ook wanneer de tekst
    enkel ter controle/nazicht wordt opgehaald — zodat het onderscheid oordeel/
    partijenstandpunt nooit afhangt van de vraagstelling.
    """
    resultaat = segmenteer(
        uitspraak.tekst,
        bron=uitspraak.treffer.bron,
        instantie=uitspraak.treffer.instantie,
    )
    uitspraak.beoordeling = resultaat.beoordeling
    uitspraak.segmentatie = resultaat.melding
    return uitspraak


def _met_norm_verwijzing(normen: list[Norm]) -> list[Norm]:
    """Vul per norm het voorstel van VENA-verwijzing in (wetgevingsvorm)."""
    for n in normen:
        if n.verwijzing is None:
            n.verwijzing = vena_verwijzing_norm(n)
    return normen


@mcp.tool()
def zoek_wetgeving(query: str, max_resultaten: int = 20) -> WetgevingRespons:
    """Zoek wetgeving (EUR-Lex, Vlaamse Codex, Justel): identifier óf vrije tekst, één tool.

    Identifiers die herkend worden:
      - CELEX ("32011L0092") of EU-citeervorm ("Richtlijn 2011/92/EU", "Verordening (EU)
        2016/679", "Verordening (EG) nr. 1367/2006") of EUR-Lex-ELI-URL -> EUR-Lex;
      - numac (10 cijfers, bv. "2014035564") -> Vlaamse Codex (ook federale normen);
      - Belgische ELI-URL (ejustice.just.fgov.be/eli/...) -> Justel (geconsolideerde tekst).
    Al het andere wordt vrij gezocht: EU-wetgeving op woorden in het Nederlandse opschrift
    (via CELLAR, het open-data-platform van het Publicatiebureau — niet in de volledige
    tekst) en de Vlaamse Codex (officiële open-data-API). Justel heeft geen robots-conforme
    zoekfunctie; een kaal numac zonder type/datum kan niet naar een Justel-ELI worden
    omgezet (de Codex vangt numacs op).

    Per bron geldt de opt-in (RECHTSPRAAK_MCP_STA_FETCH met "eurlex", "codex" en/of
    "justel"); staat alles uit, dan legt `melding` dat uit. Elke norm draagt een
    controleerbare bron-URL en een voorstel van VENA-verwijzing. LET OP bij
    verordeningen: "Verordening 2019/2010" (zonder "nr."/jaartal-eenduidigheid) is
    ambigu en wordt niet geraden — geef de CELEX of de volledige citeervorm.

    Args:
        query: Identifier of vrije zoektekst.
        max_resultaten: Max. aantal treffers per bron bij vrije-tekstzoeken (1-100).

    Returns:
        WetgevingRespons: normen, melding en handmatige links. Presenteer handmatige
        links nooit als gevonden wetgeving.
    """
    links = {
        "eurlex (zoekpagina)": (
            "https://eur-lex.europa.eu/search.html?scope=EURLEX&text="
            + urllib.parse.quote(query)
            + "&lang=nl&type=quick"
        ),
        "codex (zoekpagina)": (
            "https://codex.vlaanderen.be/Zoeken/Zoekresultaten.aspx?tekst="
            + urllib.parse.quote(query)
        ),
        "justel (zoekformulier)": _justel.zoek_deeplink(query),
    }
    adapters = actieve_wetgeving_adapters()
    actieve_codes = sorted(a.bron for a in adapters if getattr(a, "sta_fetch", False))

    # Is de query een identifier die één van de bronnen puur herkent?
    celex = _eurlex.identifier_naar_celex(query)
    is_identifier = (
        celex is not None
        or _codex.is_numac(query)
        or _justel.parse_eli_url(query) is not None
    )

    if not actieve_codes:
        melding = (
            "Alle wetgevingsbronnen staan uit (zet RECHTSPRAAK_MCP_STA_FETCH met "
            "'eurlex', 'codex' en/of 'justel'). Geen treffers — dat is ontworpen "
            "gedrag, geen storing."
        )
        if celex is not None:
            links["eurlex (onbevestigde deeplink)"] = _eurlex.content_deeplink(celex)
        return WetgevingRespons(normen=[], melding=melding, handmatige_links=links)

    if is_identifier:
        normen: list[Norm] = []
        for adapter in adapters:
            normen.extend(adapter.zoek_op_identifier(query))
        if normen:
            return WetgevingRespons(normen=_met_norm_verwijzing(normen))
        if celex is not None:
            links["eurlex (onbevestigde deeplink)"] = _eurlex.content_deeplink(celex)
        if any(getattr(a, "laatste_botcontrole", False) for a in adapters):
            melding = MELDING_EURLEX
        else:
            melding = (
                "Identifier herkend, maar geen van de actieve bronnen "
                f"({', '.join(actieve_codes)}) gaf een norm terug. Controleer de "
                "identifier of open de handmatige links."
            )
        return WetgevingRespons(normen=[], melding=melding, handmatige_links=links)

    # Vrije tekst: fan-out over de adapters met een echt zoekpad (Codex) plus de
    # EUR-Lex-zoeker; Justel heeft geen robots-conforme zoekfunctie.
    normen = []
    for adapter in adapters:
        normen.extend(adapter.zoek(query, max_resultaten=max_resultaten))
    zoeker = maak_zoeker()
    if zoeker is not None:
        normen.extend(zoeker.zoek(query, max_resultaten=max_resultaten))
    melding = None
    if not normen:
        melding = (
            f"Geen wetgeving gevonden voor deze zoekterm bij de actieve bronnen "
            f"({', '.join(actieve_codes)}). Identifier-vormen (CELEX, 'Richtlijn "
            "2011/92/EU', numac, ELI-URL) werken ook. Probeer andere trefwoorden of "
            "open de handmatige zoeklinks."
        )
    if zoeker is not None and not zoeker.laatste_botcontrole:
        melding = ((melding + " ") if melding else "") + _eurlex_zoek.BEPERKING
    if zoeker is not None and zoeker.laatste_botcontrole:
        # Andere bronnen kunnen wel treffers geven; zeg dan dat EUR-Lex niet doorzocht is.
        melding = ((melding + " ") if melding else "") + MELDING_EURLEX
    return WetgevingRespons(
        normen=_met_norm_verwijzing(normen), melding=melding, handmatige_links=links
    )


@mcp.tool()
def haal_norm(url: str) -> NormTekst | None:
    """Haal de artikelsgewijze tekst van één norm op via de EUR-Lex-URL.

    Args:
        url: EUR-Lex-deeplink (legal-content- of ELI-URL, afkomstig uit een eerdere
            wetgevingstreffer).

    Returns:
        De norm met tekst, of None wanneer de bron niets teruggeeft of de bron uit staat.
    """
    for adapter in actieve_wetgeving_adapters():
        resultaat = adapter.haal_norm(url)
        if resultaat is not None:
            _met_norm_verwijzing([resultaat.norm])
            return resultaat
    return None


def main() -> None:
    """Start de MCP-server.

    Standaard over stdio (lokale connector in Claude Desktop / Claude Code). Met
    ``RECHTSPRAAK_MCP_TRANSPORT=streamable-http`` draait dezelfde server over HTTP, zodat
    een latere schil (bv. een browserextensie of Word-invoegtoepassing) hetzelfde endpoint kan
    aanspreken — spec punt 6: remote-ready, geen tweede codebase. Zet bij HTTP een
    authenticatielaag vóór het endpoint; publiek openzetten vergt eerst de
    licentie-analyse per bron.
    """
    transport = os.environ.get("RECHTSPRAAK_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
