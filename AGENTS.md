# Agent Instructions for Hermes-Roblox

Read this file and `PROJECT_CONTEXT.md` before making changes.

Hermes-Roblox is a Roblox game-builder prototype built on a product-local Hermes agent backend. Keep work inside this repository unless explicitly told otherwise.

## Product rules

1. Roblox game creation is the product center.
2. The desktop app is the primary shipped prototype surface.
3. Hermes is the backend/runtime foundation, not the visible product identity.
4. CLI/API surfaces support testing, automation, and backend integration only.
5. Do not import live personal Hermes configuration or machine-specific tool registries.
6. Do not add machine-specific infrastructure or server-management behavior to the product scope.
7. Prefer minimal Roblox-focused toolsets and explicit allowlists.
8. Keep generated prototype and desktop assets under `product/roblox_ai_studio/` or documented project-local directories.
9. Clearly label stubs and mock integrations.
10. Keep this repository separate from unrelated Roblox or Hermes experiments.

## Useful commands

| Purpose | Command |
| --- | --- |
| Desktop static checks | `npm --prefix product/roblox_ai_studio/desktop run check` |
| Desktop static smoke | `npm --prefix product/roblox_ai_studio/desktop run smoke:static` |
| CLI smoke | `python -m product.roblox_ai_studio.app.cli "make a colorful obby" --output-root ./tmp/playro-smoke --smoke --json` |
| Backend API | `python -m product.roblox_ai_studio.app.api` |
| Focused Python tests | `python -m pytest product/roblox_ai_studio/tests product/roblox_ai_studio/app/test_security_controls.py -q` |
| Server verification | `scripts/verify-playro-desktop-server.sh` |

## Public-release hygiene

- Never commit real `.env` values, API keys, tokens, signing certificates, local databases, or generated builds.
- Keep `.env.example` placeholder-only.
- Avoid adding full local machine paths to source, docs, logs, or release artifacts.
- Keep beginner-facing Playro UI simple; put advanced/developer controls in Setup or Settings.
- Prefer explicit allowlists when exposing Hermes tools through Playro.
