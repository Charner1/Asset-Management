# jrg-asset-hub — Phase 1 Build Plan

Status: **Draft for review.** No code is written until this plan and
`CLAUDE.md` are approved.

## 1. Goal

Build a read-only service that:

1. Collects identity data (AD, ADP, Costpoint) and device data (NinjaOne,
   ThreatLocker) every day.
2. Stores every raw record, unchanged, for every run.
3. Normalizes and matches people, accounts, and devices across sources.
4. Runs rules R001, R004, and R005 and tracks findings over time.
5. Writes dated evidence reports (Markdown + CSV) for a date range.

## 2. Architecture

```
          cron / K8s CronJob (one job per command)
                          |
   +----------+----------+----------+-----------+--------------+
   | collect  | collect  | collect  | collect   | collect      |
   | ad       | adp(csv) | costpt   | ninjaone  | threatlocker |
   +----+-----+----+-----+----+-----+-----+-----+------+-------+
        |  LDAPS   |  file     |  file      | HTTPS       | HTTPS
        v          v  share    v  share     v (OAuth)     v (API key)
   +---------------------------------------------------------+
   |  PostgreSQL 16                                          |
   |  run -> raw_snapshot (append-only)                      |
   |      -> person / account / device / software_install /  |
   |         threatlocker_computer (append-only, per run)    |
   |      -> matches (per run) -> findings + observations    |
   +---------------------------------------------------------+
        ^                  ^                       |
        | match            | rules run             | evidence
        |                  |                       v
                                       reports/YYYY-MM-DD/*.md, *.csv
```

Daily order: collectors (parallel) → `match` → `rules run` → `evidence`
(on demand or weekly).

Each step is a separate CLI command and a separate `run` row. A failed step
does not block the others, but rules skip any source that is stale or failed.

## 3. Key design decisions (each becomes an ADR)

| ADR  | Decision |
|------|----------|
| 0001 | Record decisions as ADRs (Nygard format). |
| 0002 | History model: insert-only snapshots and per-run normalized rows. "As of date X" = latest **successful** run per source that finished on or before end of X. No in-place updates. |
| 0003 | Read-only enforcement: `ReadOnlyHttpClient` exposes only `get()`; a transport hook rejects any other method unless the exact URL is on a code allow list. `ReadOnlyLdapClient` exposes only bind and search. AST test rejects write calls in `collectors/`. |
| 0004 | TLS policy: verification always on. Custom CA bundle allowed. No disable flag exists. Postgres `verify-full` outside dev. |
| 0005 | Secrets: env vars or `*_FILE` mounted files (K8s Secrets, Podman secrets). No secrets in config files. |
| 0006 | Findings lifecycle: one `finding` row per episode. Reappearance after resolve opens a new row, so "time to resolve" is exact. Supporting runs in `finding_observation` (not an array column). |
| 0007 | Stale-data guard: rules declare `requires_sources` and `max_source_age_hours`. If a source is stale, the rule is skipped and nothing auto-resolves. |
| 0008 | Source interface: `Collector` protocol; ADP and Costpoint CSV collectors are swappable for API collectors later. |
| 0009 | Rule format: YAML metadata + SQL or Python check. Checks return violating subjects; the engine owns lifecycle. |
| 0010 | CLI with stdlib `argparse` (fewer dependencies to vet). |
| 0011 | Dependency policy: exact pins, ≥14 days old, hash-locked; base image pinned by digest. |
| 0012 | DB roles: migration role owns schema; app role has INSERT/SELECT on snapshot and normalized tables, UPDATE only on `finding` and `run`. |

## 4. Data model (first cut)

- `run(run_id, job, source, started_at, finished_at, status, record_count, error)`
- `raw_snapshot(id, run_id, source, source_key, collected_at, payload jsonb, payload_sha256)`
- `person(id, run_id, source, employee_id, display_name, department, employment_status, hire_date, term_date)`
  — rows from ADP and Costpoint; a view merges them per `employee_id`.
- `account(id, run_id, object_guid, sam_account_name, upn, employee_id, enabled, last_logon_ts, ou_dn, groups jsonb)`
- `device(id, run_id, source, source_device_id, hostname, hostname_norm, os, last_checkin, last_user)`
- `software_install(id, run_id, source_device_id, name, publisher, version)`
- `threatlocker_computer(id, run_id, tl_computer_id, hostname, hostname_norm, last_checkin, mode, group)`
- `person_account_match(run_id, employee_id, object_guid, method, confidence)`
- `device_person_match(run_id, device_ref, employee_id, method, confidence)`
- `device_link(run_id, ninja_device_id, tl_computer_id, method, confidence)`
- `finding(id, rule_id, subject_type, subject_key, first_seen, last_seen, status, resolved_at)`
- `finding_observation(finding_id, run_id, observed_at)`
- `rule_run(run_id, rule_id, status, skipped_reason, opened, kept, resolved)`

Indexes on `(source, run_id)`, join keys, and `(rule_id, subject_key, status)`.
Partitioning of `raw_snapshot` by month is deferred until volume needs it
(noted in ADR 0002).

## 5. Rules (Phase 1)

| ID   | Condition | Subject | Controls | Severity |
|------|-----------|---------|----------|----------|
| R001 | ADP status = terminated, AD account enabled, and now > term date + 24 h | AD account (`object_guid`) | 3.9.2, 3.1.1 | high |
| R004 | NinjaOne device with no ThreatLocker link, or ThreatLocker computer with no NinjaOne link | device (source + id) | 3.4.1, 3.14.2 | medium |
| R005 | NinjaOne software install not on the approved allow list (CSV) | device + software name | 3.4.8, 3.4.9 | medium |

