# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
"""Tests voor de REST-schil (rechtspraak_mcp/http_api.py).

Geen netwerk: elke test geeft een lege ``env`` mee (dus alle bronnen robots-conform uit)
en gebruikt als identifier een ECLI — de DBRC-adapter (wiens HEAD-probe ook zonder vlag
werkt) herkent dat formaat niet, en Juportal/RvS geven met ``sta_fetch = False`` per
definitie niets terug. Het gevulde pad wordt getest door ``actieve_adapters`` in de
http_api-module te monkeypatchen met een nepadapter op vaste gegevens.
"""
from __future__ import annotations

from datetime import date

import pytest
from starlette.testclient import TestClient

from rechtspraak_mcp import http_api
from rechtspraak_mcp.http_api import maak_app
from rechtspraak_mcp.schema import Treffer, Uitspraak

#: ECLI die geen enkele adapter offline tot een treffer brengt (zie moduledocstring).
ECLI = "ECLI:BE:CASS:2020:ARR.20201030.1N.4"

TOEGELATEN_ORIGIN = "https://localhost:3000"


def client(env: dict[str, str] | None = None) -> TestClient:
    """TestClient op een verse app met een geïnjecteerde (standaard lege) omgeving."""
    return TestClient(maak_app(env if env is not None else {}))


class NepAdapter:
    """Adapter op vaste gegevens, conform de interface uit adapters/base.py."""

    bron = "dbrc"
    instantie = "Raad voor Vergunningsbetwistingen"
    enabled = True

    def _treffer(self) -> Treffer:
        return Treffer(
            bron=self.bron,
            instantie=self.instantie,
            titel="RvVb-A-2223-0431",
            datum=date(2023, 1, 17),
            rolnummer="RvVb-A-2223-0431",
            url="https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf",
        )

    def zoek(self, query):
        return []

    def zoek_op_identifier(self, identifier):
        return [self._treffer()] if identifier == "RvVb-A-2223-0431" else []

    def haal_uitspraak(self, url):
        if url != self._treffer().url:
            return None
        return Uitspraak(treffer=self._treffer(), tekst="Integrale tekst van het arrest.")


@pytest.fixture
def nep_adapter(monkeypatch) -> NepAdapter:
    """Vervang de adapterfan-out in http_api door één nepadapter."""
    adapter = NepAdapter()
    monkeypatch.setattr(http_api, "actieve_adapters", lambda env=None: [adapter])
    return adapter


# ---------------------------------------------------------------------------
# GET /api/gezondheid
# ---------------------------------------------------------------------------


def test_gezondheid_geeft_status_versie_en_bronnen():
    r = client().get("/api/gezondheid")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "versie": "0.0.2",
        "bronnen": ["dbrc", "ehrm", "hvj", "juportal", "raadvanstate"],
    }


# ---------------------------------------------------------------------------
# POST /api/zoek-identifier
# ---------------------------------------------------------------------------


def test_zoek_identifier_leeg_zonder_bronnen():
    # Standaardconfiguratie: alle bronnen uit -> lege lijst, en zeker geen verzonnen
    # treffers (anti-hallucinatie). Een lege lijst is een geldig 200-antwoord.
    r = client().post("/api/zoek-identifier", json={"identifier": ECLI})
    assert r.status_code == 200
    assert r.json() == {"treffers": []}


def test_zoek_identifier_zonder_identifier_geeft_400():
    r = client().post("/api/zoek-identifier", json={})
    assert r.status_code == 400
    assert r.json() == {"fout": "identifier ontbreekt"}


def test_zoek_identifier_met_lege_identifier_geeft_400():
    r = client().post("/api/zoek-identifier", json={"identifier": "   "})
    assert r.status_code == 400
    assert r.json() == {"fout": "identifier ontbreekt"}


