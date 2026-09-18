#!/bin/zsh
# Copyright (c) 2026 Jef Seghers
# In licentie gegeven krachtens de EUPL
# SPDX-License-Identifier: EUPL-1.2
# Bouw de MCPB-bundel (dist/be-rechtspraak.mcpb) voor Claude Desktop.
# Vereist: uv, node/npx. De bundel zelf is een build-artefact en staat niet in git.
set -euo pipefail
setopt null_glob
HIER="${0:A:h}"
REPO="${HIER:h}"

cd "$REPO"
# Oude build-artefacten weg: anders kopieert de glob hieronder ook de wheels van vorige
# versies mee, en bevat de bundel meer dan één wheel.
rm -f dist/rechtspraak_mcp-*.whl dist/rechtspraak_mcp-*.tar.gz
uv build
rm -f "$HIER"/wheels/rechtspraak_mcp-*.whl
mkdir -p "$HIER/wheels"
cp dist/rechtspraak_mcp-*-py3-none-any.whl "$HIER/wheels/"
cp LICENSE "$HIER/LICENSE"  # EUPL-1.2 ook zichtbaar in de bundel zelf
npx --yes @anthropic-ai/mcpb validate "$HIER/manifest.json"
npx --yes @anthropic-ai/mcpb pack "$HIER" "$REPO/dist/be-rechtspraak.mcpb"
echo
echo "Klaar: $REPO/dist/be-rechtspraak.mcpb"
echo "Installeren: Claude Desktop → Instellingen → Extensies → 'Geavanceerde instellingen' → Extensie installeren…"
