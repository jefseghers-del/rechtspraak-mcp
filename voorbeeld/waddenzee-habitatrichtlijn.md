# Voorbeeld: wat BE-rechtspraak teruggeeft op één vraag

> Betaversie — geen product, geen garantie, geen aansprakelijkheid. Deze software is een experimenteel hulpmiddel in ontwikkeling, geen commercieel product of dienst. Ze wordt kosteloos aangeboden zoals ze is, zonder enige uitdrukkelijke of stilzwijgende garantie, onder meer over juistheid, volledigheid, actualiteit of geschiktheid voor een bepaald doel. De resultaten zijn een geautomatiseerde opvraging van publieke rechtspraak- en wetgevingsbronnen; ze zijn geen juridisch advies en vervangen geen raadpleging van de officiële bron of een eigen juridische analyse. Een zoektreffer of fragment kan aanslaan op wat een partij aanvoert in plaats van op het oordeel van het rechtscollege: citeer alleen na controle in de officiële bron. Nul treffers betekent niet dat een uitspraak of norm niet bestaat. De gebruiker is zelf volledig verantwoordelijk voor het controleren van de resultaten en voor elk gebruik dat ervan wordt gemaakt, ook voor het naleven van de gebruiksvoorwaarden van de geraadpleegde bronnen. De auteur is niet aansprakelijk voor schade die voortvloeit uit het gebruik van de software of de resultaten.

Opgevraagd op 18 september 2026, 13:55, met BE-rechtspraak 0.1.0 en de standaardinstellingen van de bundel.

## De vraag

> Zoek het arrest van het Hof van Justitie met ECLI:EU:C:2004:482 op, geef de VENA-verwijzing en citeer letterlijk wat het Hof voor recht verklaart. Geef ook de vindplaats van de Habitatrichtlijn (Richtlijn 92/43/EEG).

Op die vraag roept Claude drie tools van de connector aan. Hieronder staat letterlijk wat
de connector teruggeeft; Claude bouwt daar zijn antwoord op. Controleer altijd via de
bron-URL.

## 1. `zoek_op_identifier("ECLI:EU:C:2004:482")`

| Veld | Waarde |
|---|---|
| Instantie | Hof van Justitie |
| Titel | Arrest van het Hof (grote kamer) van 7 september 2004, Landelijke Vereniging tot Behoud van de Waddenzee en Nederlandse Vereniging tot Bescherming van Vogels tegen Staatssecretaris van Landbouw, Natuurbeheer en Visserij |
| Datum | 7-9-2004 |
| Zaaknummer | C-127/02 |
| ECLI | ECLI:EU:C:2004:482 |
| Bron-URL | https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=ecli:ECLI:EU:C:2004:482 |

**Voorstel van VENA-verwijzing** (partijnaam en tijdschriftvindplaats levert de bron niet;
vul die zelf aan en sluit af met een punt):

    HvJ 7 september 2004, nr. C-127/02, ECLI:EU:C:2004:482, https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=ecli:ECLI:EU:C:2004:482

## 2. `haal_uitspraak("https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=ecli:ECLI:EU:C:2004:482", "hvj")`

Integrale tekst: 50.692 tekens (niet opgenomen). Beoordelend deel: 27.327 tekens.

**Afbakening van het beoordelende deel** (veld `segmentatie`): rubriek 'De prejudiciële vragen' tot en met kosten en dictum geselecteerd; het juridisch kader en het hoofdgeding zijn weggelaten. Let op: het Hof vat binnen de beantwoording soms standpunten van partijen of van de Commissie samen — zelf controleren vóór citeren.

**Wat het Hof voor recht verklaart** (letterlijk, slot van het veld `beoordeling`):

