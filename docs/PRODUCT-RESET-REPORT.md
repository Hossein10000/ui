# Product Reset Deployment Report

## Result

`DEPLOYED — LOCAL UI VERIFICATION PASSED`

The Product Reset is committed on branch `ui-product-reset-20260724` at commit `347d69d5cc81482e4f975f0f2c496e102fc8a9fd`. The UI container was recreated only; Hermes, Qdrant, Honcho, Local Gateway, networks, and storage were not restarted or changed.

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

The current environment has no Chromium, Playwright, or Selenium executable, so pixel screenshots and touch automation were not generated locally. The public URL remains protected by the existing authentication layer; this change does not weaken it. The next human check is to open `https://agenthost.tech/ui/` after authentication and perform one real task submission.

## Rollback

- Pre-reset tag: `ui-pre-reset-20260724`.
- Backup: `/root/ui-product-reset-backup-20260724-160912`.
- Rollback is UI-only: restore the tagged files or backup, then run `docker compose up -d --no-deps --force-recreate ui-dashboard` from `/root/ui`.

## Scope note

Pre-existing unrelated worktree entries `D nginx.conf` and `__pycache__/` were deliberately excluded from the Product Reset commit.
