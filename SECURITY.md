# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability. Report suspected vulnerabilities privately through GitHub Security Advisories:

https://github.com/sokalabs/Playro/security/advisories/new

Include as much detail as you can safely provide:

- affected component and file paths
- reproduction steps or proof of concept
- expected vs. actual behavior
- impact and affected platform
- relevant logs with secrets redacted

## Supported versions

This project is an early public prototype. Security fixes are targeted at the current default branch unless a release branch is explicitly documented.

## Security model

Playro is a local-first Roblox builder. The desktop app starts a local backend API that binds to loopback by default and uses a per-session API token for protected requests. Generated Roblox projects are written to local disk for review and handoff to Rojo/Roblox Studio.

Important boundaries:

- Real API keys and provider tokens must stay in local environment variables or ignored `.env` files.
- The Electron renderer should communicate with the backend only through the documented local API and preload bridge.
- Generated Luau and Rojo mappings are executable project output and should remain reviewable by the user.
- Hermes agent/tool execution can be powerful; keep product defaults narrow and Roblox-focused.

## Non-goals

The project cannot protect secrets that are intentionally committed to Git, shared in public issues, or exposed through user-installed third-party tools. Please rotate any credential that may have been exposed.
