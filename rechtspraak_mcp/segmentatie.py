# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Segmentatie van uitspraakteksten: isoleer het beoordelende deel van het rechtscollege.

Kern-eis (docs/spec-gerichte-zoekfunctie.md, § 1): alleen de EIGEN BEOORDELING van het
rechtscollege is bruikbaar om stellingen te onderbouwen; de weergave van partijen-
standpunten in hetzelfde arrest is gevaarlijk citeermateriaal. Deze module isoleert dat
beoordelende deel — LETTERLIJK, nooit geparafraseerd — of geeft eerlijk ``None`` terug
wanneer de structuur niet herkenbaar is (geen-gok-regel). Het dictum ("Beslissing",
"OM DIE REDENEN", "Dictum", "FOR THESE REASONS") hoort bij het oordeel en wordt
meegenomen. Pure module: geen I/O, geen netwerk.

IJKING OP ECHTE UITSPRAKEN (2026-08-10; fixtures in tests/fixtures/segmentatie_*.txt):

* **Grondwettelijk Hof** — geijkt op arrest nr. 100/2021 (ECLI:BE:GHCC:2021:ARR.100,
  via de Juportal-content-pagina). LET OP: Juportal levert de GwH-tekst als ÉÉN regel
  zonder regelstructuur; kop-op-eigen-regel-herkenning is daar onmogelijk. Effectief
  aangetroffen scharnieren, inline: "III. In rechte", dan de scheidingsmarkering "-A-"
  (A-paragrafen: standpunten, "A.1.1." enz.), dan "-B-" (B-paragrafen: het oordeel,
  "B.1.1." enz.), dan "Om die redenen, het Hof zegt voor recht :" (dictum). De
  strategie eist de volgorde "In rechte" → "-A-" → "-B-" plus B-nummering ná "-B-", en
  neemt alles vanaf "-B-" (dictum inbegrepen). In een regelgebonden GwH-tekst (bv. uit
  een PDF, "- B -" met spaties) matcht dezelfde markering [TE VERIFIËREN — geen
  PDF-variant geijkt].

* **Hof van Cassatie** — geijkt op ECLI:BE:CASS:2020:ARR.20201030.1N.4 (C.20.0061.N)
  en ECLI:BE:CASS:2013:ARR.20130611.12 (P.12.1389.N), beide via Juportal (tekst met
  één regel per alinea). Effectief aangetroffen koppen: "I. RECHTSPLEGING VOOR HET
  HOF", ("II. CASSATIEMIDDELEN" — alleen in 2020), "II."/"III. BESLISSING VAN HET
  HOF", daaronder "Beoordeling", per middel "Eerste middel" enz., en "Dictum". De
  strategie snijdt vanaf de kop "BESLISSING VAN HET HOF" tot het einde. KANTTEKENING
  (2013 geijkt): binnen de beslissing vat het Hof per middel eerst het middel van de
  eiser samen ("Het middel voert schending aan van ..."); dat blijft dus in het
  geselecteerde deel staan — fijner scheiden bleek op de echte teksten niet
  betrouwbaar. De titelcase-variant "Beslissing van het Hof" is [TE VERIFIËREN].

* **RvVb / DBRC** — geijkt op RvVb-UDN-2526-0608 (arrest 23 maart 2026, PDF-tekst via
  pdfplumber). Effectief aangetroffen koppen, elk op een eigen regel: "I. Voorwerp van
  het beroep", "II. Rechtspleging", "III. Feiten", "IV. Onderzoek van de vordering",
  "A. Uiterst dringende noodzakelijkheid", "Standpunt van de partijen", "Beoordeling
  door de Raad", "B. Ernstige middelen", "V. Beslissing". Strategie: blokken vanaf
  elke "Beoordeling(...)"-kop tot de volgende standpunt-/beslissingskop, plus het
  dictum vanaf de "Beslissing"-kop. Tussenliggende sectiekoppen zónder standpuntkop
  (zoals "B. Ernstige middelen" met alleen een Raad-vaststelling) blijven binnen het
  blok — dat bleek op de echte tekst het juiste gedrag. Paginavoetregels ("RvVb - 6")
  blijven in de letterlijke tekst staan.

