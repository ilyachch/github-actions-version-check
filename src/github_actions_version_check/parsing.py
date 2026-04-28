import re
from typing import Literal

from github_actions_version_check.models import ActionRef, SemverTag, UsesLine

RefKind = Literal['sha', 'semver', 'other']

USES_RE = re.compile(
    r"""
    ^(?P<indent>\s*)
    (?P<key>uses)
    (?P<separator>\s*:\s*)
    (?P<quote>["']?)
    (?P<value>[^"'#\n]+?)
    (?P=quote)
    (?P<comment>\s*(?:\#.*)?)
    $
    """,
    re.VERBOSE,
)

REMOTE_USES_RE = re.compile(
    r"""
    ^
    (?P<owner>[A-Za-z0-9_.-]+)/
    (?P<repo>[A-Za-z0-9_.-]+)
    (?P<subpath>/[^@]+?)?
    @
    (?P<ref>[^/\s]+)
    $
    """,
    re.VERBOSE,
)

SHA1_RE = re.compile(r'^[0-9a-f]{40}$', re.IGNORECASE)
SEMVER_RE = re.compile(r'^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?$')


def parse_uses_line(line: str) -> UsesLine | None:
    raw_line = line.removesuffix('\n')
    match = USES_RE.match(raw_line)
    if match is None:
        return None
    return UsesLine(
        indent=match.group('indent'),
        key=match.group('key'),
        separator=match.group('separator'),
        quote=match.group('quote'),
        value=match.group('value').strip(),
        comment=match.group('comment'),
        newline='\n' if line.endswith('\n') else '',
    )


def parse_action_ref(value: str) -> ActionRef | None:
    trimmed = value.strip()

    if trimmed.startswith('./'):
        return None
    if trimmed.startswith('docker://'):
        return None
    if '${{' in trimmed:
        return None

    match = REMOTE_USES_RE.fullmatch(trimmed)
    if match is None:
        return None

    return ActionRef(
        owner=match.group('owner'),
        repo=match.group('repo'),
        subpath=match.group('subpath'),
        ref=match.group('ref'),
        full_value=trimmed,
    )


def parse_semver_tag(tag: str) -> SemverTag | None:
    match = SEMVER_RE.fullmatch(tag.strip())
    if match is None:
        return None
    return SemverTag(
        major=int(match.group('major')),
        minor=int(match.group('minor') or 0),
        patch=int(match.group('patch') or 0),
        raw=tag,
    )


def classify_ref(ref: str) -> RefKind:
    trimmed = ref.strip()
    if SHA1_RE.fullmatch(trimmed):
        return 'sha'
    if SEMVER_RE.fullmatch(trimmed):
        return 'semver'
    return 'other'
