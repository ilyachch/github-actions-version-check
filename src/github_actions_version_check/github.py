from dataclasses import asdict, dataclass
from typing import Any

import httpx

from github_actions_version_check.cache import CacheBackend
from github_actions_version_check.models import RepoVersionInfo, SemverTag
from github_actions_version_check.parsing import parse_semver_tag

MAX_TAG_PAGES = 5


@dataclass(frozen=True)
class SerializedRepoVersionInfo:
    latest_release: str | None
    tags: list[str]


class GitHubClient:
    def __init__(
        self,
        cache: CacheBackend,
        token: str | None = None,
        timeout_seconds: float = 20.0,
        max_tag_pages: int = MAX_TAG_PAGES,
    ) -> None:
        headers = {
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'github-actions-version-check',
        }
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self._cache = cache
        self._max_tag_pages = max_tag_pages
        self._client = httpx.Client(timeout=timeout_seconds, headers=headers)
        self._repo_cache: dict[str, RepoVersionInfo] = {}

    def close(self) -> None:
        self._client.close()

    def get_repo_version_info(self, repo_slug: str) -> RepoVersionInfo:
        key = repo_slug.lower()
        if key in self._repo_cache:
            return self._repo_cache[key]

        cached = self._load_cached_repo_version_info(repo_slug=key, allow_stale=False)
        if cached is not None:
            self._repo_cache[key] = cached
            return cached

        try:
            fresh = self._fetch_repo_version_info(repo_slug=repo_slug)
        except RuntimeError:
            stale = self._load_cached_repo_version_info(repo_slug=key, allow_stale=True)
            if stale is not None:
                self._repo_cache[key] = stale
                return stale
            raise

        self._cache.set(self._cache_key(key), asdict(self._serialize(fresh)))
        self._repo_cache[key] = fresh
        return fresh

    def _load_cached_repo_version_info(
        self,
        repo_slug: str,
        allow_stale: bool,
    ) -> RepoVersionInfo | None:
        key = self._cache_key(repo_slug)
        payload = self._cache.get_stale(key) if allow_stale else self._cache.get(key)
        return self._deserialize(payload)

    def _fetch_repo_version_info(self, repo_slug: str) -> RepoVersionInfo:
        latest_release = self._fetch_latest_release_tag(repo_slug)
        tags = self._fetch_semver_tags(repo_slug)

        if latest_release is not None:
            tags = [*tags, latest_release]

        unique_tags = self._deduplicate_sorted_tags(tags)
        latest_overall = max(unique_tags) if unique_tags else latest_release

        return RepoVersionInfo(
            latest_release=latest_release,
            latest_overall=latest_overall,
            tags=tuple(unique_tags),
        )

    def _fetch_latest_release_tag(self, repo_slug: str) -> SemverTag | None:
        url = f'https://api.github.com/repos/{repo_slug}/releases/latest'
        payload = self._request_json(url)
        if payload is None or not isinstance(payload, dict):
            return None
        tag_name = payload.get('tag_name')
        if not isinstance(tag_name, str):
            return None
        return parse_semver_tag(tag_name)

    def _fetch_semver_tags(self, repo_slug: str) -> list[SemverTag]:
        tags: list[SemverTag] = []
        for page in range(1, self._max_tag_pages + 1):
            url = f'https://api.github.com/repos/{repo_slug}/tags?per_page=100&page={page}'
            payload = self._request_json(url)
            if payload is None or not isinstance(payload, list):
                break

            tags.extend(self._extract_semver_tags(payload))
            if len(payload) < 100:
                break

        return tags

    def _extract_semver_tags(self, payload: list[Any]) -> list[SemverTag]:
        parsed_tags: list[SemverTag] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get('name')
            if not isinstance(name, str):
                continue
            parsed = parse_semver_tag(name)
            if parsed is not None:
                parsed_tags.append(parsed)
        return parsed_tags

    def _request_json(self, url: str) -> Any | None:
        try:
            response = self._client.get(url)
        except httpx.RequestError as exc:
            raise RuntimeError(f'Network error for {url}: {exc}') from exc

        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise RuntimeError(
                f'GitHub API error {response.status_code} for {url}: {response.text}'
            )

        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f'Invalid JSON response for {url}') from exc

    @staticmethod
    def _cache_key(repo_slug: str) -> str:
        return f'repo-version-info:{repo_slug}'

    def _serialize(self, value: RepoVersionInfo) -> SerializedRepoVersionInfo:
        return SerializedRepoVersionInfo(
            latest_release=value.latest_release.normalized
            if value.latest_release is not None
            else None,
            tags=[tag.normalized for tag in value.tags],
        )

    def _deserialize(self, payload: object) -> RepoVersionInfo | None:
        if not isinstance(payload, dict):
            return None

        tags_payload = payload.get('tags')
        if not isinstance(tags_payload, list):
            return None

        parsed_tags: list[SemverTag] = []
        for item in tags_payload:
            if not isinstance(item, str):
                continue
            parsed = parse_semver_tag(item)
            if parsed is not None:
                parsed_tags.append(parsed)

        latest_release_value = payload.get('latest_release')
        latest_release = None
        if isinstance(latest_release_value, str):
            latest_release = parse_semver_tag(latest_release_value)

        unique_tags = self._deduplicate_sorted_tags(
            [*parsed_tags, latest_release]
            if latest_release is not None
            else parsed_tags
        )
        latest_overall = max(unique_tags) if unique_tags else latest_release

        return RepoVersionInfo(
            latest_release=latest_release,
            latest_overall=latest_overall,
            tags=tuple(unique_tags),
        )

    @staticmethod
    def _deduplicate_sorted_tags(tags: list[SemverTag]) -> list[SemverTag]:
        deduped: dict[str, SemverTag] = {}
        for tag in tags:
            deduped[tag.normalized] = tag
        return sorted(deduped.values())
