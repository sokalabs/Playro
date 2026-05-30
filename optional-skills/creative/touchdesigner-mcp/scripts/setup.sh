#!/usr/bin/env bash
# setup.sh — Automated setup for twozero MCP plugin for TouchDesigner
# Idempotent: safe to run multiple times.
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
OK="${GREEN}✔${NC}"; FAIL="${RED}✘${NC}"; WARN="${YELLOW}⚠${NC}"

TWOZERO_URL="https://www.404zero.com/pisang/twozero.tox"
TOX_PATH="$HOME/Downloads/twozero.tox"
# Required before setup.sh will download or accept a cached twozero.tox.
# Example: TWOZERO_TOX_SHA256=<trusted sha256> ./setup.sh
TWOZERO_TOX_SHA256="${TWOZERO_TOX_SHA256:-}"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
HERMES_CFG="${HERMES_HOME_DIR}/config.yaml"
MCP_PORT=40404
MCP_ENDPOINT="http://localhost:${MCP_PORT}/mcp"

manual_steps=()

echo -e "\n${CYAN}═══ twozero MCP for TouchDesigner — Setup ═══${NC}\n"

# ── 1. Check if TouchDesigner is running ──
# Match on process *name* (not full cmdline) to avoid self-matching shells
# that happen to have "TouchDesigner" in their args. macOS and Linux pgrep
# both support -x for exact name match.
if pgrep -x TouchDesigner >/dev/null 2>&1 || pgrep -x TouchDesignerFTE >/dev/null 2>&1; then
    echo -e " ${OK} TouchDesigner is running"
    td_running=true
else
    echo -e " ${WARN} TouchDesigner is not running"
    td_running=false
fi

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        echo ""
    fi
}

verify_tox() {
    local file="$1"

    if [[ -z "$TWOZERO_TOX_SHA256" ]]; then
        return 2
    fi

    local actual
    actual=$(sha256_file "$file")
    if [[ -z "$actual" ]]; then
        return 3
    fi

    [[ "$(printf '%s' "$actual" | tr '[:upper:]' '[:lower:]')" == "$(printf '%s' "$TWOZERO_TOX_SHA256" | tr '[:upper:]' '[:lower:]')" ]]
}

# ── 2. Ensure twozero.tox exists and is integrity-checked ──
if [[ -f "$TOX_PATH" ]]; then
    if verify_tox "$TOX_PATH"; then
        echo -e " ${OK} twozero.tox exists at ${TOX_PATH} and matches TWOZERO_TOX_SHA256"
    else
        rc=$?
        if [[ "$rc" -eq 2 ]]; then
            echo -e " ${FAIL} twozero.tox exists at ${TOX_PATH}, but TWOZERO_TOX_SHA256 is not set"
            manual_steps+=("Set TWOZERO_TOX_SHA256 to a trusted SHA-256 digest before installing ${TOX_PATH}")
        elif [[ "$rc" -eq 3 ]]; then
            echo -e " ${FAIL} Could not find sha256sum or shasum to verify ${TOX_PATH}"
            manual_steps+=("Install sha256sum or shasum, then re-run setup.sh")
        else
            echo -e " ${FAIL} twozero.tox at ${TOX_PATH} does not match TWOZERO_TOX_SHA256"
            manual_steps+=("Replace ${TOX_PATH} with a trusted twozero.tox that matches TWOZERO_TOX_SHA256")
        fi
    fi
else
    mkdir -p "$(dirname "$TOX_PATH")"
    if [[ -z "$TWOZERO_TOX_SHA256" ]]; then
        echo -e " ${WARN} twozero.tox not found — automatic download skipped because TWOZERO_TOX_SHA256 is not set"
        manual_steps+=("Download twozero.tox from a trusted source, place it at ${TOX_PATH}, set TWOZERO_TOX_SHA256, and re-run setup.sh")
    else
        echo -e " ${WARN} twozero.tox not found — downloading for SHA-256 verification..."
        tmp_tox=$(mktemp "${TOX_PATH}.download.XXXXXX")
        if curl -fSL -o "$tmp_tox" "$TWOZERO_URL" 2>/dev/null && verify_tox "$tmp_tox"; then
            mv "$tmp_tox" "$TOX_PATH"
            echo -e " ${OK} Downloaded and verified twozero.tox at ${TOX_PATH}"
        else
            rm -f "$tmp_tox"
            echo -e " ${FAIL} Failed to download and verify twozero.tox from ${TWOZERO_URL}"
            manual_steps+=("Download a trusted twozero.tox to ${TOX_PATH} and verify it against TWOZERO_TOX_SHA256")
        fi
    fi
fi

# ── 3. Inspect Hermes config without enabling unauthenticated MCP trust ──
if [[ ! -f "$HERMES_CFG" ]]; then
    echo -e " ${WARN} Hermes config not found at ${HERMES_CFG}"
    manual_steps+=("Create ${HERMES_CFG} and add twozero_td only after you trust the local TouchDesigner MCP endpoint")
elif grep -q 'twozero_td' "$HERMES_CFG" 2>/dev/null; then
    echo -e " ${OK} twozero_td MCP entry exists in Hermes config"
else
    echo -e " ${WARN} twozero_td MCP entry is not configured"
    echo "       setup.sh will not persist enabled trust for an unauthenticated localhost MCP endpoint."
    manual_steps+=("Manually add twozero_td to ${HERMES_CFG} only after verifying TouchDesigner owns ${MCP_ENDPOINT}")
    manual_steps+=("Restart Hermes session after manually adding/enabling the twozero_td MCP server")
fi

# ── 4. Test if MCP port is responding ──
if nc -z 127.0.0.1 "$MCP_PORT" 2>/dev/null; then
    echo -e " ${OK} Port ${MCP_PORT} is open"

    # ── 5. Verify MCP endpoint responds ──
    resp=$(curl -s --max-time 3 "$MCP_ENDPOINT" 2>/dev/null || true)
    if [[ -n "$resp" ]]; then
        echo -e " ${OK} MCP endpoint responded at ${MCP_ENDPOINT}"
    else
        echo -e " ${WARN} Port open but MCP endpoint returned empty response"
        manual_steps+=("Verify MCP is enabled in twozero settings")
    fi
else
    echo -e " ${WARN} Port ${MCP_PORT} is not open"
    if [[ "$td_running" == true ]]; then
        manual_steps+=("In TD: drag twozero.tox into network editor → click Install")
        manual_steps+=("Enable MCP: twozero icon → Settings → mcp → 'auto start MCP' → Yes")
    else
        manual_steps+=("Launch TouchDesigner")
        manual_steps+=("Drag twozero.tox into the TD network editor and click Install")
        manual_steps+=("Enable MCP: twozero icon → Settings → mcp → 'auto start MCP' → Yes")
    fi
fi

# ── Status Report ──
echo -e "\n${CYAN}═══ Status Report ═══${NC}\n"

if [[ ${#manual_steps[@]} -eq 0 ]]; then
    echo -e " ${OK} ${GREEN}Fully configured! twozero MCP is ready to use.${NC}\n"
    exit 0
else
    echo -e " ${WARN} ${YELLOW}Manual steps remaining:${NC}\n"
    for i in "${!manual_steps[@]}"; do
        echo -e "   $((i+1)). ${manual_steps[$i]}"
    done
    echo ""
    exit 1
fi
