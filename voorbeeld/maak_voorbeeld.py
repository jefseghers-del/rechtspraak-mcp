# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Maak het voorbeeld uit de handleiding opnieuw: wat de connector teruggeeft op de voorbeeldvraag.

De voorbeeldvraag (HANDLEIDING.md, § 3, eerste vraag):

    Zoek het arrest van het Hof van Justitie met ECLI:EU:C:2004:482 op, geef de
    VENA-verwijzing en citeer letterlijk wat het Hof voor recht verklaart. Geef ook de
    vindplaats van de Habitatrichtlijn (Richtlijn 92/43/EEG).

Op die vraag roept Claude drie tools aan. Dit script doet exact dezelfde drie oproepen, met
dezelfde parameters en de standaardinstellingen van de bundel, en schrijft de antwoorden van
de connector weg als Markdown. Het is dus de grondstof waarop Claude zijn antwoord bouwt, niet
het antwoord van Claude zelf.

Gebruik (vanuit de repository, met internet):
    python voorbeeld/maak_voorbeeld.py voorbeeld/waddenzee-habitatrichtlijn.md
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

# Standaardinstellingen van de bundel: open bronnen aan, robots-beperkte bronnen uit.
os.environ["RECHTSPRAAK_MCP_STA_FETCH"] = "hvj,ehrm,eurlex,codex"

from rechtspraak_mcp import DISCLAIMER, __version__  # noqa: E402
from rechtspraak_mcp.server import haal_uitspraak, zoek_op_identifier, zoek_wetgeving  # noqa: E402

VRAAG = (
    "Zoek het arrest van het Hof van Justitie met ECLI:EU:C:2004:482 op, geef de "
    "VENA-verwijzing en citeer letterlijk wat het Hof voor recht verklaart. Geef ook de "
    "vindplaats van de Habitatrichtlijn (Richtlijn 92/43/EEG)."
)
ECLI = "ECLI:EU:C:2004:482"
NORM = "Richtlijn 92/43/EEG"


def maak() -> str:
    tijdstip = datetime.now().astimezone().strftime("%-d %B %Y, %H:%M").replace(
        "September", "september"
    )
    r1 = zoek_op_identifier(ECLI)
    if not r1.treffers:
        raise SystemExit(f"Geen treffer voor {ECLI}: {r1.melding}")
    t = r1.treffers[0]
    u = haal_uitspraak(t.url, t.bron)
    if u is None or not u.beoordeling:
        raise SystemExit("De uitspraak kon niet worden opgehaald of gesegmenteerd.")
    dictum_start = u.beoordeling.find("verklaart voor recht")
    dictum_start = u.beoordeling.rfind("\n", 0, dictum_start) + 1
    dictum = u.beoordeling[dictum_start:].strip()
    r3 = zoek_wetgeving(NORM)
    if not r3.normen:
        raise SystemExit(f"Geen norm voor {NORM}: {r3.melding}")
    n = r3.normen[0]

    regels = [
        "# Voorbeeld: wat BE-rechtspraak teruggeeft op één vraag",
        "",
        f"> {DISCLAIMER}",
        "",
        f"Opgevraagd op {tijdstip}, met BE-rechtspraak {__version__} en de standaardinstellingen van de bundel.",
        "",
        "## De vraag",
        "",
        f"> {VRAAG}",
        "",
        "Op die vraag roept Claude drie tools van de connector aan. Hieronder staat letterlijk wat",
        "de connector teruggeeft; Claude bouwt daar zijn antwoord op. Controleer altijd via de",
        "bron-URL.",
        "",
        f"## 1. `zoek_op_identifier(\"{ECLI}\")`",
        "",
        "| Veld | Waarde |",
        "|---|---|",
        f"| Instantie | {t.instantie} |",
        f"| Titel | {t.titel} |",
        f"| Datum | {t.datum:%-d-%-m-%Y} |" if t.datum else "| Datum | — |",
        f"| Zaaknummer | {t.rolnummer} |",
        f"| ECLI | {t.ecli} |",
        f"| Bron-URL | {t.url} |",
        "",
        "**Voorstel van verwijzing volgens vena.be** (partijnaam en tijdschriftvindplaats levert de",
        "bron niet; vul die zelf aan):",
        "",
        f"    {t.verwijzing}",
        "",
        f"## 2. `haal_uitspraak(\"{t.url}\", \"{t.bron}\")`",
        "",
        f"Integrale tekst: {len(u.tekst):,} tekens (niet opgenomen). Beoordelend deel: "
        f"{len(u.beoordeling):,} tekens.".replace(",", "."),
        "",
        f"**Afbakening van het beoordelende deel** (veld `segmentatie`): {u.segmentatie}",
        "",
        "**Wat het Hof voor recht verklaart** (letterlijk, slot van het veld `beoordeling`):",
        "",
    ]
    regels += [f"> {r}" if r else ">" for r in dictum.splitlines()]
    regels += [
        "",
        f"## 3. `zoek_wetgeving(\"{NORM}\")`",
        "",
        "| Veld | Waarde |",
        "|---|---|",
        f"| Opschrift | {n.opschrift} |",
        f"| CELEX | {n.celex} |",
        f"| ELI | {n.eli} |",
        f"| Vindplaats | {n.vindplaats} |",
        f"| Bron-URL | {n.url} |",
        "",
        "**Voorstel van verwijzing volgens vena.be:**",
        "",
        f"    {n.verwijzing}",
        "",
        "---",
        "",
        "Gemaakt met `voorbeeld/maak_voorbeeld.py`. Geen juridisch advies; de gebruiker blijft zelf",
        "verantwoordelijk voor controle en gebruik.",
        "",
    ]
    return "\n".join(regels)


if __name__ == "__main__":
    doel = sys.argv[1] if len(sys.argv) > 1 else "voorbeeld/waddenzee-habitatrichtlijn.md"
    tekst = maak()
    with open(doel, "w", encoding="utf-8") as f:
        f.write(tekst)
    print(doel)
