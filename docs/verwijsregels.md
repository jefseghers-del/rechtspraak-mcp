---
title: "Verwijsregels — voetnoot en bibliografie (verwijzing)"
type: methodologie
tags: [verwijsregels, voetnoten, VENA, citaten]
updated: 2026-09-09
---

# Verwijsregels — voetnoot en bibliografie

> **Samenvatting.** De uitgewerkte verwijsregels van de auteur worden buiten deze repository onderhouden. Hieronder de kernpunten waarop de verwijzingsvoorstellen van deze connector steunen. Bij twijfel geldt [vena.be](https://vena.be).

Basis: **VENA-verwijsregels** ([vena.be](https://vena.be)), voetnootvorm. VENA is géén één-op-één-voortzetting van de oude V&A-gids; er zijn uitdrukkelijke breukpunten. Kernpunten:

- **Auteur**: familienaam vóór de initialen, in hoofdletters of kleinkapitaal — `SWINNEN K.`; zelfde vorm in voetnoot en bibliografie, ook bij `noot`/`concl.` (`noot DECROES A.`). Meerdere auteurs verbinden met `en`, niet `&`; meer dan drie: eerste drie + `e.a.`
- **Pagina**: enkel het getal, geen `p.` of `blz.`; een specifieke pagina binnen een reeks als `(beginpagina) geciteerde pagina`, bv. `(963) 970`. Aflevering na de jaargang met slash (`TBP 2014/8`), niet `afl.`
- **Rechtspraak — volgorde**: instantie (afgekort) + datum (maand voluit) + rolnummer/`nr.` + eventueel ECLI + partijnaam tussen enkele aanhalingstekens + vindplaats + eventueel `concl.`/`noot`. Voorbeeld: `RvS (7de k.) 20 maart 2014, nr. 226.824, 'L.S. e.a.', TBP 2014/8, 528.` Hof van beroep: `HvB Gent`, niet de kale plaatsnaam.
- **RvVb-nummer** steeds mét prefix: `RvVb-A-XXYY-NNNN` (streepjes, vanaf ca. 2018) of `RvVb/A/XXYY/NNNN` (slashes, ouder). Niet `nr. A-XXYY-NNNN` zonder prefix.
- **Wetgeving**: `artikel` voluit schrijven (huisregel), niet `art.`; norm + datum (maand voluit) + opschrift + vindplaats (`BS`).
- **Titels**: bijdrage/artikel tussen **enkele** aanhalingstekens, boek/tijdschrift cursief. Boeken zonder plaats van uitgave.
- **Elke voetnoot eindigt met een punt.**

Voor de uitgewerkte regels per brontype (rechtsleer, parlementaire stukken, herhalingsverwijzingen, citaten): [vena.be](https://vena.be).

## Toepassing in deze MCP-server

`rechtspraak_mcp/verwijzing.py` bouwt per treffer een **voorstel** van VENA-voetnootverwijzing (veld `verwijzing` in het `Treffer`-schema), uitsluitend uit de velden die de bron effectief teruggaf (anti-hallucinatie): instantie afgekort, datum (maand voluit), `nr.` met volledig arrestnummer (RvVb steeds mét prefix), eventueel ECLI, en de bron-URL als vindplaats. Ontbrekende elementen worden weggelaten, nooit aangevuld; de gebruiker verifieert de verwijzing vóór gebruik in een processtuk. Het voorstel eindigt bewust **zonder** slotpunt en zonder partijnaam of tijdschriftvindplaats (de bron levert die niet); wie het in een voetnoot overneemt, vult aan en sluit af met een punt. Bekende beperking: bij RvS-treffers via Juportal levert de bron het rolnummer (`A. 200367/X-14733`) als `rolnummer`; het arrestnummer staat in titel/snippet en hoort in de citatie (`nr. 216.494`).
