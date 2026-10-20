# 0001. Record architecture decisions

- Status: Accepted
- Date: 2026-10-20
- Requirements: REQ-061

## Context

The project follows CMMI Dev Level 3 and supports CMMC Level 2 assessment.
Assessors and new team members need to see why the system is built the way
it is, not only what it does.

## Decision

We record each significant design decision as an ADR in `docs/adr/`, in the
Nygard format (context, decision, consequences, status). The ADR lands in the
same PR as the code it describes. Accepted ADRs are not rewritten; a new ADR
supersedes an old one.

## Consequences

- Decisions are reviewable in PRs and traceable from `docs/requirements.md`.
- Small overhead per decision. We accept it.
