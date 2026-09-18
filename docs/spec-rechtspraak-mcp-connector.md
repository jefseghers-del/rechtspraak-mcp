# Spec — "BE-rechtspraak" MCP-connector voor Claude

Herwerkte spec (vervangt `spec-rechtspraak-browserplugin.md`). Aanleiding: mail van Jef (23 juli 2026) met verzoek om een Belgische variant van een tool die hij op X zag. Nazicht van die X-post (Bob Ambrogi, 22 juli 2026) toont dat het niet om een browserplugin gaat maar om **DingDuff**, een gratis **MCP-connector voor Claude**. Deze spec volgt dat spoor. Het betreft een concept, geen eindproduct.

## 1. Referentie: DingDuff [TE VERIFIËREN]

DingDuff is een MCP-connector (Model Context Protocol) die Claude rechtstreeks koppelt aan Amerikaanse primaire rechtsbronnen: rechterlijke uitspraken, wetgeving, reglementering, procedureregels en federale procesdossiers (PACER), naar verluidt via de open data van CourtListener / Free Law Project. De gebruiker stelt in Claude een juridische vraag, Claude doorzoekt de primaire bronnen en antwoordt met controleerbare, aanklikbare citaties. Er is geen aparte applicatie. Gebouwd door twee advocaten (Kyle Dingman, Stephanie Duff-O'Bryan, Austin TX), gratis, met "tip jar". De makers claimen dat Claude Fable met DingDuff beter presteerde dan Thomson Reuters CoCounsel en Lexis Protégé (eigen benchmark, [TE VERIFIËREN]). Bronnen: X-post en LawSites-artikel, zie punt 8.

Kernles voor de Belgische variant: het onderscheidende zit niet in een UI, maar in (a) betrouwbare, geciteerde toegang tot primaire bronnen en (b) integratie binnen Claude zelf. Het grote verschil met de VS is de databeschikbaarheid: er is in België geen equivalent van CourtListener met een open bulk-API. Dat is de kritische onbekende.

## 2. Doel

Een MCP-connector die Claude toegang geeft tot de belangrijkste Belgische (en Vlaamse) rechtspraakbronnen, zodat de gebruiker binnen Claude juridische vragen kan stellen en antwoorden krijgt met controleerbare verwijzingen naar de primaire bron (rolnummer, ECLI, datum, instantie, directe link). Doelgebruiker: advocaten omgevingsrecht, breder inzetbaar.

## 3. Bronnen (scope)

Per bron moet de toegangsmethode (open API, zoek-URL, of enkel manueel) en de gebruiksvoorwaarden vóór implementatie worden geverifieerd [TE VERIFIËREN].

Juportal (federale rechtspraak, juportal.be). DBRC — Vlaamse bestuursrechtscolleges: Raad voor Vergunningsbetwistingen, Handhavingscollege, e.a. (dbrc.be). Raad van State (raadvst-consetat.be). Arrestendatabank (arrestendatabank.be). Optioneel en apart afgeschermd: interne rechtspraakoverzichten van een kantoor (SharePoint), enkel voor geauthenticeerde gebruikers, niet in een publiek gedeelde versie.

Aandachtspunt: anders dan bij CourtListener bieden deze bronnen wellicht geen open, doorzoekbare API. Voor sommige zal enkel scraping van de publieke zoekresultaten mogelijk zijn (met respect voor gebruiksvoorwaarden en robots), voor andere mogelijk niets bruikbaars zonder overeenkomst. De haalbaarheid per bron bepaalt de scope van een eerste versie.

## 4. Architectuur (voorstel)

Een MCP-server (stdio of remote/HTTP) die Claude als connector aanspreekt. De server stelt een beperkt aantal tools bloot, elk met een helder schema, bijvoorbeeld: `zoek_rechtspraak` (vrije tekst of trefwoorden, met filters op instantie, datum, rechtsgebied), `zoek_op_identifier` (ECLI of rolnummer), en `haal_uitspraak` (volledige tekst of samenvatting van één uitspraak op basis van een bron-URL/id).

Achter de tools zit per bron een aparte adapter die de zoekopdracht vertaalt naar het formaat van die bron en de respons normaliseert naar één intern schema (bron, instantie, titel, datum, ECLI/rolnummer, snippet, url). De server voert zoekopdrachten waar zinvol parallel uit over de ingeschakelde bronnen en geeft de treffers gebundeld terug, met per treffer een aanklikbare bronverwijzing zodat de gebruiker elke citatie kan controleren.

Distributie: als lokale MCP-server (per gebruiker te installeren) en/of als remote connector. Een adapter voor zulke interne overzichten blijft optioneel en vereist authenticatie (Microsoft Graph of SharePoint search-API), buiten de publiek deelbare versie.

Anti-hallucinatie: de connector levert enkel wat de bron effectief teruggeeft. Claude mag geen rechtspraak of citaties aanvullen die niet uit een tool-respons komen. Elke verwijzing blijft herleidbaar naar de bron-URL.

## 5. Aandachtspunten (juridisch en technisch)

Gebruiksvoorwaarden en auteursrecht van elke databank nagaan vóór geautomatiseerd hergebruik [TE VERIFIËREN]. Verwerking van persoonsgegevens in arresten (AVG): enkel ophalen wat de bron publiek toont, niets centraal opslaan buiten caching. Robuustheid tegen wijzigingen in de bron-HTML (adapters gescheiden houden). Rate limiting en nette identificatie per bron. Geen omzeiling van betaalmuren of botcontroles. Duidelijke bron- en foutmelding wanneer een bron onbereikbaar is.

## 6. Beslissingen (Jef, 3 augustus 2026)

De vier openstaande vragen zijn beslist. Distributievorm: beide sporen parallel, er wordt lokaal ontwikkeld maar de architectuur wordt meteen voorbereid op een remote connector (geen aannames die enkel bij stdio werken). Die interne bron komt pas later, de eerste versie beperkt zich tot publieke bronnen. De connector wordt eerst intern gebruikt (door de auteur), extern delen blijft een optie voor later en vergt dan eerst de licentie- en gebruiksvoorwaardenanalyse per bron. Prioriteit voor de volgende ontwikkelronde: de adapters voor Juportal en Raad van State worden samen aangepakt (DBRC/RvVb is al geïmplementeerd).

## 7. Volgende stap

Uitvoering van de beslissingen onder punt 6: de Juportal- en RvS-adapters implementeren (deeplinks per ECLI respectievelijk arrestnummer, zie het bronnenonderzoek), de servercode nazien op remote-geschiktheid (HTTP-transport naast stdio), en tests per adapter. Het project staat onder versiebeheer op GitHub.

## 8. Bronnen

X-post Bob Ambrogi, 22 juli 2026: https://x.com/bobambrogi/status/2079937736820072842 [geverifieerd via browser]
LawSites (LawNext), "Built By Lawyers, For Lawyers: DingDuff Is A Free Claude Connector...", juli 2026: https://www.lawnext.com/2026/07/built-by-lawyers-for-lawyers-dingduff-is-a-free-claude-connector-that-its-founders-say-rivals-the-legal-research-giants.html [TE VERIFIËREN — artikel niet volledig uitgelezen]
DingDuff: https://www.dingduff.com/ en https://github.com/DingDuff/dingduff-public/wiki [TE VERIFIËREN]
