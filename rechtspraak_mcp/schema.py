# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Intern resultaatschema en tool-invoerschema's.

Eén genormaliseerd schema waar elke bronadapter naartoe vertaalt, zodat de MCP-tools
bronoverschrijdend dezelfde structuur teruggeven. De velden volgen de spec (punt 4):
bron, instantie, titel, datum, ecli/rolnummer, snippet, url.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from . import DISCLAIMER_KORT


def _disclaimer_veld():
    return Field(
        default=DISCLAIMER_KORT,
        description="Betaversie zonder garantie of aansprakelijkheid; geen juridisch advies.",
    )


class Treffer(BaseModel):
    """Eén genormaliseerde zoektreffer, bronoverschrijdend."""

    bron: str = Field(description="Technische broncode, bv. 'dbrc', 'juportal', 'raadvanstate'.")
    instantie: str = Field(
        description="Naam van het rechtscollege, bv. 'Raad voor Vergunningsbetwistingen'."
    )
    titel: str = Field(description="Korte omschrijving of opschrift van de uitspraak.")
    datum: date | None = Field(default=None, description="Datum van de uitspraak, indien bekend.")
    ecli: str | None = Field(default=None, description="ECLI-code, indien beschikbaar.")
    rolnummer: str | None = Field(
        default=None, description="Rol-/arrestnummer, bv. 'RvVb-A-2425-0744' of '250.123'."
    )
    snippet: str | None = Field(
        default=None, description="Relevant tekstfragment of samenvatting uit de bron."
    )
    url: str = Field(description="Aanklikbare deeplink naar het brondocument, ter controle.")
    verwijzing: str | None = Field(
        default=None,
        description=(
            "Voorstel van voetnootverwijzing volgens vena.be (RS1/RS2), uitsluitend opgebouwd "
            "uit de velden hierboven; partijnaam en vindplaats vult de gebruiker aan. Vóór "
            "gebruik verifiëren via de bron-URL."
        ),
    )


class ZoekRespons(BaseModel):
    """Antwoord van de zoektools: treffers plus context wanneer er niets (meer) te vinden is.

    `treffers` bevat uitsluitend wat een bron effectief terugleverde (anti-hallucinatie).
    `melding` legt uit waarom een resultaat leeg of onvolledig is (bv. vrijetekstzoeken
    robots-geblokkeerd, bron uitgeschakeld, identifierformaat niet ondersteund).
    `handmatige_links` zijn puur geconstrueerde URL's (zoekpagina's of deeplinks) die de
    gebruiker zelf kan openen — het zijn GEEN bevestigde treffers.
    """

    treffers: list[Treffer]
    melding: str | None = Field(
        default=None, description="Uitleg bij een leeg of beperkt resultaat."
    )
    handmatige_links: dict[str, str] | None = Field(
        default=None,
        description=(
            "Zelf te openen URL's per bron (zoekpagina of onbevestigde deeplink); "
            "geen bevestigde treffers."
        ),
    )
    disclaimer: str = _disclaimer_veld()


class Uitspraak(BaseModel):
    """Volledige (of verkorte) tekst van één uitspraak, opgehaald via haal_uitspraak.

    Naast de integrale tekst draagt de uitspraak het gesegmenteerde BEOORDELENDE DEEL:
    de eigen beoordeling van het rechtscollege (GwH: B-paragrafen; Cassatie: "Beslissing
    van het Hof"; RvS/RvVb: "Beoordeling" + dictum; EHRM: "THE LAW"). Alleen dat deel is
    bruikbaar om stellingen te onderbouwen — wat partijen aanvoeren is dat niet, ook al
    staat het in hetzelfde arrest (zie docs/spec-gerichte-zoekfunctie.md, §1). Wanneer de
    structuur niet betrouwbaar herkend wordt, is `beoordeling` None en legt `segmentatie`
    dat uit; er wordt nooit geraden.
    """

    treffer: Treffer
    tekst: str = Field(description="Integrale of verkorte tekst zoals de bron die teruggeeft.")
    beoordeling: str | None = Field(
        default=None,
        description=(
            "Uitsluitend het beoordelende deel van het rechtscollege (letterlijke "
            "brontekst, incl. dictum). Citeer HIERUIT, nooit uit de partijenstandpunten "
            "in `tekst`. None wanneer de structuur niet betrouwbaar herkend werd."
        ),
    )
    segmentatie: str | None = Field(
        default=None,
        description="Hoe het beoordelende deel is afgebakend, of waarom dat niet lukte.",
    )
    disclaimer: str = _disclaimer_veld()


