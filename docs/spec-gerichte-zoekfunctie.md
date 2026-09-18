# Spec — gerichte rechtspraakzoekfunctie ("vraag in enkele zinnen") + browserextensie

Vervolgfase op [spec-rechtspraak-mcp-connector.md](spec-rechtspraak-mcp-connector.md). Concept
van 3 augustus 2026, opgesteld naar aanleiding van de bijkomende eis van Jef: de gebruiker
formuleert een juridische stelling of vraag in enkele zinnen en krijgt de rechtspraak terug die
die stelling kan onderbouwen. Onbevestigde vaststellingen zijn gemarkeerd **[TE VERIFIËREN]**.

## 1. De bepalende eis: alleen het oordeel van het rechtscollege telt

Rechtspraak dient hier één doel: **stellingen onderbouwen in wat de gebruiker schrijft**
(adviezen, verzoekschriften, nota's). Daaruit volgt een eis die het hele ontwerp stuurt:

> Enkel de **eigen beoordeling van het rechtscollege** is bruikbaar. Wat partijen aanvoeren, is
> dat niet — ook al staat het in hetzelfde arrest en gebruikt het dezelfde bewoordingen.

Dit is geen verfijning achteraf maar een primaire filter. Een arrest bestaat grotendeels uit
weergave van standpunten van partijen; wie het volledige document indexeert, krijgt overwegend
treffers op het betoog van een verzoekende partij. Zulke treffers zijn niet alleen nutteloos,
ze zijn **gevaarlijk**: geciteerd als ware het een oordeel van de Raad onderbouwen ze niets en
ondermijnen ze het stuk waarin ze belanden.

### 1.1 Segmentatie per rechtscollege

De retrieval-eenheid is dus niet het arrest maar de **overweging** binnen het beoordelende deel.

| College | Deel dat telt | Deel dat wordt uitgefilterd |
|---------|---------------|------------------------------|
| **Grondwettelijk Hof** | de **B-paragrafen** ("In rechte": B.1, B.2, …) | de **A-paragrafen** (standpunten van de partijen) |
| **Hof van Cassatie** | "Beslissing van het Hof" | de cassatiemiddelen van de eiser |
| **Raad van State** | de "Beoordeling"-onderdelen per middel + het dictum | "Standpunt van de partijen", feiten, verloop van de rechtspleging |
| **RvVb / DBRC** | idem: "Beoordeling" per middel + "Beslissing" | "Standpunt van de partijen", feiten, rechtspleging |

De GwH-splitsing A/B is de zuiverste en is een vaste conventie. Voor RvS en RvVb steunt de
segmentatie op koppen ("Standpunt van de partijen" → "Beoordeling"); de exacte formulering
varieert over de jaren heen en per kamer **[TE VERIFIËREN — te ijken op een reeks echte
arresten uit verschillende jaren vóór dit in productie gaat]**.

### 1.2 Drie categorieën die niét het oordeel zijn maar er wel op lijken

1. **Conclusie van het openbaar ministerie** (Cassatie) en **auditeursverslag** (RvS): gezaghebbend,
   afzonderlijk citeerbaar (VENA RS2: `HENKES A., 'Conclusie bij Cass. 21 oktober 2010', JT 2011, (562) 563.`),
   maar **geen oordeel van het college**. Moeten apart gelabeld worden en nooit als de beslissing
   worden gepresenteerd.
2. **Weergave van eerdere rechtspraak binnen het arrest**: het college dat een eerder arrest
   parafraseert. Citeerbaar, maar bij voorkeur wordt naar het oorspronkelijke arrest verwezen.
3. **Obiter dictum** tegenover **dragende overweging**: alleen de tweede draagt het dispositief en
   heeft volle overtuigingskracht. Automatische detectie hiervan is m.i. niet betrouwbaar te
   bouwen; de tool moet dit niet pretenderen. Wel haalbaar: de overweging tonen mét haar
   randnummer en positie, zodat de gebruiker dat zelf beoordeelt.

### 1.3 Wat één treffer moet bevatten

Eén treffer = één overweging, met: de **letterlijke tekst** van de overweging (nooit een
parafrase), het **randnummer**, de arrestmetadata, de kant-en-klare **VENA-voetnoot** (bestaat
al: `rechtspraak_mcp/verwijzing.py`) en de **deeplink** ter controle. Daarmee is de treffer
onmiddellijk bruikbaar in een lopende tekst — dat is het eigenlijke product.

## 2. De echte blokkade: er is geen corpus om in te zoeken

Zoeken op een vraag van enkele zinnen betekent semantisch zoeken, en dat vergt een **index over
de tekst van de arresten**. Die index bestaat nergens publiek, en geen van de drie bronnen laat
toe hem geautomatiseerd op te bouwen (zie [bronnenonderzoek.md](bronnenonderzoek.md)):

- **DBRC**: de arrest-PDF's zijn niet robots-disallowed, maar de disclaimer bestempelt de
  arresten als "uitsluitend bestemd voor raadpleging"; ± 19 000 PDF's systematisch ophalen om
  een index te bouwen is m.i. **hergebruik**, geen raadpleging. Vergt toestemming.
- **Juportal**: `Disallow: /` voor alle generieke bots, terwijl de FOD-gebruiksvoorwaarden
  onvoorwaardelijk hergebruik toestaan én er publieke sitemaps zijn. Die tegenstrijdigheid moet
  uitgeklaard worden bij de bron.
- **Raad van State**: `Disallow: /arr.php`, crawl-delay 10. De doorlopende nummering maakt een
  corpus technisch triviaal — wat precies de reden zal zijn dat het disallowed is.

**Het kritieke pad is dus niet technisch maar contractueel.** Drie aanvragen (DBRC via
info.dbrc@vlaanderen.be, FOD Justitie voor Juportal, RvS) bepalen of dit product kan bestaan in
de vorm die je voor ogen hebt. Ik kan die aanvragen opstellen.

### 2.1 Wat intussen wél kan — en meteen testbaar is

De volledige verwerkingsketen (segmentatie → overwegingen → index → semantisch zoeken →
VENA-citaat) is **bronneutraal**. Ze kan nu al gebouwd en getest worden op arresten die je
rechtmatig bezit: eigen dossiers en rechtspraakoverzichten, en de PDF's die je stuk voor stuk
raadpleegt. Dat levert een werkend, testbaar product op zonder één regel scraping, en het is
tegelijk de eerlijke pilot waarmee je de toestemmingsaanvraag kunt onderbouwen ("dit is wat we
willen doen, dit is de omvang, dit is de bronvermelding"). Zodra er een akkoord is, wordt de
bron er als adapter ingeschoven — de rest van de keten verandert niet.

## 3. Architectuur — één kern, twee schillen

De browserextensie is een **presentatielaag**, geen tweede product. Het ontwerp mag zich niet
splitsen in twee codebases.

```
        Chrome-extensie (zijpaneel)        Claude (MCP-connector)
                    │                                │
                    └──────────► HTTP ◄───────────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    │  gedeelde kern             │
                    │  retrieval + segmentatie   │
                    │  + VENA-citaat             │
                    └─────────────┬──────────────┘
                          adapters per bron
```

- De MCP-server krijgt naast stdio een **HTTP-transport**. Dat was al voorzien: spec punt 6
  ("architectuur meteen voorbereid op een remote connector"). De extensie praat met datzelfde
  endpoint; alleen de schil verschilt.
- De extensie kan geen embeddings lokaal draaien en heeft dus hoe dan ook een backend nodig.
- Authenticatie: intern gebruik, dus een token per gebruiker. Geen publieke endpoint zonder de
  licentie-analyse uit spec punt 6.

### 3.1 Retrieval

Hybride: trefwoorden (BM25) **en** embeddings over de overwegingen, gevolgd door een
herrangschikking. De vraag van de gebruiker is een juridische stelling, geen trefwoordenlijst —
puur lexicaal zoeken mist parafrases, puur semantisch zoeken mist exacte wettelijke begrippen.

**Anti-hallucinatie blijft absoluut**: het model mag overwegingen selecteren en rangschikken,
nooit formuleren. Wat de gebruiker ziet, staat letterlijk in de bron-PDF, met deeplink.

### 3.2 Aandachtspunt bij de keuze van de schil

Een Chrome-extensie helpt wanneer je in de browser schrijft. Schrijf je je adviezen en
processtukken in Word, dan zit de plugin op de verkeerde plaats en is de winst beperkt tot
kopiëren-en-plakken — terwijl een Word-invoegtoepassing de voetnoot rechtstreeks op de juiste
plek kan zetten (en de VENA-opmaak al klaarstaat, zie de `advies`-skill). De gedeelde kern
hierboven maakt die keuze omkeerbaar: beide schillen praten met hetzelfde endpoint. Het is dus
geen beslissing die nu vastligt, maar wel een die de moeite van het bekijken waard is.

## 4. Volgorde van uitvoering

1. **Segmentatie-experiment** op een handvol echte arresten per college (GwH, Cassatie, RvS,
   RvVb) — vaststellen hoe betrouwbaar het beoordelende deel te isoleren is, en de koppen uit
   § 1.1 ijken. Dit is de kritische technische onbekende: valt of staat het product mee.
2. **Toestemmingsaanvragen** opstellen en versturen (DBRC, FOD Justitie, RvS). Loopt parallel;
   de doorlooptijd is niet in de hand te houden, dus vroeg beginnen.
3. **Keten bouwen op eigen corpus** (eigen dossiers): overwegingen → index → zoeken → VENA-citaat.
   Levert het eerste echt testbare product.
4. **HTTP-transport** naast stdio op de MCP-server.
5. **Schil** (Chrome-extensie of Word-invoegtoepassing) op datzelfde endpoint.

## 5. Openstaande punten

- Koppenstructuur per college en per periode ijken **[TE VERIFIËREN]** (§ 1.1).
- Betrouwbaar onderscheid dragende overweging / obiter dictum: m.i. niet automatiseerbaar; te
  bevestigen of te weerleggen in stap 1.
- Keuze van het embeddingmodel en of de arrestteksten daarvoor naar een externe dienst mogen —
  raakt de gebruiksvoorwaarden van de bron én, bij eigen dossiers, het beroepsgeheim. **Dit moet
  uitgeklaard zijn vóór stap 3.**
- Chrome-extensie versus Word-invoegtoepassing (§ 3.2).
