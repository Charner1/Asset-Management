# CLAUDE.md — jrg-asset-hub

This file tells Claude Code (and people) how to work in this repo.
Read it before you change anything. If a rule here conflicts with a request,
stop and ask.

## What this service does

jrg-asset-hub collects identity and device data from JANUS systems, matches
the records, checks them against rules, keeps daily history, and writes
compliance evidence. It supports CMMC Level 2 (NIST SP 800-171) and follows
CMMI Dev Level 3 process.

Current phase: **Phase 1** (collect, normalize, match, rules R001/R004/R005,
evidence files). See `docs/PLAN.md`.

## Hard rules (do not break these)

1. **Read-only to every source.** The service never writes to Active
   Directory, NinjaOne, ThreatLocker, ADP, or Costpoint. Collectors use a
   read-only credential and call only read endpoints. People act on findings
   through Jira tickets (Phase 3), not through this service.
2. **Read-only is enforced by code and tests.** All HTTP goes through
   `ReadOnlyHttpClient`. All LDAP goes through `ReadOnlyLdapClient`.
   `tests/security/test_read_only.py` fails if a collector calls a write
   method. Any exception (for example, an OAuth token POST) must be on an
   explicit allow list in code, and must have an ADR.
3. **TLS is always verified.** LDAPS for AD. HTTPS for APIs. Postgres uses
   `sslmode=verify-full` outside local dev. You may set a custom CA bundle.
   You may not add a flag, setting, or env var that turns verification off.
4. **No secrets in the repo.** Read secrets from environment variables or
   from mounted files (`<NAME>_FILE` points to the file). gitleaks runs in
   pre-commit and CI. Never commit `.env` files.
5. **Synthetic data only.** Fixtures, tests, docs, and examples use made-up
   data. No real names, hostnames, emails, employee IDs, device IDs, IPs,
   tenant IDs, or org names. Use the patterns in "Synthetic data" below.
6. **Snapshots are append-only.** Never `UPDATE` or `DELETE` a raw snapshot
   row. The DB role for the app has no UPDATE/DELETE grant on those tables.
7. **Keep all history.** Every query must be able to answer "what was true
   on date X". Do not overwrite normalized rows in place.
8. **Do not log PII or secrets.** Logs carry IDs and counts, not names,
   emails, or raw records. Never log tokens, passwords, or headers.

## Tech stack

- Python 3.12
- SQLAlchemy 2.x (typed ORM, `Mapped[...]`) + Alembic
- PostgreSQL 16
- pydantic-settings for config
- httpx for HTTP, ldap3 for LDAP
- structlog, JSON lines to stdout (the SIEM reads stdout)
- pytest, pytest-cov, respx (HTTP mocks), ldap3 MOCK_SYNC (LDAP mocks)
- ruff (lint + format), mypy (strict on `src/`)
- Container: Red Hat UBI 9 (`ubi9/python-312`), runs as non-root
- Local dev: docker-compose with Postgres 16

### Dependency pins

- Pin every dependency (runtime and dev) to an exact version (`==`).
- Each pinned version must be **at least 14 days old** on the day you add it.
  Check the PyPI release date. Record the date check in the PR description.
- Use a lock file with hashes (`requirements.lock`, `--require-hashes`).
- Pin the base image by digest, not only by tag.

## Repo layout

```
src/jrg_asset_hub/
  cli.py              # entry point: `jrg-asset-hub <command>`
  config.py           # pydantic-settings; secrets from env or *_FILE
  logging.py          # structlog JSON setup
  db/                 # engine, session, models, as-of query helpers
  net/                # ReadOnlyHttpClient, ReadOnlyLdapClient, TLS setup
  collectors/         # one module per source; each has collect() + normalize()
    base.py           # Collector protocol, RawRecord, run bookkeeping
    ad.py  adp_csv.py  costpoint_csv.py  ninjaone.py  threatlocker.py
  matching/           # person-account, device-person, device-across-sources
  rules/
    engine.py         # loads YAML, runs checks, opens/keeps/resolves findings
    checks/           # Python checks referenced from YAML
  evidence/           # report builder (Markdown + CSV)
  integrations/       # Phase 3+ stubs: Jira, Jira Assets (interfaces only)
rules/                # rule definitions, one YAML file per rule
config/               # example config, allow list CSV example (synthetic)
migrations/           # Alembic
tests/
  unit/  integration/  security/  fixtures/
docs/
  PLAN.md  requirements.md  adr/
deploy/               # Containerfile, compose, RKE2 CronJob examples
```

## Commands

