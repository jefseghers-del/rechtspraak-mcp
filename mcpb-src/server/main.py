#!/usr/bin/env python3
# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Bootstrap-entry voor de MCPB-bundel van rechtspraak-mcp (Claude Desktop).

Bouwt bij de eerste start een eigen venv naast de bundel en installeert daarin de
meegeleverde rechtspraak-mcp-wheel met de `browser`-extra (Playwright). De dependencies
bevatten Python-minorversie-gebonden binaries (pydantic-core), dus een vooraf gebundelde lib
zou alleen op exact dezelfde Python werken. Daarna is elke start direct. Bij een nieuwe
bundelversie wordt de venv bijgewerkt (de bestandsnaam van de wheel staat in `.wheel_ok`).

Chromium (de browser die Playwright aanstuurt) wordt niet meegebundeld. Het wordt eenmalig
gedownload bij de eerste start waarin de gebruiker het browser-zoeken aanzet; wie het uit
laat, downloadt Chromium nooit.

Werkt op macOS, Linux en Windows: de wheel is platformonafhankelijk (py3-none-any) en de
dependencies komen bij de eerste start van PyPI, in de juiste variant voor het systeem.

Lessen uit echte Windows-starts:

* Gelijktijdige starts. Claude Desktop start een extensie vaak meermaals tegelijk (het gewone
  gesprek én de gedeelde pool voor Cowork- en Code-sessies). Een lockbestand (`os.O_EXCL`)
  zorgt dat precies één proces installeert; de andere wachten.
* Afgebroken starts. Claude Desktop sluit soms een instantie al na een fractie van een
  seconde af, ook als die net het slot heeft genomen. Het slot bewaart daarom het proces-ID;
  wie wacht, kijkt of dat proces nog leeft en neemt het slot van een gestopt proces meteen
  over. Een slot ouder dan 15 minuten geldt hoe dan ook als achtergelaten.
* Claude Desktop maakt de venv soms zelf aan, zonder pip. Daarom `with_pip=False` en daarna
  afzonderlijk `ensurepip`.
* Python uit de Microsoft Store leidt schrijfacties onder AppData om naar een eigen map
  (`...\\Packages\\PythonSoftwareFoundation...\\LocalCache`). Een bestand lezen op het gevraagde
  pad lukt dan wel, een proces starten niet. `os.path.realpath` geeft de echte locatie; zo
  doet `venv` het zelf ook (bpo-45337).
* Windows kent geen echte exec; de server draait daar als kindproces.

Stdio-hygiëne: stdout is het MCP-kanaal (JSON-RPC); alle bootstrap-uitvoer gaat naar stderr.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WINDOWS = sys.platform == "win32"
HIER = Path(__file__).resolve().parent  # .../server in de uitgepakte bundel
VENV = HIER / "venv"
WHEEL_SENTINEL = HIER / ".wheel_ok"  # bevat de bestandsnaam van de geïnstalleerde wheel
CHROMIUM_SENTINEL = HIER / ".chromium_ok"  # markeert dat Chromium al gedownload is
SLOT = HIER / ".bootstrap.lock"
SLOT_VERLOOPT_S = 15 * 60  # een slot ouder dan dit is hoe dan ook achtergelaten
NAAM = "be-rechtspraak"
PIP_OPTIES = ("--quiet", "--disable-pip-version-check", "--no-input", "--prefer-binary")


def _meld(boodschap: str) -> None:
    print(f"[{NAAM}] {boodschap}", file=sys.stderr, flush=True)


def _fout(boodschap: str) -> None:
    _meld(boodschap)
    sys.exit(1)


def _is_store_python() -> bool:
    return WINDOWS and any(
        "WindowsApps" in p or "PythonSoftwareFoundation" in p
        for p in (sys.executable, sys.base_prefix, sys.prefix)
    )


