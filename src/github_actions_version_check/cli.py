import sys
from importlib.metadata import version as distribution_version
from pathlib import Path

import typer

from github_actions_version_check.cache import CacheBackend, JsonTTLCache, NoopCache
from github_actions_version_check.checker import inspect_workflow_file
from github_actions_version_check.discovery import (
    DiscoveryError,
    find_project_root,
    find_workflow_files,
)
from github_actions_version_check.github import GitHubClient
from github_actions_version_check.models import CheckResult, CheckStatus
from github_actions_version_check.xdg import cache_dir

DEFAULT_CACHE_TTL_DAYS = 7
APP_NAME = 'github-actions-version-check'


def _version_callback(value: bool) -> bool:
    if value:
        print(distribution_version(APP_NAME))
        raise typer.Exit()
    return value


def run(
    fix: bool = typer.Option(
        False,
        '--fix',
        help='Rewrite workflow files in place.',
    ),
    allow_major: bool = typer.Option(
        False,
        '--allow-major',
        help='Allow updates across major versions when used with --fix.',
    ),
    token: str | None = typer.Option(
        None,
        '--token',
        envvar='GITHUB_TOKEN',
        help='GitHub token. Defaults to GITHUB_TOKEN env var.',
    ),
    verbose_skips: bool = typer.Option(
        False,
        '--verbose-skips',
        help='Show skipped refs too (SHA pins, non-semver refs, etc.).',
    ),
    cache_ttl_days: int = typer.Option(
        DEFAULT_CACHE_TTL_DAYS,
        '--cache-ttl-days',
        envvar='GITHUB_ACTIONS_VERSION_CHECK_CACHE_TTL_DAYS',
        min=1,
        help='Cache TTL in days for GitHub responses.',
    ),
    no_cache: bool = typer.Option(
        False,
        '--no-cache',
        envvar='GITHUB_ACTIONS_VERSION_CHECK_NO_CACHE',
        help='Disable disk cache for GitHub responses.',
    ),
    show_version: bool = typer.Option(
        False,
        '--version',
        callback=_version_callback,
        is_eager=True,
        help='Show version and exit.',
    ),
    path: Path = typer.Argument(
        '.',
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help='Directory to start upward search for a .github folder.',
    ),
) -> None:
    exit_code = _execute(
        fix=fix,
        allow_major=allow_major,
        token=token,
        verbose_skips=verbose_skips,
        cache_ttl_days=cache_ttl_days,
        no_cache=no_cache,
        start_dir=path,
    )
    raise typer.Exit(exit_code)


def entrypoint() -> None:
    typer.run(run)


def _execute(
    fix: bool,
    allow_major: bool,
    token: str | None,
    verbose_skips: bool,
    cache_ttl_days: int,
    no_cache: bool,
    start_dir: Path,
) -> int:
    try:
        project_root = find_project_root(start_dir)
    except DiscoveryError as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        return 1

    workflow_files = find_workflow_files(project_root)
    if not workflow_files:
        print(
            f'[ERROR] No workflow files found in {project_root / ".github/workflows"}',
            file=sys.stderr,
        )
        return 1

    cache_path = cache_dir() / 'github-api.json'
    ttl_seconds = cache_ttl_days * 24 * 60 * 60
    cache: CacheBackend
    if no_cache:
        cache = NoopCache()
    else:
        cache = JsonTTLCache(path=cache_path, ttl_seconds=ttl_seconds)

    github_client = GitHubClient(cache=cache, token=token)
    try:
        return _process_files(
            workflow_files=workflow_files,
            project_root=project_root,
            github_client=github_client,
            fix=fix,
            allow_major=allow_major,
            verbose_skips=verbose_skips,
        )
    finally:
        github_client.close()


def _process_files(
    workflow_files: list[Path],
    project_root: Path,
    github_client: GitHubClient,
    fix: bool,
    allow_major: bool,
    verbose_skips: bool,
) -> int:
    any_outdated = False
    any_changed = False
    had_errors = False

    for workflow_file in workflow_files:
        try:
            results, updated_text = inspect_workflow_file(
                path=workflow_file,
                github_client=github_client,
                allow_major=allow_major,
            )
        except Exception as exc:
            print(f'[ERROR] {workflow_file}: {exc}', file=sys.stderr)
            had_errors = True
            continue

        if _should_print_file_header(results, verbose_skips):
            print(f'\n==> {_display_path(workflow_file, project_root)}')

        for result in results:
            if result.status is CheckStatus.OK:
                continue
            if result.status is CheckStatus.SKIPPED and not verbose_skips:
                continue
            _print_result(result=result, fix=fix)
            if result.status is CheckStatus.OUTDATED:
                any_outdated = True

        if fix and updated_text is not None:
            workflow_file.write_text(updated_text, encoding='utf-8')
            any_changed = True

    return _finalize_exit_code(
        any_outdated=any_outdated,
        any_changed=any_changed,
        had_errors=had_errors,
        fix=fix,
    )


def _display_path(path: Path, project_root: Path) -> Path:
    try:
        return path.relative_to(project_root)
    except ValueError:
        return path


def _should_print_file_header(
    results: list[CheckResult],
    verbose_skips: bool,
) -> bool:
    for result in results:
        if result.status is CheckStatus.OK:
            continue
        if result.status is CheckStatus.SKIPPED and not verbose_skips:
            continue
        return True
    return False


def _print_result(result: CheckResult, fix: bool) -> None:
    if result.status is CheckStatus.SKIPPED:
        print(f'  L{result.line_number}: SKIP  {result.current_value}  [{result.note}]')
        return

    print(
        f'  L{result.line_number}: OUTDATED  {result.current_value}\n'
        f'      repo:           {result.repo_slug}\n'
        f'      current:        {result.current_ref}\n'
        f'      latest-major:   {result.latest_same_major or "-"}\n'
        f'      latest-overall: {result.latest_overall or "-"}'
    )
    if result.note:
        print(f'      note:           {result.note}')
    if fix and result.replacement_value:
        print(f'      fixed-to:       {result.replacement_value}')


def _finalize_exit_code(
    any_outdated: bool,
    any_changed: bool,
    had_errors: bool,
    fix: bool,
) -> int:
    if had_errors:
        return 1

    if fix:
        if any_changed:
            print('\nApplied updates.')
        else:
            print('\nNo changes needed.')
        return 0

    if any_outdated:
        return 2

    print(
        'All checked GitHub Actions are up to date within their current major versions.'
    )
    return 0
