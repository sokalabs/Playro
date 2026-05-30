# App Prototype

This folder contains the first Playro product surfaces:

- `cli.py`: command-line prompt-to-Roblox-project generator.
- `api.py`: tiny local HTTP API prototype for future UI wiring.
- `batch_runner.py`: 24-hour continuous build loop processor enforcing safe provider routing.
- `continuous_runner.py` (in `scripts/`): backend batch runner for processing queued 24/7 autonomous generation jobs continuously. Explicitly relies on the global provider fallback chain and does not force unsafe providers/models.

Run CLI:

```bash
python3 -m product.roblox_ai_studio.app.cli "make an obby with coins and upgrades"
```

Run API:

```bash
python3 -m product.roblox_ai_studio.app.api
```

Run Batch Loop:

```bash
python3 -m product.roblox_ai_studio.app.batch_runner --limit 5
```

Start Continuous Background Runner (processes queued jobs):

```bash
PYTHONPATH=. python3 product/roblox_ai_studio/scripts/continuous_runner.py --ticks 10 --delay 2.0
```

The API intentionally does not import live personal Hermes gateway/config/tool registries. It is a product-local surface for the Roblox AI Studio prototype.

## Provider Bridge and Safe Defaults

The backend API and batch runners intentionally avoid hardcoding `cliproxyapi` + `gpt-5.5` model overrides on a per-task basis. Doing so breaks the orchestrator loop if that primary credential pool exhausts its cooldowns.

Instead, the product surface uses the user's configured global fallback chain. If the primary model drops, Hermes automatically fails over to `gpt-5.3-codex`, `gemini-3.1-pro-high`, or `moonshotai/kimi-k2.6`.

See `product.roblox_ai_studio.app.batch_runner` and `product/roblox_ai_studio/scripts/continuous_runner.py` for continuous autonomous tick execution that relies on this safe provider routing.
