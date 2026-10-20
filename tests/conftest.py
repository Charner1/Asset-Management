import logging
import os
from collections.abc import Iterator

import pytest
import structlog


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never see real JRG_* settings from the host."""
    for key in list(os.environ):
        if key.upper().startswith("JRG_"):
            monkeypatch.delenv(key)


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    yield
    structlog.reset_defaults()
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
