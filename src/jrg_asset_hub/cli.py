"""Command-line entry point.

Each subcommand is one schedulable job. Subcommands are added in later PRs
(see docs/PLAN.md section 7).
"""

import argparse
from collections.abc import Sequence

from pydantic import ValidationError

from jrg_asset_hub import __version__
from jrg_asset_hub.config import AppSettings, ConfigError
from jrg_asset_hub.logging import configure_logging, get_logger

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jrg-asset-hub")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def load_settings() -> AppSettings | None:
    """Load settings. On failure, log field names only (never values)."""
    try:
        return AppSettings()
    except ValidationError as exc:
        configure_logging()
        errors = [
            {"field": ".".join(str(p) for p in e["loc"]), "error": e["msg"]}
            for e in exc.errors(include_input=False, include_url=False)
        ]
        get_logger(__name__).error("config_invalid", errors=errors)
    except ConfigError as exc:
        configure_logging()
        get_logger(__name__).error("config_invalid", errors=[{"error": str(exc)}])
    return None


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    settings = load_settings()
    if settings is None:
        return EXIT_CONFIG_ERROR
    configure_logging(settings.log_level)
    get_logger(__name__).info(
        "startup", version=__version__, business_timezone=settings.business_timezone
    )
    return EXIT_OK
