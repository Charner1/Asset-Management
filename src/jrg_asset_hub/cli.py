"""Command-line entry point.

Each subcommand is one schedulable job. Subcommands are added in later PRs
(see docs/PLAN.md section 7).
"""

import argparse
from collections.abc import Sequence

from jrg_asset_hub import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jrg-asset-hub")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
