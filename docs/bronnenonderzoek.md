# Bronnenonderzoek — BE-rechtspraak MCP-connector

Uitvoering van stap (a) uit punt 7 van [spec-rechtspraak-mcp-connector.md](spec-rechtspraak-mcp-connector.md):
per bron nagaan of er een gestructureerde/open API, een bruikbare publieke zoek-URL,
of geen geautomatiseerde toegang zonder overeenkomst bestaat.

**Status: concept / eerste verkenning (25 juli 2026).** Alle vaststellingen die niet
rechtstreeks konden worden bevestigd, zijn gemarkeerd met **[TE VERIFIËREN]**.

## Methode en beperkingen

- Onderzoek via websearch + gericht ophalen van publieke pagina's (geen inloggen, geen
  omzeilen van betaalmuren of botcontroles).
- De `robots.txt` van de vier bronnen kon in deze sessie **niet** worden opgehaald wegens
  een technische beperking van de fetch-tool (alleen URL's uit zoekresultaten). Elke
  robots-indicatie hieronder is dus **[TE VERIFIËREN]** en moet vóór implementatie manueel
  worden gecontroleerd (`https://<domein>/robots.txt`).
- Twee bronnen (Juportal, Raad van State) draaien op een JavaScript-front-end; de kale
  HTML-fetch gaf een lege body terug. De onderliggende data-endpoints zijn daardoor niet
  bevestigd en gemarkeerd **[TE VERIFIËREN]** (te onderzoeken via netwerkinspectie in de
  browser).

## Samenvatting (haalbaarheid eerste adapter)

| Bron | Toegangsmethode | Haalbaarheid |
|------|-----------------|--------------|
| **DBRC / RvVb** (dbrc.be) | Server-rendered zoekpagina met querystring-facetten + directe PDF-URL's | 🟢 **Groen** (technisch); juridische caveat bij commercieel/extern gebruik |
| **Juportal** (juportal.be) | JS-front-end; stabiele ECLI-deeplink; ruime hergebruiksrechten | 🟠 **Oranje** |
| **Raad van State** (raadvst-consetat.be) | Directe arrest-URL per nummer; zoekformulier op JS | 🟠 **Oranje** |
| **Arrestendatabank** (arrestendatabank.be) | Server-rendered facetten + PDF's, maar geautomatiseerd hergebruik contractueel verboden | 🔴 **Rood** |

---

## 1. DBRC — Vlaamse bestuursrechtscolleges (dbrc.be)

Omvat de Raad voor Vergunningsbetwistingen (RvVb), het Handhavingscollege (HHC), de Raad
voor betwistingen inzake studievoortgangsbeslissingen (RStvb) en de Raad voor
Verkiezingsbetwistingen (RVerkb). Meest relevante bron voor omgevingsrecht/IIOA.

### Toegangsmethode
Server-rendered Drupal/Paddle-CMS. **Geen open API, maar wel volledig doorzoekbaar via
gewone HTTP-GET zonder JavaScript.** De HTML-fetch levert direct de resultatenlijst op.

### URL-structuur / endpoint
- Zoek- en overzichtspagina: `https://www.dbrc.be/rechtspraak`
- Vrije-tekstzoekopdracht via het zoekveld op die pagina (booleaanse operatoren `AND`/`OR`/`NOT`,
  hoofdlettergevoelig; exacte frase tussen dubbele aanhalingstekens). Zoeken op datum,
  arrestnummer (`RvVb-A-1920-0284`) of rolnummer werkt.
- Facetfilters via querystring, bv.:
  - `?f[0]=document_type:49` — RvVb vernietigingsarresten (± 14 527)
  - `document_type:53` — RvVb schorsing · `:54` — RvVb UDN · `:57` — HHC · `:107` — RStvb · `:58` — RVerkb
  - `?f[0]=publication_year:121` — werkjaar 2025-2026 (een werkjaar loopt 1 sep → 31 aug)
  - Paginering `?page=N` (20 treffers/pagina; ± 19 360 resultaten totaal, ± 967 pagina's)
- Directe PDF van een arrest:
  `https://www.dbrc.be/sites/default/files/YYYY-MM/RVVB.<TYPE>.<WERKJAAR>.<NUMMER>.pdf`
  - bv. `.../2026-04/RVVB.UDN.2526.0627.pdf` en `.../2021-08/RVVB.A.2021.0268_0.pdf`
  - `YYYY-MM` = publicatiemaand (niet altijd voorspelbaar); `2526` = werkjaar 2025-2026;
    soms `_0`-suffix bij herpublicatie.
  - **Dit patroon is al in gebruik in de repo** (`src/overzicht_iioa/source_lookup.py`), wat de
    haalbaarheid bevestigt.

### Gebruiksvoorwaarden / robots
Uit de [DBRC-disclaimer](https://www.dbrc.be/disclaimer):
- "De inhoud van de arresten op deze site is **vrij beschikbaar voor iedereen**."
- De HTML-code, "selectie en organisatie van de informatie" mag niet worden overgenomen
  zonder uitdrukkelijke toestemming.
- Rubriek *Hergebruik van arresten*: arresten zijn "**uitsluitend bestemd voor raadpleging**".
  Elk geheel/gedeeltelijk hergebruik, reproductie, verspreiding of publicatie **voor
  commerciële doeleinden** is enkel toegestaan **na voorafgaande en uitdrukkelijke
  schriftelijke toestemming van de DBRC**. Zonder toestemming is elk hergebruik verboden,
  "behoudens de gevallen waarin dit uitdrukkelijk is toegestaan door de toepasselijke wetgeving".
- Belgisch recht, rechtbanken van Brussel.
- robots.txt (live gecontroleerd 25 juli 2026 via de browser): `User-agent: *` met
  `Crawl-Delay: 10`. **Belangrijk:** het bevat
  `Disallow: /*?*search_api_fulltext*` en `Disallow: /*f%5B0%5D*` — de vrije-tekstzoek en
  de facetfilters (`f[0]`) zijn dus **uitdrukkelijk verboden voor geautomatiseerde
  crawlers**. De directe PDF's onder `/sites/default/files/…` zijn **niet** disallowed
  (enkel `/sites/README.txt`). Gevolg: een robots-conforme adapter mag de zoek-/facet-URL's
  niet automatisch ophalen, maar mag wél een specifieke arrest-PDF per URL ophalen. Dit
  stuurt het adapterontwerp (zie `rechtspraak-mcp/rechtspraak_mcp/adapters/dbrc.py`):
  `zoek_op_identifier` resolvt via HEAD op de PDF-URL; automatische zoek-scraping staat
  standaard uit.

### Haalbaarheidsinschatting: 🟢 Groen (technisch), met juridische caveat
Technisch de eenvoudigste en meest betrouwbare bron: geen JS, voorspelbare URL's,
gestructureerde PDF-namen, reeds bewezen in de codebase. Juridisch geschikt voor een
**intern, niet-commercieel prototype dat enkel raadpleegt en naar de bron deeplinkt**.
Aandachtspunt: een breed gedeelde of commerciële connector raakt "hergebruik voor
commerciële doeleinden" — dat vereist voorafgaande schriftelijke DBRC-toestemming. Nette
rate limiting en bronidentificatie aangeraden.

---

## 2. Juportal (juportal.be)

Federale openbare rechtspraakdatabank, beheerd door de stafdienst ICT van de FOD Justitie
(contact via belgielex/Grondwettelijk Hof). Opvolger van Jure-Juridat (zoekmachine sinds
november 2020).

### Toegangsmethode
JavaScript-front-end (Angular-achtige single-page app). Een kale HTML-fetch van het
zoekformulier gaf een **lege body** — de resultaten worden client-side geladen, wellicht via
een achterliggend JSON-endpoint. **Geen bevestigde open/gestructureerde API [TE VERIFIËREN]**
(te onderzoeken via netwerkinspectie; de wet van 5 mei 2019 voorziet wel een open-datakader
voor rechtspraak, maar een publieke bulk-API is niet bevestigd).

### URL-structuur / endpoint
- Zoekformulier: `https://juportal.be/zoekmachine/zoekformulier`
- Resultaten: `https://juportal.be/zoekmachine/zoekresultaten`
- **Stabiele deeplink per uitspraak via ECLI**:
  `https://juportal.be/content/<ECLI>`
  - bv. `https://juportal.be/content/ECLI:BE:CASS:2020:ARR.20201030.1N.4`
  - ECLI-opbouw: `ECLI:BE:<instantiecode>:<jaar>:<volgnummer>`; partieel zoeken met `%` mogelijk
    (bv. `ECLI:BE:CASS:2012:ARR.201203%`).
- Inhoud: Grondwettelijk Hof, Hof van Cassatie (gepubliceerde arresten — volledig),
  hoven van beroep, arbeidshoven, rechtbanken van eerste aanleg, ondernemings- en
  arbeidsrechtbanken e.a. (selectie); periode 1958–heden. Raad van State slechts zeer
  beperkt aanwezig. Elk item heeft sleutelwoorden, samenvatting, (verkorte) integrale tekst
  en gestructureerde velden (wettelijke basis, publicatie).

### Gebruiksvoorwaarden / robots
- De [gebruiksvoorwaarden van FOD Justitie](https://justitie.belgium.be/nl/general_pages/gebruiksvoorwaarden)
  (rubriek III): "Tenzij anders vermeld, is de informatie op deze website **vrij van rechten**.
  Ze kan **onvoorwaardelijk worden hergebruikt** voor privé-, verenigings-, wetenschappelijke
  en **commerciële** doeleinden." Bron- en datumvermelding aanbevolen. Multimedia en
  downloadbare documenten vergen wél voorafgaande goedkeuring.
- Of deze ruime voorwaarden **letterlijk gelden voor de Juportal-arresten zelf** (Juportal
  heeft een eigen disclaimer op `juportal.be/home/disclaimer`, die niet uitleesbaar was wegens
  JS) is **[TE VERIFIËREN]**. Aandachtspunt (vondst 3 augustus 2026): de HTML van de
  content-pagina bevat de comment *"Copyright (c) 2017-2026 FOD Justitie - alle rechten
  voorbehouden. Elke reproductie, zelfs gedeeltelijk, is verboden."* — op gespannen voet met
  de ruime FOD-gebruiksvoorwaarden hierboven.
- robots.txt (live gecontroleerd 3 augustus 2026, op `juportal.be` én `juportal.just.fgov.be`):
  `User-agent: * / Disallow: /` — **alles is verboden voor generieke bots**; alleen de eigen
  `DG_JUSTICE_CRAWLER` mag. Er staan wel publieke sitemaps
  (`juportal.just.fgov.be/JUPORTAsitemap/...`). Gevolg voor het adapterontwerp: automatisch
  ophalen staat standaard uit (`sta_fetch = False` in
  `rechtspraak_mcp/adapters/juportal.py`); de pure deeplink-bouwer blijft altijd bruikbaar.
- Technische update (3 augustus 2026): de ECLI-deeplink `juportal.be/content/<ECLI>` is —
  anders dan het zoekformulier — **volledig server-rendered** (PHP, geen JS-shell), met
  parsebare metadata (ECLI, rolnummer, zaak, kamer, rechtsgebied), datum, samenvattingsfiches,
  integrale tekst en PDF-link. De CSS-klassenamen zijn geobfusceerd en wellicht instabiel;
  parsen dus op labels/structuur, niet op klassen.

### Haalbaarheidsinschatting: 🟠 Oranje
Hergebruiksrechten lijken het gunstigst van alle bronnen, en de ECLI-deeplink is uiterst
stabiel voor een `haal_uitspraak`/`zoek_op_identifier`-tool. Het obstakel is technisch:
vrije-tekstzoeken vergt het reverse-engineeren van het JSON-endpoint achter de SPA of een
headless browser. Voor omgevingsrecht is Juportal bovendien minder rijk (RvS/RvVb amper
aanwezig). Sterke kandidaat voor de **identifier/deeplink**-functionaliteit, minder voor
brede zoekopdrachten.

---

## 3. Raad van State (raadvst-consetat.be)

Hoogste administratief rechtscollege; zeer relevant voor omgevingsrecht (cassatie tegen
RvVb-arresten, annulatieberoepen).

### Toegangsmethode
Deels server-rendered (individuele arresten), deels JavaScript (zoekformulier). Geen
bevestigde open API.

### URL-structuur / endpoint
- Directe arrest-URL per nummer: `https://raadvst-consetat.be/arr.php?nr=<NUMMER>&l=nl`
  (klassiek PHP-endpoint; ook `raadvst-consetat.fgov.be/arr.php?nr=...`). De fetch gaf een
  lege body — **[TE VERIFIËREN]** of `arr.php` de fetcher blokkeert dan wel bruikbare HTML
  teruggeeft bij een geldig nummer.
- Zoekformulier: `https://www.raadvst-consetat.be/?page=search&lang=nl`
  (uitgebreid: `?page=search_help_adv`) — JS, lege body via kale fetch.
- Aanverwante databanken: **juriDict** (`juridict.raadvst-consetat.be`, trefwoorden-/
  begrippendatabank), **refLex** (`reflex.raadvst-consetat.be`, regelgeving +
  vernietigingsarresten van regelgevende aard). Arresten vanaf 1994 online; 1948–1994 op
  `arrrvs.be`.
- Bestaande repo-aanpak (`source_lookup.py`) linkt voorlopig naar de zoek-URL met het
  rolnummer als query (`?page=search&q=<rolnummer>`) i.p.v. een echte deeplink.

### Gebruiksvoorwaarden / robots
- Eigen copyright/gebruiksvoorwaarden van de RvS: **[TE VERIFIËREN]** (niet uitgelezen).
- robots.txt (live gecontroleerd 3 augustus 2026): `User-agent: *` met `Crawl-delay: 10` en
  o.m. `Disallow: /arr.php`, `/Arresten/`, `/Beschikkingen/`, `/Cass/` (+ FR-varianten) en
  `Disallow: /*page=caselaw*`. **Het deeplink-endpoint `arr.php` is dus uitdrukkelijk
  disallowed voor bots.** Gevolg voor het adapterontwerp: automatisch ophalen staat standaard
  uit (`sta_fetch = False` in `rechtspraak_mcp/adapters/raad_van_state.py`); de pure
  deeplink-bouwers blijven altijd bruikbaar.
- Technische update (3 augustus 2026, eenmalige verificatie): `arr.php?nr=250123&l=nl` geeft
  HTTP 200 met `Content-Type: application/pdf` — de **integrale arrest-PDF** (met tekstlaag),
  ook aan een niet-browser-client; de "lege body" uit de eerdere verkenning trad niet op. Een
  onbestaand nummer geeft **eveneens HTTP 200**, maar `text/html` met "Het arrest ... is niet
  toegankelijk, of bestaat niet." — gevonden/niet-gevonden is dus enkel via het Content-Type
  te onderscheiden, niet via de statuscode.

### Haalbaarheidsinschatting: 🟠 Oranje
Een deeplink of ophaling **per arrestnummer** lijkt haalbaar via `arr.php` (mits bevestigd
dat het server-rendered HTML teruggeeft). Vrije-tekstzoeken vergt echter scraping van een
JS-zoekformulier zonder eenvoudige querystring-API; dat is fragieler. Inhoudelijk essentieel
voor IIOA, dus goede tweede prioriteit — te starten met `zoek_op_identifier`/`haal_uitspraak`
per nummer, later pas vrije-tekstzoeken.

---

## 4. Arrestendatabank (arrestendatabank.be)

"Arrestendatabank Vlaams Handhavingsbeleid", uitgegeven door het agentschap Justitie en
Handhaving, afdeling Handhaving (Vlaamse overheid). Bevat geanonimiseerde
handhavingsrechtspraak (ruimtelijke ordening, wonen, milieu, dierenwelzijn, werk/sociale
economie) van straf-, burgerlijke en administratieve rechtscolleges.

### Toegangsmethode
Server-rendered Drupal 11 met facetzoeken — **technisch even scraperbaar als DBRC**, maar
zie de voorwaarden hieronder.

### URL-structuur / endpoint
- Facetzoeken via querystring, bv.
  `https://arrestendatabank.be/arresten?f[0]=facet_arrest_tags:98&f[9]=rechtsgebied:128&page=8&sort_by=field_arrest_date&sort_order=DESC`
- Directe PDF's: `https://arrestendatabank.be/system/files/arresten/<NAAM>.pdf`
  (bv. `HB 11-05-2022.pdf`, `REA 04-04-2022.pdf`).

### Gebruiksvoorwaarden / robots
Uit de [disclaimer](https://arrestendatabank.be/disclaimer) — **doorslaggevend en restrictief**:
- "Het is **niet mogelijk, noch toegestaan, om de gegevens of arresten uit de Arrestendatabank
  in bulk te downloaden**, ongeacht de gebruikte techniek of methode."
- "Elk ander gebruik, waaronder **verdere verwerking, systematisch verzamelen, integratie in
  andere toepassingen of databanken, of commercieel hergebruik, is niet toegestaan**." Enkel
  "louter informatief gebruik" is toegelaten.
- Commercieel hergebruik uitdrukkelijk verboden; niet-commercieel enkel met klikbare
  bronvermelding; framing/inkapseling verboden.
- Beroept zich uitdrukkelijk op auteursrecht (Wet 30 juni 1994) én databankbescherming
  (Wet 31 augustus 1998).
- robots.txt: **[TE VERIFIËREN]** (naar verwachting restrictief, in lijn met bovenstaande).

### Haalbaarheidsinschatting: 🔴 Rood
Hoewel technisch scraperbaar, verbieden de gebruiksvoorwaarden **expliciet** het
geautomatiseerd/systematisch ophalen, het integreren in andere toepassingen of databanken en
elk commercieel hergebruik. Een connector-adapter die deze databank bevraagt en de resultaten
in Claude integreert, is daarmee in strijd. **Niet opnemen zonder voorafgaande overeenkomst**
met het agentschap Justitie en Handhaving. De stub-adapter in de scaffold blijft daarom
uitgeschakeld met een expliciete waarschuwing.

---

## Aanbevolen volgorde voor de eerste echte adapter

1. **DBRC / RvVb** — 🟢 technisch het eenvoudigst, geen JS, voorspelbare URL's, patroon reeds
   bewezen in de repo, en de kernbron voor IIOA/omgevingsrecht. Starten als intern,
   niet-commercieel prototype dat raadpleegt en naar de bron linkt.
2. **Raad van State** — per arrestnummer (`arr.php`) voor `zoek_op_identifier`/`haal_uitspraak`.
3. **Juportal** — als deeplink-/identifierbron (stabiele ECLI-URL, gunstige hergebruiksrechten);
   vrije-tekstzoeken pas na onderzoek van het JSON-endpoint.
4. **Arrestendatabank** — 🔴 voorlopig **niet**, tenzij een overeenkomst wordt gesloten.

## Openstaande verificatiepunten

- `robots.txt` van de vier domeinen manueel controleren. **DBRC: gedaan (25 juli 2026)** —
  Crawl-Delay 10 en `search_api_fulltext`/facet-URL's disallowed (zie DBRC-sectie hierboven).
  De zoekparameter van het formulier is `search_api_fulltext` (GET naar `/rechtspraak`,
  sortering via `sort_bef_combine=name_DESC`); live bevestigd. **Juportal en RvS: gedaan
  (3 augustus 2026)** — beide restrictief, zie de respectieve secties. Alleen
  arrestendatabank.be nog te doen (adapter blijft hoe dan ook uitgeschakeld).
- Juportal: bestaat er een JSON-/REST-endpoint achter de SPA (voor vrije-tekstzoeken)?
  Gelden de ruime FOD-Justitie-hergebruiksvoorwaarden ook voor de arrestteksten zelf (eigen
  Juportal-disclaimer nalezen — zie de copyright-comment-vondst hierboven)?
- RvS: ~~geeft `arr.php?nr=...` bruikbare server-rendered HTML?~~ **Beantwoord (3 augustus
  2026): het geeft direct de arrest-PDF terug.** Eigen gebruiksvoorwaarden nog nalezen; ook
  `l=fr` en de pdfplumber-tekstextractie zijn nog te doen.
- DBRC: is voor de beoogde (interne vs. gedeelde/commerciële) distributie schriftelijke
  toestemming nodig? Contact: info.dbrc@vlaanderen.be.
- Gelet op de robots-vondsten bij alle drie de bronnen: overwegen om per bron (DBRC, FOD
  Justitie/Juportal, RvS) toestemming of een structurele toegang te vragen, zodat de
  `sta_fetch`/`sta_zoek_scraping`-vlaggen verantwoord aan kunnen.
