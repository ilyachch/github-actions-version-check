![PyPI](https://img.shields.io/pypi/v/github-actions-version-check)
![Python](https://img.shields.io/pypi/pyversions/github-actions-version-check)
![License](https://img.shields.io/github/license/ilyachch/github-actions-version-check)

# github-actions-version-check

A CLI tool to check and update GitHub Action versions in workflow files.

It scans `.github/workflows`, detects outdated `uses:` references, and can optionally rewrite them in place.

---

## ✨ Features

- Detect outdated GitHub Actions (`uses: owner/repo@ref`)
- Supports semantic version comparison
- Safe updates within the same major version by default
- Optional major upgrades (`--allow-major`)
- In-place rewriting (`--fix`)
- Pre-commit integration
- XDG-compliant cache (with TTL) to reduce GitHub API calls
- Works without a token (but supports `GITHUB_TOKEN` for higher limits)

---

## 📦 Installation

### Using uv (recommended)

```bash
uvx github-actions-version-check
```

### Using pipx

```bash
pipx install github-actions-version-check
```

---

## 🚀 Usage

### Check workflows

```bash
github-actions-version-check
```

Exit codes:

* `0` → everything is up to date
* `2` → outdated refs found
* `1` → error

---

### Check a specific directory

```bash
github-actions-version-check /path/to/repo
```

---

### Fix outdated versions

```bash
github-actions-version-check --fix
```

---

### Allow major upgrades

```bash
github-actions-version-check --fix --allow-major
```

---

### Show version

```bash
github-actions-version-check --version
```

---

## ⚙️ Configuration

### Environment variables

| Variable                                      | Description                                |
| --------------------------------------------- | ------------------------------------------ |
| `GITHUB_TOKEN`                                | Optional GitHub token to avoid rate limits |
| `GITHUB_ACTIONS_VERSION_CHECK_CACHE_TTL_DAYS` | Cache TTL (default: 7 days)                |
| `GITHUB_ACTIONS_VERSION_CHECK_NO_CACHE`       | Disable cache                              |

---

## 🧠 How it works

* Scans `.github/workflows/*.yml` and `.yaml`
* Extracts `uses:` lines
* Resolves latest versions via GitHub API
* Compares semantic versions
* Optionally rewrites outdated refs

### Supported patterns

```yaml
uses: actions/checkout@v4
uses: owner/repo@v1.2.3
```

### Limitations

* Only simple `uses:` lines are supported
* Multiline YAML (`|`, `>`) is not parsed
* SHA-pinned actions are skipped

---

## 🔌 Pre-commit integration

```yaml
repos:
  - repo: https://github.com/ilyachch/github-actions-version-check
    rev: v1.0.0
    hooks:
      - id: github-actions-version-check
        args: [--fix]
```

---

## 🗂 Cache

Stored in:

```text
$XDG_CACHE_HOME/github_actions_version_check/github-api.json
```

Fallback:

```text
~/.cache/github_actions_version_check/github-api.json
```

---

## 🛠 Development

```bash
uv sync
uv run pytest
uv run mypy
```

---

## 📄 License

MIT
