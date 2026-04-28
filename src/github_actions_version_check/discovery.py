from pathlib import Path

WORKFLOWS_DIR = Path('.github/workflows')


class DiscoveryError(RuntimeError):
    """Raised when workflow discovery prerequisites are missing."""


def find_project_root(start_dir: Path) -> Path:
    resolved_start = start_dir.resolve()
    for candidate in [resolved_start, *resolved_start.parents]:
        if (candidate / '.github').is_dir():
            return candidate
    raise DiscoveryError(
        f'Could not find a .github directory while searching upward from {resolved_start}'
    )


def find_workflow_files(project_root: Path) -> list[Path]:
    workflows_dir = project_root / WORKFLOWS_DIR
    if not workflows_dir.is_dir():
        return []

    yml_files = sorted(workflows_dir.glob('*.yml'))
    yaml_files = sorted(workflows_dir.glob('*.yaml'))
    return [*yml_files, *yaml_files]
