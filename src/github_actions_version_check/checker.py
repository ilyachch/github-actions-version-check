from pathlib import Path
from typing import Protocol

from github_actions_version_check.models import (
    ActionRef,
    CheckResult,
    CheckStatus,
    RepoVersionInfo,
    SemverTag,
    UsesLine,
)
from github_actions_version_check.parsing import (
    classify_ref,
    parse_action_ref,
    parse_semver_tag,
    parse_uses_line,
)


class SupportsRepoVersionInfo(Protocol):
    def get_repo_version_info(self, repo_slug: str) -> RepoVersionInfo: ...


def inspect_workflow_file(
    path: Path,
    github_client: SupportsRepoVersionInfo,
    allow_major: bool,
) -> tuple[list[CheckResult], str | None]:
    file_text = path.read_text(encoding='utf-8')
    lines = file_text.splitlines(keepends=True)
    updated_lines = list(lines)

    results: list[CheckResult] = []
    changed = False

    for line_number, line in enumerate(lines, start=1):
        uses_line = parse_uses_line(line)
        if uses_line is None:
            continue

        result, replacement_value = inspect_uses_line(
            file_path=path,
            line_number=line_number,
            uses_line=uses_line,
            github_client=github_client,
            allow_major=allow_major,
        )
        if result is None:
            continue

        results.append(result)
        if replacement_value is not None:
            updated_lines[line_number - 1] = uses_line.render(replacement_value)
            changed = True

    updated_text = ''.join(updated_lines) if changed else None
    return results, updated_text


def inspect_uses_line(
    file_path: Path,
    line_number: int,
    uses_line: UsesLine,
    github_client: SupportsRepoVersionInfo,
    allow_major: bool,
) -> tuple[CheckResult | None, str | None]:
    parsed_ref = parse_action_ref(uses_line.value)
    if parsed_ref is None:
        return None, None

    ref_kind = classify_ref(parsed_ref.ref)
    if ref_kind == 'sha':
        return _skip_result(
            file_path=file_path,
            line_number=line_number,
            parsed_ref=parsed_ref,
            note='SHA-pinned, skipped',
        ), None
    if ref_kind != 'semver':
        return _skip_result(
            file_path=file_path,
            line_number=line_number,
            parsed_ref=parsed_ref,
            note='Non-semver ref, skipped',
        ), None

    current_tag = parse_semver_tag(parsed_ref.ref)
    if current_tag is None:
        return _skip_result(
            file_path=file_path,
            line_number=line_number,
            parsed_ref=parsed_ref,
            note='Could not parse semver ref',
        ), None

    version_info = github_client.get_repo_version_info(parsed_ref.repo_slug)
    latest_same_major = latest_in_same_major(version_info.tags, current_tag.major)
    replacement = choose_replacement(
        action_ref=parsed_ref,
        current_tag=current_tag,
        latest_same_major=latest_same_major,
        latest_overall=version_info.latest_overall,
        allow_major=allow_major,
    )

    notes = _build_notes(
        current_tag=current_tag,
        latest_same_major=latest_same_major,
        latest_overall=version_info.latest_overall,
    )
    status = _select_status(
        current_tag=current_tag,
        latest_same_major=latest_same_major,
        latest_overall=version_info.latest_overall,
        allow_major=allow_major,
    )

    normalized_replacement = None
    if replacement is not None and replacement != uses_line.value:
        normalized_replacement = replacement

    return (
        CheckResult(
            file=file_path,
            line_number=line_number,
            current_value=uses_line.value,
            current_ref=parsed_ref.ref,
            repo_slug=parsed_ref.repo_slug,
            latest_same_major=latest_same_major.normalized
            if latest_same_major is not None
            else None,
            latest_overall=version_info.latest_overall.normalized
            if version_info.latest_overall is not None
            else None,
            status=status,
            replacement_value=normalized_replacement,
            note='; '.join(notes) if notes else None,
        ),
        normalized_replacement,
    )


def _select_status(
    current_tag: SemverTag,
    latest_same_major: SemverTag | None,
    latest_overall: SemverTag | None,
    allow_major: bool,
) -> CheckStatus:
    if latest_same_major is not None and latest_same_major > current_tag:
        return CheckStatus.OUTDATED
    if allow_major and latest_overall is not None and latest_overall > current_tag:
        return CheckStatus.OUTDATED
    return CheckStatus.OK


def latest_in_same_major(tags: tuple[SemverTag, ...], major: int) -> SemverTag | None:
    matching_tags = [tag for tag in tags if tag.major == major]
    if not matching_tags:
        return None
    return max(matching_tags)


def choose_replacement(
    action_ref: ActionRef,
    current_tag: SemverTag,
    latest_same_major: SemverTag | None,
    latest_overall: SemverTag | None,
    allow_major: bool,
) -> str | None:
    target = None
    if allow_major and latest_overall is not None and latest_overall > current_tag:
        target = latest_overall
    elif latest_same_major is not None and latest_same_major > current_tag:
        target = latest_same_major

    if target is None:
        return None
    return f'{action_ref.canonical_prefix}@{target.normalized}'


def _skip_result(
    file_path: Path,
    line_number: int,
    parsed_ref: ActionRef,
    note: str,
) -> CheckResult:
    return CheckResult(
        file=file_path,
        line_number=line_number,
        current_value=parsed_ref.full_value,
        current_ref=parsed_ref.ref,
        repo_slug=parsed_ref.repo_slug,
        latest_same_major=None,
        latest_overall=None,
        status=CheckStatus.SKIPPED,
        note=note,
    )


def _build_notes(
    current_tag: SemverTag,
    latest_same_major: SemverTag | None,
    latest_overall: SemverTag | None,
) -> list[str]:
    notes: list[str] = []
    if latest_same_major is not None and latest_same_major > current_tag:
        notes.append(f'same major has newer tag {latest_same_major.normalized}')
    if latest_overall is not None and latest_overall.major > current_tag.major:
        notes.append(f'newer major exists: {latest_overall.normalized}')
    return notes
