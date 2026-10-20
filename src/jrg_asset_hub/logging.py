"""JSON logging to stdout for the SIEM, with secret and PII redaction.

Every log line, from structlog or from the stdlib ``logging`` module, goes
through the same redaction step before it is written. See
docs/adr/0013-structured-logging.md.
"""

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any

import structlog
from pydantic import SecretBytes, SecretStr
from structlog.typing import EventDict, Processor, WrappedLogger

SERVICE_NAME = "jrg-asset-hub"
REDACTED = "[REDACTED]"

# A key is secret if its normalized form contains any of these parts.
SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "privatekey",
)

# Keys that hold personal data. Log IDs (employee_id, object_guid) instead.
PII_KEYS = frozenset(
    {
        "name",
        "displayname",
        "givenname",
        "firstname",
        "lastname",
        "surname",
        "sn",
        "fullname",
        "email",
        "mail",
        "upn",
        "userprincipalname",
        "samaccountname",
        "username",
        "lastuser",
        "lastloggedonuser",
        "phone",
        "telephonenumber",
        "address",
        "payload",
        "raw",
        "record",
    }
)

# Never redact the fields that structure the log line itself.
STRUCTURAL_KEYS = frozenset({"event", "level", "timestamp", "logger", "service"})

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=\-]+")
MAX_DEPTH = 8

# Third-party loggers that log full URLs or payloads at INFO or DEBUG.
NOISY_LOGGERS = ("httpx", "httpcore", "ldap3")


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _is_sensitive_key(key: str) -> bool:
    norm = _normalize_key(key)
    return norm in PII_KEYS or any(part in norm for part in SECRET_KEY_PARTS)


def _scrub_text(text: str) -> str:
    text = BEARER_RE.sub(lambda m: f"{m.group(1)} {REDACTED}", text)
    return EMAIL_RE.sub(REDACTED, text)


def scrub(value: Any, depth: int = 0) -> Any:
    """Return a copy of ``value`` with secrets and PII removed."""
    if depth > MAX_DEPTH:
        return REDACTED
    if isinstance(value, SecretStr | SecretBytes):
        return REDACTED
    if isinstance(value, str):
        return _scrub_text(value)
    if isinstance(value, Mapping):
        return {
            k: REDACTED if _is_sensitive_key(str(k)) else scrub(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [scrub(v, depth + 1) for v in value]
    return value


def redact_processor(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    out: EventDict = {}
    for key, value in event_dict.items():
        if key not in STRUCTURAL_KEYS and _is_sensitive_key(key):
            out[key] = REDACTED
        else:
            out[key] = scrub(value)
    return out


def _add_service(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    event_dict.setdefault("service", SERVICE_NAME)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Send all logs to stdout as one JSON object per line."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp")
    pre_chain: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_service,
        timestamper,
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *pre_chain,
            structlog.processors.StackInfoRenderer(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[*pre_chain, structlog.stdlib.ExtraAdder()],
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            redact_processor,
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger
