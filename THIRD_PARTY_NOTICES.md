# Third-Party Notices

Playro is MIT licensed. Runtime dependencies are installed through package managers or local tool installers and are not vendored into this repository.

The public source tree intentionally does not ship:

- Python standalone runtime binaries.
- Rojo executable binaries.
- Generated Electron desktop builds.
- Inherited Hermes skill packs pending individual license and product-scope review.
- Inherited Hermes plugin backends, including Spotify, Google Meet, Google Chat, Microsoft Teams, model-provider plugin profiles, memory provider plugins, and generated dashboard bundles.

Some retained Hermes runtime support files reference optional external services such as Slack, DingTalk, Vercel, Spotify, Firecrawl, and Camofox for local user-configured integrations. Playro does not vendor their SDKs, binaries, assets, credentials, or generated outputs in this repository; their names and marks belong to their respective owners.

If future work adds third-party source code, generated assets, or binary tools directly to the repository, include the upstream license, attribution, version/source URL, and a short reason it must be vendored.
