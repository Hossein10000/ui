# ADR-0001: Start with Minimal Integration

## Status

Accepted for the first vertical slice.

## Context

The live site is a small Python UI behind Traefik and Authelia. Hermes chat and the file-backed inbox are real. The vault mounted into Hermes is empty, and no separate workflow or graph service was verified.

## Decision

Reuse the current UI process, Hermes session API, and shared results-data directory. Introduce provenance and source-state contracts before adding persistence or a graph database.

## Consequences

- Small change surface and simple rollback.
- Real data remains traceable to its source.
- Knowledge graph is empty/UNAVAILABLE until the mounted vault contains notes.
- A later PostgreSQL or graph projection can be added only when measured needs justify it.

## Rejected alternatives

- A new workflow service now: no demonstrated persistence requirement.
- Neo4j/Qdrant as a graph store: neither is verified as the source of truth for document relations.
- Mock graph nodes: violates provenance requirements.
