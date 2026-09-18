# Installeren op Windows

> **Betaversie, geen product, zonder garantie of aansprakelijkheid; geen juridisch advies.** De gebruiker is
> zelf verantwoordelijk voor de controle en het gebruik van de resultaten.
> Zie de disclaimer in de [README](../README.md#disclaimer-en-privacy).

Twee wegen. De extensiebundel is de eenvoudigste; de git-route is bedoeld voor wie de code wil volgen of
aanpassen. Beide vereisen **Python 3.12 of hoger**, bij voorkeur van [python.org](https://www.python.org/downloads/)
(of `winget install Python.Python.3.12`), met **"Add python.exe to PATH"** aangevinkt.

De wheel in de bundel is platformonafhankelijk (`py3-none-any`); de dependencies worden bij de eerste
start van PyPI gehaald in de Windows-variant. Eén bundel werkt dus op macOS én Windows.

> **Eerlijk gezegd:** de bootstrap is op macOS getest, onder meer met drie gelijktijdige starts en met een
> installeerder die hard (`kill -9`) werd gestopt, met en zonder zijn pip. De Windows-specifieke paden (`Scripts\python.exe`, het kindproces in plaats
> van `exec`, de omleiding van Store-Python, de procescontrole via `OpenProcess`) zijn ontworpen op basis van
> echte Windows-logs, maar konden op macOS niet echt worden uitgevoerd. Meld problemen met het logbestand.

## Weg 1 — extensiebundel (Claude Desktop)

1. Download `be-rechtspraak.mcpb` bij de [releases](https://github.com/jefseghers-del/rechtspraak-mcp/releases).
2. Claude Desktop → Instellingen → Extensies → Geavanceerde instellingen → Extensie installeren.
3. Kies het `.mcpb`-bestand. De eerste start duurt 1 à 3 minuten: de extensie maakt dan een eigen
   Python-omgeving aan (internet nodig). Daarna start ze direct.

Werkt het niet, klik dan op **View logs** en zoek de regels die met `[be-rechtspraak]` beginnen; die
benoemen de oorzaak.

## Weg 2 — via git (Claude Code, of om te ontwikkelen)

```powershell
git clone https://github.com/jefseghers-del/rechtspraak-mcp.git
cd rechtspraak-mcp
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
pytest -q
```

Aansluiten op Claude Code:

```powershell
claude mcp add be-rechtspraak "C:\pad\naar\rechtspraak-mcp\.venv\Scripts\rechtspraak-mcp.exe"
```

Aansluiten op Claude Desktop zonder bundel: voeg dit toe aan `%APPDATA%\Claude\claude_desktop_config.json`
en herstart Claude Desktop.

```json
{
  "mcpServers": {
    "be-rechtspraak": {
      "command": "C:\\pad\\naar\\rechtspraak-mcp\\.venv\\Scripts\\rechtspraak-mcp.exe",
      "env": { "RECHTSPRAAK_MCP_STA_FETCH": "hvj,ehrm,eurlex,codex" }
    }
  }
}
```

Let op de dubbele backslashes in JSON.

## De bundel zelf bouwen op Windows

`mcpb-src/bouw.sh` is een zsh-script en draait niet op Windows. De stappen handmatig:

```powershell
cd C:\pad\naar\rechtspraak-mcp
Remove-Item dist\rechtspraak_mcp-*.whl, dist\rechtspraak_mcp-*.tar.gz -ErrorAction SilentlyContinue
uv build
Remove-Item mcpb-src\wheels\rechtspraak_mcp-*.whl -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force mcpb-src\wheels | Out-Null
Copy-Item dist\rechtspraak_mcp-*-py3-none-any.whl mcpb-src\wheels\
Copy-Item LICENSE mcpb-src\LICENSE
npx --yes @anthropic-ai/mcpb validate mcpb-src\manifest.json
npx --yes @anthropic-ai/mcpb pack mcpb-src dist\be-rechtspraak.mcpb
```

Vereist `uv` (`winget install astral-sh.uv`) en Node voor `npx`. Een bundel die op macOS is gebouwd,
werkt ongewijzigd op Windows.

## Bekende aandachtspunten op Windows

- **Startcommando.** Op Windows start de bundel met `python`, niet met `python3`: de installatie van
  python.org levert geen `python3.exe`.
- **Python uit de Microsoft Store.** Die Python leidt schrijfacties onder `AppData` om naar een eigen map
  (`...\Packages\PythonSoftwareFoundation.Python.3.1x_...\LocalCache`). Het log toont dan "Actual
  environment location may have moved". De bootstrap volgt die omleiding (via `os.path.realpath`, zoals
  `venv` zelf), maar de versie van python.org blijft de betrouwbaarste keuze.
- **Gelijktijdige starts.** Claude Desktop start de extensie vaak meermaals tegelijk, en sluit soms een
  instantie na een fractie van een seconde weer af. Precies één proces installeert de omgeving
  (lockbestand `server\.bootstrap.lock`); de andere wachten. Het slot bewaart de proces-ID's van de
  installeerder en, sinds versie 0.1.2, ook van zijn pip-processen (en van `playwright install`): zijn die
  allemaal gestopt, dan neemt een wachtend proces het slot meteen over. Zo schrijven een verweesde pip en
  een overnemer nooit tegelijk in dezelfde omgeving. Een slot ouder dan 15 minuten vervalt hoe dan ook.
- **Afgebroken installatie.** pip installeert niet atomair: een hard afgebroken pip kan een pakket half
  achterlaten, dat een volgende pip dan als "al geïnstalleerd" overslaat. Sinds versie 0.1.2 staat er
  daarom een marker `server\.installatie_bezig` zolang de installatie loopt; vindt een volgende start die
  nog, dan bouwt hij de omgeving opnieuw op ("Een vorige installatie werd afgebroken" in het log).
- **Duurt de eerste installatie** langer dan Claude Desktop wil wachten, dan verschijnt "Request timed
  out"; de installatie loopt gewoon door en de volgende start werkt.
- **Geen echte `exec`.** De bootstrap start de server daarom als kindproces en geeft de exitcode door; op
  macOS en Linux vervangt hij het proces met `os.execve`.
- **Browser-zoeken op Juportal (optioneel).** Playwright en Chromium bestaan voor Windows; bij het aanzetten
  downloadt de extensie eenmalig Chromium (±100 MB) naar `%LOCALAPPDATA%\ms-playwright`. Deze functie is
  op Windows niet getest.
- **Een oude installatie opruimen.** Lukt de eerste start blijvend niet: sluit Claude Desktop volledig af,
  verwijder de extensie, installeer ze opnieuw en wacht drie minuten. Gebruikte u Store-Python, verwijder
  dan ook de mappen `be-rechtspraak` onder
  `%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.1x_...\LocalCache\`.
- **PowerShell-uitvoeringsbeleid**: lukt `Activate.ps1` niet, gebruik dan `.\.venv\Scripts\activate.bat`
  in een gewone opdrachtprompt, of eenmalig `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
