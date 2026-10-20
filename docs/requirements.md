# Requirements and Traceability — jrg-asset-hub

Each requirement has a stable ID. Do not renumber. To retire one, mark it
**Withdrawn** and say why. Update the traceability table in the same PR that
changes the behavior (CLAUDE.md, "Process").

Status values: **Done**, **Partial**, **Planned (PR n)** — PR numbers follow
`docs/PLAN.md` section 7.

## 1. Requirements

### Security (001–009)

| ID | Requirement |
|----|-------------|
| REQ-001 | The service is read-only to every source system (AD, ADP, Costpoint, NinjaOne, ThreatLocker). It never creates, changes, or deletes source data. |
| REQ-002 | Each collector uses a read-only credential and calls only read endpoints. Any non-GET HTTP call must be on an explicit allow list in code, with an ADR. |
| REQ-003 | An automated test fails if a collector uses a write method (HTTP or LDAP). |
| REQ-004 | TLS certificate verification is on for every connection. No setting, flag, or env var can turn it off. A custom CA bundle is allowed. |
| REQ-005 | No secrets in the repo. Secrets come from environment variables or mounted files (`<NAME>_FILE`). |
| REQ-006 | gitleaks scans for secrets in pre-commit and in CI (full history). |
| REQ-007 | The repo, fixtures, tests, and docs contain only synthetic data: no real names, hostnames, emails, or IDs. |
| REQ-008 | A `.gitignore` blocks secrets, env files, keys, data exports, and reports. |
| REQ-009 | Logs contain no secrets and no PII (names, emails, raw records). |

### Collectors (010–019)

| ID | Requirement |
|----|-------------|
| REQ-010 | AD collector (ldap3 over LDAPS) reads accounts, enabled state, `lastLogonTimestamp`, group membership, OU, and `employeeID`. |
| REQ-011 | ADP collector reads employment status, hire date, and termination date from a scheduled CSV export on a file share. |
| REQ-012 | Costpoint collector reads employee ID and department from a scheduled CSV export on a file share. |
| REQ-013 | ADP and Costpoint collectors implement a common interface so an API collector can replace the CSV collector with no downstream change. |
| REQ-014 | NinjaOne collector (public API v2, OAuth client credentials) reads devices, installed software, last check-in, and last logged-on user. |
| REQ-015 | ThreatLocker collector (Portal API, API key) reads computers and check-in state. |
| REQ-016 | Each collector, the match job, the rules job, and the evidence job run as separate CLI commands that cron or a Kubernetes CronJob can schedule. Exit code is non-zero on failure. |
| REQ-017 | A collector run is all-or-nothing. A failed run is never treated as current data. |

### Data model and history (020–029)

| ID | Requirement |
|----|-------------|
| REQ-020 | Raw snapshot tables store one row per source record per run, with `run_id`, `source`, `collected_at`, and the raw JSON. Snapshots are never updated or deleted. |
| REQ-021 | Normalized tables `person`, `account`, `device`, `software_install`, `threatlocker_computer` link each row to the run that produced it. |
| REQ-022 | Match tables (person-to-account, device-to-person, device-across-sources) record match method and confidence. |
| REQ-023 | People join on Costpoint employee ID, stored in AD `employeeID`. |
| REQ-024 | Devices join on NinjaOne device ID, with hostname as a fallback match at lower confidence. |
| REQ-025 | The findings table stores `rule_id`, subject, `first_seen`, `last_seen`, status (open/resolved), and the run IDs that support it. |
| REQ-026 | All history is retained. A query can answer "what was true on date X". |

### Rules (030–039)

| ID | Requirement |
|----|-------------|
| REQ-030 | Rules are defined in YAML with id, description, control mapping, severity, and a SQL or Python check. |
| REQ-031 | R001: ADP shows terminated, but the AD account is still enabled more than 24 hours after the term date. Controls: NIST 800-171 3.9.2, 3.1.1. |
| REQ-032 | R004: device exists in NinjaOne but not in ThreatLocker, or the reverse. Controls: 3.4.1, 3.14.2. |
| REQ-033 | R005: software installed per NinjaOne is not on the approved allow list, loaded from CSV. Controls: 3.4.8, 3.4.9. |
| REQ-034 | Findings open when the condition appears, stay open while it holds, and auto-resolve when it clears. |
| REQ-035 | A rule never auto-resolves a finding from stale or failed source data. |

### Platform (040–049)

| ID | Requirement |
|----|-------------|
| REQ-040 | Stack: Python 3.12, SQLAlchemy 2 + Alembic, PostgreSQL 16, pydantic-settings, httpx, structlog, pytest. |
| REQ-041 | Every dependency is pinned to an exact version that is at least 14 days old when added. Lock files carry hashes. |
| REQ-042 | Container image is based on Red Hat UBI 9. docker-compose provides local dev with Postgres. |
| REQ-043 | Logs are JSON lines on stdout (structlog) for SIEM ingestion. |

### Evidence (050–059)

| ID | Requirement |
|----|-------------|
| REQ-050 | A command writes a dated report (Markdown and CSV) for a date range: inventory counts by source, match rates, open and resolved findings per rule, and time to resolve. |

### Process (060–069)

