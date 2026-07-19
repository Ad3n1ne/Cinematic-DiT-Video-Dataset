#!/usr/bin/env python3
"""Validate generated video dataset files, tasks, and worker states."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def detect_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "tasks").is_dir() and (cwd / "state").is_dir() and (cwd / "output").is_dir():
        return cwd
    if (cwd / "worker" / "tasks").is_dir():
        return cwd / "worker"
    return cwd


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}:{line_no}: {exc}") from exc
    return rows


def load_tasks(tasks_dir: Path) -> dict[str, dict]:
    tasks = {}
    duplicates = []
    for path in sorted(tasks_dir.glob("tasks_*.jsonl")):
        for task in read_jsonl(path):
            task_id = task.get("task_id")
            if not task_id:
                raise SystemExit(f"Task without task_id in {path}")
            if task_id in tasks:
                duplicates.append(task_id)
            tasks[task_id] = task
    if duplicates:
        raise SystemExit(f"Duplicate task_id values: {duplicates[:10]}")
    return tasks


def load_states(state_dir: Path) -> dict[str, dict]:
    states = {}
    bad = []
    for path in sorted(state_dir.glob("*.json")):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            bad.append(path.name)
            continue
        task_id = state.get("task_id") or path.stem
        states[task_id] = state
    if bad:
        print(f"Warning: skipped invalid state JSON files: {bad[:10]}")
    return states


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=detect_root())
    parser.add_argument("--min-size", type=int, default=1024, help="Minimum acceptable mp4 size in bytes")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve()
    tasks_dir = root / "tasks"
    state_dir = root / "state"
    output_dir = root / "output"
    release_dir = root / "release"
    release_dir.mkdir(exist_ok=True)
    report_path = args.out or release_dir / "validation_report.json"

    tasks = load_tasks(tasks_dir)
    states = load_states(state_dir)
    mp4s = {p.stem: p for p in output_dir.glob("*.mp4")}

    task_ids = set(tasks)
    state_ids = set(states)
    mp4_ids = set(mp4s)

    missing_state = sorted(task_ids - state_ids)
    missing_video = sorted(task_ids - mp4_ids)
    extra_state = sorted(state_ids - task_ids)
    extra_video = sorted(mp4_ids - task_ids)
    not_done = sorted(
        task_id for task_id in task_ids
        if states.get(task_id, {}).get("status") != "done"
    )
    small_or_empty = sorted(
        {
            task_id: path.stat().st_size
            for task_id, path in mp4s.items()
            if task_id in task_ids and path.stat().st_size < args.min_size
        }.items()
    )

    by_account = defaultdict(Counter)
    by_resolution = Counter()
    for task in tasks.values():
        by_account[task["account"]][task["resolution"]] += 1
        by_resolution[task["resolution"]] += 1

    video_size_bytes = sum(p.stat().st_size for p in mp4s.values() if p.stem in task_ids)
    report = {
        "root": str(root),
        "counts": {
            "tasks": len(tasks),
            "states": len(states),
            "mp4": len(mp4s),
            "task_mp4": len(task_ids & mp4_ids),
            "video_size_bytes": video_size_bytes,
        },
        "by_account": {account: dict(counter) for account, counter in sorted(by_account.items())},
        "by_resolution": dict(by_resolution),
        "problems": {
            "missing_state": missing_state,
            "missing_video": missing_video,
            "extra_state": extra_state,
            "extra_video": extra_video,
            "not_done": not_done,
            "small_or_empty": small_or_empty,
        },
        "ok": not any([missing_state, missing_video, not_done, small_or_empty]),
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"root: {root}")
    print(f"tasks={len(tasks)} states={len(states)} mp4={len(mp4s)} task_mp4={len(task_ids & mp4_ids)}")
    print(f"video_size={video_size_bytes / 1024**3:.2f} GiB")
    print(f"missing_state={len(missing_state)} missing_video={len(missing_video)} not_done={len(not_done)}")
    print(f"extra_state={len(extra_state)} extra_video={len(extra_video)} small_or_empty={len(small_or_empty)}")
    print(f"report: {report_path}")
    print("OK" if report["ok"] else "FAILED")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
