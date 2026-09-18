# Gebruiksvoorwaarden en robots.txt per bron — primaire teksten

Live opgehaald op 4 augustus 2026, ter eigen nalezing. Per bron: de robots.txt (integraal,
technische data), de vindplaats van de gebruiksvoorwaarden, de kernpassages (beknopt, met
pinpoint), en de lezing van de auteur — telkens gemarkeerd als *m.i.*. Die lezing is geen
juridisch advies; het is aan de lezer om ze te toetsen.

---

## 1. Raad van State (raadvst-consetat.be)

**Disclaimer**: https://www.raadvst-consetat.be/?page=disclaimer&lang=nl (server-rendered,
integraal leesbaar; zo ook de FR-versie via `lang=fr`).

Kernpunten uit de tekst:

- Rubriek *Auteursrecht*: de inhoud van de arresten op de site is "vrij beschikbaar voor
  iedereen"; wat níet mag worden overgenomen zonder toestemming: de HTML-code, grafische
  voorstellingen, en de "selectie en organisatie van de informatie".
- De disclaimer verankert de publicatie in de wet: artikel 28 gecoördineerde wetten op de
  Raad van State (arresten toegankelijk voor het publiek), uitgevoerd door het KB van 7 juli
  1997 (de Raad "waarborgt … de publicatie van de arresten" via een publiek toegankelijk
  informatienetwerk) en het MB van 3 februari 1998 (publicatie via de website).
- De disclaimer citeert zelf RvS 26 februari 1998, nr. 72.098: eenieder kan ter griffie
  kennisnemen van elk arrest, er afschrift van nemen, er "documentatie" over aanleggen en
  die verspreiden "in welke vorm ook".
- Links naar de site "dienen te worden gemeld aan de webmaster" (en in een nieuw venster te
  openen) — verouderde webpraktijk, maar het staat er.
- Belgisch recht, rechtbanken van Brussel.

**robots.txt** (https://www.raadvst-consetat.be/robots.txt):

```
User-agent: *
Disallow: /arr.php
Disallow: /Arresten/
Disallow: /arresten/
Disallow: /Arrets/
Disallow: /arrets/
Disallow: /Beschikkingen/
Disallow: /beschikkingen/
Disallow: /Ordonnances/
Disallow: /ordonnances/
Disallow: /Cass/
Disallow: /cass/
Disallow: /dbx/
Disallow: /dbx_dev/
Disallow: /*page=job*
Disallow: /*page=caselaw*
Disallow: /*page=hearing*
Crawl-delay: 10

User-agent: Googlebot-Image
Disallow: /
```

*M.i.*: de inhoud van de arresten is naar de eigen voorwaarden van de RvS vrij; de wettelijke
openbaarheidsregeling en het geciteerde arrest nr. 72.098 versterken dat aanzienlijk. De
robots-disallow op `arr.php` is een technische maatregel (vermoedelijk load- en
crawlerbeheersing), geen hergebruiksverbod, en robots.txt heeft geen eigen wettelijke
grondslag. Verdedigbaar is dat gerichte, incidentele opvraging per arrestnummer — wat een
gebruiker in een browser ook doet — geen "crawling" is waar robots.txt zich tegen richt.
Systematisch de hele collectie afhalen is een andere zaak: daar komt het databankenrecht in
beeld (zie § 5) en is de nette weg een afspraak met de griffie/webmaster, waarvoor het
geciteerde wettelijke kader een sterk aanknopingspunt biedt.

---

## 2. Juportal (juportal.be)

**Disclaimer**: https://juportal.be/home/disclaimer (server-rendered, integraal leesbaar —
de eerdere aanname dat deze pagina JS vereist, klopte niet).

Kernpunten uit de tekst:

- Uitdrukkelijk: op vonnissen, arresten en conclusies van het openbaar ministerie bestaat
  **geen auteursrecht** (artikel XI.172, §2 WER); zij "kunnen hergebruikt worden,
  overeenkomstig de regels vervat in de Wet van 4 mei 2016 inzake het hergebruik van
  overheidsinformatie".
- De disclaimer beschrijft verder de dekking per rechtscollege (GwH volledig; RvS sinds
  1995; Cassatie een selectie volgens de criteria uit BS 5 oktober 2007; overige colleges
  wisselend) — nuttig om de reikwijdte van de bron correct in te schatten.
- De copyrightvermelding "© 2017-2026 ICT Dienst - FOD Justitie" (en de strengere
  copyright-comment in de paginabron) slaat *m.i.* op de site/zoekmachine zelf, niet op de
  arrestteksten — de disclaimer zegt voor die laatste immers het omgekeerde.

