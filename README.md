# rechtspraak-mcp — BE-rechtspraak (beta)

> [!WARNING]
> **Betaversie — geen product, geen garantie, geen aansprakelijkheid.** Deze software is een experimenteel
> hulpmiddel in ontwikkeling, geen commercieel product of dienst. Ze wordt kosteloos aangeboden zoals ze is,
> zonder enige uitdrukkelijke of stilzwijgende garantie, onder meer over juistheid, volledigheid, actualiteit of
> geschiktheid voor een bepaald doel. De resultaten zijn een geautomatiseerde opvraging van publieke rechtspraak-
> en wetgevingsbronnen; ze zijn **geen juridisch advies** en vervangen geen raadpleging van de officiële bron of
> een eigen juridische analyse. Een zoektreffer of fragment kan aanslaan op wat een partij aanvoert in plaats van
> op het oordeel van het rechtscollege: citeer alleen na controle in de officiële bron. Nul treffers betekent niet
> dat een uitspraak of norm niet bestaat. **De gebruiker is zelf volledig verantwoordelijk** voor het controleren
> van de resultaten en voor elk gebruik dat ervan wordt gemaakt, ook voor het naleven van de gebruiksvoorwaarden
> van de geraadpleegde bronnen. De auteur is niet aansprakelijk voor schade die voortvloeit uit het gebruik van de
> software of de resultaten.

MCP-connector die Claude toegang geeft tot Belgische en Europese rechtspraak en wetgeving: Juportal, de
Vlaamse bestuursrechtscolleges (DBRC, onder meer de Raad voor Vergunningsbetwistingen), de Raad van State,
het Hof van Justitie van de EU, het EHRM, EU-wetgeving, de Vlaamse Codex en Justel.

Elke treffer komt terug met een **controleerbare bron-URL** en een **voorstel van VENA-voetnootverwijzing**.
Bij een opgehaalde uitspraak markeert de connector het **beoordelende deel** (het oordeel van het
rechtscollege, niet wat partijen aanvoeren) als het enige citeermateriaal. De tools geven uitsluitend terug
wat de bron effectief levert.

