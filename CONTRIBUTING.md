# Contributing to Playro

Thanks for your interest in contributing. Playro is an early public prototype focused on Roblox game creation through a desktop-first builder experience.

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Product direction

Please keep contributions aligned with the project scope:

- Roblox game creation is the primary product focus.
- The Electron desktop app is the main user-facing surface.
- Hermes agent code is the backend/runtime foundation, not the visible product identity.
- CLI and API surfaces support testing, automation, and desktop integration.
- Avoid adding machine-specific infrastructure, private service assumptions, or broad unrelated tool surfaces to the default Playro flow.

## Getting started

1. Fork and clone the repository.
2. Install desktop dependencies:

   ```bash
   cd product/roblox_ai_studio/desktop
   npm install
   ```

3. Run the desktop app:

   ```bash
   npm run start
   ```

4. Run a no-key CLI smoke test from the repo root:

   ```bash
   python -m product.roblox_ai_studio.app.cli \
     "make a colorful obby" \
     --output-root ./tmp/playro-smoke \
     --smoke \
     --json
   ```

## Development checks

Run the most relevant checks for the files you changed:

```bash
npm --prefix product/roblox_ai_studio/desktop run check
npm --prefix product/roblox_ai_studio/desktop run smoke:static
python -m pytest product/roblox_ai_studio/tests product/roblox_ai_studio/app/test_security_controls.py -q
```

For broader verification, run:

```bash
scripts/verify-playro-desktop-server.sh
```

## Architecture hints & where to start

For first-time contributors, Playro is split into a few key areas:
- **`product/roblox_ai_studio/desktop/`**: The frontend UI (Electron + React/TypeScript). Start here if you want to improve the look and feel or user experience of the Playro app.
- **`product/roblox_ai_studio/roblox/`**: Contains the internal Roblox project generation logic, Luau code templates, and Rojo manifests. Start here if you want to teach Playro how to generate new types of games (like RPGs, Tycoons, or Shooters).
- **`product/roblox_ai_studio/hermes_backend/`**: The Python communication layer connecting the desktop app to the Hermes AI agent. Start here if you want to add new LLM capabilities, refine code validation, or change the API layer.

If you're looking for a first issue, check out the issue tracker for "good first issue" tags, or try improving a Luau code template in the `roblox/` directory.

## Pull request guidelines

- Keep PRs focused and explain the user-facing change.
- Include screenshots or short recordings for visible desktop UI changes when helpful.
- Add or update tests for behavior changes.
- Update documentation when setup, configuration, commands, or generated outputs change.
- Do not commit generated desktop builds, generated Roblox projects, local databases, logs, or cache directories.
- Do not commit secrets. Use `.env` for local values and keep `.env.example` placeholder-only.

## Security-sensitive changes

For changes touching agent execution, file access, subprocesses, Electron IPC, local HTTP APIs, generated Luau, or package/release automation:

- Prefer explicit allowlists over broad access.
- Keep local servers bound to loopback unless there is a documented reason not to.
- Treat generated Luau and Rojo mappings as executable output that users must be able to review.
- Avoid printing secrets, full local paths, or raw provider responses in logs/artifacts.
- If you find a vulnerability, report it privately through GitHub Security Advisories rather than a public issue.

## Commit style

Use short, imperative commit subjects, for example:

```text
Add Rojo validation for generated projects
```

A body is optional; include one only when it adds useful context.
