# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de bootstrap van de MCPB-bundel (mcpb-src/server/main.py), zonder netwerk.

De echte Windows-paden (Store-Python, OpenProcess) kunnen op macOS niet worden uitgevoerd;
de logica errond wordt hier wel getoetst, met een symlink als nabootsing van de omleiding.
De volledige installatie met gelijktijdige starts wordt apart getest op een uitgepakte bundel.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

MAIN = Path(__file__).parent.parent / "mcpb-src" / "server" / "main.py"


@pytest.fixture()
def boot(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("bundel_main", MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "SLOT", tmp_path / ".bootstrap.lock")
    return module


def _dood_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


# -- schakelaars -> omgevingsvariabelen, beide richtingen ------------------------------------
def test_server_env_alles_aan(boot, monkeypatch):
    for naam in boot.FETCH_SCHAKELAARS:
        monkeypatch.setenv(naam, "true")
    monkeypatch.setenv("RECHTSPRAAK_MCP_BROWSER_ZOEK_JUPORTAL", "true")
    env = boot._server_env()
    assert env["RECHTSPRAAK_MCP_STA_FETCH"].split(",") == list(boot.FETCH_SCHAKELAARS.values())
    assert env["RECHTSPRAAK_MCP_BROWSER_ZOEK"] == "juportal"


def test_server_env_alles_uit(boot, monkeypatch):
    for naam in boot.FETCH_SCHAKELAARS:
        monkeypatch.setenv(naam, "false")
    monkeypatch.setenv("RECHTSPRAAK_MCP_BROWSER_ZOEK_JUPORTAL", "false")
    monkeypatch.setenv("RECHTSPRAAK_MCP_STA_FETCH", "juportal")  # restant van buitenaf
    env = boot._server_env()
    assert "RECHTSPRAAK_MCP_STA_FETCH" not in env
    assert "RECHTSPRAAK_MCP_BROWSER_ZOEK" not in env


def test_server_env_standaard_van_het_manifest(boot, monkeypatch):
    # Zoals Claude Desktop het met de standaardwaarden doorgeeft.
    for naam, aan in {
        "RECHTSPRAAK_MCP_FETCH_JUPORTAL": "false", "RECHTSPRAAK_MCP_FETCH_RVS": "false",
        "RECHTSPRAAK_MCP_FETCH_HVJ": "true", "RECHTSPRAAK_MCP_FETCH_EHRM": "true",
        "RECHTSPRAAK_MCP_FETCH_EURLEX": "true", "RECHTSPRAAK_MCP_FETCH_CODEX": "true",
        "RECHTSPRAAK_MCP_FETCH_JUSTEL": "false", "RECHTSPRAAK_MCP_BROWSER_ZOEK_JUPORTAL": "false",
    }.items():
        monkeypatch.setenv(naam, aan)
    env = boot._server_env()
    assert env["RECHTSPRAAK_MCP_STA_FETCH"] == "hvj,ehrm,eurlex,codex"


# -- slot ------------------------------------------------------------------------------------
def test_proces_leeft(boot):
    assert boot._proces_leeft(os.getpid()) is True
    assert boot._proces_leeft(_dood_pid()) is False
    assert boot._proces_leeft(0) is False


def test_slot_van_gestopt_proces_wordt_meteen_overgenomen(boot):
    boot.SLOT.write_text(f"{_dood_pid()} {time.time():.0f}\n")
    slot = boot._Slot()
    assert slot.probeer() is False  # ruimt het achtergelaten slot op
    assert slot.probeer() is True
    slot.los()
    assert not boot.SLOT.exists()


def test_slot_van_levend_proces_blijft_staan(boot):
    boot.SLOT.write_text(f"{os.getpid()} {time.time():.0f}\n")
    assert boot._Slot().probeer() is False
    assert boot.SLOT.exists()


def test_te_oud_slot_vervalt_ook_bij_levend_proces(boot):
    boot.SLOT.write_text(f"{os.getpid()} 0\n")
    oud = time.time() - boot.SLOT_VERLOOPT_S - 10
    os.utime(boot.SLOT, (oud, oud))
    slot = boot._Slot()
    assert slot.probeer() is False
    assert slot.probeer() is True
    slot.los()


def test_leeg_slot_is_niet_achtergelaten(boot):
    # Net aangemaakt door een ander proces dat zijn PID nog niet schreef: niet afpakken.
    boot.SLOT.write_text("")
    assert boot._Slot().probeer() is False
    assert boot.SLOT.exists()


# -- venv-pad --------------------------------------------------------------------------------
def test_venv_pad_windows_volgt_de_omleiding(boot, tmp_path, monkeypatch):
    # Nabootsing van Store-Python: het gevraagde pad verwijst naar een andere echte locatie.
    echt = tmp_path / "LocalCache" / "venv"
    (echt / "Scripts").mkdir(parents=True)
    (echt / "Scripts" / "python.exe").write_text("")
    gevraagd = tmp_path / "bundel" / "venv"
    gevraagd.parent.mkdir()
    gevraagd.symlink_to(echt, target_is_directory=True)
    monkeypatch.setattr(boot, "WINDOWS", True)
    monkeypatch.setattr(boot, "VENV", gevraagd)
    assert boot._venv_py() == Path(os.path.realpath(echt / "Scripts" / "python.exe"))


def test_venv_pad_macos_volgt_de_symlink_niet(boot, tmp_path, monkeypatch):
    # Op macOS/Linux is bin/python een symlink naar de basis-Python: niet oplossen.
    monkeypatch.setattr(boot, "WINDOWS", False)
    monkeypatch.setattr(boot, "VENV", tmp_path / "venv")
    assert boot._venv_py() == tmp_path / "venv" / "bin" / "python"
