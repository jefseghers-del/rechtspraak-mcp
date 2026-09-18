# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Bewaakt wat de publieke versie moet dragen: disclaimer, licentie, versie, standaarden.

Eén bron van waarheid (rechtspraak_mcp/__init__.py); deze tests zorgen dat de andere
plaatsen die bron blijven volgen.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import tomllib
from pathlib import Path

from rechtspraak_mcp import DISCLAIMER, DISCLAIMER_KORT, PRIVACY, REPO_URL, __version__
from rechtspraak_mcp.server import _leg_lege_identifier_uit, mcp

ROOT = Path(__file__).parent.parent
MANIFEST = json.loads((ROOT / "mcpb-src" / "manifest.json").read_text(encoding="utf-8"))
KERN = ("Betaversie", "geen product", "geen garantie", "geen aansprakelijkheid", "zelf volledig verantwoordelijk")


# -- disclaimer ------------------------------------------------------------------------------
def test_disclaimer_bevat_de_kernpunten():
    for kern in KERN + ("geen juridisch advies", "niet aansprakelijk", "gebruiksvoorwaarden"):
        assert kern in DISCLAIMER, kern


def test_disclaimer_zit_in_de_serverinstructies():
    """De disclaimer geldt voor de hele server: Claude krijgt ze bij elke verbinding."""
    assert DISCLAIMER in mcp.instructions
    assert PRIVACY in mcp.instructions
    assert "beta" in mcp.title.lower()
    assert "geen product" in mcp.description


def test_disclaimer_in_manifest():
    assert MANIFEST["display_name"] == "BE-rechtspraak (beta)"
    assert MANIFEST["description"].startswith("Betaversie, geen product")
    assert MANIFEST["long_description"].startswith(DISCLAIMER)
    assert PRIVACY in MANIFEST["long_description"]


def test_disclaimer_in_readme_en_handleiding():
    for naam in ("README.md", "HANDLEIDING.md"):
        tekst = (ROOT / naam).read_text(encoding="utf-8")
        assert "> [!WARNING]" in tekst, naam
        assert "Betaversie — geen product, geen garantie, geen aansprakelijkheid" in tekst, naam


def test_tool_antwoorden_dragen_de_disclaimer():
    r = asyncio.run(mcp.call_tool("zoek_op_identifier", {"identifier": "onzin"}))
    assert r.structured_content["disclaimer"] == DISCLAIMER_KORT
    assert _leg_lege_identifier_uit("RvVb-A-2425-0744").disclaimer == DISCLAIMER_KORT


# -- privégegevens, licentie, versie ---------------------------------------------------------
def test_geen_privegegevens_in_de_getrackte_bestanden():
    uit = subprocess.run(
        ["git", "grep", "--untracked", "-l", "-I", "-i", "-E", "gmail|/Users/"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.split()
    assert [f for f in uit if f != "tests/test_publicatie.py"] == []


def test_user_agents_verwijzen_naar_de_repository():
    from rechtspraak_mcp import browser_zoek, cellar
    from rechtspraak_mcp.adapters import dbrc, ehrm, juportal, raad_van_state
    from rechtspraak_mcp.wetgeving import codex, justel

    for mod in (browser_zoek, cellar, dbrc, ehrm, juportal, raad_van_state, codex, justel):
        assert REPO_URL in mod.USER_AGENT, mod.__name__
        assert "@" not in mod.USER_AGENT, mod.__name__


def test_licentie_eupl():
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("OPENBARE LICENTIE VAN DE EUROPESE UNIE v. 1.2")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["license"] == "EUPL-1.2"
    assert MANIFEST["license"] == "EUPL-1.2"
    bronnen = subprocess.run(["git", "ls-files", "*.py", "*.sh"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    zonder = [f for f in bronnen if "SPDX-License-Identifier: EUPL-1.2" not in (ROOT / f).read_text(encoding="utf-8")[:400]]
    assert zonder == []


def test_versie_overal_gelijk():
    """De bootstrap herkent een update aan de wheelnaam: pyproject, pakket, server en manifest lopen gelijk."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__
    assert MANIFEST["version"] == __version__
    assert mcp.version == __version__


def test_manifest_zonder_email_met_repository():
    assert "email" not in MANIFEST["author"]
    assert MANIFEST["author"]["url"] == REPO_URL
    assert MANIFEST["repository"]["url"] == REPO_URL


# -- standaardinstellingen en platformen -----------------------------------------------------
ROBOTS_BEPERKT = {"juportal_ophalen", "rvs_ophalen", "justel_ophalen", "juportal_browser_zoek"}
OPEN_BRONNEN = {"hvj_ophalen", "ehrm_ophalen", "eurlex_ophalen", "codex_ophalen"}


def test_bronnen_met_robotsbeperking_staan_standaard_uit():
    uc = MANIFEST["user_config"]
    assert set(uc) == ROBOTS_BEPERKT | OPEN_BRONNEN
    for sleutel in ROBOTS_BEPERKT:
        assert uc[sleutel]["default"] is False, sleutel
        assert "verantwoordelijkheid" in uc[sleutel]["description"], sleutel
    for sleutel in OPEN_BRONNEN:
        assert uc[sleutel]["default"] is True, sleutel


def test_manifest_windows_en_macos():
    assert set(MANIFEST["compatibility"]["platforms"]) == {"darwin", "win32", "linux"}
    config = MANIFEST["server"]["mcp_config"]
    assert config["command"] == "python3"
    assert config["platform_overrides"]["win32"]["command"] == "python"
