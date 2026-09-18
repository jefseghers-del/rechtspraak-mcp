# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Browser-gedreven vrijetekstzoeken (opt-in) — contract en Playwright-aandrijving.

WAAROM DEZE MODULE BESTAAT
--------------------------
De drie bronnen bieden hun vrije zoek aan via een JavaScript-formulier (Juportal, RvS) of
achter een robots-verbod op de zoekparameter (DBRC `search_api_fulltext`). Een gewone
HTTP-fetch komt er dus niet; enkel een echte, JS-renderende browser die het formulier invult
kan doen wat een gebruiker met de hand doet. Deze module levert die browser-aandrijving.

BEWUSTE KEUZE, STANDAARD UIT
----------------------------
Browser-zoeken automatiseert de zoek-endpoints die robots.txt afraadt. Dat is een richtlijn,
geen technische afweer, en het inschakelen is een uitdrukkelijke keuze en verantwoordelijkheid
van de gebruiker (zie docs/bronnen-gebruiksvoorwaarden.md). Daarom staat het STANDAARD UIT
(config `RECHTSPRAAK_MCP_BROWSER_ZOEK`, leeg = uit) en is Playwright een optionele dependency.

Twee grenzen die hard in de code zitten:
  * **Bot-challenges worden NOOIT omzeild.** Toont een bron een CAPTCHA of Cloudflare-
    botchallenge, dan heft de aandrijving `BotdetectieError` op en stopt — er wordt niet
    geprobeerd die te verslaan. (De RvS zit achter Cloudflare; Juportal en DBRC zijn gewone
    servers.)
  * **Interactief, niet systematisch.** Eén gerichte zoekopdracht per vraag met nette rate
    limiting en een herkenbare User-Agent is raadpleging; bulk-crawlen raakt het
    databankenrecht (Wet 31 augustus 1998) en is niet de bedoeling van deze module.

