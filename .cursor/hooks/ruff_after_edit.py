#!/usr/bin/env python3
"""afterFileEdit: track the edited Python path only (no Ruff — runs too often)."""

from __future__ import annotations

from pathlib import Path

from ruff_common import (
    conversation_id,
    emit,
    is_project_python,
    normalize_workspace_path,
    read_payload,
    track_edited_file,
    workspace_root,
)


def main() -> None:
    payload = read_payload()
    root = workspace_root(payload)
    file_path = normalize_workspace_path(Path(payload.get("file_path") or ""), root)
    if not is_project_python(file_path, root):
        emit()
        return

    # Track only — format + autofix happen on stop/subagentStop where we can
    # afford a broader file set once per turn.
    track_edited_file(conversation_id(payload), file_path)
    emit()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit()