def _venv_py() -> Path:
    """Pad naar de Python van de venv, met de Store-omleiding opgelost (alleen Windows).

    Op macOS en Linux is `bin/python` een symlink naar de basis-Python; `realpath` zou de venv
    daar juist omzeilen. Op Windows is `Scripts/python.exe` een eigen bestand, en volgt
    `realpath` de omleiding van Store-Python naar de echte locatie.
    """
    if not WINDOWS:
        return VENV / "bin" / "python"
    kandidaat = VENV / "Scripts" / "python.exe"
    echt = Path(os.path.realpath(kandidaat))
    return echt if echt.exists() else kandidaat


def _bundelwheel() -> Path:
    """De wheel die in deze bundel meegeleverd is."""
    wheels = sorted((HIER.parent / "wheels").glob("rechtspraak_mcp-*.whl"))
    if not wheels:
        _fout("de rechtspraak-mcp-wheel ontbreekt in de bundel — bundel opnieuw bouwen.")
    if len(wheels) > 1:
        # Bewust geen gok op versievolgorde (lexicografisch klopt die niet vanaf 0.0.10).
        _fout(f"meer dan één wheel in de bundel ({', '.join(w.name for w in wheels)}) — bundel opnieuw bouwen.")
    return wheels[0]


def _pip(*argumenten: str) -> int:
    return subprocess.run(
        [str(_venv_py()), "-m", "pip", *argumenten], stdout=sys.stderr, stderr=sys.stderr
    ).returncode


