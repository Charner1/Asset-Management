# 0005. Secrets from environment variables or mounted files

- Status: Accepted
- Date: 2026-10-20
- Requirements: REQ-005, REQ-006, REQ-008, REQ-009

## Context

The service needs an AD bind password, a NinjaOne OAuth client secret, a
ThreatLocker API key, and a database password. It runs on a RHEL 9 VM now
and on RKE2 later. Secrets must never enter the repo, images, or logs.

## Decision

- Each secret setting `X` is read from env var `JRG_X`, or from the file
  named by `JRG_X_FILE`. If both are set, startup fails. File form is
  preferred: Kubernetes Secrets and Podman/systemd credentials mount as files.
- Secret values use pydantic `SecretStr`, so `repr` and logs show `**********`.
- No config file in the repo holds a secret. Examples use placeholders.
- `.gitignore` blocks `.env*`, keys, and certificates.
- gitleaks runs in pre-commit (staged changes) and in CI (full history).
- The logging setup redacts known secret keys as a second guard.

## Consequences

- Same code path on the VM (systemd `LoadCredential=` or env file with mode
  0600 outside the repo) and on RKE2 (mounted Secret).
- Rotation is a restart, not a code change.
- Developers need a local `.env` outside git for compose. We document it.