def test_zoek_identifier_met_onleesbare_body_geeft_400():
    r = client().post(
        "/api/zoek-identifier",
        content=b"geen json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 400
    assert r.json() == {"fout": "identifier ontbreekt"}


def test_zoek_identifier_gevuld_pad_met_verwijzing(nep_adapter):
    r = client().post("/api/zoek-identifier", json={"identifier": "RvVb-A-2223-0431"})
    assert r.status_code == 200
    treffers = r.json()["treffers"]
    assert len(treffers) == 1
    t = treffers[0]
    # Exacte pydantic-serialisatie: model_dump(mode="json"), datum als "YYYY-MM-DD".
    assert t["bron"] == "dbrc"
    assert t["instantie"] == "Raad voor Vergunningsbetwistingen"
    assert t["titel"] == "RvVb-A-2223-0431"
    assert t["datum"] == "2023-01-17"
    assert t["ecli"] is None
    assert t["rolnummer"] == "RvVb-A-2223-0431"
    assert t["snippet"] is None
    assert t["url"].startswith("https://www.dbrc.be/")
    # De VENA-verwijzing wordt server-side ingevuld en meegeserialiseerd.
    assert t["verwijzing"].startswith("RvVb 17 januari 2023, nr. RvVb-A-2223-0431, ")
    assert set(t) == {
        "bron",
        "instantie",
        "titel",
        "datum",
        "ecli",
        "rolnummer",
        "snippet",
        "url",
        "verwijzing",
    }


# ---------------------------------------------------------------------------
# POST /api/haal
# ---------------------------------------------------------------------------


def test_haal_zonder_url_of_bron_geeft_400():
    for body in ({}, {"url": "https://example.org"}, {"bron": "dbrc"}, {"url": "", "bron": "dbrc"}):
        r = client().post("/api/haal", json=body)
        assert r.status_code == 400, body
        assert r.json() == {"fout": "url of bron ontbreekt"}


def test_haal_niets_gevonden_geeft_404(nep_adapter):
    # De adapter geeft None terug (onbekende URL) -> 404, geen verzonnen tekst.
    r = client().post("/api/haal", json={"url": "https://www.dbrc.be/onbekend.pdf", "bron": "dbrc"})
    assert r.status_code == 404
    assert r.json() == {"fout": "niets gevonden"}


def test_haal_onbekende_bron_geeft_404(nep_adapter):
    r = client().post("/api/haal", json={"url": "https://example.org/x.pdf", "bron": "bestaatniet"})
    assert r.status_code == 404
    assert r.json() == {"fout": "niets gevonden"}


def test_haal_gevuld_pad(nep_adapter):
    url = "https://www.dbrc.be/sites/default/files/2023-01/RVVB.A.2223.0431.pdf"
    r = client().post("/api/haal", json={"url": url, "bron": "dbrc"})
    assert r.status_code == 200
    data = r.json()
    assert data["tekst"] == "Integrale tekst van het arrest."
    assert data["treffer"]["url"] == url
    assert data["treffer"]["datum"] == "2023-01-17"
    assert data["treffer"]["verwijzing"].startswith("RvVb 17 januari 2023, ")


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_headers_voor_toegelaten_origin():
    r = client().get("/api/gezondheid", headers={"Origin": TOEGELATEN_ORIGIN})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == TOEGELATEN_ORIGIN


def test_cors_preflight_voor_toegelaten_origin():
    r = client().options(
        "/api/zoek-identifier",
        headers={
            "Origin": TOEGELATEN_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == TOEGELATEN_ORIGIN
    assert "POST" in r.headers["access-control-allow-methods"]


def test_cors_weigert_vreemde_origin():
    r = client().get("/api/gezondheid", headers={"Origin": "https://kwaadaardig.example"})
    # Het antwoord zelf blijft 200 (CORS is een browserbescherming), maar zonder
    # allow-origin-header zal de browser het antwoord niet vrijgeven.
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_cors_origins_configureerbaar_via_env():
    c = client({"RECHTSPRAAK_MCP_CORS_ORIGINS": "https://voorbeeld.be, https://ander.be"})
    r = c.get("/api/gezondheid", headers={"Origin": "https://voorbeeld.be"})
    assert r.headers["access-control-allow-origin"] == "https://voorbeeld.be"
    # De localhost-defaults gelden dan niet meer.
    r2 = c.get("/api/gezondheid", headers={"Origin": TOEGELATEN_ORIGIN})
    assert "access-control-allow-origin" not in r2.headers


# ---------------------------------------------------------------------------
# Authenticatie (bearer-token)
# ---------------------------------------------------------------------------


def test_zonder_token_env_geen_auth_vereist():
    r = client().post("/api/zoek-identifier", json={"identifier": ECLI})
    assert r.status_code == 200


def test_met_token_env_is_bearer_verplicht():
    c = client({"RECHTSPRAAK_MCP_API_TOKEN": "geheim123"})
    r = c.post("/api/zoek-identifier", json={"identifier": ECLI})
    assert r.status_code == 401
    assert r.json() == {"fout": "authenticatie vereist"}


def test_met_token_env_wordt_fout_token_geweigerd():
    c = client({"RECHTSPRAAK_MCP_API_TOKEN": "geheim123"})
    r = c.post(
        "/api/zoek-identifier",
        json={"identifier": ECLI},
        headers={"Authorization": "Bearer fout"},
    )
    assert r.status_code == 401


def test_met_token_env_werkt_geldig_token():
    c = client({"RECHTSPRAAK_MCP_API_TOKEN": "geheim123"})
    r = c.post(
        "/api/zoek-identifier",
        json={"identifier": ECLI},
        headers={"Authorization": "Bearer geheim123"},
    )
    assert r.status_code == 200
    assert r.json() == {"treffers": []}
    r2 = c.post(
        "/api/haal",
        json={"url": "https://example.org/x.pdf", "bron": "dbrc"},
        headers={"Authorization": "Bearer geheim123"},
    )
    assert r2.status_code in (200, 404)  # auth passeert; inhoudelijk verder afgehandeld


def test_gezondheid_blijft_open_met_token_env():
    c = client({"RECHTSPRAAK_MCP_API_TOKEN": "geheim123"})
    r = c.get("/api/gezondheid")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_preflight_botst_niet_op_token():
    # Een browser-preflight draagt geen Authorization-header; de CORS-laag moet die
    # dus vóór de tokencontrole afhandelen.
    c = client({"RECHTSPRAAK_MCP_API_TOKEN": "geheim123"})
    r = c.options(
        "/api/zoek-identifier",
        headers={
            "Origin": TOEGELATEN_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == TOEGELATEN_ORIGIN
