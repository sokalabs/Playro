# Project Context: Playro

Playro is an open-source Roblox game-builder prototype. The user-facing desktop app is currently branded as Playro. It helps users turn Roblox game prompts into Rojo-ready projects using a product-local Hermes agent backend foundation.

## Identity

- Repository: `Playro`
- Product surface: desktop-first Roblox builder
- Backend foundation: Hermes agent runtime and supporting tooling
- Primary output: generated Roblox project folders with plans, manifests, Rojo mappings, and Luau source

## Product boundary

Allowed default product surface:

- Prompt intake for Roblox game ideas
- Roblox game planning
- Roblox project scaffolding
- Luau script/module generation
- Iteration and refinement loops
- Product-local skills and workflows
- Clean hooks for future Rojo, Roblox Studio, rbxmk, Wally, and Roblox Open Cloud integrations

Out of scope by default:

- Machine-specific runtime configuration
- Personal tool registries or private service integrations
- Broad unrelated assistant/plugin surfaces in the beginner build flow
- Generated release artifacts or local user data in source control

## Prototype target

A contributor should be able to clone the repository, launch the Electron desktop app, enter a Roblox game prompt, and receive a generated project folder with readable handoff files and starter Luau code.

CLI and API surfaces may exist for smoke tests and internal automation, but the visible product should remain a polished Roblox creation app rather than a terminal-first Hermes utility.
