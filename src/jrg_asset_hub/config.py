"""Settings loaded from environment variables or mounted files.

Every setting ``x`` on a ``JrgSettings`` subclass is read from env var
``<PREFIX>X``, or from the file named by ``<PREFIX>X_FILE``. Setting both is
an error. See docs/adr/0005-secrets-handling.md.
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

FILE_SUFFIX = "_FILE"
MAX_SECRET_FILE_BYTES = 64 * 1024


class ConfigError(Exception):
    """Configuration is invalid. Messages never include setting values."""


def read_secret_file(path: Path, var_name: str) -> str:
    """Read one value from a mounted file. Strip one trailing newline."""
    if not path.is_file():
        raise ConfigError(f"{var_name} points to a path that is not a readable file")
    if path.stat().st_size > MAX_SECRET_FILE_BYTES:
        raise ConfigError(f"{var_name} points to a file larger than {MAX_SECRET_FILE_BYTES} bytes")
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{var_name} points to a file that cannot be read as UTF-8") from exc
    value = value.removesuffix("\n").removesuffix("\r")
    if not value:
        raise ConfigError(f"{var_name} points to an empty file")
    return value


class FileEnvSettingsSource(PydanticBaseSettingsSource):
    """Reads ``<PREFIX><FIELD>_FILE`` env vars and loads the named files."""

    def __init__(
        self, settings_cls: type[BaseSettings], environ: Mapping[str, str] | None = None
    ) -> None:
        super().__init__(settings_cls)
        self._environ = os.environ if environ is None else environ

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        # Not used: __call__ resolves all fields at once.
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        prefix = str(self.config.get("env_prefix", "")).upper()
        env = {k.upper(): v for k, v in self._environ.items()}
        values: dict[str, Any] = {}
        for name in self.settings_cls.model_fields:
            env_name = f"{prefix}{name}".upper()
            file_var = f"{env_name}{FILE_SUFFIX}"
            if file_var not in env:
                continue
            if env_name in env:
                raise ConfigError(f"set {env_name} or {file_var}, not both")
            values[name] = read_secret_file(Path(env[file_var]), file_var)
        return values


class JrgSettings(BaseSettings):
    """Base for all settings classes. Subclasses set their own env_prefix."""

    model_config = SettingsConfigDict(env_prefix="JRG_", extra="ignore", frozen=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # No .env loading and no pydantic secrets_dir: one documented path only.
        return (init_settings, env_settings, FileEnvSettingsSource(settings_cls))


class AppSettings(JrgSettings):
    """Settings shared by every command."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    business_timezone: str = "America/New_York"

    @field_validator("business_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("not a valid IANA time zone") from exc
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)
