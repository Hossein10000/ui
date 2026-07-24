# Product Reset Deployment Report

## Result

`DEPLOYED — LOCAL UI VERIFICATION PASSED`

The Product Reset is committed on branch `ui-product-reset-20260724` at commit `3d40097bd56f119b6d98b231d2b0e4e1e7830740`. The UI container was recreated only; Hermes, Qdrant, Honcho, Local Gateway, networks, and storage were not restarted or changed.

## Delivered

- Five primary destinations: Home, Tasks, Inbox, Hermes, More.
- Services and Knowledge under More.
- Real metrics, tasks, artifacts, events, service sources, and provenance.
- Task search/filter/sort and task detail with real events and retry.
- Artifact detail with task/run/source/provenance metadata.
- Separate Hermes chat surface.
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

Chromium headless was available in the local Playwright cache and was used against the UI container. The mobile interaction suite passed 13/13 checks: RTL, 390×844 overflow, navigation, task search, Inbox search, task detail, Run detail, create-task dialog, Services, and truthful Knowledge empty state. A real task submitted through the UI completed as `task-fa33b5c781364b42`, run `run-9d0cc72663bb4a6c`, artifact `artifact-3f6ba0f4e46a4513`; the UI polling path updates the result without a manual refresh. Chromium measured `scrollWidth=390` at viewport width 390. Screenshots: `/tmp/agenthost-product-reset-mobile-fixed.png` and `/tmp/agenthost-product-reset-desktop-final.png`. The public URL remains protected by the existing authentication layer; this change does not weaken it. The next human check is to open `https://agenthost.tech/ui/` after authentication and confirm the same rendered view on the target iPhone.

## Rollback

- Pre-reset tag: `ui-pre-reset-20260724`.
- Backup: `/root/ui-product-reset-backup-20260724-160912`.
- Rollback is UI-only: restore the tagged files or backup, then run `docker compose up -d --no-deps --force-recreate ui-dashboard` from `/root/ui`.

## Scope note

The pre-existing `nginx.conf` deletion was preserved separately in Git stash `preserve pre-existing nginx deletion before product reset`; generated `__pycache__/` was removed. Neither is part of the Product Reset.
