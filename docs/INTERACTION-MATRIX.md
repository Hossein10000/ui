# Interaction Matrix

| Surface | Action | API/data | Expected result |
|---|---|---|---|
| Home | New task | `POST /api/tasks` | Task dialog submits; task/run become visible |
| Home | Open task | `GET /api/tasks/{id}` | Task details and real events open |
| Home | Open artifact | `GET /api/artifacts/{id}` | Artifact content and provenance open |
| Tasks | Search/filter/sort | loaded `/api/tasks` | list changes without mock data |
| Tasks | Retry failed run | `POST /api/tasks/{id}/retry` | same task, new run; page reloads |
| Inbox | Search | loaded `/api/inbox` | matching artifacts only |
| Hermes | Chat | `POST /api/chat` | response appended to chat thread |
| More | Services | `/api/system/overview` | real service sources shown |
| More | Knowledge | vault/graph endpoint semantics | explicit empty/unavailable state |

All IDs, timestamps, paths, and source references use LTR islands inside the Arabic RTL layout.
