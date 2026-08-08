#!/usr/bin/env python3
"""stop / subagentStop: format + autofix a broader Python set, then follow up.

Broader than afterFileEdit (track-only): tracked edits, payload modified_files,
git dirty/untracked, and branch-changed files vs origin/staging.
"""

from __future__ import annotations

from ruff_common import (
    app_paths,
    clear_tracked_files,
    conversation_id,
    emit,
    files_for_stop_lint,
    paths_for_ruff,
    read_payload,
    resolve_ruff,
    run_ruff,
    strip_ansi,
    workspace_root,
    write_last_stop_log,
)

MAX_FOLLOWUPS = 2
MAX_LINT_LINES = 80
MAX_FILES_IN_MESSAGE = 20
MAX_FILES_IN_LOG = 40


def main() -> None:
    payload = read_payload()
    event = payload.get("hook_event_name") or "stop"
    status = payload.get("status")
    if status != "completed":
        write_last_stop_log(
            {
                "event": event,
                "outcome": "skipped_status",
                "status": status,
                "conversation_id": conversation_id(payload),
            }
        )
        emit()
        return

    loop_count = int(payload.get("loop_count") or 0)
    if loop_count >= MAX_FOLLOWUPS:
        write_last_stop_log(
            {
                "event": event,
                "outcome": "skipped_loop_limit",
                "loop_count": loop_count,
                "conversation_id": conversation_id(payload),
            }
        )
        emit()
        return

    root = workspace_root(payload)
    conv_id = conversation_id(payload)
    files = files_for_stop_lint(conv_id, root, payload)
    if not files:
        write_last_stop_log(
            {
                "event": event,
                "outcome": "skipped_no_files",
                "conversation_id": conv_id,
            }
        )
        emit()
        return

    app_dir, config = app_paths(root)
    app_dir = app_dir.resolve()
    config = config.resolve()
    if not config.is_file() or not app_dir.is_dir():
        write_last_stop_log(
            {
                "event": event,
                "outcome": "skipped_no_config",
                "config": str(config),
                "app_dir": str(app_dir),
                "conversation_id": conv_id,
            }
        )
        emit()
        return

    ruff = resolve_ruff(app_dir)
    if ruff is None:
        write_last_stop_log(
            {
                "event": event,
                "outcome": "skipped_no_ruff",
                "app_dir": str(app_dir),
                "conversation_id": conv_id,
            }
        )
        emit()
        return

    file_args = paths_for_ruff(files, app_dir)
    if not file_args:
        write_last_stop_log(
            {
                "event": event,
                "outcome": "skipped_no_ruff_paths",
                "conversation_id": conv_id,
                "file_count": len(files),
            }
        )
        emit()
        return

    log_files = file_args[:MAX_FILES_IN_LOG]

    # Run from app_dir so ``src = ["backend/"]`` in pyproject.toml resolves to app/backend/.
    # Passing ``app/backend/...`` paths from repo root makes Ruff treat src as repo/backend/.
    fmt = run_ruff(ruff, ["format", "--quiet", *file_args], cwd=app_dir, quiet=True)
    fix = run_ruff(
        ruff,
        ["check", "--fix", "--unsafe-fixes", "--quiet", *file_args],
        cwd=app_dir,
        quiet=True,
    )
    check = run_ruff(ruff, ["check", "--output-format", "concise", *file_args], cwd=app_dir)

    # Exit 2 = invalid config / CLI / internal failure. Fail open; keep tracking.
    if 2 in (fix.returncode, fmt.returncode, check.returncode):
        write_last_stop_log(
            {
                "event": event,
                "outcome": "ruff_exit_2",
                "conversation_id": conv_id,
                "file_count": len(file_args),
                "files": log_files,
                "fix_code": fix.returncode,
                "fmt_code": fmt.returncode,
                "check_code": check.returncode,
                "ruff": str(ruff),
            }
        )
        emit()
        return

    if check.returncode == 0:
        clear_tracked_files(conv_id)
        write_last_stop_log(
            {
                "event": event,
                "outcome": "clean",
                "conversation_id": conv_id,
                "file_count": len(file_args),
                "files": log_files,
                "fix_code": fix.returncode,
                "fmt_code": fmt.returncode,
                "ruff": str(ruff),
            }
        )
        emit()
        return

    # Only treat exit 1 as remaining lint findings worth a follow-up.
    if check.returncode != 1:
        write_last_stop_log(
            {
                "event": event,
                "outcome": "unexpected_check_code",
                "conversation_id": conv_id,
                "check_code": check.returncode,
                "file_count": len(file_args),
                "files": log_files,
            }
        )
        emit()
        return

    lint_text = strip_ansi(check.stdout or check.stderr or "")
    lint_text = "\n".join(lint_text.splitlines()[:MAX_LINT_LINES])
    file_list = "\n".join(file_args[:MAX_FILES_IN_MESSAGE])
    write_last_stop_log(
        {
            "event": event,
            "outcome": "followup",
            "conversation_id": conv_id,
            "file_count": len(file_args),
            "files": log_files,
            "loop_count": loop_count,
            "lint_preview": lint_text[:2000],
        }
    )
    emit(
        {
            "followup_message": (
                "Ruff still reports issues on Python files in the stop lint set "
                "(tracked edits + dirty + branch-changed + subagent modified_files). "
                "Fix them now (do not ask me to lint). Autofix already ran; remaining "
                f"findings need manual edits.\n\nFiles:\n{file_list}\n\n"
                f"Ruff output:\n{lint_text}"
            )
        }
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_last_stop_log({"outcome": "exception", "error": repr(exc)})
        emit()
