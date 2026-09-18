# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de omgevingsconfiguratie (rechtspraak_mcp.config).

Alles offline: `lees_config` krijgt een geïnjecteerde mapping mee, of de omgeving wordt
via pytest-monkeypatch gezet. Geen netwerkcalls, geen afhankelijkheid van de echte
procesomgeving.
"""
from __future__ import annotations

import pytest

from rechtspraak_mcp.adapters import (
    ArrestendatabankAdapter,
    DbrcAdapter,
    JuportalAdapter,
    RaadVanStateAdapter,
    actieve_adapters,
    alle_adapters,
)
from rechtspraak_mcp.config import (
    ENV_DBRC_ZOEK_SCRAPING,
    ENV_STA_FETCH,
    Config,
    lees_config,
    pas_toe,
)


# ---------------------------------------------------------------------------------------
# Parsen van RECHTSPRAAK_MCP_STA_FETCH
# ---------------------------------------------------------------------------------------
def test_lees_config_zonder_env_alles_uit():
    config = lees_config(env={})
    assert config.sta_fetch == frozenset()
    assert config.dbrc_zoek_scraping is False
    assert config.onbekende_codes == frozenset()


def test_lees_config_lege_string():
    config = lees_config(env={ENV_STA_FETCH: ""})
    assert config.sta_fetch == frozenset()
    assert config.onbekende_codes == frozenset()


def test_lees_config_enkele_code():
    config = lees_config(env={ENV_STA_FETCH: "juportal"})
    assert config.sta_fetch == frozenset({"juportal"})


def test_lees_config_meerdere_codes_met_whitespace_en_hoofdletters():
    config = lees_config(env={ENV_STA_FETCH: "  Juportal ,RAADVANSTATE  "})
    assert config.sta_fetch == frozenset({"juportal", "raadvanstate"})
    assert config.onbekende_codes == frozenset()


def test_lees_config_onbekende_codes_verzameld_maar_genegeerd():
    config = lees_config(env={ENV_STA_FETCH: "juportal, dbrc, onzin"})
    # "dbrc" is bewust GEEN geldige fetch-code: zoek-scraping vergt de aparte variabele.
    assert config.sta_fetch == frozenset({"juportal"})
    assert config.onbekende_codes == frozenset({"dbrc", "onzin"})


def test_lees_config_losse_kommas_geven_geen_lege_codes():
    config = lees_config(env={ENV_STA_FETCH: ", ,raadvanstate,,"})
    assert config.sta_fetch == frozenset({"raadvanstate"})
    assert config.onbekende_codes == frozenset()


# ---------------------------------------------------------------------------------------
# Parsen van RECHTSPRAAK_MCP_DBRC_ZOEK_SCRAPING
# ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("waarde", ["1", "true", "TRUE", "ja", "Ja", " ja "])
def test_dbrc_zoek_scraping_waar(waarde: str):
    config = lees_config(env={ENV_DBRC_ZOEK_SCRAPING: waarde})
    assert config.dbrc_zoek_scraping is True


@pytest.mark.parametrize("waarde", ["", "0", "false", "nee", "yes", "onzin"])
def test_dbrc_zoek_scraping_onwaar(waarde: str):
    config = lees_config(env={ENV_DBRC_ZOEK_SCRAPING: waarde})
    assert config.dbrc_zoek_scraping is False


# ---------------------------------------------------------------------------------------
# pas_toe op losse adapter-instanties
# ---------------------------------------------------------------------------------------
def test_pas_toe_zet_sta_fetch_op_genoemde_adapters():
    config = Config(sta_fetch=frozenset({"juportal", "raadvanstate"}))
    juportal = JuportalAdapter()
    rvs = RaadVanStateAdapter()
    pas_toe(juportal, config)
    pas_toe(rvs, config)
    assert juportal.sta_fetch is True
    assert rvs.sta_fetch is True


def test_pas_toe_laat_niet_genoemde_adapters_uit():
    config = Config(sta_fetch=frozenset({"juportal"}))
    rvs = RaadVanStateAdapter()
    pas_toe(rvs, config)
    assert rvs.sta_fetch is False


def test_pas_toe_dbrc_zoek_scraping_enkel_via_aparte_variabele():
    dbrc = DbrcAdapter()
    # De fetch-variabele raakt DBRC niet aan.
    pas_toe(dbrc, Config(sta_fetch=frozenset({"juportal", "raadvanstate"})))
    assert dbrc.sta_zoek_scraping is False
    # De aparte variabele wel.
    pas_toe(dbrc, Config(dbrc_zoek_scraping=True))
    assert dbrc.sta_zoek_scraping is True


def test_pas_toe_wijzigt_klasse_defaults_niet():
    config = Config(sta_fetch=frozenset({"juportal"}), dbrc_zoek_scraping=True)
    pas_toe(JuportalAdapter(), config)
    pas_toe(DbrcAdapter(), config)
    # De defaults op de klassen blijven robots-conform False.
    assert JuportalAdapter.sta_fetch is False
    assert DbrcAdapter.sta_zoek_scraping is False
    assert JuportalAdapter().sta_fetch is False
    assert DbrcAdapter().sta_zoek_scraping is False


def test_pas_toe_activeert_arrestendatabank_niet():
    adb = ArrestendatabankAdapter()
    pas_toe(adb, Config(sta_fetch=frozenset({"arrestendatabank", "juportal"}), dbrc_zoek_scraping=True))
    assert adb.enabled is False


# ---------------------------------------------------------------------------------------
# Integratie met het adapterregister
# ---------------------------------------------------------------------------------------
def _per_bron(adapters):
    return {a.bron: a for a in adapters}


def test_alle_adapters_defaults_zonder_env():
    per_bron = _per_bron(alle_adapters(env={}))
    assert per_bron["juportal"].sta_fetch is False
    assert per_bron["raadvanstate"].sta_fetch is False
    assert per_bron["dbrc"].sta_zoek_scraping is False


def test_alle_adapters_past_env_toe():
    env = {
        ENV_STA_FETCH: "juportal, raadvanstate",
        ENV_DBRC_ZOEK_SCRAPING: "ja",
    }
    per_bron = _per_bron(alle_adapters(env=env))
    assert per_bron["juportal"].sta_fetch is True
    assert per_bron["raadvanstate"].sta_fetch is True
    assert per_bron["dbrc"].sta_zoek_scraping is True


def test_alle_adapters_leest_env_per_aanroep_vers():
    aan = _per_bron(alle_adapters(env={ENV_STA_FETCH: "juportal"}))
    assert aan["juportal"].sta_fetch is True
    # Volgende aanroep zonder env: geen doorsijpelende toestand.
    uit = _per_bron(alle_adapters(env={}))
    assert uit["juportal"].sta_fetch is False


def test_alle_adapters_via_monkeypatch_os_environ(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(ENV_STA_FETCH, "RaadVanState")
    monkeypatch.delenv(ENV_DBRC_ZOEK_SCRAPING, raising=False)
    per_bron = _per_bron(alle_adapters())
    assert per_bron["raadvanstate"].sta_fetch is True
    assert per_bron["juportal"].sta_fetch is False
    assert per_bron["dbrc"].sta_zoek_scraping is False


def test_actieve_adapters_blijft_arrestendatabank_uitsluiten():
    env = {ENV_STA_FETCH: "juportal,raadvanstate", ENV_DBRC_ZOEK_SCRAPING: "1"}
    actief = actieve_adapters(env=env)
    assert all(a.enabled for a in actief)
    assert not any(isinstance(a, ArrestendatabankAdapter) for a in actief)
    bronnen = {a.bron for a in actief}
    assert bronnen == {"dbrc", "raadvanstate", "juportal", "hvj", "ehrm"}
