# Supermemory Memory Provider

Semantic long-term memory with profile recall, semantic search, explicit memory tools, and session-end conversation ingest.

## Requirements

- `pip install supermemory`
- Supermemory API key from [supermemory.ai](https://supermemory.ai)

## Setup

```bash
hermes memory setup    # select "supermemory"
```

Or manually:

```bash
hermes config set memory.provider supermemory
echo 'SUPERMEMORY_API_KEY=***' >> ~/.hermes/.env
```

## Config

Config file: `$HERMES_HOME/supermemory.json`

| Key | Default | Description |
|-----|---------|-------------|
| `container_tag` | `hermes` | Base container tag prefix used for search and writes. The provider appends a hashed runtime scope derived from `user_id`, `agent_identity`, `agent_workspace`, or `session_id` so users/sessions do not share one Supermemory namespace. Supports `{identity}` in the base prefix. |
| `auto_recall` | `true` | Inject relevant memory context before turns |
| `auto_capture` | `true` | Store cleaned user-assistant turns after each response |
| `max_recall_results` | `10` | Max recalled items to format into context |
| `profile_frequency` | `50` | Include profile facts on first turn and every N turns |
| `capture_mode` | `all` | Skip tiny or trivial turns by default |
| `search_mode` | `hybrid` | Search mode: `hybrid` (profile + memories), `memories` (memories only), `documents` (documents only) |
| `entity_context` | built-in default | Extraction guidance passed to Supermemory |
| `api_timeout` | `5.0` | Timeout for SDK and ingest requests |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SUPERMEMORY_API_KEY` | API key (required) |
| `SUPERMEMORY_CONTAINER_TAG` | Override the base container tag prefix (takes priority over config file; runtime scoping is still enforced) |

## Tools

| Tool | Description |
|------|-------------|
| `supermemory_store` | Store an explicit memory |
| `supermemory_search` | Search memories by semantic similarity |
| `supermemory_forget` | Forget a memory by ID or best-match query |
| `supermemory_profile` | Retrieve persistent profile and recent context |

## Behavior

When enabled, Hermes can:

- prefetch relevant memory context before each turn
- store cleaned conversation turns after each completed response
- ingest the full session on session end for richer graph updates
- expose explicit tools for search, store, forget, and profile access

## Runtime-Scoped Containers

Supermemory container tags are always scoped at runtime. The configured `container_tag` is treated as a base prefix, and the provider appends a short hash built from the runtime isolation context:

- `user_id` when available for gateway/multi-user sessions
- `agent_identity` and `agent_workspace` for profile/workspace scoping
- `session_id` as a fallback when no principal/profile fields are available

This prevents different users or anonymous sessions from reading, poisoning, or deleting one another's memories even when they all use the default `hermes` base tag. Use `{identity}` in the base tag if you want the visible prefix to include the Hermes profile before the runtime scope is appended:

```json
{
  "container_tag": "hermes-{identity}"
}
```

For a profile named `coder`, the base prefix resolves to `hermes-coder` and is then runtime-scoped before any read, write, profile, forget, or conversation-ingest operation.

## Multi-Container Mode

For advanced setups (e.g. OpenClaw-style multi-workspace), you can enable custom container tags so the agent can read/write across multiple named containers:

```json
{
  "container_tag": "hermes",
  "enable_custom_container_tags": true,
  "custom_containers": ["project-alpha", "project-beta", "shared-knowledge"],
  "custom_container_instructions": "Use project-alpha for coding tasks, project-beta for research, and shared-knowledge for team-wide facts."
}
```

When enabled:
- `supermemory_search`, `supermemory_store`, `supermemory_forget`, and `supermemory_profile` accept an optional `container_tag` parameter
- The tag must be in the whitelist: primary base container + `custom_containers`
- Custom container names are aliases; each alias is resolved to the current runtime scope before Supermemory is called
- Automatic operations (turn sync, prefetch, memory write mirroring, session ingest) always use the **primary** scoped container only
- Custom container instructions are injected into the system prompt

## Support

- [Supermemory Discord](https://supermemory.link/discord)
- [support@supermemory.com](mailto:support@supermemory.com)
- [supermemory.ai](https://supermemory.ai)
