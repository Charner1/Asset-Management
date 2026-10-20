"""REQ-041: every dependency is pinned to an exact version."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXACT_PIN = re.compile(r"^[A-Za-z0-9_.\-]+(\[[A-Za-z0-9_,\-]+\])?==[A-Za-z0-9_.]+$")


def _pyproject() -> dict:  # type: ignore[type-arg]
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def _all_requirements() -> list[str]:
    data = _pyproject()
    reqs = list(data["project"]["dependencies"])
    for extra in data["project"].get("optional-dependencies", {}).values():
        reqs.extend(extra)
    reqs.extend(data["build-system"]["requires"])
    return reqs


def test_every_dependency_is_exactly_pinned() -> None:
    loose = [r for r in _all_requirements() if not EXACT_PIN.match(r)]
    assert loose == [], f"not exactly pinned: {loose}"


def test_lock_files_have_hashes() -> None:
    for name in ("requirements.lock", "requirements-dev.lock"):
        text = (ROOT / name).read_text()
        pins = [ln for ln in text.splitlines() if re.match(r"^[a-z0-9]", ln)]
        assert pins, f"{name} has no pins"
        assert all("==" in ln for ln in pins), f"{name} has a loose pin"
        assert text.count("--hash=sha256:") >= len(pins), f"{name} is missing hashes"


def test_lock_files_cover_direct_dependencies() -> None:
    dev_lock = (ROOT / "requirements-dev.lock").read_text().lower()
    for req in _all_requirements():
        name = re.split(r"[\[=]", req)[0].lower()
        version = req.split("==")[1]
        assert f"{name}=={version}" in dev_lock, f"{req} missing from requirements-dev.lock"