def _heeft_module(module: str) -> bool:
    """Is de module installeerbaar gevonden, ZONDER haar te importeren?

    Een echte import laadt mcp, pydantic en httpx; op Windows kost dat bij de eerste keer
    tientallen seconden (pyc-compilatie, virusscanner). find_spec kijkt alleen of het pakket
    er staat."""
    code = f"import importlib.util,sys; sys.exit(0 if importlib.util.find_spec({module!r}) else 1)"
    try:
        return subprocess.run(
            [str(_venv_py()), "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode == 0
    except OSError:
        return False


def _zorg_voor_pip() -> bool:
    """Claude Desktop maakt de venv soms zelf aan (zonder pip); zet pip erin via ensurepip."""
    if _heeft_module("pip"):
        return True
    _meld("pip ontbreekt in de omgeving; wordt toegevoegd (ensurepip).")
    return subprocess.run(
        [str(_venv_py()), "-m", "ensurepip", "--upgrade"], stdout=sys.stderr, stderr=sys.stderr
    ).returncode == 0


def _klaar(wheel: Path) -> bool:
    try:
        return _venv_py().exists() and WHEEL_SENTINEL.read_text().strip() == wheel.name
    except OSError:
        return False


# -- slot ------------------------------------------------------------------------------------
def _proces_leeft(pid: int) -> bool:
    """Leeft het proces met dit PID nog? Zonder afhankelijkheden, ook op Windows.

    Op Windows NIET `os.kill(pid, 0)` gebruiken: dat roept daar TerminateProcess aan en zou
    het proces stoppen in plaats van het te controleren.
    """
    if pid <= 0:
        return False
    if WINDOWS:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # toegang geweigerd: het proces bestaat wel
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _slot_achtergelaten() -> bool:
    """Is het bestaande slot van een gestopt proces, of te oud?"""
    try:
        if time.time() - SLOT.stat().st_mtime > SLOT_VERLOOPT_S:
            return True
        inhoud = SLOT.read_text().split()
    except OSError:
        return False
    if not inhoud:
        return False  # net aangemaakt, PID nog niet geschreven
    try:
        return not _proces_leeft(int(inhoud[0]))
    except ValueError:
        return False


class _Slot:
    """Exclusief lockbestand, zonder afhankelijkheden, werkt op elk besturingssysteem.

    `os.O_EXCL` maakt het aanmaken atomair: van twee gelijktijdige processen slaagt er precies
    één. Wie het slot niet krijgt, wacht tot het vrijkomt, of neemt het over wanneer het
    proces dat het nam niet meer bestaat."""

    def __init__(self) -> None:
        self.fd: int | None = None

    def probeer(self) -> bool:
        try:
            self.fd = os.open(str(SLOT), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.fd, f"{os.getpid()} {time.time():.0f}\n".encode())
            return True
        except FileExistsError:
            if _slot_achtergelaten():
                _meld("achtergelaten installatieslot van een gestopt proces; wordt overgenomen.")
                SLOT.unlink(missing_ok=True)
            return False

    def los(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        SLOT.unlink(missing_ok=True)


def _met_slot(klaar, werk) -> None:
    """Voer `werk()` uit onder het slot, tenzij `klaar()` (eventueel dankzij een ander proces)."""
    if klaar():
        return
    slot = _Slot()
    gewacht = False
    begin = time.time()
    while not slot.probeer():
        if not gewacht:
            _meld("Een ander proces zet de omgeving klaar; even wachten.")
            gewacht = True
        time.sleep(1.0)
        if klaar() and not SLOT.exists():
            return  # het andere proces is klaar
        if time.time() - begin > SLOT_VERLOOPT_S + 60:
            _fout("wachten op de installatie duurde te lang. Start Claude Desktop opnieuw.")
    try:
        if not klaar():  # misschien deed een ander proces het werk terwijl we wachtten
            werk()
    finally:
        slot.los()


# -- installatie -----------------------------------------------------------------------------
def _maak_venv() -> None:
    import venv

    try:
        # Zonder pip: venv's eigen ensurepip-oproep faalde op Windows wanneer Claude Desktop de
        # map al had aangemaakt. _zorg_voor_pip doet dat daarna afzonderlijk en robuust.
        venv.create(VENV, with_pip=False)
    except FileExistsError:
        pass  # map bestond al (door Claude Desktop aangemaakt); de interpreter volgt hieronder
    if not _venv_py().exists():
        venv.EnvBuilder(with_pip=False, clear=False, upgrade=True).create(VENV)


def _installeer(wheel: Path) -> None:
    """Enkel aanroepen met het slot in handen."""
    eerste_keer = not (_venv_py().exists() and WHEEL_SENTINEL.exists() and _heeft_module("rechtspraak_mcp"))
    if eerste_keer:
        _meld("Eerste start: lokale omgeving wordt aangemaakt (eenmalig, 1 à 3 minuten, vergt internet).")
        if _is_store_python():
            _meld("Python uit de Microsoft Store in gebruik. Dat werkt, maar Python van python.org is "
                  "de aanbevolen keuze (zie docs/installeren-windows.md).")
        if not _venv_py().exists():
            _maak_venv()
    else:
        _meld(f"Nieuwe versie in de bundel ({wheel.name}); de lokale omgeving wordt bijgewerkt.")
    if not _zorg_voor_pip():
        shutil.rmtree(VENV, ignore_errors=True)
        _fout("pip kon niet in de omgeving worden gezet. Start Claude Desktop opnieuw; lukt het dan "
              "niet, installeer Python opnieuw via python.org.")
    # De [browser]-extra trekt Playwright mee (de Python-kant); Chromium volgt apart en
    # enkel wanneer het browser-zoeken effectief aan staat.
    doel = f"{wheel}[browser]"
    if eerste_keer:
        ok = _pip("install", *PIP_OPTIES, doel) == 0
    else:
        # Eerst een gewone upgrade (haalt eventuele nieuwe dependencies binnen), daarna de
        # wheel zelf geforceerd zonder deps: zo landt ook een herbouw met hetzelfde
        # versienummer effectief in de venv.
        ok = (_pip("install", *PIP_OPTIES, "--upgrade", doel) == 0
              and _pip("install", *PIP_OPTIES, "--force-reinstall", "--no-deps", str(wheel)) == 0)
    if not ok:
        if eerste_keer:
            WHEEL_SENTINEL.unlink(missing_ok=True)
            _fout("installatie mislukt. De eerste start vergt een internetverbinding (dependencies "
                  "van PyPI); start Claude Desktop daarna opnieuw.")
        _meld("Bijwerken mislukt; de server start met de vorige versie.")
        return
    WHEEL_SENTINEL.write_text(wheel.name + "\n")
    _meld("Omgeving klaar." if eerste_keer else "Bijgewerkt.")


def _zorg_voor_omgeving(wheel: Path) -> None:
    _met_slot(
        klaar=lambda: _klaar(wheel) and _heeft_module("rechtspraak_mcp"),
        werk=lambda: _installeer(wheel),
    )


def _download_chromium() -> None:
    _meld("Browser-zoeken aan: Chromium wordt eenmalig gedownload (~100 MB, vergt internet)...")
    resultaat = subprocess.run(
        [str(_venv_py()), "-m", "playwright", "install", "chromium"],
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    if resultaat.returncode == 0:
        CHROMIUM_SENTINEL.write_text("ok\n")
        _meld("Chromium klaar.")
    else:
        # Niet-fataal: het browser-zoeken geeft dan lege resultaten met een melding.
        _meld("Chromium-download mislukt; het browser-zoeken werkt pas na een geslaagde download "
              "(herstart met internet). De overige functies werken gewoon.")


def _zorg_voor_chromium() -> None:
    """Download Chromium eenmalig zodra het browser-zoeken aan staat (idempotent, onder het slot)."""
    _met_slot(klaar=CHROMIUM_SENTINEL.exists, werk=_download_chromium)


# -- configuratie ----------------------------------------------------------------------------
def _aan(env: dict[str, str], naam: str) -> bool:
    return env.get(naam, "").strip().lower() in ("1", "true", "ja", "yes", "on")


#: user_config-schakelaar (omgevingsvariabele uit het manifest) -> broncode in de server.
FETCH_SCHAKELAARS = {
    "RECHTSPRAAK_MCP_FETCH_JUPORTAL": "juportal",
    "RECHTSPRAAK_MCP_FETCH_RVS": "raadvanstate",
    "RECHTSPRAAK_MCP_FETCH_HVJ": "hvj",
    "RECHTSPRAAK_MCP_FETCH_EHRM": "ehrm",
    "RECHTSPRAAK_MCP_FETCH_EURLEX": "eurlex",
    "RECHTSPRAAK_MCP_FETCH_CODEX": "codex",
    "RECHTSPRAAK_MCP_FETCH_JUSTEL": "justel",
}


def _server_env() -> dict[str, str]:
    """Vertaal de user_config-schakelaars naar de omgevingsvariabelen van de server."""
    env = os.environ.copy()
    bronnen = [code for naam, code in FETCH_SCHAKELAARS.items() if _aan(env, naam)]
    if bronnen:
        env["RECHTSPRAAK_MCP_STA_FETCH"] = ",".join(bronnen)
    else:
        env.pop("RECHTSPRAAK_MCP_STA_FETCH", None)
    if _aan(env, "RECHTSPRAAK_MCP_BROWSER_ZOEK_JUPORTAL"):
        env["RECHTSPRAAK_MCP_BROWSER_ZOEK"] = "juportal"
    else:
        env.pop("RECHTSPRAAK_MCP_BROWSER_ZOEK", None)
    return env


def main() -> None:
    if sys.version_info < (3, 12):
        _fout(f"Python 3.12 of hoger is vereist (gevonden: {sys.version.split()[0]}). "
              "Installeer een recente Python via python.org.")
    wheel = _bundelwheel()
    _zorg_voor_omgeving(wheel)
    env = _server_env()
    if env.get("RECHTSPRAAK_MCP_BROWSER_ZOEK"):
        _zorg_voor_chromium()
    venv_py = str(_venv_py())
    argumenten = [venv_py, "-m", "rechtspraak_mcp.server"]
    if WINDOWS:
        # Windows kent geen echte exec: het proces zou worden vervangen door een nieuw proces
        # met een eigen PID, wat de pipes van Claude Desktop verbreekt. Daarom als kindproces
        # draaien met overgeërfde stdio, en de exitcode doorgeven.
        sys.exit(subprocess.run(argumenten, env=env).returncode)
    os.execve(venv_py, argumenten, env)


if __name__ == "__main__":
    main()
