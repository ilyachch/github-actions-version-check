from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class CheckStatus(StrEnum):
    OK = 'ok'
    OUTDATED = 'outdated'
    SKIPPED = 'skipped'


@dataclass(frozen=True, order=True)
class SemverTag:
    major: int
    minor: int
    patch: int
    raw: str = field(compare=False)

    @property
    def normalized(self) -> str:
        return f'v{self.major}.{self.minor}.{self.patch}'


@dataclass(frozen=True)
class ActionRef:
    owner: str
    repo: str
    subpath: str | None
    ref: str
    full_value: str

    @property
    def repo_slug(self) -> str:
        return f'{self.owner}/{self.repo}'

    @property
    def canonical_prefix(self) -> str:
        if self.subpath:
            return f'{self.repo_slug}{self.subpath}'
        return self.repo_slug


@dataclass(frozen=True)
class UsesLine:
    indent: str
    key: str
    separator: str
    quote: str
    value: str
    comment: str
    newline: str

    def render(self, replacement_value: str) -> str:
        return (
            f'{self.indent}{self.key}{self.separator}{self.quote}{replacement_value}'
            f'{self.quote}{self.comment}{self.newline}'
        )


@dataclass(frozen=True)
class RepoVersionInfo:
    latest_release: SemverTag | None
    latest_overall: SemverTag | None
    tags: tuple[SemverTag, ...]


@dataclass(frozen=True)
class CheckResult:
    file: Path
    line_number: int
    current_value: str
    current_ref: str
    repo_slug: str
    latest_same_major: str | None
    latest_overall: str | None
    status: CheckStatus
    replacement_value: str | None = None
    note: str | None = None
