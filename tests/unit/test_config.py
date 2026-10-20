"""REQ-005: settings come from env vars or mounted files, never the repo."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict

from jrg_asset_hub.config import (
    MAX_SECRET_FILE_BYTES,
    AppSettings,
    ConfigError,
    FileEnvSettingsSource,
    JrgSettings,
    read_secret_file,
)

FAKE_SECRET = "fake-value-for-tests"


class _DemoSettings(JrgSettings):
    model_config = SettingsConfigDict(env_prefix="JRG_DEMO_")

    api_key: SecretStr
    region: str = "test"


def _write(tmp_path: Path, content: bytes, name: str = "secret") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_defaults() -> None:
    settings = AppSettings()
    assert settings.log_level == "INFO"
    assert settings.business_timezone == "America/New_York"
    assert settings.tz.key == "America/New_York"


def test_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JRG_LOG_LEVEL", "DEBUG")
    assert AppSettings().log_level == "DEBUG"


def test_reads_file_var_and_strips_newline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JRG_LOG_LEVEL_FILE", str(_write(tmp_path, b"WARNING\n")))
    assert AppSettings().log_level == "WARNING"


def test_strips_crlf(tmp_path: Path) -> None:
    assert read_secret_file(_write(tmp_path, b"abc\r\n"), "X_FILE") == "abc"


def test_keeps_inner_whitespace(tmp_path: Path) -> None:
    assert read_secret_file(_write(tmp_path, b" a b \n"), "X_FILE") == " a b "


def test_env_and_file_both_set_is_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JRG_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("JRG_LOG_LEVEL_FILE", str(_write(tmp_path, b"INFO")))
    with pytest.raises(ConfigError, match="not both"):
        AppSettings()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"\n", "empty"),
        (b"\xff\xfe\xfa", "UTF-8"),
        (b"x" * (MAX_SECRET_FILE_BYTES + 1), "larger than"),
    ],
)
def test_bad_file_content(tmp_path: Path, content: bytes, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        read_secret_file(_write(tmp_path, content), "X_FILE")


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a readable file"):
        read_secret_file(tmp_path / "absent", "X_FILE")


def test_directory_is_not_a_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a readable file"):
        read_secret_file(tmp_path, "X_FILE")


def test_unreadable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write(tmp_path, b"abc")

    def _deny(*_: object, **__: object) -> str:
        raise PermissionError

    monkeypatch.setattr(Path, "read_text", _deny)
    with pytest.raises(ConfigError, match="cannot be read"):
        read_secret_file(path, "X_FILE")


def test_error_message_never_contains_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JRG_DEMO_API_KEY", FAKE_SECRET)
    monkeypatch.setenv("JRG_DEMO_API_KEY_FILE", str(_write(tmp_path, FAKE_SECRET.encode())))
    with pytest.raises(ConfigError) as exc:
        _DemoSettings()  # type: ignore[call-arg]
    assert FAKE_SECRET not in str(exc.value)


def test_secret_from_file_is_hidden_in_repr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JRG_DEMO_API_KEY_FILE", str(_write(tmp_path, FAKE_SECRET.encode())))
    settings = _DemoSettings()  # type: ignore[call-arg]
    assert settings.api_key.get_secret_value() == FAKE_SECRET
    assert FAKE_SECRET not in repr(settings)
    assert FAKE_SECRET not in str(settings.model_dump())


def test_subclass_prefix_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JRG_DEMO_API_KEY", FAKE_SECRET)
    monkeypatch.setenv("JRG_REGION", "wrong-prefix")
    settings = _DemoSettings()  # type: ignore[call-arg]
    assert settings.region == "test"


def test_env_var_names_are_case_insensitive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("jrg_demo_api_key_file", str(_write(tmp_path, FAKE_SECRET.encode())))
    settings = _DemoSettings()  # type: ignore[call-arg]
    assert settings.api_key.get_secret_value() == FAKE_SECRET


def test_dotenv_file_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("JRG_LOG_LEVEL=ERROR\n")
    monkeypatch.chdir(tmp_path)
    assert AppSettings().log_level == "INFO"


def test_invalid_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JRG_BUSINESS_TIMEZONE", "Not/A_Zone")
    with pytest.raises(ValidationError, match="IANA"):
        AppSettings()


def test_settings_are_frozen() -> None:
    settings = AppSettings()
    with pytest.raises(ValidationError):
        settings.log_level = "DEBUG"  # type: ignore[misc]


def test_source_with_explicit_environ(tmp_path: Path) -> None:
    path = _write(tmp_path, b"ERROR")
    source = FileEnvSettingsSource(AppSettings, environ={"JRG_LOG_LEVEL_FILE": str(path)})
    assert source() == {"log_level": "ERROR"}
    assert source.get_field_value(AppSettings.model_fields["log_level"], "log_level") == (
        None,
        "log_level",
        False,
    )