DE NAAD (voor test- en uitbreidbaarheid)
----------------------------------------
`BrowserZoeker` is het smalle contract: geef een bron + query, krijg de HTML van de gerenderde
resultatenpagina terug. De adapters parseren die HTML met hun eigen pure parsers (DBRC:
`parse_zoekresultaten`; Juportal: `parse_juportal_zoekresultaten`). Zo blijft de brongebonden
parseerlogica testbaar op vaste fixtures, los van een echte browser, en kunnen tests een
nep-`BrowserZoeker` injecteren die vaste HTML teruggeeft.
"""
from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from . import user_agent


#: Herkenbare User-Agent (geen botmaskering), met de repository als contactpunt.
USER_AGENT = user_agent("opt-in browser-zoek; incidentele raadpleging")
#: Conservatieve rate limit tussen opeenvolgende zoekopdrachten (zelfde keuze als de fetch-adapters).
RATE_LIMIT_S = 10.0
#: Maximale wachttijd op het renderen van de resultatenpagina.
TIMEOUT_S = 30.0

#: Broncodes waarvoor browser-zoeken geïmplementeerd is. Enkel Juportal: dat is de echte
#: JS-SPA die een renderende browser vereist. DBRC heeft al een server-rendered zoekpad
#: (DbrcAdapter met RECHTSPRAAK_MCP_DBRC_ZOEK_SCRAPING); de RvS zit achter Cloudflare en een
#: JS-formulier en valt buiten scope (bot-challenges worden niet omzeild).
ONDERSTEUNDE_BRONNEN = ("juportal",)


class ZoekError(Exception):
    """Basisfout voor het browser-zoeken (renderfout, time-out, onbereikbare bron)."""


class BotdetectieError(ZoekError):
    """De bron toont een bot-challenge (CAPTCHA/Cloudflare). Wordt NOOIT omzeild.

    De adapter vangt deze op en geeft een eerlijke melding terug in plaats van een treffer.
    """


@runtime_checkable
class BrowserZoeker(Protocol):
    """Contract tussen de adapters en de browser-aandrijving.

    Een implementatie rendert het zoekformulier van `bron`, vult `query` in, verzendt het en
    geeft de HTML van de resultatenpagina terug. Ze doet GEEN parsing (dat is de taak van de
    bronadapter) en lost GEEN bot-challenges op (die geven `BotdetectieError`).
    """

    def haal_zoekpagina_html(self, bron: str, query: str, *, max_resultaten: int = 20) -> str:
        """Geef de gerenderde resultaten-HTML voor (bron, query).

        Heft `BotdetectieError` op bij een bot-challenge, `ZoekError` bij een andere fout,
        en `ValueError` bij een niet-ondersteunde bron.
        """
        ...


# -------------------------------------------------------------------------------------------
# Concrete aandrijving: Playwright + headless Chromium
# -------------------------------------------------------------------------------------------

#: URL van het Juportal-zoekformulier (JS-SPA; vereist een renderende browser).
_JUPORTAL_FORMULIER_URL = "https://juportal.be/zoekmachine/zoekformulier"
#: Pad-fragment van de resultatenpagina waarnaar het formulier na submit navigeert.
_JUPORTAL_RESULTATEN_PAD = "/zoekmachine/zoekresultaten"
#: Zoekveld -> CSS-selector op het Juportal-formulier (live geverifieerd op 2026-08-09).
_JUPORTAL_VELDEN = {
    "tekst": "#texpression",  # vrije tekst (name TEXPRESSION)
    "rolnummer": "#trechnorole",  # rolnummer (name TRECHNOROLE, bv. "P.20.0234.N")
}

#: Tekstsignalen (lowercase) van een bot-challenge in de gerenderde pagina. Eén treffer
#: volstaat om te stoppen: challenges worden NOOIT opgelost of omzeild.
_BOTDETECTIE_SIGNALEN = (
    "checking your browser",
    "verify you are human",
    "cloudflare",
    "captcha",
    "challenge-platform",  # pad van het Cloudflare-challenge-script (/cdn-cgi/challenge-platform/)
)


def _lijkt_botdetectie(html: str) -> bool:
    """Puur: herken een bot-challenge (CAPTCHA/Cloudflare-interstitial) in gerenderde HTML.

    Bewust simpel en aan de voorzichtige kant: zowel de bekende interstitial-teksten als de
    challenge-iframe/-scriptpaden tellen mee. Een vals positief kost hooguit een gemiste
    zoekopdracht; een vals negatief zou betekenen dat we een challenge-pagina als resultaat
    doorgeven — dat is erger. Los testbaar zonder browser.
    """
    laag = html.lower()
    return any(signaal in laag for signaal in _BOTDETECTIE_SIGNALEN)


class PlaywrightZoeker:
    """Concrete `BrowserZoeker` op Playwright + headless Chromium.

    Doet per zoekopdracht wat een gebruiker met de hand doet: het Juportal-zoekformulier
    openen, het gevraagde veld invullen, verzenden met Enter en wachten tot de resultaten-
    pagina gerenderd is. Geeft de volledige HTML terug; parsing (en het aftoppen op
    `max_resultaten`) is de taak van de bronadapter.

    Ontwerpkeuzes:

    * **Playwright is een lazy import** binnen `haal_zoekpagina_html`. Constructie van deze
      klasse slaagt dus altijd, ook zonder de optionele `browser`-dependency; pas bij een
      effectieve zoekopdracht volgt dan een `ZoekError` met installatiehint.
    * **Rate limiting per instantie** (zelfde patroon als `DbrcAdapter._wacht`): tussen twee
      opeenvolgende zoekopdrachten op dezelfde instantie zit minstens `rate_limit_s` seconden.
      Het register injecteert daarom ÉÉN gedeelde instantie in alle browser-zoek-adapters,
      zodat de limiet over de bronnen heen geldt. Tests zetten `rate_limit_s=0`.
    * **Bot-challenges stoppen de rit** (`BotdetectieError`), zowel op het formulier als op de
      resultatenpagina. Er wordt nooit geprobeerd een challenge op te lossen.
    * De browser wordt per zoekopdracht gestart en in een ``finally`` gesloten: geen lang-
      levende browserprocessen in een MCP-server die vooral stil staat.
    """

    def __init__(
        self,
        *,
        rate_limit_s: float = RATE_LIMIT_S,
        timeout_s: float = TIMEOUT_S,
        headless: bool = True,
    ):
        self._rate_limit_s = rate_limit_s
        self._timeout_s = timeout_s
        self._headless = headless
        self._laatste_zoekopdracht: float = 0.0

    # -- rate limiting (patroon DbrcAdapter._wacht) --------------------------------------
    def _wacht(self) -> None:
        verstreken = time.monotonic() - self._laatste_zoekopdracht
        if verstreken < self._rate_limit_s:
            time.sleep(self._rate_limit_s - verstreken)
        self._laatste_zoekopdracht = time.monotonic()

    # -- botdetectie ---------------------------------------------------------------------
    @staticmethod
    def _controleer_challenge(html: str) -> None:
        if _lijkt_botdetectie(html):
            raise BotdetectieError(
                "De bron toont een bot-challenge (CAPTCHA/Cloudflare). Die wordt bewust "
                "niet omzeild; raadpleeg de bron handmatig via de deeplink."
            )

    # -- publieke API --------------------------------------------------------------------
    def haal_zoekpagina_html(
        self, bron: str, query: str, *, max_resultaten: int = 20, veld: str = "tekst"
    ) -> str:
        """Rendert het zoekformulier van `bron`, zoekt `query` en geeft de resultaten-HTML.

        `veld` kiest het formulierveld: ``"tekst"`` (vrije tekst) of ``"rolnummer"``.
        `max_resultaten` hoort bij het `BrowserZoeker`-contract maar wordt hier niet
        toegepast: deze klasse geeft de volledige pagina terug en de adapter-parser topt af.

        Heft op: `ValueError` (niet-ondersteunde bron of onbekend veld — gecontroleerd vóór
        de playwright-import, dus ook zonder geïnstalleerde playwright), `BotdetectieError`
        (bot-challenge; wordt nooit omzeild) en `ZoekError` (playwright ontbreekt, time-out
        of browserfout).
        """
        # Validatie vóór de lazy import: foute aanroepen geven ook zonder playwright een
        # duidelijke ValueError in plaats van een installatiehint.
        if bron not in ONDERSTEUNDE_BRONNEN:
            raise ValueError(
                f"Browser-zoeken is niet ondersteund voor bron '{bron}' "
                f"(wel voor: {', '.join(ONDERSTEUNDE_BRONNEN)})."
            )
        if veld not in _JUPORTAL_VELDEN:
            raise ValueError(
                f"Onbekend zoekveld '{veld}' (wel: {', '.join(sorted(_JUPORTAL_VELDEN))})."
            )
        selector = _JUPORTAL_VELDEN[veld]

        try:
            from playwright.sync_api import (
                Error as _PlaywrightError,
                TimeoutError as _PlaywrightTimeout,
                sync_playwright,
            )
        except ImportError as exc:
            raise ZoekError(
                "Playwright is niet geïnstalleerd; browser-zoeken vereist de optionele "
                "'browser'-dependency. Installeer met `pip install 'rechtspraak-mcp[browser]'` "
                "en daarna `python -m playwright install chromium`."
            ) from exc

        self._wacht()
        timeout_ms = int(self._timeout_s * 1000)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self._headless)
                try:
                    context = browser.new_context(user_agent=USER_AGENT)
                    page = context.new_page()
                    page.goto(
                        _JUPORTAL_FORMULIER_URL, wait_until="networkidle", timeout=timeout_ms
                    )
                    self._controleer_challenge(page.content())
                    page.fill(selector, query, timeout=timeout_ms)
                    page.press(selector, "Enter", timeout=timeout_ms)
                    page.wait_for_url(
                        lambda url: _JUPORTAL_RESULTATEN_PAD in url,
                        wait_until="networkidle",
                        timeout=timeout_ms,
                    )
                    html = page.content()
                    self._controleer_challenge(html)
                    return html
                finally:
                    browser.close()
        except BotdetectieError:
            raise
        except _PlaywrightTimeout as exc:
            raise ZoekError(
                f"Time-out ({self._timeout_s:g}s) bij het browser-zoeken op '{bron}'."
            ) from exc
        except _PlaywrightError as exc:
            raise ZoekError(f"Browserfout bij het zoeken op '{bron}': {exc}") from exc


__all__ = [
    "USER_AGENT",
    "RATE_LIMIT_S",
    "TIMEOUT_S",
    "ONDERSTEUNDE_BRONNEN",
    "ZoekError",
    "BotdetectieError",
    "BrowserZoeker",
    "PlaywrightZoeker",
]
