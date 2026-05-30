# Playro Desktop

Electron desktop shell for the Playro Roblox game builder.

## Local checks

```bash
cd product/roblox_ai_studio/desktop
npm run check
npm run smoke
npm run build:win
npm run verify:packaged
npm run release:manifest
npm run release:notes
npm run release:sell-check
# For production direct-download EXEs, use npm run release:win:production instead of build:win:test.
```

`refinement-flow-smoke.js` exercises the important submit loop without a live backend:

1. render the landing prompt box,
2. submit a first prompt,
3. submit a follow-up refinement from the refinement box,
4. assert the refinement is appended as a user message and shown as a preview-only refinement if the backend is unavailable.

Smoke artifacts are written under `product/roblox_ai_studio/artifacts/desktop-smoke/`.

`npm run smoke` requires Chrome, Edge, or Chromium for rendered desktop proof. Set `PLAYRO_BROWSER_BIN` if the browser is installed outside the default paths.

## Windows acceptance notes

The 1280x800 Windows/RDP test viewport has limited vertical room. The landing page uses compact responsive top padding so the prompt box and Build Roblox Project CTA remain visible/clickable in that viewport.

For live proof runs, use `TESTING_WINDOWS11.md` on a real Windows 11 desktop or disposable test VM. Keep VM controller tooling outside the Playro product docs unless it is checked into this repo and documented as a product-local test harness.
