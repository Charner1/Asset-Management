# Architecture Decision Records

One file per decision: `NNNN-short-title.md`. Use `0000-template.md`.
Never edit an accepted ADR's decision. To change it, write a new ADR that
supersedes it, and set the old one's status to "Superseded by NNNN".

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0005](0005-secrets-handling.md) | Secrets from env vars or mounted files | Accepted |
| [0011](0011-dependency-policy.md) | Dependency pinning and supply chain | Accepted |
| [0013](0013-structured-logging.md) | Structured JSON logging with redaction | Accepted |

ADR numbers 0002–0004 and 0006–0010, 0012 are reserved for the decisions
listed in `docs/PLAN.md` section 3 and land with the PR that implements them.
