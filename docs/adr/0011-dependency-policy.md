# 0011. Dependency pinning and supply chain

- Status: Accepted
- Date: 2026-10-20
- Requirements: REQ-041

## Context

The service holds identity and device data for a DoD contractor (CMMC L2).
A compromised or broken new release of a dependency is a real risk. Most
malicious package releases are found and pulled within days.

## Decision

- `pyproject.toml` pins every direct dependency (runtime, dev, and build
  backend) with `==`.
- Lock files `requirements.lock` (runtime) and `requirements-dev.lock`
  (dev) pin every transitive dependency with `--hash` entries. Installs use
  `pip install --require-hashes --no-deps`.
- Each pinned version must be **at least 14 days old** when added.
  `make lock` resolves with `uv pip compile --exclude-newer <today - 14 days>`,
  so the rule holds for transitive dependencies too.
- Each PR that changes pins lists the PyPI release date of each changed
  direct dependency.
- GitHub Actions and pre-commit hooks are pinned by commit SHA with the tag
  in a comment, and meet the same 14-day rule.
- Downloaded binaries in CI (gitleaks) are verified by SHA-256.
- Container base images are pinned by digest (PR 15).
- `tests/security/test_dependency_pins.py` fails on a loose pin or a lock
  file without hashes.

## Consequences

- Security fixes arrive 14 days late by default. For an urgent CVE fix, a
  PR may waive the rule for that one package, with the reason and approver
  in the PR description.
- `ldap3==2.9.1` (2021) is the latest release and has no recent upstream
  activity. We accept it for Phase 1 because it is pure Python, widely used,
  and we use only bind and search. We review this before Phase 2.