> HET HOF VAN JUSTITIE (grote kamer) verklaart voor recht:
> 1)
> De mechanische kokkelvisserij, die al vele jaren wordt uitgeoefend maar waarvoor elk jaar voor een beperkte periode een vergunning
> wordt verleend, waarbij telkens opnieuw wordt beoordeeld of, en zo ja in welk gebied, de activiteit mag worden uitgeoefend,
> valt onder het begrip „plan” of „project” in artikel 6, lid 3, van richtlijn 92/43/EEG van de Raad van 21 mei 1992 inzake
> de instandhouding van de natuurlijke habitats en de wilde flora en fauna.
> 2)
> Bij artikel 6, lid 3, van richtlijn 92/43 wordt een procedure ingevoerd die is bedoeld om door middel van voorafgaande controle
> te garanderen dat voor een plan of project dat niet direct verband houdt met of nodig is voor het beheer van het betrokken
> gebied, maar dat voor het gebied significante gevolgen kan hebben, alleen toestemming wordt verleend voorzover dit de natuurlijke
> kenmerken van het gebied niet aantast, terwijl artikel 6, lid 2, van die richtlijn een algemene beschermingsverplichting oplegt,
> die erin bestaat verslechteringen of verstoringen te voorkomen die gelet op de doelstellingen van de richtlijn significante
> gevolgen zouden kunnen hebben, en niet tegelijkertijd met artikel 6, lid 3, kan worden toegepast.
> 3)
> a)
> Artikel 6, lid 3, eerste volzin, van richtlijn 92/43 moet aldus worden uitgelegd dat voor elk plan of project dat niet direct
> verband houdt met of nodig is voor het beheer van een gebied, een passende beoordeling wordt gemaakt van de gevolgen voor
> dat gebied, rekening houdend met de instandhoudingsdoelstellingen van het gebied, wanneer op grond van objectieve gegevens
> niet kan worden uitgesloten dat het afzonderlijk of in combinatie met andere plannen of projecten significante gevolgen heeft
> voor dat gebied.
> b) Op grond van artikel 6, lid 3, eerste volzin, van richtlijn 92/43 moet een plan of project dat niet direct verband houdt met
> of nodig is voor het beheer van een gebied, wanneer het de instandhoudingsdoelstellingen daarvan in gevaar dreigt te brengen,
> worden beschouwd als een plan of project dat significante gevolgen kan hebben voor het betrokken gebied. Dit moet met name
> worden beoordeeld in het licht van de specifieke milieukenmerken en omstandigheden van het gebied waarop het plan of project
> betrekking heeft.
> 4) Ingevolge artikel 6, lid 3, van richtlijn 92/43 brengt een passende beoordeling van de gevolgen van een plan of project voor
> het betrokken gebied mee dat, voordat voor dit plan of project toestemming wordt verleend, op basis van de beste wetenschappelijke
> kennis ter zake, alle aspecten van het plan of het project die op zichzelf of in combinatie met andere plannen of projecten
> de instandhoudingsdoelstellingen van dit gebied in gevaar kunnen brengen, moeten worden geïnventariseerd. De bevoegde nationale
> autoriteiten geven op basis van de passende beoordeling van de gevolgen van de mechanische kokkelvisserij voor het betrokken
> gebied, in het licht van de instandhoudingsdoelstellingen daarvan, slechts toestemming voor deze activiteit wanneer zij de
> zekerheid hebben verkregen dat de activiteit geen schadelijke gevolgen heeft voor de natuurlijke kenmerken van het betrokken
> gebied. Dit is het geval wanneer er wetenschappelijk gezien redelijkerwijs geen twijfel bestaat dat er geen schadelijke gevolgen
> zijn.
> 5) Wanneer een nationale rechter moet nagaan of de toestemming voor een plan of project in de zin van artikel 6, lid 3, van richtlijn
> 92/43 rechtmatig is verleend, kan hij toetsen of de door deze bepaling aan de beoordelingsmarge van de bevoegde nationale
> autoriteiten gestelde grenzen in acht zijn genomen, ook als de bepaling niet in de rechtsorde van de betrokken lidstaat is
> omgezet ofschoon de daartoe gestelde termijn is verstreken.

## 3. `zoek_wetgeving("Richtlijn 92/43/EEG")`

| Veld | Waarde |
|---|---|
| Opschrift | Richtlijn 92/43/EEG van de Raad van 21 mei 1992 inzake de instandhouding van de natuurlijke habitats en de wilde flora en fauna |
| CELEX | 31992L0043 |
| ELI | http://data.europa.eu/eli/dir/1992/43/oj |
| Vindplaats | PB L 206 van 22.7.1992 |
| Bron-URL | https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:31992L0043 |

**Voorstel van VENA-verwijzing:**

    Richtl.Raad 92/43/EEG, 21 mei 1992 inzake de instandhouding van de natuurlijke habitats en de wilde flora en fauna, PB L 206 van 22.7.1992, https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:31992L0043

---

Gemaakt met `voorbeeld/maak_voorbeeld.py`. Geen juridisch advies; de gebruiker blijft zelf
verantwoordelijk voor controle en gebruik.
