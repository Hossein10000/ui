# Product Reset Deployment Report

## Result

`DEPLOYED — LOCAL UI VERIFICATION PASSED`

The Product Reset is committed on branch `ui-product-reset-20260724` at commit `7cf762bfe85123a0d0303711cd98e6ecf189d38b`. The UI container was recreated only; Hermes, Qdrant, Honcho, Local Gateway, networks, and storage were not restarted or changed.

## Delivered

- Five primary destinations: Home, Tasks, Inbox, Hermes, More.
- Services and Knowledge under More.
- Real metrics, tasks, artifacts, events, service sources, and provenance.
- Task search/filter/sort and task detail with real events and retry.
- Artifact detail with task/run/source/provenance metadata.
- File artifacts open through their real Inbox file URL when provided by the API.
- Separate Hermes chat surface.
- Hermes chat restores the existing session history through `/api/chat/history`.
- Truthful Knowledge unavailable/empty state from the API source.
- RTL mobile rules, touch-size minimums, focus states, reduced-motion support, and LTR identifier islands.

## Verification

| Check | Result |
|---|---|
| `node --check app.js` | PASS |
| `python3 -m py_compile server.py` | PASS; backend unchanged |
| Docker Compose config | PASS |
| `git diff --check` | PASS |
| UI health | HTTP 200 |
| UI HTML | HTTP 200; new navigation and panels present inside container |
| `/api/system/overview` | HTTP 200 |
| `/api/tasks` | HTTP 200 |
| `/api/inbox` | HTTP 200 |
| `/api/knowledge/graph` | HTTP 200; unavailable state preserved truthfully |
| UI restart count | 0 after recreate |
| Chromium mobile interaction suite | 13/13 PASS |
| UI-created acceptance task | completed; artifact created automatically |
| UI failure and Retry acceptance | PASS; failed Run `run-c3bab6f38a1145f4`, retry Run `run-6aa654d30e26466d`, Artifact created |

Chromium headless was available in the local Playwright cache and was used against the UI container. The mobile interaction suite passed 13/13 checks: RTL, 390×844 overflow, navigation, task search, Inbox search, task detail, Run detail, create-task dialog, Services, and truthful Knowledge empty state. A real task submitted through the UI completed as `task-fa33b5c781364b42`, run `run-9d0cc72663bb4a6c`, artifact `artifact-3f6ba0f4e46a4513`; the UI polling path updates the result without a manual refresh. Chromium measured `scrollWidth=390` at viewport width 390. Screenshots: `/tmp/agenthost-product-reset-mobile-fixed.png` and `/tmp/agenthost-product-reset-desktop-final.png`. The public URL remains protected by the existing authentication layer; this change does not weaken it. The next human check is to open `https://agenthost.tech/ui/` after authentication and confirm the same rendered view on the target iPhone.

The safe failure path was also exercised through the UI context: Task `task-5d9e48c3b38f4d19` failed visibly, exposed Retry, and completed on a new Run with an automatically created Artifact. No Hermes service or routing was intentionally disrupted.

## Rollback

- Pre-reset tag: `ui-pre-reset-20260724`.
- Backup: `/root/ui-product-reset-backup-20260724-160912`.
- Rollback is UI-only: restore the tagged files or backup, then run `docker compose up -d --no-deps --force-recreate ui-dashboard` from `/root/ui`.

## Scope note

The pre-existing `nginx.conf` deletion was preserved separately in Git stash `preserve pre-existing nginx deletion before product reset`; generated `__pycache__/` was removed. Neither is part of the Product Reset.
