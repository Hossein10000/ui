# Feature Inventory

| Feature | UI surface | Source | State |
|---|---|---|---|
| Service overview | Home / More / Services | `/api/system/overview` | live |
| Task list and status | Home / Tasks | `/api/tasks` | live |
| Task detail and events | Task dialog | `/api/tasks/{id}` | live |
| Retry failed task | Task dialog | `/api/tasks/{id}/retry` | live |
| Artifact list | Home / Inbox | `/api/inbox` | live |
| Artifact detail | Artifact dialog | `/api/artifacts/{id}` | live |
| Hermes chat | Hermes | `/api/chat` | live |
| Knowledge empty state | More / Knowledge | `/api/knowledge/graph` semantics | truthful UNAVAILABLE |
| Task filters | Tasks | client-side filtering of `/api/tasks` | live |

No static health percentage, model count, fake graph, or unconnected action is presented.
