from importlib.metadata import version as distribution_version
from pathlib import Path

import pytest
import typer
from click import Command
from click.testing import CliRunner
from typer.main import get_command

import github_actions_version_check.cli as cli


def _build_command() -> Command:
    app = typer.Typer(add_completion=False)
    app.command()(cli.run)
    return get_command(app)


def test_run_defaults_to_current_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_start_dir: Path | None = None

    def fake_execute(
        fix: bool,
        allow_major: bool,
        token: str | None,
        verbose_skips: bool,
        cache_ttl_days: int,
        no_cache: bool,
        start_dir: Path,
    ) -> int:
        nonlocal captured_start_dir
        captured_start_dir = start_dir
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, '_execute', fake_execute)

    result = CliRunner().invoke(_build_command(), [])

    assert result.exit_code == 0
    assert captured_start_dir == tmp_path.resolve()


def test_run_accepts_positional_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_start_dir: Path | None = None

    def fake_execute(
        fix: bool,
        allow_major: bool,
        token: str | None,
        verbose_skips: bool,
        cache_ttl_days: int,
        no_cache: bool,
        start_dir: Path,
    ) -> int:
        nonlocal captured_start_dir
        captured_start_dir = start_dir
        return 0

    monkeypatch.setattr(cli, '_execute', fake_execute)

    result = CliRunner().invoke(_build_command(), [str(tmp_path)])

    assert result.exit_code == 0
    assert captured_start_dir == tmp_path.resolve()


def test_run_reads_cache_settings_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_cache_ttl_days: int | None = None
    captured_no_cache = False
    captured_start_dir: Path | None = None

    def fake_execute(
        fix: bool,
        allow_major: bool,
        token: str | None,
        verbose_skips: bool,
        cache_ttl_days: int,
        no_cache: bool,
        start_dir: Path,
    ) -> int:
        nonlocal captured_cache_ttl_days, captured_no_cache, captured_start_dir
        captured_cache_ttl_days = cache_ttl_days
        captured_no_cache = no_cache
        captured_start_dir = start_dir
        return 0

    monkeypatch.setenv('GITHUB_ACTIONS_VERSION_CHECK_CACHE_TTL_DAYS', '11')
    monkeypatch.setenv('GITHUB_ACTIONS_VERSION_CHECK_NO_CACHE', '1')
    monkeypatch.setattr(cli, '_execute', fake_execute)

    result = CliRunner().invoke(_build_command(), [str(tmp_path)])

    assert result.exit_code == 0
    assert captured_cache_ttl_days == 11
    assert captured_no_cache is True
    assert captured_start_dir == tmp_path.resolve()


def test_run_rejects_start_dir_option(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        _build_command(),
        ['--start-dir', str(tmp_path)],
    )
    assert result.exit_code != 0


def test_version_option_prints_package_version() -> None:
    result = CliRunner().invoke(_build_command(), ['--version'])

    assert result.exit_code == 0
    assert result.output.strip() == distribution_version('github-actions-version-check')