Notes:
- R001: ADP gives a date, not a time. The rule treats the term date as
  ending at 23:59:59 in the business time zone (`America/New_York`), then
  adds 24 h.
- R004: a device "exists" if it checked in within a configurable window
  (default 30 days), so retired devices do not create noise.
- R005: allow list columns `name_pattern, publisher, notes`. Matching is
  case-insensitive with glob patterns. The CSV loader sits behind an
  `AllowListSource` interface for the future UI.

## 6. Evidence report

`jrg-asset-hub evidence --from D1 --to D2 --out DIR` writes
`DIR/<D2>/evidence.md` plus CSVs:

- `inventory_counts.csv` — records per source per day
- `match_rates.csv` — person-account, device-person, Ninja-TL link rates
- `findings.csv` — every finding open at any time in the range
- `findings_summary.csv` — per rule: opened, resolved, open at end,
  median and p90 time to resolve
- `evidence.md` — the same data with control mapping and run IDs, plus a
  SHA-256 manifest of the CSVs

## 7. PR sequence

Each PR is small, has tests, and updates `docs/requirements.md`.

| #  | PR | Contents |
|----|----|----------|
| 1  | **Plan** | `CLAUDE.md`, `docs/PLAN.md` (this PR) |
| 2  | Repo skeleton | `pyproject.toml`, pinned lock, `.gitignore`, pre-commit (gitleaks, ruff, mypy), Makefile, CI workflow, `docs/requirements.md` v0, ADR 0001, 0005, 0011 |
| 3  | Config + logging | pydantic-settings with `*_FILE`, structlog JSON, redaction filter; tests |
| 4  | Safe network layer | `ReadOnlyHttpClient`, `ReadOnlyLdapClient`, TLS setup, read-only security tests; ADR 0003, 0004 |
| 5  | DB schema v1 | SQLAlchemy models, Alembic baseline, roles/grants, `db/asof.py`; ADR 0002, 0012 |
| 6  | Collector base + CLI | `Collector` protocol, run bookkeeping, `cli.py`; ADR 0008, 0010 |
| 7  | AD collector | ldap3 paged search, normalization; MOCK_SYNC tests |
| 8  | ADP + Costpoint CSV collectors | CSV schemas, validation, normalization; tests |
| 9  | NinjaOne collector | OAuth client credentials, devices, software, paging; respx tests |
| 10 | ThreatLocker collector | computers + check-in; respx tests |
| 11 | Matching | three match types, methods, confidence; tests |
| 12 | Rules engine | YAML loader, lifecycle, stale-data guard; ADR 0006, 0007, 0009 |
| 13 | Rules R001, R004, R005 | YAML + checks + allow list loader; tests incl. open/keep/resolve |
| 14 | Evidence report | Markdown + CSV writer; golden-file tests |
| 15 | Packaging | UBI 9 Containerfile, docker-compose, RHEL cron example, RKE2 CronJob example |
| 16 | Integration stubs | `integrations/jira.py`, `integrations/jira_assets.py`, `collectors/entra.py` interfaces only |

## 8. Testing strategy

- Unit: every collector (respx / ldap3 MOCK_SYNC), every rule (SQL run
  against a test Postgres with fixture rows), matching, engine lifecycle.
- Lifecycle tests per rule: condition appears → open; persists → same
  finding, `last_seen` moves; clears → resolved; source stale → no change.
- History tests: load three days of fixtures, assert as-of queries return
  the right state for each day.
- Security tests: read-only (method + AST), no TLS-disable path, no secret
  patterns in fixtures, log redaction.
- CI: lint, mypy, pytest with `--cov-fail-under=80`, gitleaks.

## 9. Open questions for review

1. **ThreatLocker read endpoints use POST.** — *Accepted with plan
   approval; ADR in PR 4.* Several Portal API list/search
   calls (for example, computer search by parameters) are POST with a JSON
   query body. Proposal: allow a fixed list of these POST URLs in
   `ReadOnlyHttpClient`, with an ADR, and use an API key scoped to read-only
   permissions. Please confirm this is acceptable.
2. **NinjaOne OAuth token request is a POST.** — *Accepted with plan
   approval; ADR in PR 4.* Same approach: allow only
   the token URL. Confirm the API client has only the `monitoring` scope
   (no `management` or `control`).
3. **ADP export format.** Need a synthetic sample of the column headers,
   date format, and the exact values that mean "terminated".
4. **Costpoint export format.** Same: headers and department field.
5. ~~**Business time zone**~~ — **Resolved 2026-10-20:** `America/New_York`
   (setting `JRG_BUSINESS_TIMEZONE`).
6. **File share access on RKE2.** Assumed an SMB/NFS mount into the pod,
   read-only. Confirm the mount method.
7. **Repository and CI.** Which GitHub org/repo, and is CI GitHub Actions
   or an on-prem runner?
8. **Postgres hosting.** Same VM, or a managed on-prem instance? This
   affects TLS and backup notes.
9. **AD scope.** Which base DNs to search, and should disabled-OU accounts
   be collected? (Plan: collect all user objects; rules decide.)

## 10. Risks

| Risk | Mitigation |
|------|-----------|
| `lastLogonTimestamp` lags up to ~14 days by design | Document it; do not use it for R001. Use it only for staleness reporting later. |
| Hostname reuse causes false device matches | Hostname match has lower confidence; NinjaOne ID wins; report ambiguous matches. |
| Partial collector run causes false auto-resolve | All-or-nothing runs + stale-data guard (ADR 0007). |
| Raw snapshot growth | JSONB + hash; monthly partitioning when needed; retention is "keep all" by requirement. |
| Database holds real PII once deployed | DB stays on-prem; TLS; least-privilege roles; no PII in logs; synthetic data only in repo. |
