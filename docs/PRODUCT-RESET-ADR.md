# Product Reset — Architecture Decision Record

## Context

The existing UI backend already exposes task, run, event, artifact, inbox, chat, system overview, and knowledge endpoints. The reset must reveal those capabilities without changing the backend, schema, storage paths, Hermes, or supporting services.

## Decisions

1. Keep the current Python UI server and file-backed workflow storage.
2. Keep the existing API contracts and use `/api/tasks`, `/api/inbox`, `/api/system/overview`, `/api/chat`, task detail, event, artifact, and knowledge endpoints as the single UI data sources.
3. Use five primary destinations: Home, Tasks, Inbox, Hermes, and More. Services and Knowledge remain under More.
4. Use a data-empty state for the unavailable Obsidian graph; do not fabricate nodes or notes.
5. Keep the existing dark RTL visual language and add only reset-scoped accessibility, mobile, focus, and filter rules.
6. Do not add a queue, database, graph engine, or workflow service.

## Consequences

The UI remains operationally small and rollback-friendly. Graph editing, richer file preview, and server-side filtering remain constrained by the existing API and are not invented in the frontend.

## Rollback

Restore the pre-reset tag `ui-pre-reset-20260724` or the backup recorded in the final report, then recreate only `ui-dashboard`.
