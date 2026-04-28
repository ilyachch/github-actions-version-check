from github_actions_version_check.parsing import (
    classify_ref,
    parse_action_ref,
    parse_semver_tag,
    parse_uses_line,
)


def test_parse_semver_tag_rejects_prerelease() -> None:
    assert parse_semver_tag('v4.2.1') is not None
    assert parse_semver_tag('v4.2.1-rc1') is None


def test_parse_action_ref_supports_subpaths() -> None:
    parsed = parse_action_ref('owner/repo/sub/path@v1.2.3')
    assert parsed is not None
    assert parsed.repo_slug == 'owner/repo'
    assert parsed.subpath == '/sub/path'


def test_parse_uses_line_preserves_comments_quotes_and_newline() -> None:
    line = '  uses: "actions/checkout@v4"  # pinned\n'
    parsed = parse_uses_line(line)
    assert parsed is not None
    assert parsed.value == 'actions/checkout@v4'
    assert parsed.render('actions/checkout@v4.2.1') == (
        '  uses: "actions/checkout@v4.2.1"  # pinned\n'
    )
    assert classify_ref('v4') == 'semver'
