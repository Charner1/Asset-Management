# 0013. Structured JSON logging with redaction

- Status: Accepted
- Date: 2026-10-20
- Requirements: REQ-009, REQ-043

## Context

The SIEM collects container stdout. Logs support NIST 800-171 audit
controls (3.3.x), so they must be machine-readable and complete. The service
also handles identity data and credentials, so logs must not leak PII or
secrets. Third-party libraries (httpx, ldap3) log through stdlib `logging`
and can include URLs, headers, or payloads.

## Decision

- structlog renders one JSON object per line to **stdout**. Fields:
  `timestamp` (ISO 8601 UTC), `level`, `logger`, `service`, `event`, plus
  event fields. Bound context (for example `run_id`) comes from contextvars.
- stdlib `logging` is routed through the same formatter, so third-party
  logs are JSON and redacted too.
- A redaction step runs last, before rendering, on every line:
  - Keys that look secret (`password`, `secret`, `token`, `api_key`,
    `authorization`, `cookie`, `credential`, `private_key`) → `[REDACTED]`.
  - Keys that hold PII (`name`, `display_name`, `email`, `upn`,
    `sAMAccountName`, `last_logged_on_user`, `payload`, …) → `[REDACTED]`.
  - `SecretStr` values → `[REDACTED]`.
  - Emails and `Bearer`/`Basic` credentials inside any string → `[REDACTED]`.
  - Applied recursively to nested dicts and lists, to a fixed depth.
- `httpx`, `httpcore`, and `ldap3` loggers are held at WARNING.
- Code logs IDs and counts (`employee_id`, `object_guid`, `hostname`,
  `run_id`, `record_count`), not names or raw records.
- Config errors log field names and messages only, never input values.

## Consequences

- Redaction is a safety net, not a license: code still must not log PII.
- A new PII field name must be added to `PII_KEYS`, with a test.
- `hostname` and `employee_id` stay visible. They are needed to act on a
  finding. If policy changes, add them to `PII_KEYS`.
- Some over-redaction is possible (any key containing `token`). We accept it.
