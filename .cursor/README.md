# Cursor agent config

| File | Role |
|------|------|
| `rules/agent-router.mdc` | Always-on pointers to `AGENTS.md` and workflows |
| `rules/python-conventions.mdc` | `src/` + `tests/` Python style |
| `hooks.json` + `hooks/` | Track edits; run Ruff format/fix on agent stop |
| `environment.json` | Cloud Agent boot: `uv sync --group dev` |

## Workspace file

Open **`reskinned-fashionclip-service.code-workspace`** (repo root) so Cursor picks up Python interpreter, pytest, Ruff, and recommended extensions.

Folder-only opens still use `.vscode/settings.json` with the same defaults.

## Hooks

Same pattern as `reskinned-inventory`: `afterFileEdit` tracks paths; `stop` / `subagentStop` run `ruff format` + `ruff check --fix` on edited/dirty/branch-changed files.

Diagnostics: `${TMPDIR}/cursor-ruff-lint/last-stop.json`

Hook helper smoke test (optional):

```bash
python3 -m unittest discover -s .cursor/hooks -p 'test_*.py' 2>/dev/null || true
```

Inventory ships `test_ruff_common.py`; copy over if you want the same unit tests here.