| ID | Requirement |
|----|-------------|
| REQ-060 | `docs/requirements.md` holds numbered requirements and a traceability table to code and tests. |
| REQ-061 | Design decisions are recorded as ADRs in `docs/adr/`. |
| REQ-062 | Each collector and rule ships with unit tests using mocked HTTP and LDAP responses. |
| REQ-063 | Line coverage on `src/` is at least 80%, enforced in CI. |

### Future interfaces (070–079)

| ID | Requirement |
|----|-------------|
| REQ-070 | Clean interfaces exist for Jira ticket creation, Jira Assets push, an Entra ID GCC High collector, and an allow list UI. They are not implemented in Phase 1. |

## 2. Traceability

| ID | Code | Tests | Status |
|----|------|-------|--------|
| REQ-001 | `net/` | `tests/security/test_read_only.py` | Planned (PR 4) |
| REQ-002 | `net/http.py` allow list; ADR 0003 | `tests/security/test_read_only.py` | Planned (PR 4) |
| REQ-003 | — | `tests/security/test_read_only.py` | Planned (PR 4) |
| REQ-004 | `net/tls.py`; ADR 0004 | `tests/security/test_tls.py` | Planned (PR 4) |
| REQ-005 | ADR 0005; `config.py` | `tests/unit/test_config.py` | Partial — decision recorded; loader in PR 3 |
| REQ-006 | `.pre-commit-config.yaml`, `.github/workflows/ci.yml` (`secret-scan`) | CI job `secret-scan` | Done |
| REQ-007 | CLAUDE.md "Synthetic data" | review + gitleaks | Partial — fixture check added with first fixtures (PR 7) |
| REQ-008 | `.gitignore` | — | Done |
| REQ-009 | `logging.py` redaction | `tests/unit/test_logging.py` | Planned (PR 3) |
| REQ-010 | `collectors/ad.py` | `tests/unit/collectors/test_ad.py` | Planned (PR 7) |
| REQ-011 | `collectors/adp_csv.py` | `tests/unit/collectors/test_adp_csv.py` | Planned (PR 8) |
| REQ-012 | `collectors/costpoint_csv.py` | `tests/unit/collectors/test_costpoint_csv.py` | Planned (PR 8) |
| REQ-013 | `collectors/base.py`; ADR 0008 | `tests/unit/collectors/test_base.py` | Planned (PR 6) |
| REQ-014 | `collectors/ninjaone.py` | `tests/unit/collectors/test_ninjaone.py` | Planned (PR 9) |
| REQ-015 | `collectors/threatlocker.py` | `tests/unit/collectors/test_threatlocker.py` | Planned (PR 10) |
| REQ-016 | `cli.py`; ADR 0010 | `tests/unit/test_cli.py` | Partial — entry point only |
| REQ-017 | `collectors/base.py` | `tests/unit/collectors/test_base.py` | Planned (PR 6) |
| REQ-020 | `db/models.py`, `migrations/`; ADR 0002, 0012 | `tests/integration/test_snapshot_append_only.py` | Planned (PR 5) |
| REQ-021 | `db/models.py` | `tests/integration/test_models.py` | Planned (PR 5) |
| REQ-022 | `matching/` | `tests/unit/matching/` | Planned (PR 11) |
| REQ-023 | `matching/person_account.py` | `tests/unit/matching/test_person_account.py` | Planned (PR 11) |
| REQ-024 | `matching/devices.py` | `tests/unit/matching/test_devices.py` | Planned (PR 11) |
| REQ-025 | `db/models.py`; ADR 0006 | `tests/integration/test_findings.py` | Planned (PR 5) |
| REQ-026 | `db/asof.py`; ADR 0002 | `tests/integration/test_asof.py` | Planned (PR 5) |
| REQ-030 | `rules/engine.py`; ADR 0009 | `tests/unit/rules/test_engine.py` | Planned (PR 12) |
| REQ-031 | `rules/R001.yaml` | `tests/integration/rules/test_r001.py` | Planned (PR 13) |
| REQ-032 | `rules/R004.yaml` | `tests/integration/rules/test_r004.py` | Planned (PR 13) |
| REQ-033 | `rules/R005.yaml`, allow list loader | `tests/integration/rules/test_r005.py` | Planned (PR 13) |
| REQ-034 | `rules/engine.py` | `tests/integration/rules/test_lifecycle.py` | Planned (PR 12) |
| REQ-035 | `rules/engine.py`; ADR 0007 | `tests/integration/rules/test_stale_guard.py` | Planned (PR 12) |
| REQ-040 | `pyproject.toml` | CI job `test` | Partial — runtime libs pinned; used from PR 3 on |
| REQ-041 | `pyproject.toml`, `requirements*.lock`, `Makefile` (`lock`); ADR 0011 | `tests/security/test_dependency_pins.py` | Done |
| REQ-042 | `deploy/Containerfile`, `deploy/compose.yaml` | — | Planned (PR 5 compose, PR 15 image) |
| REQ-043 | `logging.py` | `tests/unit/test_logging.py` | Planned (PR 3) |
| REQ-050 | `evidence/` | `tests/unit/evidence/` | Planned (PR 14) |
| REQ-060 | this file | review | Done |
| REQ-061 | `docs/adr/` | review | Done |
| REQ-062 | per collector and rule | per collector and rule | Planned (PR 7–13) |
| REQ-063 | `pyproject.toml` (`--cov-fail-under=80`), CI job `test` | CI job `test` | Done |
| REQ-070 | `integrations/`, `collectors/base.py` | — | Planned (PR 16) |
