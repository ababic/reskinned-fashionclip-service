"""Shared helpers for Cursor Ruff hooks.

Hooks always fail open (print ``{}`` and exit 0) so a broken environment never
blocks the agent. Prefer ``app/.venv/bin/ruff`` so host + Docker lockfile stay aligned.

``afterFileEdit`` only tracks paths (no Ruff). Stop lint is broader but still
file-scoped: tracked edits + payload ``modified_files`` + git dirty/untracked +
branch-changed vs ``origin/staging`` — never a full-tree walk of ``app/``.

Every skip / run writes ``${TMPDIR}/cursor-ruff-lint/last-stop.json`` so silent
no-ops are diagnosable after the fact.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SKIP_PATH_PARTS = (".venv", "site-packages", "node_modules")
STATE_DIR = Path(os.environ.get("TMPDIR", "/tmp")) / "cursor-ruff-lint"
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
# Soft cap for branch-diff stop lint (vs origin/staging); dirty/tracked are uncapped.
BRANCH_DIFF_FILE_CAP = 400


def emit(payload: dict | None = None) -> None:
    print(json.dumps(payload if payload is not None else {}))


def read_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}


def conversation_id(payload: dict) -> str:
    return payload.get("conversation_id") or payload.get("session_id") or "unknown"


def workspace_root(payload: dict) -> Path:
    roots = payload.get("workspace_roots") or []
    if roots:
        return Path(roots[0])
    # .cursor/hooks/<this file> → repo root
    return Path(__file__).resolve().parents[2]


def app_paths(root: Path) -> tuple[Path, Path]:
    """Return ``(app_dir, pyproject.toml)`` for repo-root or ``app/`` workspaces.

    Prefer ``app/pyproject.toml`` when it exists. Use ``pyproject.toml`` at the
    workspace root only when there is no app-level config (workspace opened at
    ``app/``, or a root-only project layout).
    """
    root = root.resolve()
    app_dir = root / "app"
    config_in_app = app_dir / "pyproject.toml"
    if config_in_app.is_file():
        return app_dir, config_in_app
    config_at_root = root / "pyproject.toml"
    if config_at_root.is_file():
        return root, config_at_root
    return app_dir, config_in_app


def normalize_workspace_path(path: Path, root: Path) -> Path:
    """Resolve ``path`` inside ``root``; hook payloads use workspace-relative paths."""
    root = root.resolve()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def paths_for_ruff(files: list[Path], app_dir: Path) -> list[str]:
    """Paths relative to ``app_dir`` so Ruff resolves ``src = [\"backend/\"]`` correctly."""
    app_resolved = app_dir.resolve()
    args: list[str] = []
    for path in files:
        try:
            args.append(str(path.resolve().relative_to(app_resolved)))
        except (OSError, ValueError):
            continue
    return args


def resolve_ruff(app_dir: Path) -> Path | None:
    venv_ruff = (app_dir / ".venv" / "bin" / "ruff").resolve()
    if venv_ruff.is_file() and os.access(venv_ruff, os.X_OK):
        return venv_ruff
    found = shutil.which("ruff")
    if not found:
        return None
    return Path(found).resolve()


def is_project_python(path: Path, root: Path) -> bool:
    """Accept only real ``.py`` files that resolve inside the workspace root.

    Skips ``tmp_*.py`` scratch scripts (gitignored + ruff-excluded).
    """
    try:
        resolved = normalize_workspace_path(path, root)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    if resolved.suffix != ".py" or not resolved.is_file():
        return False
    if resolved.name.startswith("tmp_"):
        return False
    return not any(part in SKIP_PATH_PARTS for part in resolved.parts)


def state_file_for(conv_id: str) -> Path:
    return STATE_DIR / f"{conv_id}.txt"


def ensure_state_dir() -> bool:
    """Create ``STATE_DIR`` as an owner-only real directory (not a symlink)."""
    try:
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        st = STATE_DIR.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            return False
        if st.st_uid != os.getuid():
            return False
        if stat.S_IMODE(st.st_mode) != 0o700:
            STATE_DIR.chmod(0o700)
        return True
    except OSError:
        return False


def _open_state_file(path: Path, flags: int, mode: int = 0o600) -> int:
    """Open a state file without following symlinks (``O_NOFOLLOW`` when available)."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags | nofollow, mode)


def track_edited_file(conv_id: str, path: Path) -> None:
    if not ensure_state_dir():
        return
    try:
        fd = _open_state_file(state_file_for(conv_id), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, f"{path.resolve()}\n".encode())
        finally:
            os.close(fd)
    except OSError:
        return


def tracked_python_files(conv_id: str, root: Path) -> list[Path]:
    if not ensure_state_dir():
        return []
    path = state_file_for(conv_id)
    try:
        st = path.lstat()
    except OSError:
        return []
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return []
    files: list[Path] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        candidate = normalize_workspace_path(Path(line.strip()), root)
        if not is_project_python(candidate, root):
            continue
        key = str(candidate.resolve())
        if key in seen:
            continue
        seen.add(key)
        files.append(candidate)
    return files


def _dedupe_project_python(paths: list[Path], root: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for candidate in paths:
        if not is_project_python(candidate, root):
            continue
        try:
            key = str(candidate.resolve())
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        files.append(candidate)
    return files


def discover_dirty_python_files(root: Path) -> list[Path]:
    """Independent stop-time discovery via git (covers missed ``afterFileEdit`` events)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "-uall"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    candidates: list[Path] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        entry = line[3:]
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        entry = entry.strip().strip('"')
        if not entry:
            continue
        candidates.append(root / entry)
    return _dedupe_project_python(candidates, root)


def discover_branch_changed_python_files(root: Path) -> list[Path]:
    """Python files changed on this branch tip vs ``origin/staging`` (or upstream).

    Broader than dirty-only so stop still catches lint debt after a mid-session
    commit. Never walks the full tree — only the branch diff. Caps at
    ``BRANCH_DIFF_FILE_CAP`` so huge branches stay bounded.
    """
    merge_base = None
    for base_ref in ("origin/staging", "@{upstream}", "origin/main"):
        try:
            probed = subprocess.run(
                ["git", "-C", str(root), "merge-base", "HEAD", base_ref],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probed.returncode == 0 and probed.stdout.strip():
            merge_base = probed.stdout.strip()
            break
    if not merge_base:
        return []

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--name-only",
                "--diff-filter=ACMR",
                f"{merge_base}...HEAD",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    candidates = [root / line.strip() for line in result.stdout.splitlines() if line.strip()]
    return _dedupe_project_python(candidates, root)[:BRANCH_DIFF_FILE_CAP]


def paths_from_payload(payload: dict, root: Path) -> list[Path]:
    """``subagentStop`` supplies ``modified_files``; include those when present."""
    candidates: list[Path] = []
    for raw in payload.get("modified_files") or []:
        text = str(raw or "").strip()
        if not text:
            continue
        candidate = Path(text)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidates.append(candidate)
    return _dedupe_project_python(candidates, root)


def files_for_stop_lint(conv_id: str, root: Path, payload: dict | None = None) -> list[Path]:
    """Broader stop set: tracked edits + payload + dirty + branch-changed Python."""
    files: list[Path] = []
    seen: set[str] = set()
    for candidate in [
        *tracked_python_files(conv_id, root),
        *paths_from_payload(payload or {}, root),
        *discover_dirty_python_files(root),
        *discover_branch_changed_python_files(root),
    ]:
        try:
            key = str(candidate.resolve())
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        files.append(candidate)
    return files


def clear_tracked_files(conv_id: str) -> None:
    if not ensure_state_dir():
        return
    state_file_for(conv_id).unlink(missing_ok=True)


def write_last_stop_log(record: dict) -> None:
    """Best-effort diagnostics for silent skip / fail-open paths.

    Uses an owner-only state dir and ``O_NOFOLLOW`` so a pre-planted symlink under
    shared ``TMPDIR`` cannot redirect the write.
    """
    try:
        if not ensure_state_dir():
            return
        payload = json.dumps({**record, "ts": time.time()}, indent=2) + "\n"
        fd = _open_state_file(
            STATE_DIR / "last-stop.json",
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


def run_ruff(
    ruff: Path,
    args: list[str],
    *,
    cwd: Path | None = None,
    quiet: bool = False,
) -> subprocess.CompletedProcess[str]:
    cmd = [str(ruff), *args]
    run_kwargs: dict[str, Any] = {}
    if cwd is not None:
        run_kwargs["cwd"] = str(cwd)
    if quiet:
        return subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **run_kwargs)
    return subprocess.run(cmd, check=False, capture_output=True, text=True, **run_kwargs)


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)
