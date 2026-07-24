# ADR-0002: Provenance Before Visualization

## Status

Accepted for the first vertical slice.

Every displayed entity or relation must carry `source_type`, `source_id`, `last_verified_at`, `health_state`, and `data_origin`. If the source is absent or stale, the UI displays `UNAVAILABLE`; it does not synthesize counts, agents, containers, or graph edges.
