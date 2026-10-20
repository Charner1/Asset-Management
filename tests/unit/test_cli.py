import pytest

from jrg_asset_hub import __version__
from jrg_asset_hub.cli import main


def test_main_with_no_args_exits_zero() -> None:
    assert main([]) == 0


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
