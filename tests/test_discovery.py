from pathlib import Path

import pytest

from github_actions_version_check.discovery import (
    DiscoveryError,
    find_project_root,
    find_workflow_files,
)


def test_find_project_root_searches_upward(tmp_path: Path) -> None:
    root = tmp_path / 'repo'
    nested = root / 'a' / 'b'
    workflows = root / '.github' / 'workflows'

    nested.mkdir(parents=True)
    workflows.mkdir(parents=True)
    (workflows / 'ci.yml').write_text('name: CI\n', encoding='utf-8')

    found_root = find_project_root(nested)

    assert found_root == root
    assert find_workflow_files(found_root) == [workflows / 'ci.yml']


def test_find_project_root_raises_without_github(tmp_path: Path) -> None:
    child = tmp_path / 'repo' / 'child'
    child.mkdir(parents=True)

    with pytest.raises(DiscoveryError):
        find_project_root(child)
