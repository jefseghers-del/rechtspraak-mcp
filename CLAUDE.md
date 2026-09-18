# CLAUDE.md

## Project

rechtspraak-mcp (BE-rechtspraak, betaversie, EUPL-1.2) is een MCP-server die Claude toegang geeft tot Belgische en Europese rechtspraak en wetgeving (Juportal, DBRC/RvVb, Raad van State, HvJ EU en EU-wetgeving via CELLAR, EHRM via HUDOC, Vlaamse Codex, Justel). Gebruikersdocumentatie: `HANDLEIDING.md`; technisch: `README.md`. Leidraad: `docs/spec-rechtspraak-mcp-connector.md` (spec, met de beslissingen van 3 augustus 2026 in punt 6) en `docs/bronnenonderzoek.md` (haalbaarheid en concrete aanknopingspunten per bron). Lees beide vóór je aan adapters werkt.

## Stand van zaken en prioriteit

Alle adapters werken (concept, betaversie), elk met tests op vaste fixtures (`tests/`, zonder netwerk). EU-rechtspraak en -wetgeving lopen via CELLAR (`rechtspraak_mcp/cellar.py`), omdat EUR-Lex een botcontrole plaatst; botcontroles worden nooit omzeild (`rechtspraak_mcp/botcontrole.py`). Juportal, Raad van State en Justel hebben een restrictieve robots.txt en staan in de publieke bundel standaard uit; de pure deeplink-bouwers blijven bruikbaar. Zie `docs/bronnen-gebruiksvoorwaarden.md` en `docs/bronnenonderzoek.md` vóór je daaraan raakt. Elke treffer krijgt via `rechtspraak_mcp/verwijzing.py` een voorstel van VENA-voetnootverwijzing mee (`docs/verwijsregels.md`), en `haal_uitspraak` bakent via `rechtspraak_mcp/segmentatie.py` het beoordelende deel af. Volgende kandidaten: vrij zoeken in EU-rechtspraak via CELLAR, het Juportal-zoekendpoint, en per bron toestemming of structurele toegang regelen. Houd de architectuur remote-ready: lokaal (stdio) is het eerste spoor, maar vermijd keuzes die een latere remote/HTTP-variant blokkeren. Een bron met eigen (niet-publieke) documenten komt pas later en hoort niet in deze publieke repository.

## Harde regels

- De arrestendatabank-adapter blijft uitgeschakeld (`enabled = False`): geautomatiseerd hergebruik is er contractueel verboden. Niet activeren zonder overeenkomst.
- Anti-hallucinatie: de tools geven uitsluitend terug wat een adapter effectief van de bron ontvangt. Elke treffer behoudt een controleerbare bron-URL. Vul nooit rechtspraak of citaties aan die niet uit een tool-respons komen.
- Scraping: respecteer robots.txt en gebruiksvoorwaarden, hanteer nette rate limiting en een herkenbare User-Agent, en omzeil geen betaalmuren of botcontroles. Bronnen waarvan de robots.txt geautomatiseerde opvraging afraadt (Juportal, Raad van State, Justel) staan in de publieke bundel standaard uit.
- Publieke repository: geen dossier- of cliëntgegevens, geen namen of adressen uit lopende zaken, geen persoonsgegevens (fixtures pseudonimiseren, zie `tests/fixtures/README.md`), geen lokale paden of privé-e-mailadressen — ook niet in commitberichten.
- Disclaimer, privacyverklaring, versie en User-Agent staan op één plaats: `rechtspraak_mcp/__init__.py`. Tests bewaken dat ze in de serverinstructies en het manifest aanwezig blijven. Verhoog bij elke codewijziging de versie (in `__init__.py`, `pyproject.toml` en `mcpb-src/manifest.json`; een test bewaakt dat ze gelijk zijn): de bootstrap herkent een nieuwe versie aan de bestandsnaam van de wheel.

## Technisch

- Python 3.12+, FastMCP (`mcp`-package), httpx, beautifulsoup4, pydantic.
- Installatie: `uv venv && source .venv/bin/activate && uv pip install -e .`
- Tests: `pytest`. Nieuwe adapters testen tegen fixtures in `tests/fixtures/`, geen live netwerkcalls in tests.
- Adapters normaliseren elke treffer naar het `Treffer`-schema in `rechtspraak_mcp/schema.py` en implementeren de interface uit `rechtspraak_mcp/adapters/base.py`.

## Taal en stijl

Nederlands (Belgisch juridisch register) voor documentatie, docstrings en commitboodschappen. Onzekere juridische of feitelijke beweringen in documentatie markeren als [TE VERIFIËREN].
