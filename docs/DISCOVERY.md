# AgentHost UI — Discovery (2026-07-24)

## Confidence labels

- **VERIFIED**: observed directly from files, Git, Docker, or a live local endpoint.
- **INFERRED**: strongly implied by verified wiring, but not independently proven.
- **UNVERIFIED**: not checked or not available.
- **NOT_FOUND**: searched in the scoped locations and not found.

## Verified topology

| Area | Finding | Evidence |
|---|---|---|
| Website code | `ui` repository at `/root/ui` | Git worktree and `origin` remote |
| Remote | `https://github.com/Hossein10000/ui.git` | `git remote -v` |
| Branch | `main`, one local commit ahead of `origin/main`; worktree has uncommitted changes | `git status`, `git log` |
| Runtime | Python 3.12 `ui-dashboard` container | `/root/ui/docker-compose.yml`, Docker inspect |
| Public route | `agenthost.tech/ui` and `ui.agenthost.tech` | Traefik labels in Compose |
| Authentication | Authelia middleware on the UI route | Traefik labels; public HEAD redirects to `auth.agenthost.tech` |
| UI network | `traefik_default`; UI address observed as `172.16.7.7` | Docker network inspect |
| Hermes | `hermes-agent-8yvs-hermes-agent-1`, internal API at port 8642 | Docker inspect and UI `HERMES_UPSTREAM` |
| Inbox storage | File-backed JSON/items, files, uploads, and upload metadata | `/root/platform-gateway/results-data`, `/root/ui/server.py` |
| Chat | UI creates/loads a Hermes session and uses `/api/chat` and `/api/chat/history` | `/root/ui/server.py`, live local endpoint returned 200 |
| Results API | Separate source exists at `/root/platform-gateway/results-api/server.py`; UI currently reads the shared results directory directly | Source inspection |
| GitHub Projects | User has projects `ui`, `UI Design for agenthost.tech` (two), `ui-test-shim`, and `Hermes Server Engineering` | `gh project list` |
| GitHub repositories | `Hossein10000/ui`, `Aiagent`, `copilot-cli`, `hermes-v3-architecture` were returned | `gh api user/repos` |
| Obsidian | Hermes mount source is `/root/obsidian-vault`; it currently contains zero files | Docker inspect and `find` |
| Existing Obsidian sample | A separate `/root/obsidian-web/config/Obsidian Vault` contains one sample note; it is not the mounted Hermes vault | Read-only filesystem inspection |

## Current data flow

```text
Browser
  -> Traefik HTTPS + Authelia
  -> ui-dashboard:8080
  -> /api/chat -> Hermes session API -> configured model routing
  -> /api/inbox -> shared results-data/items + uploads
  -> /api/inbox/files/* -> shared results-data files/uploads
```

## Real versus absent

### Real and connected

- The current UI repository and running container.
- Hermes chat history and a working local health endpoint.
- Shared result JSON and file storage.
- Traefik routing and Authelia protection.
- Docker services for Hermes, Hermes WebUI, UI, FreeLLM, Local Gateway, Honcho, Qdrant, SearXNG, Traefik, Redis, PostgreSQL, and Authelia.

### Not established / not present in the scoped runtime

- No populated Obsidian vault in the path actually mounted into Hermes.
- No verified graph database, workflow queue, event bus, or dedicated workflow service.
- No verified GitHub write integration for the UI runtime.
- No verified file preview pipeline beyond direct browser download/open.
- No basis for graph nodes or edges beyond future source records; mock graph data is prohibited.

## Current UI gaps

- Workflow panel is presentation-level; no verified task execution API or durable workflow model was found.
- Inbox is real and file-backed, but normalization metadata (`source_type`, `source_id`, `last_verified_at`, `health_state`, `data_origin`) is not consistently enforced by the current API.
- File opening is implemented through same-origin URLs, but content preview is not a separate capability.
- The UI has no verified Obsidian graph endpoint because the mounted vault is empty.
- The Compose file contains an API credential inline; this is an operational security finding for a later, separately approved patch and is not changed in discovery.

## Architecture alternatives

### Minimal Integration

Reuse the existing Python UI, shared result storage, Hermes sessions, Traefik, and Authelia. Add a small read-only source/health contract and a workflow timeline derived only from existing result records. No new database or queue. Lowest risk and reversible; cannot provide a populated knowledge graph until the vault has data.

### Balanced Architecture

Keep the current UI and add a small versioned API layer for normalized artifacts, workflow runs, and source metadata, backed initially by the existing file store. Add adapters for Hermes and the actual Obsidian vault, and add graph extraction only when source notes exist. Promote to the existing PostgreSQL only when file-backed limits are demonstrated. Moderate effort and reversible.

### Full Personal AI OS

Introduce dedicated workflow persistence, event processing, artifact indexing, graph projection, semantic search, and richer frontend services. This would require new operational components and a populated knowledge source. It is not justified by the current empty vault and would increase attack surface and rollback cost.

## Decision

Choose **Minimal Integration first**, with a migration seam toward Balanced Architecture. The existing live connections are useful and working; the missing facts are data and contracts, not a missing database. The first vertical slice should make provenance explicit, expose real health/source state, and leave graph data empty rather than inventing it.

## Immediate vertical slice

1. Add a read-only `/api/system/overview` contract sourced from Docker-independent runtime facts already available to the UI process.
2. Add `/api/knowledge/graph` that returns an empty graph with `UNAVAILABLE` and the verified vault path when no notes exist.
3. Normalize inbox items with provenance fields without changing existing result files.
4. Render workflow timeline entries only from real inbox/result records.
5. Add tests for health, provenance, empty-graph behavior, path safety, and existing chat/inbox routes.

No production restart, new service, public port, volume change, or data deletion is required for this slice.