**Voor gebruikers:** lees de [HANDLEIDING](HANDLEIDING.md). Installeren gaat in vier stappen via de
[releases](https://github.com/jefseghers-del/rechtspraak-mcp/releases), op macOS en Windows.

---

## De vijf tools

| Tool | Doel | Invoer |
|---|---|---|
| `zoek_op_identifier` | Eén uitspraak opzoeken | ECLI, DBRC-arrestnummer (`RvVb-A-2425-0744`), RvS-arrestnummer (`250.123`), EHRM-verzoekschriftnummer; bij DBRC ook `datum` |
| `haal_uitspraak` | Integrale tekst plus het beoordelende deel (`beoordeling`) | bron-URL en broncode uit een treffer |
| `zoek_rechtspraak` | Vrij zoeken | zoekterm; werkt voor het EHRM (HUDOC) en, als u dat aanzet, voor Juportal |
| `zoek_wetgeving` | Wetgeving opzoeken of zoeken | CELEX, citeervorm (`Richtlijn 2011/92/EU`), numac, ELI-URL, of vrije tekst |
| `haal_norm` | Tekst van één norm | bron-URL uit een treffer |

Elk antwoord bevat een veld `disclaimer`. Een leeg resultaat komt altijd met een `melding` die uitlegt
waarom (bron uit, botcontrole, tijdsbudget, onbekend formaat) en met `handmatige_links` die u zelf kunt
openen. Die links zijn **geen gevonden rechtspraak**.

### Citeren: alleen het beoordelende deel

`haal_uitspraak` splitst de tekst en geeft in `beoordeling` alleen de eigen beoordeling van het
rechtscollege, met het dictum. Welk deel dat is, verschilt per college:

| College | Beoordelend deel |
|---|---|
| Grondwettelijk Hof | de B-overwegingen |
| Hof van Cassatie | "Beslissing van het Hof" |
| Raad van State, RvVb | "Beoordeling (door de Raad)" en de beslissing |
| Hof van Justitie | "Beoordeling door het Hof", of bij prejudiciële arresten "Beantwoording van de prejudiciële vragen", telkens met kosten en dictum |
| EHRM | "The Court's assessment" en het dictum, zonder separate opinions |

Herkent de connector de structuur niet, dan blijft `beoordeling` leeg en zegt `segmentatie` dat. Er wordt
nooit geraden. Het veld `segmentatie` beschrijft ook wat er is weggelaten en waar u zelf moet opletten.

### VENA-verwijzing

Het veld `verwijzing` volgt de regels van [vena.be](https://vena.be) (RS1 en RS2 voor rechtspraak en
conclusies, WG2 en WG3 voor Belgische en Europese normen; samenvatting in
[docs/verwijsregels.md](docs/verwijsregels.md)), maar alleen met wat de bron levert. Partijnaam,
tijdschriftvindplaats en noot ontbreken dus; vul die zelf aan. Een URL staat er alleen in als er geen ECLI of
ELI is; de bron-URL staat altijd in het veld `url`. Voorbeelden:

    HvJ 7 september 2004, C-127/02, ECLI:EU:C:2004:482.
    Richtlijn 92/43/EEG van de Raad van 21 mei 1992 inzake de instandhouding van de natuurlijke habitats en de wilde flora en fauna, Pb.L. 22 juli 1992, 7, http://data.europa.eu/eli/dir/1992/43/oj.

---

## Bronnen en gebruiksvoorwaarden

Op uitspraken en officiële akten rust geen auteursrecht (artikel XI.172, §2 WER). Dat betekent niet dat
elke bron geautomatiseerde opvraging toelaat. Per bron:

| Bron | Standaard in de bundel | Toegang | robots.txt en voorwaarden |
|---|---|---|---|
| Hof van Justitie EU | **aan** | CELLAR (open data van het Publicatiebureau) | vrij hergebruik (Besluit 2011/833/EU) |
| EU-wetgeving | **aan** | CELLAR | idem; zoeken gebeurt op woorden in het opschrift |
| EHRM (HUDOC) | **aan** | publieke HUDOC-API | publieke data-API van het EHRM |
| Vlaamse Codex | **aan** | officiële open-data-API | open data van de Vlaamse overheid |
| DBRC op arrestnummer | altijd | HEAD-verzoek op de PDF-URL | PDF-pad niet disallowed; `Crawl-Delay: 10` wordt gerespecteerd |
| **Juportal** | **uit** | ECLI-deeplink | `Disallow: /`; de disclaimer staat hergebruik van rechtspraak toe |
| **Raad van State** | **uit** | `arr.php`-deeplink | `Disallow: /arr.php`; de disclaimer noemt de arresten vrij beschikbaar |
| **Justel** | **uit** | ELI-deeplink | `/eli/` disallowed |
| Juportal vrij zoeken | **uit** | headless browser (Playwright) | robots raadt geautomatiseerd zoeken af |
| DBRC vrij zoeken | uit (alleen via omgevingsvariabele) | zoekpagina | disallowed; vergt een akkoord van de DBRC |
| Arrestendatabank | nooit | — | geautomatiseerd hergebruik contractueel verboden; de adapter bevat bewust geen code die de databank bevraagt |

**Bronnen die standaard uit staan, zet u zelf aan en op eigen verantwoordelijkheid.** In Claude Desktop:
Instellingen → Extensies → BE-rechtspraak → Configureren. Bij elke schakelaar staat wat de robots.txt
zegt. De connector doet dan alleen gerichte opvragingen per nummer, met een herkenbare User-Agent en
rate limiting. Hij crawlt nooit een collectie af en omzeilt nooit een botcontrole: krijgt hij er een, dan
stopt hij en zegt dat.

De primaire teksten (robots.txt integraal, kernpassages van de disclaimers, vindplaatsen) staan in
[docs/bronnen-gebruiksvoorwaarden.md](docs/bronnen-gebruiksvoorwaarden.md). De lezingen daarin zijn als
eigen lezing gemarkeerd (*m.i.*) en zijn geen juridisch advies.

**EUR-Lex en CELLAR.** Sinds september 2026 plaatst EUR-Lex een botcontrole (AWS WAF) voor
geautomatiseerde opvragingen. De connector haalt EU-rechtspraak en -wetgeving daarom op via CELLAR, de
open-data-dienst van het Publicatiebureau. De links in de antwoorden blijven de gewone EUR-Lex-pagina's,
die u in de browser gewoon kunt openen.

---

## Disclaimer en privacy

> [!WARNING]
> **Betaversie — geen product, geen garantie, geen aansprakelijkheid.** Zie de volledige tekst bovenaan. De
> tekst staat op één plaats in de code (`rechtspraak_mcp/__init__.py`, `DISCLAIMER`); de server geeft hem bij
> elke verbinding mee aan Claude, en tests bewaken dat hij in de serverinstructies en het manifest blijft staan.

**Wat de connector bewaart.** Geen uitspraken, wetteksten of zoekopdrachten: er is geen cache en geen
geschiedenis, en niets van de opgevraagde inhoud wordt naar schijf geschreven. Opvragingen gaan rechtstreeks
van uw computer naar de bron; er is geen tussenserver van de auteur. Op schijf staan alleen:

- de Python-omgeving van de extensie (map `server/venv` in de extensiemap van Claude Desktop);
- twee markeringen (`.wheel_ok` met de geïnstalleerde versie, `.chromium_ok` als Chromium is gedownload);
- Chromium, alleen als u het browser-zoeken aanzet, in de standaardmap van Playwright;
- het logbestand dat Claude Desktop zelf bijhoudt. De connector schrijft daar alleen technische meldingen
  naar, geen inhoud van uitspraken.

**Persoonsgegevens in uitspraken.** Uitspraken kunnen namen en andere persoonsgegevens bevatten, zoals de
bron ze publiceert. De connector geeft die door zoals de bron ze levert; wat u ermee doet, valt onder uw
eigen verantwoordelijkheid. De resultaten komen in uw gesprek met Claude terecht, zoals alles wat u in dat
gesprek plakt.

**Testbestanden.** De uitspraakteksten in `tests/fixtures/` zijn gepseudonimiseerd: natuurlijke personen
staan er met initialen in, adressen en kadastrale gegevens zijn weggelaten
([tests/fixtures/README.md](tests/fixtures/README.md)).

---

## Licentie

Copyright © 2026 Jef Seghers. In licentie gegeven krachtens de EUPL.

De code valt onder de **Openbare Licentie van de Europese Unie, versie 1.2 (EUPL-1.2)**. De officiële
Nederlandse tekst staat in [LICENSE](LICENSE); alle taalversies hebben gelijke rechtskracht
([overzicht bij de Europese Commissie](https://interoperable-europe.ec.europa.eu/collection/eupl/eupl-text-eupl-12)).
U mag de code gebruiken, bestuderen, aanpassen en verspreiden. Wie een aangepaste versie verspreidt of online
als dienst aanbiedt, doet dat onder dezelfde licentie. Elk bronbestand draagt bovenaan de kennisgeving
`SPDX-License-Identifier: EUPL-1.2`.

GitHub herkent alleen de Engelse licentietekst automatisch en toont daarom geen licentiebadge. Juridisch
speelt dat geen rol.

De licentie geldt voor de **code**, niet voor de uitspraken en wetteksten die de tools teruggeven. Op
uitspraken en officiële akten rust geen auteursrecht (artikel XI.172, §2 WER); EUR-Lex- en CELLAR-inhoud is
vrij herbruikbaar (Besluit 2011/833/EU). Voor het gebruik van elke bron gelden haar eigen voorwaarden (zie
*Bronnen en gebruiksvoorwaarden*).

De afhankelijkheden worden niet meegeleverd maar bij de eerste start van PyPI gehaald. Hun licenties zijn
verenigbaar met de EUPL:

| Pakket | Licentie |
|---|---|
| mcp | MIT |
| httpx | BSD-3-Clause |
| beautifulsoup4 | MIT |
| pydantic | MIT |
| pdfplumber, pdfminer.six | MIT |
| starlette, uvicorn | BSD-3-Clause |
| playwright (optioneel, browser-zoeken) | Apache-2.0 |

---

## Installatie

### Als extensie in Claude Desktop (aanbevolen)

Zie de [HANDLEIDING](HANDLEIDING.md). Kort: download `be-rechtspraak.mcpb` bij de
[releases](https://github.com/jefseghers-del/rechtspraak-mcp/releases), en kies in Claude Desktop
Instellingen → Extensies → Geavanceerde instellingen → Extensie installeren. Vereist Python 3.12 of hoger.
De eerste start duurt 1 à 3 minuten (eenmalige installatie, internet nodig).

Voor Windows: [docs/installeren-windows.md](docs/installeren-windows.md).

### Vanuit de broncode

```bash
git clone https://github.com/jefseghers-del/rechtspraak-mcp.git
cd rechtspraak-mcp
uv venv && source .venv/bin/activate
uv pip install -e .            # met browser-zoeken: uv pip install -e ".[browser]"
pytest -q                      # geen netwerk; live-tests alleen met RUN_LIVE=1
```

Aansluiten op Claude Code:

```bash
claude mcp add be-rechtspraak /pad/naar/rechtspraak-mcp/.venv/bin/rechtspraak-mcp
```

Aansluiten op Claude Desktop zonder bundel: voeg dit toe aan `claude_desktop_config.json` en herstart
Claude Desktop.

```json
{
  "mcpServers": {
    "be-rechtspraak": {
      "command": "/pad/naar/rechtspraak-mcp/.venv/bin/rechtspraak-mcp",
      "env": { "RECHTSPRAAK_MCP_STA_FETCH": "hvj,ehrm,eurlex,codex" }
    }
  }
}
```

### Omgevingsvariabelen

Buiten de bundel staat elke bron standaard uit. De bundel vertaalt de schakelaars in Claude Desktop naar
deze variabelen.

| Variabele | Effect |
|---|---|
| `RECHTSPRAAK_MCP_STA_FETCH` | kommagescheiden bronnen die effectief worden opgehaald: `hvj`, `ehrm`, `eurlex`, `codex`, `juportal`, `raadvanstate`, `justel` |
| `RECHTSPRAAK_MCP_BROWSER_ZOEK=juportal` | vrij zoeken op Juportal via een headless browser (vergt de extra `[browser]` en `python -m playwright install chromium`) |
| `RECHTSPRAAK_MCP_DBRC_ZOEK_SCRAPING=1` | DBRC vrij zoeken (robots-disallowed; alleen met een akkoord van de DBRC) |
| `RECHTSPRAAK_MCP_TRANSPORT=streamable-http` | dezelfde server over HTTP in plaats van stdio |

**DBRC-nummers: geef de uitspraakdatum mee** (parameter `datum` van `zoek_op_identifier`). De DBRC publiceert
haar PDF's onder een publicatiemaand die niet uit het arrestnummer af te leiden is. Zonder datum probeert de
adapter maand na maand, met de voorgeschreven wachttijd van 10 s per poging, en stopt na 40 s
(`dbrc.TIJDSBUDGET_S`). De melding zegt dat dan uitdrukkelijk: "niet gevonden" betekent in dat geval niet
"bestaat niet".

### REST-API

`rechtspraak-mcp-http` start dezelfde kern als eenvoudige REST-API (`/api/gezondheid`,
`/api/zoek-identifier`, `/api/haal`), standaard op `127.0.0.1:8765`, met optioneel een bearer-token
(`RECHTSPRAAK_MCP_API_TOKEN`). Zie de docstring van `rechtspraak_mcp/http_api.py`. Zet die API niet publiek
open zonder token en zonder de bronvoorwaarden na te gaan.

---

## Ontwikkelen

```
rechtspraak_mcp/
├── __init__.py          # versie, repository-URL, User-Agent, DISCLAIMER, PRIVACY (één bron)
├── server.py            # MCP-server en de vijf tools
├── schema.py            # Treffer, Uitspraak, Norm, ZoekRespons, WetgevingRespons
├── segmentatie.py       # afbakening van het beoordelende deel per college
├── verwijzing.py        # VENA-verwijzingsvoorstel
├── cellar.py            # CELLAR (SPARQL + tekst) voor EU-rechtspraak en -wetgeving
├── botcontrole.py       # herkent botcontroles; de adapters stoppen dan
├── config.py            # schakelaars per bron (omgevingsvariabelen)
├── browser_zoek.py      # opt-in Juportal-zoeken met Playwright
├── http_api.py          # REST-schil op dezelfde kern
├── adapters/            # dbrc, juportal, raad_van_state, hvj, ehrm, arrestendatabank (stub)
└── wetgeving/           # eurlex, eurlex_zoek, codex, justel
mcpb-src/                # manifest, bootstrap (server/main.py) en bouwscript van de bundel
voorbeeld/               # voorbeelduitvoer en het script dat ze maakt
```

- **Tests**: `pytest -q`. Nieuwe adapters test u tegen vaste fixtures in `tests/fixtures/`, zonder netwerk.
  Gebruik alleen publieke uitspraken en pseudonimiseer natuurlijke personen.
- **Bundel bouwen**: `zsh mcpb-src/bouw.sh` (vereist `uv` en Node voor `npx`). Verhoog bij elke
  codewijziging de versie in `rechtspraak_mcp/__init__.py`, `pyproject.toml` en `mcpb-src/manifest.json`
  (een test bewaakt dat ze gelijk zijn): de bootstrap herkent een nieuwe versie aan de bestandsnaam van de
  wheel.
- **Voorbeeld opnieuw maken**: `python voorbeeld/maak_voorbeeld.py`.

### Harde regels

- **Anti-hallucinatie.** De tools geven uitsluitend terug wat een adapter effectief van de bron ontvangt;
  elke treffer behoudt een controleerbare bron-URL. Nul treffers is een geldig antwoord.
- **Bronnen respecteren.** robots.txt en gebruiksvoorwaarden volgen, nette rate limiting, een herkenbare
  User-Agent, nooit een betaalmuur of botcontrole omzeilen. De arrestendatabank blijft uit zonder overeenkomst.
- **Geen persoons- of dossiergegevens** in code, tests, documentatie of commitberichten.

Bijdragen en meldingen zijn welkom via [issues](https://github.com/jefseghers-del/rechtspraak-mcp/issues).