**robots.txt** (identiek op juportal.be én juportal.just.fgov.be):

```
User-agent: *
Disallow: /

User-agent: DG_JUSTICE_CRAWLER
Allow: /
```

(plus een lange lijst publieke sitemaps onder `juportal.just.fgov.be/JUPORTAsitemap/…`)

*M.i.*: juridisch de sterkste bron — geen auteursrecht op de teksten, hergebruik wettelijk
geregeld (Wet 4 mei 2016, die overheden juist tot hergebruik-vriendelijkheid verplicht). De
blanket-disallow staat daar haaks op en is vermoedelijk een botweringsmaatregel; de
tegenstrijdigheid (disallow alles én publieke sitemaps én hergebruik-vriendelijke
disclaimer) is precies wat bij de FOD Justitie (info-JUPORTAL@just.fgov.be) uitgeklaard kan
worden — met de eigen disclaimer als vertrekpunt.

---

## 3. DBRC / Vlaamse bestuursrechtscolleges (dbrc.be)

**Disclaimer**: https://www.dbrc.be/disclaimer (server-rendered).

Kernpunten uit de tekst:

- Rubriek *Hergebruik van arresten*: de arresten zijn "uitsluitend bestemd voor raadpleging";
  geheel of gedeeltelijk hergebruik, reproductie, verspreiding of publicatie **voor
  commerciële doeleinden** enkel na voorafgaande en uitdrukkelijke schriftelijke toestemming.
  Zonder toestemming is elk hergebruik verboden, "behoudens de gevallen waarin dit
  uitdrukkelijk is toegestaan door de toepasselijke wetgeving".
- Site-inhoud: HTML-code en "selectie en organisatie van de informatie" niet overnemen
  zonder toestemming.
- Belgisch recht, rechtbanken van Brussel. Contact: via de contactpagina
  (info.dbrc@vlaanderen.be).

