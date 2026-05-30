# Hermes-Roblox

Hermes-Roblox is an open-source, desktop-first Roblox game builder. The desktop app, currently branded as **Playro**, turns a plain-language game idea into a Rojo-ready Roblox project with a build plan, manifest, Luau scripts, and handoff files for Roblox Studio.

The project uses a product-local Hermes agent backend as the runtime foundation for planning, generation, validation, and refinement. The visible product is the Roblox builder experience; the CLI and API are support layers for testing, automation, and desktop integration.

> Status: early public prototype. Expect rough edges, incomplete integrations, and fast-moving APIs.

## What it does

- Accepts a Roblox game prompt from the Electron desktop UI.
- Produces a readable game plan and build receipt.
- Generates Rojo project files and starter Luau source.
- Validates generated Roblox artifacts before handoff.
- Supports a deterministic smoke mode that does not require an LLM/API key.
- Can use the Hermes agent runtime when configured locally.

Generated projects include files such as:

```text
default.project.json
manifest.json
game_plan.md
wally.toml
src/ReplicatedStorage/GameConfig.lua
src/ServerScriptService/Main.server.lua
src/StarterPlayer/StarterPlayerScripts/HUD.client.lua
```

## Repository layout

```text
product/roblox_ai_studio/              Roblox builder backend, generator, app tests
product/roblox_ai_studio/desktop/      Electron desktop app and packaging scripts
product/playro_marketing_site/         Marketing site prototype
scripts/verify-playro-desktop-server.sh  Server-side verification workflow
agent/, tools/, gateway/, skills/      Hermes runtime foundation retained for backend work
```

## Requirements

- Python 3.11+
- Node.js 20+
- npm
- [Rojo](https://rojo.space/) (Required for syncing generated files into Roblox Studio)
- [Roblox Studio](https://create.roblox.com/)

## Quick start: desktop app

```bash
git clone https://github.com/sokalabs/Hermes-Roblox.git
cd Hermes-Roblox/product/roblox_ai_studio/desktop
npm install
npm run start
```

The Electron app starts the local Playro backend automatically and opens the desktop UI.

## Using with Roblox Studio

Once the Playro desktop app generates your project:
1. Open Roblox Studio and start a new baseplate template.
2. Ensure you have the **Rojo** plugin installed in your Roblox Studio.
3. Open a terminal in the generated project directory (the output directory of your game plan).
4. Run `rojo serve` to start the live sync server.
5. In Roblox Studio, click the Rojo plugin button and hit **Connect**.
6. The generated Luau source files and game configurations will sync instantly. Hit Play inside Studio to test your game!

## Configuration

Copy the example environment file if you want local overrides:

```bash
cp .env.example .env
```

Do not put real secrets in source control. The root `.gitignore` excludes `.env` and common secret/config files; `.env.example` should contain placeholders only.

Useful environment variables:

| Variable | Purpose |
| --- | --- |
| `PLAYRO_USE_HERMES_AGENT=0` | Use the deterministic local generator instead of the Hermes agent. Good for smoke tests. |
| `PLAYRO_USE_HERMES_AGENT=1` | Enable the Hermes-backed generation path when your local Hermes runtime is configured. |
| `PLAYRO_API_TOKEN` | Required for protected standalone API requests. The desktop app generates one automatically. |
| `HERMES_ROBLOX_API_HOST` / `HERMES_ROBLOX_API_PORT` | Local API bind host/port. Defaults to `127.0.0.1:8765`. |
| `PLAYRO_DATA_DIR` | Override where generated projects and backend state are written. |
| `PLAYRO_HERMES_BIN` | Override the Hermes executable used by the backend. |
| `PLAYRO_ROJO_BIN` | Override the Rojo executable used by desktop handoff checks. |

## CLI smoke test

This verifies Roblox artifact generation without requiring an API key or LLM call:

```bash
cd Hermes-Roblox
python -m product.roblox_ai_studio.app.cli \
  "make a colorful obby with checkpoints, coins, and a shop" \
  --output-root ./tmp/playro-smoke \
  --smoke \
  --json
```

## Backend API

For standalone API testing, set a local token and start the server:

```bash
cd Hermes-Roblox
PLAYRO_API_TOKEN=dev-local-token python -m product.roblox_ai_studio.app.api
```

Health check:

```bash
curl http://127.0.0.1:8765/health
```

Protected endpoints require the `X-Playro-API-Token` header.

## Validation

Recommended focused checks:

```bash
# Desktop static checks
npm --prefix product/roblox_ai_studio/desktop run check
npm --prefix product/roblox_ai_studio/desktop run smoke:static

# Python/Product tests
python -m pytest product/roblox_ai_studio/tests product/roblox_ai_studio/app/test_security_controls.py -q

# End-to-end server-side verification
scripts/verify-playro-desktop-server.sh
```

Some inherited Hermes tests cover broader agent/runtime surfaces and may require platform-specific tools or credentials.

## Security notes

- The backend binds to loopback by default.
- The desktop app generates a local API token for protected requests.
- Real provider credentials belong in your local environment or ignored `.env`, never in Git.
- Generated projects and packaged desktop outputs are ignored by default.

If you find a vulnerability, please report it privately using GitHub Security Advisories instead of opening a public issue.

## Contributing

Community contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.

## License

MIT. See [`LICENSE`](LICENSE).
