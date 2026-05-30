#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP="$ROOT/product/roblox_ai_studio/desktop"
ARTIFACT_ROOT="$ROOT/product/roblox_ai_studio/artifacts/server-build-verify"
CLI_OUT="$ARTIFACT_ROOT/cli-smoke"
LOG_DIR="$ARTIFACT_ROOT/logs"
SUMMARY="$ARTIFACT_ROOT/summary.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"
API_PORT="${HERMES_ROBLOX_API_PORT:-18765}"
SMOKE_PORT="${ROBLOX_AI_STUDIO_SMOKE_PORT:-19876}"

mkdir -p "$CLI_OUT" "$LOG_DIR"
: > "$SUMMARY"

log() {
  printf '\n==> %s\n' "$*" | tee -a "$SUMMARY"
}

run() {
  local name="$1"
  shift
  log "$name"
  printf '$ %q' "$@" | tee -a "$SUMMARY"
  printf '\n' | tee -a "$SUMMARY"
  "$@" 2>&1 | tee "$LOG_DIR/${name//[^A-Za-z0-9_.-]/_}.log"
}

run_in_desktop() {
  local name="$1"
  shift
  log "$name"
  (cd "$DESKTOP" && printf '$ %q' "$@" && printf '\n') | tee -a "$SUMMARY"
  (cd "$DESKTOP" && "$@") 2>&1 | tee "$LOG_DIR/${name//[^A-Za-z0-9_.-]/_}.log"
}

cleanup() {
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

log "Playro server-side desktop build/verification workflow"
printf 'Root: %s\nDesktop: %s\nArtifacts: %s\n' "$ROOT" "$DESKTOP" "$ARTIFACT_ROOT" | tee -a "$SUMMARY"

if [[ ! -d "$DESKTOP" ]]; then
  echo "Missing desktop app: $DESKTOP" >&2
  exit 1
fi

if [[ ! -d "$DESKTOP/node_modules" ]]; then
  if [[ -f "$DESKTOP/package-lock.json" ]]; then
    run_in_desktop "npm ci" npm ci
  else
    run_in_desktop "npm install" npm install
  fi
else
  log "npm dependencies present; skipping install"
fi

run_in_desktop "desktop static syntax checks" npm run check
run_in_desktop "desktop static product smoke" npm run smoke:static
run_in_desktop "desktop sidebar fake-DOM smoke" node scripts/sidebar-button-smoke.js
run_in_desktop "desktop handoff fake-DOM smoke" node scripts/handoff-smoke.js
run_in_desktop "desktop refinement flow smoke" node scripts/refinement-flow-smoke.js
run_in_desktop "desktop SSE completion smoke" node scripts/sse-completion-smoke.js

log "desktop Chromium runtime smoke (skip only when browser/display unavailable)"
if PLAYRO_RUNTIME_SMOKE_ALLOW_BROWSER_SKIP=1 ROBLOX_AI_STUDIO_SMOKE_PORT="$SMOKE_PORT" \
  npm --prefix "$DESKTOP" run smoke:runtime 2>&1 | tee "$LOG_DIR/desktop_runtime_smoke.log"; then
  echo "runtime smoke completed; check report for browserSkipped flag" | tee -a "$SUMMARY"
else
  echo "runtime smoke failed even with browser-skip enabled" >&2
  exit 1
fi

log "backend API health smoke"
PLAYRO_USE_HERMES_AGENT=0 PLAYRO_DATA_DIR="$CLI_OUT/api-data" HERMES_ROBLOX_API_PORT="$API_PORT" \
  "$PYTHON_BIN" -m product.roblox_ai_studio.app.api > "$LOG_DIR/backend_api.log" 2>&1 &
API_PID=$!
"$PYTHON_BIN" - <<PY | tee -a "$SUMMARY"
import json, time, urllib.request, sys
url = 'http://127.0.0.1:${API_PORT}/health'
last = None
for _ in range(40):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            body = response.read().decode('utf-8')
            print(body)
            payload = json.loads(body)
            if response.status == 200 and payload.get('ok'):
                sys.exit(0)
    except Exception as exc:
        last = exc
        time.sleep(0.25)
print(f'API health check failed: {last}', file=sys.stderr)
sys.exit(1)
PY
cleanup
unset API_PID

run "CLI smoke generation" env PLAYRO_USE_HERMES_AGENT=0 "$PYTHON_BIN" -m product.roblox_ai_studio.app.cli \
  "make a colorful obby with checkpoints, coins, and a shop" \
  --output-root "$CLI_OUT/generated-projects" --smoke --json

run "targeted Python tests" bash -lc '
set -Eeuo pipefail
PYTEST_FILES=(
  product/roblox_ai_studio/tests/test_generator.py
  product/roblox_ai_studio/tests/test_build_jobs.py
  product/roblox_ai_studio/tests/test_project_api.py
  product/roblox_ai_studio/tests/test_refine_generate.py
  product/roblox_ai_studio/tests/test_build_events.py
  product/roblox_ai_studio/app/test_security_controls.py
)
if command -v venv/bin/python >/dev/null 2>&1 && venv/bin/python -m pytest --version >/dev/null 2>&1; then
  PY=venv/bin/python
elif command -v .venv/bin/python >/dev/null 2>&1 && .venv/bin/python -m pytest --version >/dev/null 2>&1; then
  PY=.venv/bin/python
elif python3 -m pytest --version >/dev/null 2>&1; then
  PY=python3
elif command -v uv >/dev/null 2>&1; then
  PYTEST_ADDOPTS="" PLAYRO_USE_HERMES_AGENT=0 uv run --no-project --with pytest --with pytest-xdist python -m pytest "${PYTEST_FILES[@]}" -q
  exit $?
else
  echo "pytest unavailable and uv not found; cannot run targeted Python tests" >&2
  exit 1
fi
PYTEST_ADDOPTS="-m 'not integration'" PLAYRO_USE_HERMES_AGENT=0 "$PY" -m pytest "${PYTEST_FILES[@]}" -q
'

log "Workflow complete"
printf 'Summary: %s\nLogs: %s\nCLI artifacts: %s\nDesktop smoke artifacts: %s\n' \
  "$SUMMARY" "$LOG_DIR" "$CLI_OUT" "$ROOT/product/roblox_ai_studio/artifacts/desktop-smoke" | tee -a "$SUMMARY"