* **Raad van State** — geijkt op arrest nr. 226.824 van 20 maart 2014 (Nederlands, via
  arr.php/pdfplumber): "I. Voorwerp van het beroep", "II. Verloop van de
  rechtspleging", "III. Feiten", "IV. Ontvankelijkheid van het beroep" (met subkop
  "Beoordeling"), "V. Onderzoek van het enig middel" ("Standpunt van de partijen" →
  "Beoordeling"), "BESLISSING" (dictum). Zelfde strategie als RvVb. NIET BETROUWBAAR
  gebleken: arrest nr. 250.123 (16 maart 2021) is FRANS ("Objet du recours", "PAR CES
  MOTIFS") en heeft géén standpunt/beoordeling-splitsing — daarvoor is het eerlijke
  resultaat ``None``; Franse RvS-koppen zijn niet geijkt [TE VERIFIËREN].

* **EHRM** — geijkt op Lambert e.a. t. Frankrijk (HUDOC 001-155352, Engelse
  bodytekst; regelgebonden, maar rubrieknummers als "I."/"A."/"2." en
  paragraafnummers als "89." staan elk op een EIGEN regel, los van de titel).
  Effectief aangetroffen: "THE FACTS", "THE LAW", subkoppen "The parties'
  submissions", "The submissions of the parties and the third-party interveners",
  "The Court's assessment" (3×), dictum "FOR THESE REASONS, THE COURT", slotregel
  "Done in English and in French, ...", daarna separate opinions ("JOINT PARTLY
  DISSENTING OPINION OF ..."). Strategie (betrouwbaar gebleken): de "The Court's
  assessment"-blokken plus het dictum; separate opinions en submissions worden
  uitgesloten. Terugval wanneer die subkoppen ontbreken: "THE LAW" tot het einde van
  het dictum, met een uitdrukkelijke waarschuwing dat daar ook partijenstandpunten in
  zitten. Franse HUDOC-teksten zijn niet geijkt [TE VERIFIËREN].

* **HvJ / Gerecht (EUR-Lex)** — geijkt op twee formaten. OUD (arrest 20 februari
  1979, Cassis de Dijon, ECLI:EU:C:1979:42, NL): vaste rubrieken elk op een eigen
  regel — "Trefwoorden", "Samenvatting", "Partijen", "Onderwerp", "Overwegingen van
  het arrest", "Beslissing inzake de kosten", "Dictum"; bovenaan staat dezelfde lijst
  nogmaals als inhoudsopgave, dus de LAATSTE "Overwegingen van het arrest" telt.
  KANTTEKENING: binnen de overwegingen vat het Hof partijenstandpunten samen zonder
  aparte kop — fijner scheiden is in dit formaat niet mogelijk. RECENT (beschikking
  Gerecht 8 mei 2019, Carvalho, T-330/18, EN): koppen zonder nummering op een eigen
  regel — "Arguments of the parties" vs. "Findings of the Court" (per onderdeel),
  "Costs", dictum "On those grounds, ... hereby orders:". Strategie recent: de
  "Findings"-blokken plus kosten en dictum. De Nederlandse recente varianten
  ("Beoordeling door het Hof", "Argumenten van partijen", "Kosten", "Om die redenen")
  zijn NIET live geijkt (EUR-Lex gaf tijdens de ijking geen 200 op het NL-arrest)
  [TE VERIFIËREN] — ze zijn wel opgenomen omdat ze exact dezelfde plaats innemen.

GEEN-GOK-REGEL: zijn de scharnierkoppen niet herkenbaar, dan is ``beoordeling`` None
met een eerlijke melding. Een halve match (wel een beginkop, geen dictumkop) mag, mits
de melding dat zegt. Kop-herkenning is regelgebonden (de kop staat op een eigen regel,
eventueel met nummering ervoor) behalve bij het GwH, waar Juportal geen regels levert.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Segmentatie", "segmenteer"]


@dataclass(frozen=True)
class Segmentatie:
    """Resultaat van :func:`segmenteer`.

    ``beoordeling`` is de LETTERLIJKE tekst van het beoordelende deel (nooit een
    parafrase), of None wanneer de structuur niet herkend is. ``methode`` benoemt de
    gebruikte strategie; ``melding`` zegt in één zin wat er herkend is of waarom het
    niet lukte.
    """

    beoordeling: str | None
    methode: str | None
    melding: str


# ----------------------------------------------------------------------------------
# Kop-patronen (regelgebonden: het hele regel-item is de kop, evt. met nummering)
# ----------------------------------------------------------------------------------
#: Nummering vóór een kop: Romeins ("IV."), cijfer ("1.") of één hoofdletter ("B.").
_NUMMERING = r"(?:[IVXLC]{1,6}|\d{1,2}|[A-Z])[.\)]"

#: "Beoordeling"-kop (RvVb/RvS): eigen regel, hoofdletter-start (een afgebroken
#: PDF-regel die toevallig met "beoordeling" begint, matcht dus niet), optionele
#: korte staart zonder zinseinde ("door de Raad", "van het eerste middel").
_BEOORDELING_KOP_RE = re.compile(
    rf"^\s*(?:{_NUMMERING}\s+)?(?:Beoordeling|BEOORDELING)(?:\s+[^.\n]{{0,60}})?\s*$"
)

#: Standpunt-achtige koppen (uitgefilterd deel). Live geijkt: "Standpunt van de
#: partijen"; de overige werkwoorden zijn defensieve varianten [TE VERIFIËREN].
_STANDPUNT_KOP_RE = re.compile(
    rf"^\s*(?:{_NUMMERING}\s+)?"
    r"(?:Standpunt|STANDPUNT|Uiteenzetting|UITEENZETTING|Antwoord|ANTWOORD|"
    r"Repliek|REPLIEK|Wederantwoord|WEDERANTWOORD)\b[^.\n]{0,60}$"
)

#: Dictumkop RvVb/RvS: "V. Beslissing" (RvVb) en "BESLISSING" (RvS), beide geijkt.
_BESLISSING_KOP_RE = re.compile(
    rf"^\s*(?:{_NUMMERING}\s+)?(?:Beslissing|BESLISSING)\s*$"
)

#: Cassatie-scharnier: "II./III. BESLISSING VAN HET HOF" (geijkt, hoofdletters);
#: titelcase-variant defensief [TE VERIFIËREN].
_CASSATIE_KOP_RE = re.compile(
    r"^\s*(?:[IVX]{1,4}\.\s*)?(?:BESLISSING VAN HET HOF|Beslissing van het Hof)\s*$"
)

# GwH (Juportal levert één regel zonder regelstructuur): volgorde-markeringen.
_GWH_IN_RECHTE_RE = re.compile(r"\bIn rechte\b")
_GWH_A_RE = re.compile(r"(?:^|\s)[-–]\s?A\s?[-–](?=\s|$)")
_GWH_B_RE = re.compile(r"(?:^|\s)[-–]\s?B\s?[-–](?=\s|$)")
_GWH_B_NUMMER_RE = re.compile(r"\bB\.\d")

# EHRM (HUDOC-bodytekst, Engels; geijkt op Lambert).
_EHRM_ASSESSMENT_RE = re.compile(r"^\s*(?:\d{1,2}\.\s*)?The Court[’']s assessment\s*$")
_EHRM_SUBMISSIONS_RE = re.compile(
    r"^\s*(?:\d{1,2}\.\s*)?The (?:parties[’'] submissions|submissions of the parties)"
    r"\b[^.\n]{0,80}$"
)
_EHRM_REASONS_RE = re.compile(r"^\s*FOR THESE REASONS\b")
_EHRM_DONE_RE = re.compile(r"^\s*Done in (?:English|French)\b")

# HvJ/Gerecht — oud EUR-Lex-formaat (geijkt op Cassis 1979, NL).
_HVJ_OVERWEGINGEN_KOP = "overwegingen van het arrest"
# HvJ/Gerecht — recent formaat (geijkt op Carvalho 2019, EN; NL-varianten
# [TE VERIFIËREN]).
_HVJ_FINDINGS_RE = re.compile(
    r"^\s*(?:Findings of the Court|The Court[’']s (?:findings|reply)|"
    r"Beoordeling door het Hof|Beoordeling door het Gerecht)\s*$"
)
_HVJ_ARGUMENTEN_RE = re.compile(
    r"^\s*(?:Arguments of the parties|Argumenten van (?:de )?partijen)\s*$"
)
_HVJ_KOSTEN_RE = re.compile(r"^\s*(?:Costs|Kosten)\s*$")
_HVJ_DICTUM_RE = re.compile(r"^\s*(?:On those grounds\b|Om die redenen\b)[^.\n]{0,80}$")
# HvJ — prejudiciële arresten in het Nederlands, zoals CELLAR ze levert (geijkt op
# Waddenzee, C-127/02, 2004, en Inter-Environnement Wallonie, C-411/17, 2019): het oordeel
# van het Hof staat onder "De prejudiciële vragen" of "III. Beantwoording van de
# prejudiciële vragen", gevolgd door kosten en dictum ("... verklaart voor recht:").
_HVJ_VRAGEN_RE = re.compile(
    r"^\s*(?:[IVX]+\.\s+)?(?:Beantwoording van de (?:prejudiciële )?vra(?:ag|gen)|"
    r"De prejudiciële vra(?:ag|gen))\s*$",
    re.IGNORECASE,
)
_HVJ_ONDERTEKENING_RE = re.compile(r"^\s*(?:Ondertekening(?:en)?|Signatures?)\s*$", re.IGNORECASE)


def _is_caps_kop(regel: str) -> bool:
    """Regel die volledig in hoofdletters staat (EHRM-rubriekkop), met >= 2 letters."""
    kaal = regel.strip()
    letters = [c for c in kaal if c.isalpha()]
    return len(letters) >= 2 and kaal == kaal.upper()


# ----------------------------------------------------------------------------------
# Strategieën — elk puur: tekst in, Segmentatie of None (structuur niet herkend) uit
# ----------------------------------------------------------------------------------
def _segmenteer_gwh(tekst: str) -> Segmentatie | None:
    """GwH: alles vanaf de '-B-'-markering (B-paragrafen + dictum), zie moduledocstring."""
    m_rechte = _GWH_IN_RECHTE_RE.search(tekst)
    if m_rechte is None:
        return None
    m_a = _GWH_A_RE.search(tekst, m_rechte.end())
    if m_a is None:
        return None
    m_b = _GWH_B_RE.search(tekst, m_a.end())
    if m_b is None:
        return None
    beoordeling = tekst[m_b.end():].strip()
    if not beoordeling or not _GWH_B_NUMMER_RE.search(beoordeling):
        return None
    melding = (
        "B-paragrafen herkend (markering '-B-' na 'In rechte'), inclusief het dictum; "
        "de A-paragrafen met de standpunten van de partijen zijn weggelaten."
    )
    return Segmentatie(beoordeling=beoordeling, methode="gwh-b-paragrafen", melding=melding)


def _segmenteer_cassatie(tekst: str) -> Segmentatie | None:
    """Cassatie: vanaf de kop 'BESLISSING VAN HET HOF' tot het einde (met dictum)."""
    regels = tekst.splitlines()
    for i, regel in enumerate(regels):
        if _CASSATIE_KOP_RE.match(regel):
            beoordeling = "\n".join(regels[i:]).strip()
            melding = (
                f"tekst vanaf de kop '{regel.strip()}' tot het einde (dictum inbegrepen); "
                "let op: binnen dit deel vat het Hof per middel eerst het cassatiemiddel "
                "van de eiser kort samen."
            )
            return Segmentatie(
                beoordeling=beoordeling, methode="cassatie-beslissing-kop", melding=melding
            )
    return None


def _segmenteer_beoordeling_koppen(tekst: str) -> Segmentatie | None:
    """RvVb/DBRC en RvS: 'Beoordeling'-blokken per middel plus het dictum.

    Een blok loopt van een 'Beoordeling(...)'-kop tot de volgende standpunt-achtige
    kop, de volgende 'Beoordeling'-kop of de dictumkop ('Beslissing'/'BESLISSING');
    het dictum loopt tot het einde. Blokken worden aaneengezet met een lege regel;
    elke oorspronkelijke kopregel blijft als eerste regel van haar blok staan.
    """
    regels = tekst.splitlines()
    beoordeling_starts = [i for i, r in enumerate(regels) if _BEOORDELING_KOP_RE.match(r)]
    beslissing_starts = [i for i, r in enumerate(regels) if _BESLISSING_KOP_RE.match(r)]
    if not beoordeling_starts and not beslissing_starts:
        return None

    dictum_start = beslissing_starts[-1] if beslissing_starts else None

    def _blok_einde(start: int) -> int:
        for j in range(start + 1, len(regels)):
            if (
                _STANDPUNT_KOP_RE.match(regels[j])
                or _BEOORDELING_KOP_RE.match(regels[j])
                or _BESLISSING_KOP_RE.match(regels[j])
            ):
                return j
        return len(regels)

    blokken: list[str] = []
    koppen: list[str] = []
    for start in beoordeling_starts:
        if dictum_start is not None and start >= dictum_start:
            continue  # valt al binnen het dictum
        einde = _blok_einde(start)
        blok = "\n".join(regels[start:einde]).strip()
        if blok:
            blokken.append(blok)
            koppen.append(regels[start].strip())
    if dictum_start is not None:
        blok = "\n".join(regels[dictum_start:]).strip()
        if blok:
            blokken.append(blok)
    if not blokken:
        return None

    beoordeling = "\n\n".join(blokken)
    kop_opsomming = ", ".join(f"'{k}'" for k in koppen)
    if koppen and dictum_start is not None:
        melding = (
            f"{len(koppen)} beoordelingsblok(ken) ({kop_opsomming}) plus het dictum "
            f"vanaf '{regels[dictum_start].strip()}' geselecteerd; standpunten van de "
            "partijen, feiten en rechtspleging zijn weggelaten."
        )
    elif koppen:
        melding = (
            f"{len(koppen)} beoordelingsblok(ken) ({kop_opsomming}) geselecteerd; geen "
            "afzonderlijke dictumkop ('Beslissing') aangetroffen — controleer het slot "
            "van de tekst zelf."
        )
    else:
        melding = (
            f"alleen het dictum vanaf '{regels[dictum_start].strip()}' herkend; "
            "'Beoordeling'-koppen ontbreken — raadpleeg de integrale tekst voor de "
            "motivering."
        )
    return Segmentatie(
        beoordeling=beoordeling, methode="beoordeling-koppen", melding=melding
    )


def _segmenteer_ehrm(tekst: str) -> Segmentatie | None:
    """EHRM: 'The Court's assessment'-blokken plus dictum; terugval op 'THE LAW'."""
    regels = tekst.splitlines()
    assessment_starts = [i for i, r in enumerate(regels) if _EHRM_ASSESSMENT_RE.match(r)]
    reasons_starts = [i for i, r in enumerate(regels) if _EHRM_REASONS_RE.match(r)]
    law_starts = [i for i, r in enumerate(regels) if r.strip() == "THE LAW"]

    def _dictum_einde(start: int) -> int:
        """Einde van het dictum: de 'Done in ...'-slotregel (inclusief), anders de
        eerstvolgende opinion-kop, anders het einde van de tekst."""
        for j in range(start + 1, len(regels)):
            if _EHRM_DONE_RE.match(regels[j]):
                return j + 1
            if _is_caps_kop(regels[j]) and "OPINION" in regels[j].upper():
                return j
        return len(regels)

    def _blok_einde(start: int) -> int:
        for j in range(start + 1, len(regels)):
            regel = regels[j]
            if (
                _EHRM_SUBMISSIONS_RE.match(regel)
                or _EHRM_ASSESSMENT_RE.match(regel)
                or _EHRM_REASONS_RE.match(regel)
                or _is_caps_kop(regel)
            ):
                return j
        return len(regels)

    if assessment_starts:
        blokken = []
        for start in assessment_starts:
            blok = "\n".join(regels[start:_blok_einde(start)]).strip()
            if blok:
                blokken.append(blok)
        if reasons_starts:
            start = reasons_starts[0]
            blokken.append("\n".join(regels[start:_dictum_einde(start)]).strip())
        if not blokken:
            return None
        melding = (
            f"{len(assessment_starts)} 'The Court's assessment'-blok(ken)"
            + (" plus het dictum vanaf 'FOR THESE REASONS'" if reasons_starts else "")
            + " geselecteerd; partijenstandpunten en separate opinions zijn weggelaten"
            + ("" if reasons_starts else " (geen dictumkop 'FOR THESE REASONS' gevonden)")
            + "."
        )
        return Segmentatie(
            beoordeling="\n\n".join(blokken),
            methode="ehrm-assessment-koppen",
            melding=melding,
        )

    if law_starts:
        start = law_starts[0]
        einde = _dictum_einde(reasons_starts[0]) if reasons_starts else len(regels)
        beoordeling = "\n".join(regels[start:einde]).strip()
        if not beoordeling:
            return None
        melding = (
            "vanaf 'THE LAW' tot het einde van het dictum; LET OP: 'The Court's "
            "assessment'-subkoppen ontbreken, dus dit deel bevat óók de weergave van de "
            "partijenstandpunten — zelf controleren vóór citeren."
        )
        return Segmentatie(beoordeling=beoordeling, methode="ehrm-the-law", melding=melding)
    return None


def _segmenteer_hvj_recent(tekst: str) -> Segmentatie | None:
    """HvJ/Gerecht recent formaat: 'Findings of the Court'-blokken plus kosten/dictum."""
    regels = tekst.splitlines()
    findings_starts = [i for i, r in enumerate(regels) if _HVJ_FINDINGS_RE.match(r)]
    if not findings_starts:
        return None
    kosten_starts = [i for i, r in enumerate(regels) if _HVJ_KOSTEN_RE.match(r)]
    dictum_starts = [i for i, r in enumerate(regels) if _HVJ_DICTUM_RE.match(r)]
    staart_start = kosten_starts[-1] if kosten_starts else (
        dictum_starts[-1] if dictum_starts else None
    )

    def _blok_einde(start: int) -> int:
        for j in range(start + 1, len(regels)):
            regel = regels[j]
            if (
                _HVJ_ARGUMENTEN_RE.match(regel)
                or _HVJ_FINDINGS_RE.match(regel)
                or _HVJ_KOSTEN_RE.match(regel)
                or _HVJ_DICTUM_RE.match(regel)
            ):
                return j
        return len(regels)

    blokken = []
    for start in findings_starts:
        if staart_start is not None and start >= staart_start:
            continue
        blok = "\n".join(regels[start:_blok_einde(start)]).strip()
        if blok:
            blokken.append(blok)
    if staart_start is not None:
        blokken.append("\n".join(regels[staart_start:]).strip())
    if not blokken:
        return None
    melding = (
        f"{len(findings_starts)} beoordelingsblok(ken) ('Findings of the Court'/"
        "'Beoordeling')"
        + (
            f" plus het slot vanaf '{regels[staart_start].strip()}' (kosten en dictum)"
            if staart_start is not None
            else ""
        )
        + " geselecteerd; de argumentenrubrieken van partijen zijn weggelaten."
    )
    return Segmentatie(
        beoordeling="\n\n".join(blokken), methode="hvj-recente-koppen", melding=melding
    )


def _segmenteer_hvj_vragen(tekst: str) -> Segmentatie | None:
    """HvJ prejudicieel arrest (NL): vanaf 'Beantwoording van de prejudiciële vragen' tot de ondertekening."""
    regels = tekst.splitlines()
    starts = [i for i, r in enumerate(regels) if _HVJ_VRAGEN_RE.match(r)]
    if not starts:
        return None
    start = starts[-1]  # een eventuele inhoudsopgave bovenaan telt niet
    einde = next(
        (j for j in range(start + 1, len(regels)) if _HVJ_ONDERTEKENING_RE.match(regels[j])),
        len(regels),
    )
    beoordeling = "\n".join(regels[start:einde]).strip()
    if "\n" not in beoordeling:
        return None
    melding = (
        f"rubriek '{regels[start].strip()}' tot en met kosten en dictum geselecteerd; het "
        "juridisch kader en het hoofdgeding zijn weggelaten. Let op: het Hof vat binnen "
        "de beantwoording soms standpunten van partijen of van de Commissie samen — zelf "
        "controleren vóór citeren."
    )
    return Segmentatie(beoordeling=beoordeling, methode="hvj-prejudiciele-vragen", melding=melding)


def _segmenteer_hvj_oud(tekst: str) -> Segmentatie | None:
    """HvJ oud EUR-Lex-formaat: vanaf de laatste rubriek 'Overwegingen van het arrest'."""
    regels = tekst.splitlines()
    starts = [
        i for i, r in enumerate(regels) if r.strip().lower() == _HVJ_OVERWEGINGEN_KOP
    ]
    if not starts:
        return None
    start = starts[-1]  # de eerste vermelding is de inhoudsopgave bovenaan
    if start + 1 >= len(regels):
        return None
    staart = regels[start:]
    while staart and staart[-1].strip() in ("", "Top"):  # EUR-Lex-navigatieregel
        staart = staart[:-1]
    beoordeling = "\n".join(staart).strip()
    if not beoordeling:
        return None
    melding = (
        "rubriek 'Overwegingen van het arrest' tot en met het dictum geselecteerd; let "
        "op: in dit oude arrestformaat vat het Hof partijenstandpunten binnen de "
        "overwegingen samen zonder aparte kop — zelf controleren vóór citeren."
    )
    return Segmentatie(
        beoordeling=beoordeling, methode="hvj-oude-rubrieken", melding=melding
    )


def _segmenteer_hvj(tekst: str) -> Segmentatie | None:
    """HvJ/Gerecht: eerst het recente koppenformaat, dan de prejudiciële vragen, dan het oude rubriekenformaat."""
    return _segmenteer_hvj_recent(tekst) or _segmenteer_hvj_vragen(tekst) or _segmenteer_hvj_oud(tekst)


# ----------------------------------------------------------------------------------
# Strategiekeuze
# ----------------------------------------------------------------------------------
#: Volgorde bij detectie zonder bruikbare hint: specifieke structuren eerst, de
#: generieke 'Beoordeling'-koppendetectie (RvVb/RvS) als laatste.
_ALLE_STRATEGIEEN = (
    _segmenteer_gwh,
    _segmenteer_cassatie,
    _segmenteer_ehrm,
    _segmenteer_hvj,
    _segmenteer_beoordeling_koppen,
)

_STRATEGIEEN_PER_BRON = {
    "dbrc": (_segmenteer_beoordeling_koppen,),
    "raadvanstate": (_segmenteer_beoordeling_koppen,),
    # Juportal herbergt meerdere colleges (CASS, GHCC, RVSCE): probeer ze in volgorde.
    "juportal": (_segmenteer_gwh, _segmenteer_cassatie, _segmenteer_beoordeling_koppen),
    "ehrm": (_segmenteer_ehrm,),
    "hvj": (_segmenteer_hvj,),
    "eurlex": (_segmenteer_hvj,),
}

#: Instantie-herkenning op substring (kleine letters); wint van de bron-hint omdat de
#: instantienaam specifieker is.
_STRATEGIEEN_PER_INSTANTIE = (
    ("cassatie", (_segmenteer_cassatie,)),
    ("grondwettelijk", (_segmenteer_gwh,)),
    ("raad van state", (_segmenteer_beoordeling_koppen,)),
    ("vergunningsbetwistingen", (_segmenteer_beoordeling_koppen,)),
    ("handhavingscollege", (_segmenteer_beoordeling_koppen,)),
    ("studievoortgang", (_segmenteer_beoordeling_koppen,)),
    ("verkiezingsbetwistingen", (_segmenteer_beoordeling_koppen,)),
    ("bestuursrechtscolleges", (_segmenteer_beoordeling_koppen,)),
    ("rechten van de mens", (_segmenteer_ehrm,)),
    ("hof van justitie", (_segmenteer_hvj,)),
    ("gerecht", (_segmenteer_hvj,)),
)

_MELDING_NIET_HERKEND = (
    "structuur niet herkend; gebruik de integrale tekst en controleer zelf welk deel "
    "het oordeel van het rechtscollege is."
)


def _kies_strategieen(bron: str | None, instantie: str | None):
    if instantie:
        naam = instantie.strip().lower()
        for sleutel, strategieen in _STRATEGIEEN_PER_INSTANTIE:
            if sleutel in naam:
                return strategieen
    if bron:
        strategieen = _STRATEGIEEN_PER_BRON.get(bron.strip().lower())
        if strategieen:
            return strategieen
    return _ALLE_STRATEGIEEN


def segmenteer(
    tekst: str, bron: str | None = None, instantie: str | None = None
) -> Segmentatie:
    """Isoleer het beoordelende deel uit de integrale tekst van één uitspraak.

    Puur (geen I/O). ``bron`` (broncode, bv. 'dbrc', 'juportal', 'ehrm') en/of
    ``instantie`` (naam van het rechtscollege) sturen de strategiekeuze; zonder
    bruikbare hint worden alle geijkte strategieën in volgorde geprobeerd. Wordt de
    koppenstructuur niet herkend, dan is ``beoordeling`` None met een eerlijke
    melding — er wordt nooit gegokt en nooit geparafraseerd.
    """
    if not tekst or not tekst.strip():
        return Segmentatie(
            beoordeling=None, methode=None, melding="lege tekst — niets te segmenteren."
        )
    for strategie in _kies_strategieen(bron, instantie):
        resultaat = strategie(tekst)
        if resultaat is not None:
            return resultaat
    return Segmentatie(beoordeling=None, methode=None, melding=_MELDING_NIET_HERKEND)
