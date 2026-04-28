from pathlib import Path

from github_actions_version_check.cache import JsonTTLCache


def test_json_ttl_cache_get_and_stale_access(tmp_path: Path) -> None:
    state = {'now': 1000.0}

    def fake_now() -> float:
        return state['now']

    cache = JsonTTLCache(path=tmp_path / 'cache.json', ttl_seconds=10, now=fake_now)
    cache.set('alpha', {'value': 1})

    assert cache.get('alpha') == {'value': 1}

    state['now'] = 1011.0
    assert cache.get('alpha') is None
    assert cache.get_stale('alpha') == {'value': 1}
