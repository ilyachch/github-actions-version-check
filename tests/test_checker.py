from pathlib import Path

from github_actions_version_check.checker import inspect_workflow_file
from github_actions_version_check.models import CheckStatus, RepoVersionInfo, SemverTag


class FakeGitHubClient:
    def __init__(self, version_info: RepoVersionInfo) -> None:
        self.version_info = version_info
        self.requested_repo_slugs: list[str] = []

    def get_repo_version_info(self, repo_slug: str) -> RepoVersionInfo:
        self.requested_repo_slugs.append(repo_slug)
        return self.version_info


def _write_workflow(path: Path, uses_ref: str) -> None:
    path.write_text(
        (
            'name: CI\n'
            'on: push\n'
            'jobs:\n'
            '  test:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            f'      uses: actions/checkout@{uses_ref}\n'
        ),
        encoding='utf-8',
    )


def _version_info(tags: list[SemverTag]) -> RepoVersionInfo:
    latest_overall = max(tags) if tags else None
    latest_release = max(tags) if tags else None
    return RepoVersionInfo(
        latest_release=latest_release,
        latest_overall=latest_overall,
        tags=tuple(tags),
    )


def test_same_major_updates_fail_check_without_allow_major(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / 'ci.yml'
    _write_workflow(workflow, 'v4.0.0')
    github_client = FakeGitHubClient(
        _version_info(
            [
                SemverTag(major=4, minor=0, patch=1, raw='v4.0.1'),
                SemverTag(major=5, minor=0, patch=0, raw='v5.0.0'),
            ]
        )
    )

    results, updated_text = inspect_workflow_file(
        path=workflow,
        github_client=github_client,
        allow_major=False,
    )

    assert len(results) == 1
    assert results[0].status is CheckStatus.OUTDATED
    assert results[0].replacement_value == 'actions/checkout@v4.0.1'
    assert updated_text is not None
    assert 'actions/checkout@v4.0.1' in updated_text


def test_major_only_updates_fail_only_with_allow_major(
    tmp_path: Path,
) -> None:
    workflow = tmp_path / 'ci.yml'
    _write_workflow(workflow, 'v4.0.0')
    github_client = FakeGitHubClient(
        _version_info([SemverTag(major=5, minor=0, patch=0, raw='v5.0.0')])
    )

    results_without_allow_major, updated_without_allow_major = inspect_workflow_file(
        path=workflow,
        github_client=github_client,
        allow_major=False,
    )
    results_with_allow_major, updated_with_allow_major = inspect_workflow_file(
        path=workflow,
        github_client=github_client,
        allow_major=True,
    )

    assert updated_without_allow_major is None
    assert len(results_without_allow_major) == 1
    assert results_without_allow_major[0].status is CheckStatus.OK
    assert results_without_allow_major[0].replacement_value is None

    assert len(results_with_allow_major) == 1
    assert results_with_allow_major[0].status is CheckStatus.OUTDATED
    assert results_with_allow_major[0].replacement_value == 'actions/checkout@v5.0.0'
    assert updated_with_allow_major is not None
    assert 'actions/checkout@v5.0.0' in updated_with_allow_major
