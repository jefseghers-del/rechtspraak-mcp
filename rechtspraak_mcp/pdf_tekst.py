# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tekstextractie uit arrest-PDF's (pdfplumber).

Pure hulpmodule zonder netwerk-I/O. De adapters (DBRC, Raad van State) halen de
arrest-PDF zelf op en geven de bytes hieraan door. Anti-hallucinatie: deze module
geeft uitsluitend terug wat pdfplumber effectief uit de tekstlaag haalt — geen
aanvulling, geen herformattering die de brontekst wijzigt. Alleen overbodige
whitespace wordt licht genormaliseerd (trailing spaties weg, opeengestapelde lege
regels binnen een pagina samengevoegd).
"""
from __future__ import annotations

import io

import pdfplumber


def _normaliseer_pagina(tekst: str) -> str:
    """Lichte whitespace-opkuis binnen één pagina; de tekst zelf blijft brontekst."""
    regels = [regel.rstrip() for regel in tekst.splitlines()]
    genormaliseerd: list[str] = []
    vorige_leeg = False
    for regel in regels:
        if not regel:
            if vorige_leeg:
                continue  # nooit meer dan één lege regel na elkaar binnen een pagina
            vorige_leeg = True
        else:
            vorige_leeg = False
        genormaliseerd.append(regel)
    return "\n".join(genormaliseerd).strip()


def pdf_naar_tekst(inhoud: bytes) -> str | None:
    """Extraheer de tekstlaag uit een PDF; None bij een onleesbare of lege PDF.

    Pagina's worden gescheiden door één lege regel. Geeft None terug wanneer de
    bytes geen leesbare PDF vormen (corrupt, geen PDF) of wanneer er geen tekst
    in de tekstlaag zit (bv. een gescande PDF zonder OCR) — de aanroeper kan dan
    eerlijk melden dat extractie niet lukte. Crasht nooit op corrupte invoer.
    """
    if not inhoud:
        return None
    paginas: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(inhoud)) as pdf:
            for pagina in pdf.pages:
                tekst = _normaliseer_pagina(pagina.extract_text() or "")
                if tekst:
                    paginas.append(tekst)
    except Exception:
        # pdfplumber/pdfminer gooit uiteenlopende excepties op corrupte invoer
        # (PDFSyntaxError, PSException, ValueError, ...). Nooit laten crashen.
        return None
    volledige_tekst = "\n\n".join(paginas)
    return volledige_tekst or None
