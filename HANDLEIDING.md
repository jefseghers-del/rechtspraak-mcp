# BE-rechtspraak — handleiding

Voor wie de connector gewoon wil gebruiken. Geen programmeerkennis nodig.

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

BE-rechtspraak laat Claude rechtspraak en wetgeving opzoeken in de officiële bronnen: het Hof van Justitie
van de EU, het Europees Hof voor de Rechten van de Mens, EU-richtlijnen en -verordeningen, de Vlaamse Codex,
de Raad voor Vergunningsbetwistingen en de andere Vlaamse bestuursrechtscolleges, en (als u dat aanzet)
Juportal, de Raad van State en Justel.

Bij elk resultaat krijgt u de **link naar de officiële bron** en een **voorstel van voetnoot volgens de
VENA-regels**. Bij een opgehaalde uitspraak duidt de connector het **beoordelende deel** aan: wat het
rechtscollege zelf oordeelt, los van wat de partijen aanvoeren.

U stelt uw vraag gewoon in het Nederlands. Claude kiest zelf de juiste opzoeking.

---

## 1. Installeren

**Wat u eerst nodig hebt**

- Claude Desktop (Mac of Windows).
- Python 3.12 of hoger. Nog niet geïnstalleerd? Haal het op bij [python.org](https://www.python.org/downloads/).
  Vink op Windows tijdens de installatie **"Add python.exe to PATH"** aan. Gebruik op Windows bij voorkeur
  de versie van python.org, niet die uit de Microsoft Store.

**Installeren in vier stappen**

1. Ga naar de [releases van de repository](https://github.com/jefseghers-del/rechtspraak-mcp/releases)
   en download het bestand `be-rechtspraak.mcpb` van de bovenste release.
2. Open Claude Desktop en ga naar **Instellingen → Extensies**.
3. Klik op **Geavanceerde instellingen → Extensie installeren** en kies het gedownloade bestand.
4. De eerste keer duurt het opstarten één tot drie minuten: de extensie zet dan haar eigen
   werkomgeving klaar. Daarvoor is internet nodig. Claude Desktop wacht daar niet altijd op en kan een
   time-out melden. **Wacht dan drie minuten en start Claude Desktop opnieuw**; de tweede keer start de
   extensie meteen.

Meer over Windows: [docs/installeren-windows.md](docs/installeren-windows.md).

**Controleren of het werkt**

Typ in een nieuw gesprek:

> Zoek het arrest met ECLI:EU:C:2004:482 op.

Krijgt u het Waddenzee-arrest van het Hof van Justitie van 7 september 2004 (zaak C-127/02), met een link
naar EUR-Lex, dan werkt de connector. Ziet u bij Extensies de melding **Failed**, klik dan op **View logs**
en stuur de regels door die beginnen met `[be-rechtspraak]`.

---

## 2. Welke bronnen staan aan

| Bron | Standaard | Wat u krijgt |
|---|---|---|
| Hof van Justitie EU (en Gerecht) | aan | opzoeken op ECLI, volledige tekst, beoordelend deel |
| EU-wetgeving | aan | opzoeken op nummer (Richtlijn 2011/92/EU, CELEX), zoeken op woorden in de titel, volledige tekst |
| EHRM | aan | opzoeken op ECLI of verzoekschriftnummer, vrij zoeken, volledige tekst |
| Vlaamse Codex | aan | Vlaamse en federale wetgeving: zoeken, opzoeken op numac |
| Raad voor Vergunningsbetwistingen, Handhavingscollege en de andere DBRC-colleges | altijd | opzoeken op arrestnummer, volledige tekst |
| Juportal (Cassatie, Grondwettelijk Hof, hoven en rechtbanken, RvS) | **uit** | opzoeken op ECLI |
| Raad van State | **uit** | opzoeken op arrestnummer |
| Justel | **uit** | geconsolideerde wetteksten via ELI-link |
| Vrij zoeken op Juportal | **uit** | zoeken op woorden of rolnummer (vergt een eenmalige download van ±100 MB) |

**Waarom sommige bronnen uit staan.** Juportal, de Raad van State en Justel vragen in hun robots.txt om hun
sites niet geautomatiseerd te bevragen. Op de uitspraken en wetteksten zelf rust geen auteursrecht, en de
connector vraagt alleen één document per keer op, zoals u dat in de browser zou doen. Toch is het aanzetten
**uw eigen keuze en uw eigen verantwoordelijkheid**.

**Zo zet u een bron aan:** Instellingen → Extensies → BE-rechtspraak → **Configureren**. Bij elke
schakelaar staat wat de bron voorschrijft. Staat een bron uit, dan geeft de connector een link die u zelf
kunt openen.

---

## 3. Voorbeeldvragen

U kunt deze vragen letterlijk overnemen. Vervang de nummers door die van uw dossier.

### Europese rechtspraak en wetgeving

> Zoek het arrest van het Hof van Justitie met ECLI:EU:C:2004:482 op, geef de VENA-verwijzing en citeer
> letterlijk wat het Hof voor recht verklaart. Geef ook de vindplaats van de Habitatrichtlijn (Richtlijn
> 92/43/EEG).

Wat de connector op deze vraag teruggeeft, staat in
[voorbeeld/waddenzee-habitatrichtlijn.md](voorbeeld/waddenzee-habitatrichtlijn.md).

> Welke EU-richtlijnen hebben "milieueffectbeoordeling" in hun titel? Geef per richtlijn het CELEX-nummer en
> de vindplaats in het Publicatieblad.

> Geef de tekst van artikel 6 van de Habitatrichtlijn (Richtlijn 92/43/EEG), met de VENA-verwijzing.

> Zoek het EHRM-arrest met verzoekschriftnummer 53600/20 op en vat samen wat het Hof oordeelt over
> artikel 8 EVRM. Citeer alleen uit het beoordelende deel.

> Zoek EHRM-arresten over "climate change" sinds 2020, met datum en zaaknummer.

### Vlaamse bestuursrechtspraak

> Zoek het arrest RvVb-A-2425-0744 van 3 juni 2025 op. Geef de VENA-verwijzing en vat het beoordelende deel
> samen.

Geef bij een RvVb- of ander DBRC-nummer **altijd de datum van de uitspraak mee** als u die kent. Zonder datum
moet de connector de publicatiemaand raden en stopt hij na 40 seconden (zie § 6).

### Wetgeving

> Welke recente Vlaamse regelgeving vermeldt "stikstof"? Geef opschrift, datum en vindplaats in het
> Belgisch Staatsblad.

### Met Juportal of de Raad van State aangezet

Een algemenere vraag vanuit een dossier. Hiervoor moeten **"Juportal automatisch ophalen"** en
**"Vrij zoeken op Juportal"** aan staan (zie § 2):

> Mijn cliënt ondervindt al maanden hinder van werken op het aanpalende perceel: trillingen en scheuren in
> de gevel. Welke voorwaarden stelt het Hof van Cassatie voor een vordering wegens burenhinder (artikel 544
> oud BW, nu artikel 3.101 BW)? Zoek rechtspraak op Juportal, haal de relevante arresten op en citeer alleen
> uit de beslissing van het Hof, telkens met de VENA-verwijzing.

Claude zoekt dan op Juportal, haalt de arresten op en citeert uit de beslissing van het Hof. Vraag bij
een algemene vraag altijd naar de arresten zelf: de korte samenvatting die Juportal bij een treffer toont
(de fiche), is geen tekst van het Hof.

> Haal het arrest van het Hof van Cassatie met ECLI:BE:CASS:2013:ARR.20130611.12 op en geef alleen de
> beslissing van het Hof.

> Haal RvS-arrest nr. 264.818 op en vat de beoordeling door de Raad samen, met de VENA-verwijzing.

---

## 4. Waar u op moet letten

**U blijft zelf verantwoordelijk.** De connector is een betaversie en geeft geen enkele garantie over de
resultaten. Het is geen juridisch advies. Controleer wat u in een advies, conclusie of nota overneemt, altijd
via de link naar de officiële bron.

**Citeer alleen uit het beoordelende deel.** Een arrest bevat ook wat de partijen aanvoeren. De connector
zet het oordeel van het rechtscollege apart (veld *beoordeling*) en zegt hoe hij het heeft afgebakend.
Herkent hij de structuur niet, dan zegt hij dat; kijk dan zelf na welk deel het oordeel is. Vraag Claude
uitdrukkelijk om alleen uit het beoordelende deel te citeren.

**Arrest, conclusie of fiche.** Juportal bevat naast arresten ook conclusies van het openbaar ministerie
en samenvattingen (fiches). Een conclusie is geen uitspraak van het Hof: de connector herkent ze, geeft er
geen "beoordelend deel" voor en stelt een voetnoot voor in de vorm die VENA voor conclusies voorschrijft:
"[FAMILIENAAM I.], 'Conclusie bij Cass. …', ECLI". Vul de naam van de magistraat zelf in. Citeer het
oordeel van het Hof altijd uit het arrest.

**Nul treffers betekent niet: bestaat niet.** De connector geeft alleen wat de bron teruggeeft. Vindt hij
niets, dan zegt hij waarom (bron uit, nummer niet herkend, tijdslimiet, botcontrole) en geeft hij een link
om zelf te zoeken. Claude vult niets aan uit zijn geheugen.

**De voetnoot is een voorstel.** De verwijzing volgt de regels van [vena.be](https://vena.be), maar bevat
alleen wat de bron levert, bv. "Cass. 5 december 2016, C.16.0150.N, ECLI:BE:CASS:2016:ARR.20161205.2." of
"Richtlijn 92/43/EEG van de Raad van 21 mei 1992 inzake …, Pb.L. 22 juli 1992, 7,
http://data.europa.eu/eli/dir/1992/43/oj." Partijnaam, tijdschriftvindplaats en een eventuele noot of
conclusie ontbreken; vul die zelf aan. Bij RvVb-arresten ontbreekt de datum soms, omdat de bron die niet
meegeeft; neem ze dan over uit het arrest.

**EU-wetgeving: de oorspronkelijke tekst, niet de geconsolideerde.** De connector geeft een richtlijn of
verordening zoals ze in het Publicatieblad verscheen, zonder latere wijzigingen. Controleer de geldende
versie op EUR-Lex. Zoeken in EU-wetgeving gebeurt bovendien op de titel: een zoekwoord moet in het
opschrift staan, niet ergens in de tekst.

**Botcontroles.** Sommige bronnen tonen soms een controle "bent u een mens?". De connector omzeilt die nooit.
U krijgt dan een melding en een link; probeer het later opnieuw of open de link zelf.

**Gebruiksvoorwaarden van de bronnen.** Zet u Juportal, de Raad van State of Justel aan, dan doet u dat op
eigen verantwoordelijkheid (zie § 2). Gebruik de connector voor gerichte opzoekingen, niet om een
collectie af te halen.

**Persoonsgegevens.** Uitspraken kunnen namen bevatten, zoals de bron ze publiceert. De connector bewaart
zelf niets: geen uitspraken, geen zoekopdrachten, geen geschiedenis. Wat u met de resultaten doet, valt
onder uw eigen verantwoordelijkheid.

---

## 5. Handige preciseringen in uw vraag

| Wat u toevoegt | Wat het doet |
|---|---|
| "van 3 juni 2025" (bij een DBRC-nummer) | de connector vindt het arrest meteen, zonder maanden af te zoeken |
| "citeer alleen uit het beoordelende deel" | Claude citeert niet uit wat partijen aanvoeren |
| "letterlijk" | een citaat in plaats van een samenvatting |
| "met de VENA-verwijzing" | het voorstel van voetnoot komt mee |
| "geef de link naar de bron" | u kunt meteen controleren |
| "sinds 2020" (bij EHRM-zoeken) | beperkt tot recente arresten |
| "het ECLI" of "het CELEX-nummer" | het vaste nummer van de uitspraak of norm, handig voor later |

---

## 6. Als er iets misloopt

**De extensie start niet.** Instellingen → Extensies → View logs, en kijk naar de regels met
`[be-rechtspraak]`. Meestal ontbreekt Python 3.12 of was er bij de eerste start geen internet.

**Bij de eerste start: "Request timed out".** Dat is normaal. De extensie installeert op de achtergrond
verder; staat er in het log "Omgeving klaar", start dan Claude Desktop opnieuw.

**Windows: Python gevonden?** De extensie start Python met de opdracht `python`. Werkt die opdracht niet
in een opdrachtprompt, installeer Python dan opnieuw via python.org en vink "Add python.exe to PATH" aan.
Meldt het log "Python uit de Microsoft Store in gebruik", dan werkt het meestal wel, maar de versie van
python.org is betrouwbaarder.

**"Het automatisch ophalen staat uit".** De bron staat uit (zie § 2). Zet ze aan, of open de link die de
connector meegeeft.

**"De zoektocht is op het tijdsbudget gestopt"** (bij een RvVb- of DBRC-nummer). Geef de datum van de
uitspraak mee in uw vraag. Die melding zegt niets over het bestaan van het arrest.

**"Vroeg een botcontrole".** De bron vroeg om een menselijke controle. Probeer het later opnieuw, of open de
link zelf.

**Een Frans of Duits arrest.** De connector geeft de tekst in de taal van de bron. Bij sommige arresten
van het Gerecht bestaat geen Nederlandse versie; dan krijgt u de Engelse, en de connector zegt dat.

**Feedback.** Meld fouten en suggesties via de
[issues van de repository](https://github.com/jefseghers-del/rechtspraak-mcp/issues), liefst met de vraag die
u stelde en, bij een fout, het logbestand (Instellingen → Extensies → View logs).
