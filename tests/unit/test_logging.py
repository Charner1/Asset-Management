"""REQ-009 and REQ-043: JSON logs on stdout, no secrets, no PII."""

import json
import logging
from typing import Any

import pytest
from pydantic import SecretStr

from jrg_asset_hub.logging import (
    MAX_DEPTH,
    REDACTED,
    SERVICE_NAME,
    configure_logging,
    get_logger,
    scrub,
)


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def test_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    log = get_logger("test")
    log.info("first", count=3)
    log.warning("second")
    lines = _lines(capsys)
    assert [ln["event"] for ln in lines] == ["first", "second"]
    first = lines[0]
    assert first["level"] == "info"
    assert first["count"] == 3
    assert first["service"] == SERVICE_NAME
    assert first["logger"] == "test"
    assert first["timestamp"].endswith("Z")


def test_nothing_goes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    get_logger().error("boom")
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "bind_password",
        "api_key",
        "apiKey",
        "client_secret",
        "access_token",
        "Authorization",
        "cookie",
        "credentials",
        "private_key",
    ],
)
def test_secret_keys_are_redacted(capsys: pytest.CaptureFixture[str], key: str) -> None:
    configure_logging()
    get_logger().info("evt", **{key: "fake-value"})
    line = _lines(capsys)[0]
    assert line[key] == REDACTED


@pytest.mark.parametrize(
    "key",
    [
        "display_name",
        "displayName",
        "email",
        "mail",
        "upn",
        "sAMAccountName",
        "last_logged_on_user",
        "payload",
        "name",
    ],
)
def test_pii_keys_are_redacted(capsys: pytest.CaptureFixture[str], key: str) -> None:
    configure_logging()
    get_logger().info("evt", **{key: "Test User 001"})
    assert _lines(capsys)[0][key] == REDACTED


def test_ids_and_counts_are_kept(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    get_logger().info(
        "evt",
        employee_id="E9000001",
        object_guid="00000000-0000-4000-8000-000000000001",
        hostname="WS-TEST-0001",
        record_count=12,
        run_id="00000000-0000-4000-8000-000000000002",
    )
    line = _lines(capsys)[0]
    assert line["employee_id"] == "E9000001"
    assert line["hostname"] == "WS-TEST-0001"
    assert line["record_count"] == 12


def test_nested_values_are_scrubbed(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    get_logger().info(
        "evt",
        context={"source": "ad", "auth": {"token": "fake"}, "items": [{"email": "x"}]},
    )
    ctx = _lines(capsys)[0]["context"]
    assert ctx["source"] == "ad"
    assert ctx["auth"]["token"] == REDACTED
    assert ctx["items"][0]["email"] == REDACTED


def test_secretstr_value_is_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    get_logger().info("evt", value=SecretStr("fake-value"))
    assert _lines(capsys)[0]["value"] == REDACTED


def test_email_and_bearer_in_text_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    get_logger().info("lookup user001@example.test", detail="header Bearer abc.def-ghi")
    line = _lines(capsys)[0]
    assert "user001@example.test" not in json.dumps(line)
    assert line["event"] == f"lookup {REDACTED}"
    assert line["detail"] == f"header Bearer {REDACTED}"


def test_stdlib_logging_is_json_and_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    logging.getLogger("thirdparty").warning(
        "contact user002@example.test", extra={"password": "fake-value", "attempt": 2}
    )
    line = _lines(capsys)[0]
    assert line["logger"] == "thirdparty"
    assert line["level"] == "warning"
    assert line["password"] == REDACTED
    assert line["attempt"] == 2
    assert "user002@example.test" not in line["event"]


def test_level_filtering(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("WARNING")
    log = get_logger()
    log.info("hidden")
    log.warning("shown")
    assert [ln["event"] for ln in _lines(capsys)] == ["shown"]


def test_noisy_loggers_are_quieted() -> None:
    configure_logging("DEBUG")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_reconfigure_does_not_duplicate_handlers(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    configure_logging()
    get_logger().info("once")
    assert len(_lines(capsys)) == 1


def test_exception_is_rendered_and_scrubbed(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    try:
        raise RuntimeError("bind failed for user003@example.test")
    except RuntimeError:
        get_logger().exception("failed")
    line = _lines(capsys)[0]
    assert "RuntimeError" in line["exception"]
    assert "user003@example.test" not in line["exception"]


def test_scrub_depth_limit() -> None:
    deep: Any = "leaf"
    for _ in range(MAX_DEPTH + 2):
        deep = {"k": deep}
    flat = json.dumps(scrub(deep))
    assert "leaf" not in flat
    assert REDACTED in flat


def test_scrub_sets_and_tuples() -> None:
    assert scrub(("a@example.test", 1)) == [REDACTED, 1]
    assert scrub({"x@example.test"}) == [REDACTED]
