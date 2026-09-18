---
title: "Verwijsregels — VENA, zoals de connector ze toepast"
type: methodologie
tags: [verwijsregels, voetnoten, VENA, citaten]
updated: 2026-09-18
---

# Verwijsregels — VENA, zoals de connector ze toepast

De connector stelt bij elke treffer een voetnoot voor volgens de **VENA-verwijsregels**
([vena.be](https://vena.be)). Deze samenvatting geeft de regels die de code toepast, nagekeken op vena.be op
18 september 2026. Bij twijfel geldt vena.be.

## Algemeen

- Alle onderdelen worden gescheiden door een komma; **elke voetnoot eindigt met een punt** (algemene regel 5).
- Datums met de maand voluit: `2 maart 2021`.
- Een URL wordt alleen vermeld als het om een minder bekende vindplaats gaat (regel 10). De connector zet de
  URL daarom alleen in de verwijzing als er geen ECLI (rechtspraak) of ELI (wetgeving) is. De bron-URL blijft
  altijd beschikbaar in het veld `url`, om te controleren.

## Rechtspraak (RS1)

`Instantie (afgekort) + datum, nummer, ECLI, 'partijen of benaming', tijdschrift jaargang, pagina, URL, noot.`

- Afkortingen volgens de VENA-lijst: `Cass.`, `GwH`, `RvS`, `RvVb`, `HHC`, `R.Stvb.`, `R.Verkb.`, `HvB Gent`,
  `HvJ`, `Ger.EU`, `Ger.Ambt.EU`, `EHRM`.
- Het nummer staat er zonder "AR" en zonder "nr." ("nr." mag facultatief): `Cass. 2 maart 2021, P.20.1057.N,
  ECLI:BE:CASS:2021:ARR.20210302.2N.22.`; `RvS 26 maart 2024, 259.259, ECLI:BE:RVSCE:2024:ARR.259.259.`
- **RvVb-nummers** behouden hun prefix: `RvVb-A-2425-0744`.
- **Wat de connector niet kan invullen:** de kamer, de partijnaam of benaming van de zaak ("'Cassis de
  Dijon'"), de tijdschriftvindplaats en een noot of conclusie. Die vult u zelf aan.
- Bij RvS-arresten via Juportal neemt de connector het arrestnummer uit de ECLI
  (`ECLI:BE:RVSCE:2016:ARR.233.796` → `233.796`), niet het rolnummer.

## Conclusies van het openbaar ministerie of de advocaat-generaal (RS2)

`FAMILIENAAM I., 'Conclusie bij Cass. <datum>, <nummer>', tijdschrift, ECLI van de conclusie.`

Voorbeeld op vena.be: `LECLERCQ J.F., 'Conclusie bij Cass. 6 juni 2014, C.10.0482.F',
ECLI:BE:CASS:2014:CONC.20140606.4.` De bron levert de naam van de magistraat niet mee; de connector zet
daarom `[FAMILIENAAM I.]` als invulveld. Een conclusie is geen uitspraak van het Hof: de connector geeft er
geen beoordelend deel voor.

## Belgische normen (WG2)

`Aard (afgekort, met orgaan) + datum + rest van het opschrift, BS <datum>, ELI.`

- Afkortingen volgens de VENA-lijst: `Wet` (met hoofdletter), `Decr.Vl.`, `Decr.`, `Ord.Br.`, `KB`, `MB`,
  `B.Vl.Reg.`, `B.`, `Omz.`, `Gw.`
- Voorbeeld op vena.be: `Decr.Vl. 4 april 2014 betreffende de organisatie en de rechtspleging van sommige
  Vlaamse bestuursrechtscolleges, BS 1 oktober 2014, <ELI>.`
- Een decreet uit de Vlaamse Codex is een Vlaams decreet (`Decr.Vl.`); bij Justel is het orgaan niet af te
  leiden en blijft het `Decr.`
- Het ELI komt erbij als de bron het geeft (Justel); de Vlaamse Codex geeft geen ELI.

## Europese normen (WG3)

`Opschrift (aard voluit, met nummer, orgaan en datum), Pb.L. <datum>, <pagina>, ELI.`

- De aard wordt **niet** afgekort: `Richtlijn 2011/92/EU van het Europees Parlement en de Raad van 13 december
  2011 betreffende …`
- Vindplaats `Pb.L.` of `Pb.C.` met de datum van het Publicatieblad en de beginpagina:
  `Pb.L. 28 januari 2012, 1`. Sinds oktober 2023 verschijnt elke akte afzonderlijk, zonder paginanummer:
  `Pb.L. 29 juli 2024`.
- Het staartje "Voor de EER relevante tekst" hoort niet bij het opschrift en wordt weggelaten.

## Artikels

Een verwijzing naar een artikel (`Art. 6, lid 3 Habitatrichtlijn.`, WG1) maakt de connector niet zelf; vraag
Claude om het artikelnummer vooraan toe te voegen.
