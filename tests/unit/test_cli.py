import json
from pathlib import Path
from typing import Any

import pytest

from jrg_asset_hub import __version__
from jrg_asset_hub.cli import EXIT_CONFIG_ERROR, EXIT_OK, main


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in capsys.readouterr().out.splitlines() if ln.strip()]


def test_main_logs_startup(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == EXIT_OK
    line = _lines(capsys)[0]
    assert line["event"] == "startup"
    assert line["version"] == __version__
    assert line["business_timezone"] == "America/New_York"


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_invalid_setting_exits_2_without_echoing_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("JRG_BUSINESS_TIMEZONE", "Fake/Zone_Value_123")
    assert main([]) == EXIT_CONFIG_ERROR
    out = capsys.readouterr().out
    assert "Fake/Zone_Value_123" not in out
    line = json.loads(out.splitlines()[0])
    assert line["event"] == "config_invalid"
    assert line["level"] == "error"
    assert line["errors"][0]["field"] == "business_timezone"


def test_env_and_file_conflict_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = tmp_path / "level"
    path.write_text("INFO")
    monkeypatch.setenv("JRG_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JRG_LOG_LEVEL_FILE", str(path))
    assert main([]) == EXIT_CONFIG_ERROR
    line = _lines(capsys)[0]
    assert line["event"] == "config_invalid"
    assert "not both" in line["errors"][0]["error"]