```
make dev          # create venv, install pinned deps, install pre-commit
make up           # docker-compose: start local Postgres
make migrate      # alembic upgrade head
make test         # pytest with coverage (fails under 80%)
make lint         # ruff check, ruff format --check, mypy
make scan         # gitleaks detect

jrg-asset-hub collect <source>    # ad | adp | costpoint | ninjaone | threatlocker
jrg-asset-hub match
jrg-asset-hub rules run [--rule R001]
jrg-asset-hub evidence --from YYYY-MM-DD --to YYYY-MM-DD --out DIR
jrg-asset-hub db check            # migrations current, grants correct
```

Each command is one job. It exits 0 on success and non-zero on failure, so
cron or a Kubernetes CronJob can schedule and alert on it. Every command
writes one `run` row with start, end, status, and counts.

## Data model conventions

- `run`: one row per job execution (`run_id` UUID, `job`, `source`,
  `started_at`, `finished_at`, `status`, counts).
- `raw_snapshot`: one row per source record per run. Columns: `run_id`,
  `source`, `source_key`, `collected_at`, `payload` (JSONB), `payload_sha256`.
  Insert only.
- Normalized tables (`person`, `account`, `device`, `software_install`,
  `threatlocker_computer`): one row per entity per run, with `run_id`.
  Insert only. "Current" = rows from the latest successful run per source.
- Match tables (`person_account_match`, `device_person_match`,
  `device_link`): `run_id`, both keys, `method`, `confidence` (0.0–1.0).
- `finding`: `rule_id`, `subject_type`, `subject_key`, `first_seen`,
  `last_seen`, `status` (`open` | `resolved`), `resolved_at`.
  `finding_observation` links a finding to each `run_id` that supports it.
- All timestamps are `timestamptz` in UTC. Date rules and reports use the
  business time zone (`JRG_BUSINESS_TIMEZONE`, default `America/New_York`).
- As-of queries live in `db/asof.py`. Use them. Do not write ad-hoc
  "latest" queries in collectors or rules.

## Join keys

- Person: Costpoint employee ID. AD stores it in `employeeID`. ADP rows map
  to it through the ADP export column for employee ID.
- Device: NinjaOne device ID first. Hostname (normalized: lower case, no
  domain suffix) is the fallback match, with lower confidence.
- Record the match method and confidence on every match row.

## Rules

- One YAML file per rule in `rules/`. Fields: `id`, `title`,
  `description`, `controls` (list of NIST 800-171 IDs), `severity`,
  `requires_sources`, `max_source_age_hours`, and exactly one of
  `check.sql` or `check.python`.
- A check returns the set of subjects that violate the rule now.
- The engine opens new findings, updates `last_seen` on open ones, and
  resolves findings whose subject is no longer returned.
- **The engine never resolves a finding from stale or failed data.** If a
  required source has no successful run inside `max_source_age_hours`, the
  rule is skipped and the skip is logged and recorded.

## Collectors

- Each collector implements the `Collector` protocol in
  `collectors/base.py`: `source`, `collect() -> Iterator[RawRecord]`, and
  `normalize(records) -> NormalizedBatch`.
- ADP and Costpoint read CSV exports from a file share now. They implement
  the same protocol so an API collector can replace them with no change
  downstream.
- A collector run is all-or-nothing. If it fails midway, the run is marked
  `failed` and its rows are not used as "current".
- Use paging. Respect rate limits with backoff. Set timeouts on every call.

## Testing

- Every collector and every rule ships with unit tests in the same PR.
- Mock HTTP with respx. Mock LDAP with ldap3 `MOCK_SYNC`. No test calls a
  real system.
- Integration tests run against the compose Postgres.
- Coverage target: 80% line coverage on `src/`, enforced in CI.
- Fixtures live in `tests/fixtures/` and are synthetic.

## Synthetic data

Use these patterns so no fixture looks like real data:

- Names: `Test User 001`, `Alpha Tester`
- Emails/UPNs: `user001@example.test`
- Employee IDs: `E9000001` and up
- Hostnames: `WS-TEST-0001`, `SRV-TEST-0001`
- Domains: `corp.example.test`, `DC=example,DC=test`
- Device IDs / UUIDs: obviously fake (`00000000-0000-4000-8000-000000000001`)
- IPs: `192.0.2.0/24`, `198.51.100.0/24` (RFC 5737)

## Process (CMMI Dev L3)

- Small PRs, one concern each. The PR description states: what, why,
  requirement IDs covered, tests added, and dependency date checks.
- Requirements live in `docs/requirements.md` with IDs (`REQ-###`) and a
  traceability table (requirement → code → tests). Update it in the same PR
  that changes the behavior.
- Record design decisions as ADRs in `docs/adr/NNNN-title.md`
  (context, decision, consequences, status).
- Do not merge with failing lint, type check, tests, coverage, or gitleaks.
- AI-generated code gets human review before merge.

## Out of scope (Phase 1)

Jira ticket creation, Jira Assets push, Entra ID GCC High collector, allow
list UI, any web UI. Leave interfaces in `integrations/` and the
`Collector` protocol so these plug in later. Do not build them now.
