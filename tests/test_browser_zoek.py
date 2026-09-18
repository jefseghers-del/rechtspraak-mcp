# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor het browser-gedreven zoeken (rechtspraak_mcp.browser_zoek + config/register).

Alles offline: de standaardtests starten GEEN browser en doen GEEN netwerkcalls. De
validatie van bron/veld gebeurt vóór de lazy playwright-import en is dus ook testbaar in
een omgeving zonder playwright; het ontbrekende-playwright-pad wordt gesimuleerd door de
module in ``sys.modules`` te blokkeren. Eén live smoke-test (marker ``live``) doet één
echte Juportal-zoekopdracht en draait enkel met ``RUN_LIVE=1``.
"""
from __future__ import annotations

import os
import sys

import pytest

from rechtspraak_mcp.adapters import alle_adapters
from rechtspraak_mcp.browser_zoek import (
    ONDERSTEUNDE_BRONNEN,
    BrowserZoeker,
    PlaywrightZoeker,
    ZoekError,
    _lijkt_botdetectie,
)
from rechtspraak_mcp.config import ENV_BROWSER_ZOEK, ENV_STA_FETCH, lees_config


# ---------------------------------------------------------------------------------------
# Config-parsing van RECHTSPRAAK_MCP_BROWSER_ZOEK
# ---------------------------------------------------------------------------------------
def test_lees_config_zonder_env_browser_zoek_uit():
    config = lees_config(env={})
    assert config.browser_zoek == frozenset()


def test_lees_config_lege_string_browser_zoek_uit():
    config = lees_config(env={ENV_BROWSER_ZOEK: ""})
    assert config.browser_zoek == frozenset()
    assert config.onbekende_codes == frozenset()


def test_lees_config_juportal_aan():
    config = lees_config(env={ENV_BROWSER_ZOEK: "juportal"})
    assert config.browser_zoek == frozenset({"juportal"})
    assert config.onbekende_codes == frozenset()


def test_lees_config_trim_en_hoofdletters():
    config = lees_config(env={ENV_BROWSER_ZOEK: "  JuPortal , "})
    assert config.browser_zoek == frozenset({"juportal"})


def test_lees_config_niet_ondersteunde_code_naar_onbekende_codes():
    # "dbrc" is een bestaande bron, maar valt buiten ONDERSTEUNDE_BRONNEN voor
    # browser-zoeken; hij wordt genegeerd en verzameld zodat het register kan waarschuwen.
    config = lees_config(env={ENV_BROWSER_ZOEK: "juportal, dbrc, onzin"})
    assert config.browser_zoek == frozenset({"juportal"})
    assert config.onbekende_codes == frozenset({"dbrc", "onzin"})


def test_lees_config_onbekende_codes_uit_beide_variabelen_samengevoegd():
    config = lees_config(env={ENV_STA_FETCH: "onzin", ENV_BROWSER_ZOEK: "dbrc"})
    assert config.onbekende_codes == frozenset({"onzin", "dbrc"})
    assert config.sta_fetch == frozenset()
    assert config.browser_zoek == frozenset()


def test_browser_zoek_staat_los_van_sta_fetch():
    config = lees_config(env={ENV_STA_FETCH: "juportal"})
    assert config.sta_fetch == frozenset({"juportal"})
    assert config.browser_zoek == frozenset()


# ---------------------------------------------------------------------------------------
# PlaywrightZoeker: validatie (vóór de playwright-import, dus zonder browser)
# ---------------------------------------------------------------------------------------
def test_playwright_zoeker_voldoet_aan_protocol():
    assert isinstance(PlaywrightZoeker(), BrowserZoeker)


@pytest.mark.parametrize("bron", ["dbrc", "raadvanstate", "onzin", ""])
def test_niet_ondersteunde_bron_geeft_valueerror(bron: str):
    zoeker = PlaywrightZoeker(rate_limit_s=0)
    with pytest.raises(ValueError, match="niet ondersteund"):
        zoeker.haal_zoekpagina_html(bron, "jachtdecreet")


@pytest.mark.parametrize("veld", ["ecli", "TEKST", ""])
def test_onbekend_veld_geeft_valueerror(veld: str):
    zoeker = PlaywrightZoeker(rate_limit_s=0)
    with pytest.raises(ValueError, match="zoekveld"):
        zoeker.haal_zoekpagina_html("juportal", "jachtdecreet", veld=veld)


def test_validatie_gaat_voor_de_playwright_import(monkeypatch: pytest.MonkeyPatch):
    # Ook met geblokkeerde playwright komt er een ValueError, geen installatiehint:
    # de bron/veld-validatie staat vóór de lazy import.
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    zoeker = PlaywrightZoeker(rate_limit_s=0)
    with pytest.raises(ValueError):
        zoeker.haal_zoekpagina_html("raadvanstate", "x")
    with pytest.raises(ValueError):
        zoeker.haal_zoekpagina_html("juportal", "x", veld="onzin")


# ---------------------------------------------------------------------------------------
# PlaywrightZoeker: ontbrekende playwright -> ZoekError met installatiehint
# ---------------------------------------------------------------------------------------
def test_ontbrekende_playwright_geeft_zoekerror_met_hint(monkeypatch: pytest.MonkeyPatch):
    # None in sys.modules laat "from playwright.sync_api import ..." falen met ImportError.
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    zoeker = PlaywrightZoeker(rate_limit_s=0)
    with pytest.raises(ZoekError) as excinfo:
        zoeker.haal_zoekpagina_html("juportal", "jachtdecreet")
    melding = str(excinfo.value)
    assert "rechtspraak-mcp[browser]" in melding
    assert "playwright install chromium" in melding


# ---------------------------------------------------------------------------------------
# PlaywrightZoeker: rate limiting (patroon DbrcAdapter._wacht)
# ---------------------------------------------------------------------------------------
def test_rate_limit_wacht_tussen_opeenvolgende_oproepen(monkeypatch: pytest.MonkeyPatch):
    slaap: list[float] = []
    monkeypatch.setattr(
        "rechtspraak_mcp.browser_zoek.time.sleep", lambda s: slaap.append(s)
    )
    zoeker = PlaywrightZoeker(rate_limit_s=5.0)
    zoeker._wacht()  # eerste oproep: geen wachttijd
    assert slaap == []
    zoeker._wacht()  # meteen erna: bijna de volle limiet wachten
    assert len(slaap) == 1
    assert 0 < slaap[0] <= 5.0


def test_rate_limit_nul_slaapt_nooit(monkeypatch: pytest.MonkeyPatch):
    slaap: list[float] = []
    monkeypatch.setattr(
        "rechtspraak_mcp.browser_zoek.time.sleep", lambda s: slaap.append(s)
    )
    zoeker = PlaywrightZoeker(rate_limit_s=0)
    zoeker._wacht()
    zoeker._wacht()
    assert slaap == []


# ---------------------------------------------------------------------------------------
# Botdetectie-heuristiek (puur, zonder browser)
# ---------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "html",
    [
        "<title>Just a moment...</title><body>Checking your browser before accessing</body>",
        "<body><h1>Verify you are human</h1></body>",
        '<script src="/cdn-cgi/challenge-platform/h/b/orchestrate.js"></script>',
        '<iframe src="https://challenges.cloudflare.com/turnstile/v0/"></iframe>',
        '<div class="g-recaptcha" data-sitekey="x">CAPTCHA</div>',
    ],
)
def test_lijkt_botdetectie_herkent_challenges(html: str):
    assert _lijkt_botdetectie(html) is True


def test_lijkt_botdetectie_laat_normale_resultaten_door():
    html = (
        "<html><body>90 resultaten - 1-50 "
        '<a href="/content/ECLI:BE:GHCC:2024:ARR.100/NL">Arrest</a></body></html>'
    )
    assert _lijkt_botdetectie(html) is False


# ---------------------------------------------------------------------------------------
# Register-injectie (adapters/__init__.py)
# ---------------------------------------------------------------------------------------
def _per_bron(adapters):
    return {a.bron: a for a in adapters}


def test_alle_adapters_zonder_env_geen_browser_zoek():
    per_bron = _per_bron(alle_adapters(env={}))
    for adapter in per_bron.values():
        assert not getattr(adapter, "browser_zoek_aan", False)


def test_alle_adapters_injecteert_zoeker_in_juportal():
    per_bron = _per_bron(alle_adapters(env={ENV_BROWSER_ZOEK: "juportal"}))
    juportal = per_bron["juportal"]
    assert getattr(juportal, "browser_zoek_aan", False) is True
    assert isinstance(juportal._zoeker, PlaywrightZoeker)
    # De andere adapters blijven onaangeroerd.
    for bron, adapter in per_bron.items():
        if bron != "juportal":
            assert not getattr(adapter, "browser_zoek_aan", False)


def test_alle_adapters_leest_browser_zoek_per_aanroep_vers():
    aan = _per_bron(alle_adapters(env={ENV_BROWSER_ZOEK: "juportal"}))
    assert getattr(aan["juportal"], "browser_zoek_aan", False) is True
    uit = _per_bron(alle_adapters(env={}))
    assert not getattr(uit["juportal"], "browser_zoek_aan", False)


def test_alle_adapters_negeert_niet_ondersteunde_browser_zoek_code(caplog):
    per_bron = _per_bron(alle_adapters(env={ENV_BROWSER_ZOEK: "dbrc"}))
    for adapter in per_bron.values():
        assert not getattr(adapter, "browser_zoek_aan", False)
    assert "dbrc" in caplog.text


# ---------------------------------------------------------------------------------------
# Live smoke (enkel met RUN_LIVE=1): één echte Juportal-zoekopdracht
# ---------------------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1",
    reason="Live Juportal-smoke; zet RUN_LIVE=1 om te draaien.",
)
def test_live_juportal_zoek_smoke():
    """Eén gerichte zoekopdracht ('jachtdecreet') tegen het echte Juportal-formulier.

    Controleert enkel dat de gerenderde resultatenpagina uitspraaklinks bevat
    (``/content/ECLI``); parsing is de taak van de adapter en wordt op fixtures getest.
    """
    zoeker = PlaywrightZoeker()  # standaard rate limit; dit is de enige live oproep
    html = zoeker.haal_zoekpagina_html("juportal", "jachtdecreet")
    assert "/content/ECLI" in html


def test_ondersteunde_bronnen_enkel_juportal():
    # Vangnet: breidt iemand ONDERSTEUNDE_BRONNEN uit, dan moeten de veld-selectors en de
    # formulier-URL in PlaywrightZoeker mee uitgebreid worden (nu Juportal-specifiek).
    assert ONDERSTEUNDE_BRONNEN == ("juportal",)
