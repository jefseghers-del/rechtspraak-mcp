# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""HTTP/REST-API naast de MCP-server: dezelfde kern, een dunne schil erover.

Waarom
------
Schillen die geen MCP spreken (bv. een Word-invoegtoepassing of een browserextensie, niet in
deze repository) moeten
dezelfde adapters en dezelfde VENA-verwijzingslogica kunnen aanspreken als de MCP-tools,
zonder tweede codebase ("één kern, dunne schillen").
Deze module herbruikt daarom rechtstreeks ``actieve_adapters()`` en importeert
``_met_verwijzing`` uit ``server.py`` — bewust géén eigen variant, zodat de
verwijzingsinvulling maar op één plaats bestaat en de twee ingangen (MCP en REST)
niet uiteen kunnen lopen.

Contract
--------
``GET /api/gezondheid``
    ``200 {"status": "ok", "versie": "<pakketversie>", "bronnen": [<broncodes>]}``.
    ``bronnen`` zijn de codes van de actieve adapters, alfabetisch gesorteerd.

``POST /api/zoek-identifier`` met body ``{"identifier": "..."}``
    ``200 {"treffers": [<Treffer>, ...]}`` — een lege lijst is een geldig antwoord
    (anti-hallucinatie: er wordt nooit iets aangevuld dat niet van een bron komt).
    ``400 {"fout": "identifier ontbreekt"}`` bij ontbrekende/lege identifier of
    onleesbare JSON-body.

``POST /api/haal`` met body ``{"url": "...", "bron": "..."}``
    ``200 {"treffer": <Treffer>, "tekst": "..."}``.
    ``404 {"fout": "niets gevonden"}`` wanneer de adapter ``None`` teruggeeft of de
    broncode geen actieve adapter heeft (zelfde semantiek als de MCP-tool
    ``haal_uitspraak``, die dan ook ``None`` geeft).
    ``400 {"fout": "url of bron ontbreekt"}`` bij ontbrekende velden of onleesbare JSON.

``<Treffer>`` is exact de JSON-serialisatie van het pydantic-model
(``model_dump(mode="json")``): datum als ``"YYYY-MM-DD"`` of ``null``, en het veld
``verwijzing`` met het voorstel van VENA-voetnoot.

Beveiliging
-----------
* **CORS**: standaard zijn enkel ``https://localhost:3000`` en ``http://localhost:3000``
  toegelaten (bv. een Office.js-taakvenster in Word). Andere origins via
  ``RECHTSPRAAK_MCP_CORS_ORIGINS`` (kommagescheiden). Nooit standaard ``*``.
* **Authenticatie**: optioneel bearer-token via ``RECHTSPRAAK_MCP_API_TOKEN``. Staat de
  variabele niet, dan is er geen authenticatie (lokaal gebruik op 127.0.0.1); staat ze
  wel, dan is ``Authorization: Bearer <token>`` verplicht op alle ``/api/``-routes
  behalve ``/api/gezondheid`` (anders 401).
* De server bindt standaard op ``127.0.0.1``. **Publiek openzetten zonder token (en
  zonder TLS ervoor) is onverantwoord**: de API geeft dan iedereen een scraping-proxy op
  de bronnen, wat haaks staat op de robots-/licentieafspraken per bron
  (docs/bronnenonderzoek.md) — zet dus eerst ``RECHTSPRAAK_MCP_API_TOKEN`` én een
  HTTPS-laag, en lees spec punt 6 over de licentieanalyse.

Draaien
-------
``rechtspraak-mcp-http`` (entry point in pyproject.toml) start uvicorn op
``RECHTSPRAAK_MCP_HTTP_HOST``/``RECHTSPRAAK_MCP_HTTP_PORT`` (default 127.0.0.1:8765).
"""
from __future__ import annotations

import hmac
import os
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version

from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from . import __version__
from .adapters import actieve_adapters
from .server import _met_verwijzing

#: Omgevingsvariabelen (namen hier gedocumenteerd zodat tests en schillen ze delen).
ENV_API_TOKEN = "RECHTSPRAAK_MCP_API_TOKEN"
ENV_CORS_ORIGINS = "RECHTSPRAAK_MCP_CORS_ORIGINS"
ENV_HTTP_HOST = "RECHTSPRAAK_MCP_HTTP_HOST"
ENV_HTTP_PORT = "RECHTSPRAAK_MCP_HTTP_PORT"

#: Default-origins: het Office.js-taakvenster draait op localhost:3000 (https en http).
DEFAULT_CORS_ORIGINS = ("https://localhost:3000", "http://localhost:3000")

#: Route die ook mét token zonder authenticatie bereikbaar blijft (health check).
_ONBEVEILIGD_PAD = "/api/gezondheid"


def _versie() -> str:
    """Pakketversie uit de installatiemetadata; valt terug op de versie in de code."""
    try:
        return version("rechtspraak-mcp")
    except PackageNotFoundError:  # pragma: no cover - enkel buiten een installatie
        return __version__


class BearerTokenMiddleware:
    """Dwingt ``Authorization: Bearer <token>`` af op /api/-routes (behalve gezondheid).

    Pure ASGI-middleware. Wordt enkel gemonteerd wanneer er effectief een token
    geconfigureerd is; zonder token bestaat deze laag niet (lokaal gebruik).
    De vergelijking gebeurt met ``hmac.compare_digest`` (constante tijd).
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            pad = scope.get("path", "")
            if pad.startswith("/api/") and pad != _ONBEVEILIGD_PAD:
                if not self._geldig(Headers(scope=scope).get("authorization", "")):
                    respons = JSONResponse({"fout": "authenticatie vereist"}, status_code=401)
                    await respons(scope, receive, send)
                    return
        await self.app(scope, receive, send)

    def _geldig(self, header: str) -> bool:
        schema, _, kandidaat = header.partition(" ")
        if schema.lower() != "bearer" or not kandidaat:
            return False
        return hmac.compare_digest(kandidaat.strip().encode(), self._token.encode())


