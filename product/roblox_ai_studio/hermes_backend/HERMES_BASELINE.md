# Hermes Backend Baseline & Upstream Audit

Playro embeds a product-local Hermes agent runtime as its backend foundation.
This file records the vendored baseline and the result of auditing it against
upstream `NousResearch/hermes-agent`, so future updates have a documented
starting point instead of an inferred one.

## Vendored baseline

- **Vendored Hermes version:** `0.13.0` (release date `2026.5.7`)
- **Source of truth:** [`hermes_cli/__init__.py`](../../../hermes_cli/__init__.py)
  (`__version__ = "0.13.0"`, `__release_date__ = "2026.5.7"`).
- The vendored runtime tree lives at the repo root (`agent/`, `tools/`,
  `gateway/`, `cron/`, `providers/`, `hermes_cli/`, and the `hermes_*.py` /
  `run_agent.py` support files) and is retained as "source-based Hermes runtime
  support behind Playro boundaries". It is **not** part of the installable
  Playro package (`pyproject.toml` packages only `product`, `product.*`).

## How Playro couples to Hermes

The product integration is **decoupled through a stable CLI contract**, not by
importing vendored Hermes modules:

- [`agent_pipeline.py`](agent_pipeline.py) shells out to a product-local
  `hermes` binary: `hermes chat -q <prompt> -t <toolsets>`.
- The Hermes binary is resolved only from product-local paths
  (`PLAYRO_HERMES_BIN`, `PLAYRO_HERMES_HOME`, or a product venv); the live/global
  install is never used unless `PLAYRO_ALLOW_PATH_HERMES` is explicitly opted in.
- Exposed toolsets are an explicit allowlist: `file`, `skills`, `fact_store`
  (with `terminal`, `cronjob`, `session_search`, `memory`, `todo` denied).
- No file under `product/` imports `agent`, `hermes_cli`, `gateway`, `cron`,
  `providers`, `tools`, or the root `hermes_*` modules. (Verified by grep.)

Because of this boundary, the upstream agent-module refactor and most v0.14/v0.15
feature work do **not** change Playro's product code as long as the
`hermes chat -t` CLI contract holds (upstream notes confirm the v0.15.0 `agent/*`
refactor preserved backward compatibility for external callers).

## Upstream audit — 2026-05-30

- **Latest upstream tag checked:** `v0.15.2` / `v2026.5.29.2` (packaging hotfix),
  reviewing the `v0.15.0` "Velocity" line and `v0.15.1` hotfix, plus `v0.14.0`.
- Source: GitHub Releases for `NousResearch/hermes-agent`.

| Upstream area (v0.14 → v0.15.2) | Playro impact | Rationale |
| --- | --- | --- |
| Agent module refactor (`run_agent.py` → `agent/*`, v0.15.0) | **Not applicable** | Product does not import vendored modules; couples via `hermes chat` CLI, which stayed backward compatible. |
| MCP command resolution / tool catalog (`npx/npm/node` → `/usr/local/bin`, Nous MCP catalog) | **Not applicable** | Docker-specific; product uses no MCP and passes an explicit `-t` toolset allowlist. |
| Skills / catalog (skills.sh 19,932 entries, skill bundles, Skills Hub) | **Not applicable** | Product ships only native Playro skills; `restored_skills` is empty by policy. |
| Provider / `/model` picker unification, Bitwarden secrets | **Not applicable** | Product has its own self-contained `provider_bridge`; does not call `hermes model` or import provider plugins. |
| Dashboard / API / auth / loopback / `--insecure` (v0.15.1) | **Not applicable** | Playro ships its own loopback-default, token-gated API server (`app/api.py`), not the Hermes dashboard. |
| Docker / `HERMES_DASHBOARD_INSECURE` / env | **Not applicable** | Playro ships no Docker image or dashboard. |
| Redaction / promptware defense (v0.15.0); web-URL redaction passthrough (v0.15.1) | **Not applicable** | Product has independent secret/path redaction in `agent_pipeline.py`; it intentionally does **not** adopt the upstream web-URL passthrough behavior. |
| Packaging: bundled `plugin.yaml` manifests in wheel/sdist (v0.15.2) | **Not applicable** | Repo ships no `plugin.yaml` and does not build a `hermes-agent` wheel. |

**Conclusion:** No changes are required to Playro's product-local Hermes
integration for upstream `v0.15.2`. The relevant upstream work is either
out of the documented Playro product scope (messaging, Docker, dashboard,
Kanban, secrets, MCP) or already covered by Playro's own product-local
implementations (provider routing, API auth, redaction, skill catalog).

## When to revisit

Re-run this audit and update the table if any of these become true:

1. Playro's product-local `hermes` binary is upgraded to a newer Hermes line,
   especially if the `hermes chat -q ... -t ...` flag surface changes.
2. Playro begins importing vendored `agent/*` or `hermes_cli/*` modules directly
   instead of shelling out.
3. Playro starts shipping a Hermes dashboard, Docker image, MCP catalog, or
   `plugin.yaml` manifests.