class Norm(BaseModel):
    """Eén genormaliseerde wetgevingstreffer (tweede spoor naast rechtspraak).

    Een norm is geen arrest: identificatie loopt via CELEX/ELI/nummer en de
    VENA-verwijzing volgt de wetgevingsvorm (norm + datum met maand voluit + opschrift +
    vindplaats). Zelfde anti-hallucinatieregel als bij Treffer: uitsluitend velden die de
    bron effectief teruggaf, met altijd een controleerbare bron-URL.
    """

    bron: str = Field(description="Technische broncode, bv. 'eurlex' (later 'codex', 'justel').")
    type: str | None = Field(
        default=None, description="Aard van de norm, bv. 'richtlijn', 'verordening', 'besluit'."
    )
    nummer: str | None = Field(default=None, description="Normnummer, bv. '2011/92/EU'.")
    opschrift: str = Field(description="Volledig opschrift zoals de bron het geeft.")
    datum: date | None = Field(default=None, description="Datum van de norm, indien bekend.")
    celex: str | None = Field(default=None, description="CELEX-nummer (EUR-Lex), bv. '32011L0092'.")
    eli: str | None = Field(default=None, description="ELI-identifier of -URL, indien beschikbaar.")
    vindplaats: str | None = Field(
        default=None, description="Officiële vindplaats in VENA-vorm, bv. 'Pb.L. 28 januari 2012, 1' of 'BS 1 oktober 2014'."
    )
    url: str = Field(description="Aanklikbare deeplink naar de brontekst, ter controle.")
    verwijzing: str | None = Field(
        default=None,
        description=(
            "Voorstel van verwijzing volgens vena.be (WG2/WG3), opgebouwd uit de velden "
            "hierboven; vóór gebruik verifiëren via de bron-URL."
        ),
    )


class NormTekst(BaseModel):
    """Volledige (of gedeeltelijke) tekst van één norm, opgehaald via haal_norm."""

    norm: Norm
    tekst: str = Field(description="Tekst zoals de bron die teruggeeft.")
    disclaimer: str = _disclaimer_veld()


class WetgevingRespons(BaseModel):
    """Antwoord van de wetgevingstools; zelfde eerlijkheidscontract als ZoekRespons."""

    normen: list[Norm]
    melding: str | None = Field(
        default=None, description="Uitleg bij een leeg of beperkt resultaat."
    )
    handmatige_links: dict[str, str] | None = Field(
        default=None,
        description=(
            "Zelf te openen URL's (zoekpagina of onbevestigde deeplink); geen bevestigde "
            "treffers."
        ),
    )
    disclaimer: str = _disclaimer_veld()


class ZoekQuery(BaseModel):
    """Genormaliseerde zoekopdracht die de server aan elke adapter doorgeeft."""

    query: str = Field(description="Vrije tekst of trefwoorden.")
    instanties: list[str] | None = Field(
        default=None,
        description="Optionele filter op broncodes (bv. ['dbrc']). None = alle ingeschakelde bronnen.",
    )
    datum_van: date | None = Field(default=None, description="Ondergrens uitspraakdatum (optioneel).")
    datum_tot: date | None = Field(default=None, description="Bovengrens uitspraakdatum (optioneel).")
    max_resultaten: int = Field(default=20, ge=1, le=100, description="Max. treffers per bron.")