async def _json_body(request: Request) -> dict | None:
    """Lees de JSON-body; None bij onleesbare of niet-object-JSON."""
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


async def gezondheid(request: Request) -> JSONResponse:
    """GET /api/gezondheid — status, versie en broncodes van de actieve adapters."""
    bronnen = sorted(a.bron for a in actieve_adapters(request.app.state.env))
    return JSONResponse({"status": "ok", "versie": _versie(), "bronnen": bronnen})


async def zoek_identifier(request: Request) -> JSONResponse:
    """POST /api/zoek-identifier — fan-out van de identifier over de actieve adapters.

    Zelfde doorstroom als de MCP-tool ``zoek_op_identifier``: enkel wat de adapters
    effectief teruggeven, met per treffer het VENA-verwijzingsvoorstel ingevuld.
    """
    body = await _json_body(request)
    identifier = (body or {}).get("identifier")
    if not isinstance(identifier, str) or not identifier.strip():
        return JSONResponse({"fout": "identifier ontbreekt"}, status_code=400)
    treffers = []
    for adapter in actieve_adapters(request.app.state.env):
        treffers.extend(adapter.zoek_op_identifier(identifier.strip()))
    _met_verwijzing(treffers)
    return JSONResponse({"treffers": [t.model_dump(mode="json") for t in treffers]})


async def haal(request: Request) -> JSONResponse:
    """POST /api/haal — integrale tekst van één uitspraak via de bron-URL.

    Zelfde semantiek als de MCP-tool ``haal_uitspraak``: geen actieve adapter met die
    broncode, of een adapter die ``None`` teruggeeft, betekent 404 "niets gevonden".
    """
    body = await _json_body(request)
    url = (body or {}).get("url")
    bron = (body or {}).get("bron")
    if not isinstance(url, str) or not url.strip() or not isinstance(bron, str) or not bron.strip():
        return JSONResponse({"fout": "url of bron ontbreekt"}, status_code=400)
    for adapter in actieve_adapters(request.app.state.env):
        if adapter.bron == bron.strip():
            uitspraak = adapter.haal_uitspraak(url.strip())
            if uitspraak is None:
                break
            _met_verwijzing([uitspraak.treffer])
            return JSONResponse(
                {"treffer": uitspraak.treffer.model_dump(mode="json"), "tekst": uitspraak.tekst}
            )
    return JSONResponse({"fout": "niets gevonden"}, status_code=404)


def _cors_origins(env: Mapping[str, str]) -> list[str]:
    """Toegelaten origins: uit ``RECHTSPRAAK_MCP_CORS_ORIGINS`` of de localhost-defaults."""
    ruw = env.get(ENV_CORS_ORIGINS, "")
    origins = [stuk.strip() for stuk in ruw.split(",") if stuk.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def maak_app(env: Mapping[str, str] | None = None) -> Starlette:
    """Bouw de Starlette-app. ``env`` is injecteerbaar voor tests (default os.environ).

    De meegegeven ``env`` wordt ook op ``app.state.env`` bewaard en per request aan
    ``actieve_adapters()`` doorgegeven, zodat de hele app (auth, CORS én
    bronconfiguratie) uit één omgeving leest.
    """
    if env is None:
        env = os.environ

    # CORS als buitenste laag, zodat een preflight (OPTIONS) nooit op de
    # token-controle botst; de browser stuurt bij een preflight immers geen
    # Authorization-header mee.
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=_cors_origins(env),
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )
    ]
    token = env.get(ENV_API_TOKEN, "").strip()
    if token:
        middleware.append(Middleware(BearerTokenMiddleware, token=token))

    app = Starlette(
        routes=[
            Route("/api/gezondheid", gezondheid, methods=["GET"]),
            Route("/api/zoek-identifier", zoek_identifier, methods=["POST"]),
            Route("/api/haal", haal, methods=["POST"]),
        ],
        middleware=middleware,
    )
    app.state.env = env
    return app


def main() -> None:
    """Start de REST-API met uvicorn (entry point ``rechtspraak-mcp-http``).

    Bindt standaard op 127.0.0.1:8765 — bewust niet 0.0.0.0. Publiek openzetten
    zonder ``RECHTSPRAAK_MCP_API_TOKEN`` en zonder TLS is onverantwoord (zie
    moduledocstring, "Beveiliging").
    """
    import uvicorn

    host = os.environ.get(ENV_HTTP_HOST, "127.0.0.1")
    poort = int(os.environ.get(ENV_HTTP_PORT, "8765"))
    uvicorn.run(maak_app(), host=host, port=poort)


if __name__ == "__main__":
    main()