**robots.txt** (gecontroleerd 25 juli 2026): `Crawl-Delay: 10`;
`Disallow: /*?*search_api_fulltext*` en `Disallow: /*f%5B0%5D*` (zoek- en facet-URL's);
de arrest-PDF's onder `/sites/default/files/` zijn **niet** disallowed.

*M.i.*: de clausule "behoudens … toepasselijke wetgeving" is belangrijker dan ze lijkt: op de
arresten zelf rust ook hier geen auteursrecht (artikel XI.172, §2 WER geldt onverkort — de
DBRC kan geen auteursrecht claimen dat de wet uitsluit), en het decreet hergebruik
overheidsinformatie is "toepasselijke wetgeving". De disclaimer beperkt dus vooral wat de
DBRC contractueel kán beperken: het gebruik van haar databank en site. Raadpleging en
incidentele opvraging zijn uitdrukkelijk de bedoeling; het geautomatiseerd afhalen van de
collectie raakt het databankenrecht van de DBRC en het uitdrukkelijke toestemmingsvereiste
voor commercieel/breed hergebruik. Voor een intern kantoorinstrument is de vraag of dat
"commerciële doeleinden" zijn — verdedigbaar van niet (raadpleging in de uitoefening van het
beroep), maar de veilige route blijft de schriftelijke toestemming, zeker voor corpus-opbouw.

---

## 4. Arrestendatabank (arrestendatabank.be)

**Disclaimer**: https://arrestendatabank.be/disclaimer (server-rendered).

Kernpunten uit de tekst:

- "Het is niet mogelijk, noch toegestaan, om de gegevens of arresten uit de Arrestendatabank
  in bulk te downloaden, ongeacht de gebruikte techniek of methode."
- Gedownloade gegevens niet verwerken of aanwenden buiten "louter informatief gebruik"; elk
  ander gebruik — "verdere verwerking, systematisch verzamelen, integratie in andere
  toepassingen of databanken, of commercieel hergebruik" — is niet toegestaan.
- Beroept zich op auteursrecht (Wet 30 juni 1994) én databankbescherming (Wet 31 augustus
  1998), toegepast "op de gehele database … en op de inhoud ervan"; integriteit van de
  documenten moet gerespecteerd blijven.
- Beheerd door het agentschap Justitie en Handhaving, afdeling Handhaving; voorwaarden
  eenzijdig wijzigbaar.

*M.i.*: het auteursrechtberoep op de arrestteksten zelf botst op artikel XI.172, §2 WER, maar
het **databankenrecht** op de verzameling staat sterker, en het verbod op "integratie in
andere toepassingen" is precies wat een MCP-adapter doet. Dit blijft de enige bron waar de
voorwaarden de connector als zodanig raken — vandaar: niet zonder overeenkomst.

---

## 4bis. EUR-Lex (via CELLAR), HUDOC en Vlaamse Codex

Nagekeken op 18 september 2026.

**EUR-Lex.** Hergebruik van EUR-Lex-inhoud is vrij (Besluit 2011/833/EU van de Commissie). De
legal-content-pagina's en de zoekpagina antwoorden op geautomatiseerde opvragingen echter met
HTTP 202, een lege body en de header `x-amzn-waf-action: challenge`: een botcontrole (AWS WAF).
Die omzeilt de connector niet. Hij gebruikt daarom **CELLAR**, de machinetoegang die het
Publicatiebureau zelf aanbiedt voor dezelfde documenten: het SPARQL-endpoint
`https://publications.europa.eu/webapi/rdf/sparql` en de content negotiation op
`https://publications.europa.eu/resource/celex/<CELEX>`. De robots.txt van publications.europa.eu
(die doorverwijst naar op.europa.eu) sluit die paden niet uit. De links die de gebruiker krijgt,
blijven de gewone EUR-Lex-pagina's.

**HUDOC (EHRM).** De connector gebruikt de publieke JSON-API van HUDOC. De site zit achter
Cloudflare, dat met tussenpozen een challenge toont (HTTP 403, `cf-mitigated: challenge`). De
connector stopt dan, probeert het niet opnieuw en meldt het.

**Vlaamse Codex.** Officiële open-data-API van de Vlaamse overheid
(`codex.opendata.api.vlaanderen.be`); geen robots-kwestie.

---

## 5. Dwarsdoorsnede: "er bestaan toch veel scrapers?"

Klopt, en de verklaring zit in de gelaagdheid — het zijn vijf verschillende vragen:

1. **robots.txt** is een technische conventie zonder eigen wettelijke grondslag. Negeren is
   niet per se onrechtmatig; naleven is wel de nette praktijk en weegt mee bij de beoordeling
   van goede trouw (en bij de vraag of opvragingen "systematisch" zijn in de zin van het
   databankenrecht).
2. **Auteursrecht op de arresten zelf: nee** — artikel XI.172, §2 WER sluit officiële akten
   van de overheid uit. Juportal zegt dat met zoveel woorden; de RvS noemt de inhoud van de
   arresten vrij beschikbaar. Auteursrecht speelt wél voor site-opmaak, koppen, samenvattingen
   en selectie.
3. **Databankenrecht** (Wet 31 augustus 1998 / sui generis): verbiedt het opvragen of
   hergebruiken van een substantieel deel van een beschermde databank, én het "herhaald en
   systematisch" opvragen van niet-substantiële delen. Dít is de echte juridische rem op
   corpus-opbouw — niet het auteursrecht. Incidentele opvraging per identifier raakt het niet.
4. **Gebruiksvoorwaarden** als eenzijdige kennisgeving (browse-wrap): afdwingbaarheid is
   betwistbaar, maar de overheid kan als databankproducent wél voorwaarden stellen aan wat
   verder gaat dan het wettelijk toegestane hergebruik.
5. **AVG**: arresten bevatten persoonsgegevens; systematische verzameling maakt je verwerker
   met eigen verplichtingen. Bij incidentele raadpleging is dat verwaarloosbaar, bij een
   eigen index niet.

De commerciële aanbieders die dit al doen, vallen doorgaans in één van drie categorieën:
ze hebben een licentie of aanleverafspraak met de bron, ze steunen op het wettelijke
hergebruikskader (Juportal-achtige bronnen), of ze dragen bewust het risico onder 3 en 4.
Het bestaan van scrapers bewijst dus niet dat het mag — maar de eigen teksten van RvS en
Juportal bieden wél een aanzienlijk sterkere basis dan de robots-bestanden doen vermoeden.

**Praktische slotsom** (*m.i.*, ter toetsing door de lezer): incidentele opvraging per
ECLI/arrestnummer is bij RvS en Juportal goed verdedigbaar op hun eigen voorwaarden, en bij
DBRC minstens verdedigbaar als "raadpleging"; corpus-opbouw voor de semantische zoekfunctie
vergt bij alle bronnen een afspraak — en de teksten hierboven (wettelijke openbaarheid RvS,
hergebruikswet bij Juportal) zijn daarvoor de beste argumenten in de aanvraagbrief.
