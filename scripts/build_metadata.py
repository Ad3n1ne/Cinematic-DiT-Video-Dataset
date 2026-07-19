#!/usr/bin/env python3
"""Build dataset metadata, prompt table, and checksums from worker outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


SOURCE_MODEL = "agnes-video-v2.0"
GENERATION_API = "Agnes Video V2.0"
OBSERVED_VIDEO_SPECS = {
    "1080p": {"width": 1920, "height": 1088},
    "720p": {"width": 1088, "height": 832},
    "480p": {"width": 704, "height": 512},
}


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
    for path in sorted(tasks_dir.glob("tasks_*.jsonl")):
        for task in read_jsonl(path):
            tasks[task["task_id"]] = task
    return tasks


def load_states(state_dir: Path) -> dict[str, dict]:
    states = {}
    for path in sorted(state_dir.glob("*.json")):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        task_id = state.get("task_id") or path.stem
        states[task_id] = state
    return states


def load_jsonl_task_ids(path: Path, key: str = "task_id") -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for rec in read_jsonl(path):
        if rec.get(key):
            ids.add(rec[key])
    return ids


def discover_repair_stages(root: Path) -> dict[str, str]:
    stages: dict[str, str] = {}
    rerun99 = sorted((root / "state").glob("rerun_99_state_backup_*.jsonl"))
    if rerun99:
        for task_id in load_jsonl_task_ids(rerun99[-1]):
            stages[task_id] = "rerun_99"

    policy_manifest = root / "tasks" / "rerun_policy16" / "rerun_policy16_manifest.jsonl"
    for task_id in load_jsonl_task_ids(policy_manifest):
        stages[task_id] = "policy16_prompt_rewrite"
    return stages


def load_canonical_prompt_overrides(root: Path) -> dict[int, str]:
    path = root / "tasks" / "rerun_policy16" / "rerun_policy16_manifest.jsonl"
    if not path.exists():
        return {}
    overrides: dict[int, str] = {}
    for record in read_jsonl(path):
        task = record.get("task") or {}
        gid = task.get("global_id")
        prompt = record.get("new_prompt") or task.get("raw_prompt")
        if gid is None or not prompt:
            continue
        gid = int(gid)
        if gid in overrides and overrides[gid] != prompt:
            raise SystemExit(f"Conflicting canonical prompt rewrites for global_id={gid}")
        overrides[gid] = prompt
    return overrides


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_frame_rate(value: object) -> float | str:
    if value in (None, ""):
        return ""
    raw = str(value)
    if "/" in raw:
        numerator, denominator = raw.split("/", 1)
        try:
            return round(float(numerator) / float(denominator), 6)
        except (ValueError, ZeroDivisionError):
            return raw
    try:
        return round(float(raw), 6)
    except ValueError:
        return raw


def parse_int(value: object) -> int | str:
    if value in (None, ""):
        return ""
    try:
        return int(value)
    except (TypeError, ValueError):
        return ""


def parse_float(value: object) -> float | str:
    if value in (None, ""):
        return ""
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return ""


def normalize_probe_record(record: dict) -> dict:
    return {
        "actual_width": parse_int(record.get("actual_width", record.get("width"))),
        "actual_height": parse_int(record.get("actual_height", record.get("height"))),
        "actual_frame_rate": parse_frame_rate(
            record.get("actual_frame_rate", record.get("frame_rate"))
        ),
        "actual_duration_seconds": parse_float(
            record.get("actual_duration_seconds", record.get("duration_seconds"))
        ),
        "actual_num_frames": parse_int(
            record.get("actual_num_frames", record.get("num_frames"))
        ),
    }


def load_probe_cache(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    if not path.exists():
        raise SystemExit(f"Probe cache not found: {path}")
    with path.open(encoding="utf-8", newline="") as f:
        return {
            row["task_id"]: normalize_probe_record(row)
            for row in csv.DictReader(f)
            if row.get("task_id")
        }


def load_metadata_cache(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    if not path.exists():
        raise SystemExit(f"Metadata cache not found: {path}")
    return {
        row["task_id"]: row
        for row in read_jsonl(path)
        if row.get("task_id")
    }


def observed_profile(task: dict) -> dict:
    spec = OBSERVED_VIDEO_SPECS.get(task.get("resolution"), {})
    frame_rate = parse_frame_rate(task.get("frame_rate"))
    num_frames = parse_int(task.get("num_frames"))
    duration = ""
    if isinstance(frame_rate, float) and isinstance(num_frames, int) and frame_rate:
        duration = round(num_frames / frame_rate, 6)
    return {
        "actual_width": spec.get("width", ""),
        "actual_height": spec.get("height", ""),
        "actual_frame_rate": frame_rate,
        "actual_duration_seconds": duration,
        "actual_num_frames": num_frames,
    }


def ffprobe(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        return {}
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,duration,nb_frames",
        "-of", "json",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        data = json.loads(proc.stdout)
    except Exception:
        return {}
    streams = data.get("streams") or []
    if not streams:
        return {}
    stream = streams[0]
    return normalize_probe_record({
        "actual_width": stream.get("width", ""),
        "actual_height": stream.get("height", ""),
        "actual_frame_rate": stream.get("avg_frame_rate", ""),
        "actual_duration_seconds": stream.get("duration", ""),
        "actual_num_frames": stream.get("nb_frames", ""),
    })


def import_prompt_enhancer(root: Path):
    sys.path.insert(0, str(root))
    from prompt_enhancer import enhance_prompt  # type: ignore
    return enhance_prompt


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def maybe_write_parquet(csv_path: Path, parquet_path: Path) -> bool:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return False
    try:
        df = pd.read_csv(csv_path)
        df.to_parquet(parquet_path, index=False)
    except Exception:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=detect_root())
    parser.add_argument("--release-dir", type=Path, default=None)
    parser.add_argument("--no-sha256", action="store_true")
    parser.add_argument("--ffprobe", action="store_true", help="Use ffprobe if available")
    parser.add_argument(
        "--probe-cache",
        type=Path,
        default=None,
        help="CSV generated by probe_videos.sh; takes precedence over --ffprobe",
    )
    parser.add_argument(
        "--reuse-checksums-from",
        type=Path,
        default=None,
        help="Reuse SHA-256 when cached file_size matches the current MP4",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    release_dir = args.release_dir or root / "release"
    release_dir.mkdir(exist_ok=True)

    tasks = load_tasks(root / "tasks")
    states = load_states(root / "state")
    stages = discover_repair_stages(root)
    canonical_prompt_overrides = load_canonical_prompt_overrides(root)
    enhance_prompt = import_prompt_enhancer(root)
    probe_cache = load_probe_cache(args.probe_cache)
    metadata_cache = load_metadata_cache(args.reuse_checksums_from)

    rows: list[dict] = []
    prompt_groups: dict[int, dict] = {}
    checksums = []
    reused_checksums = 0

    task_ids = sorted(tasks)
    for index, task_id in enumerate(task_ids, 1):
        task = tasks[task_id]
        state = states.get(task_id, {})
        path = root / "output" / f"{task_id}.mp4"
        if not path.exists():
            raise SystemExit(f"Missing mp4 for {task_id}: {path}")
        if state.get("status") != "done":
            raise SystemExit(f"State is not done for {task_id}: {state.get('status')}")

        enhanced_prompt, negative_prompt = enhance_prompt(task["raw_prompt"])
        file_size = path.stat().st_size
        cached = metadata_cache.get(task_id, {})
        cached_digest = cached.get("sha256", "")
        cached_size = parse_int(cached.get("file_size"))
        can_reuse_digest = (
            isinstance(cached_size, int)
            and cached_size == file_size
            and isinstance(cached_digest, str)
            and len(cached_digest) == 64
        )
        if args.no_sha256:
            digest = ""
        elif can_reuse_digest:
            digest = cached_digest
            reused_checksums += 1
        else:
            digest = sha256_file(path)
        if digest:
            checksums.append(f"{digest}  output/{task_id}.mp4")

        probe = probe_cache.get(task_id)
        media_metadata_source = "ffprobe_cache"
        if probe is None and args.ffprobe:
            probe = ffprobe(path)
            media_metadata_source = "ffprobe"
        if not probe:
            probe = observed_profile(task)
            media_metadata_source = "observed_resolution_profile"
        duration = task["num_frames"] / task["frame_rate"]
        stage = stages.get(task_id)
        if not stage:
            stage = "state_repair" if state.get("repaired_at") else "initial"

        row = {
            "task_id": task_id,
            "account": task.get("account", task_id.split("_", 1)[0]),
            "global_id": task.get("global_id", ""),
            "prompt_id": task.get("global_id", ""),
            "shot_id": task.get("prompt_id", ""),
            "category": task.get("category", ""),
            "resolution": task.get("resolution", ""),
            "prompt_zh": task.get("raw_prompt", ""),
            "enhanced_prompt": enhanced_prompt,
            "negative_prompt": negative_prompt,
            "requested_width": task.get("width", ""),
            "requested_height": task.get("height", ""),
            "actual_width": probe.get("actual_width", ""),
            "actual_height": probe.get("actual_height", ""),
            "num_frames": task.get("num_frames", ""),
            "frame_rate": task.get("frame_rate", ""),
            "duration_seconds": round(duration, 6),
            "actual_frame_rate": probe.get("actual_frame_rate", ""),
            "actual_duration_seconds": probe.get("actual_duration_seconds", ""),
            "actual_num_frames": probe.get("actual_num_frames", ""),
            "media_metadata_source": media_metadata_source,
            "source_model": SOURCE_MODEL,
            "generation_api": GENERATION_API,
            "video_id": state.get("video_id", ""),
            "status": state.get("status", ""),
            "started_at": state.get("started_at", ""),
            "completed_at": state.get("completed_at", ""),
            "retries": state.get("retries", 0),
            "repair_stage": stage,
            "file_name": f"output/{task_id}.mp4",
            "shard": "",
            "file_size": file_size,
            "sha256": digest,
        }
        rows.append(row)

        gid = task.get("global_id")
        if gid is not None:
            group = prompt_groups.setdefault(int(gid), {
                "global_id": gid,
                "prompt_id": gid,
                "shot_id": task.get("prompt_id", ""),
                "category": task.get("category", ""),
                "task_ids": [],
                "prompt_variants": set(),
            })
            group["task_ids"].append(task_id)
            group["prompt_variants"].add(task.get("raw_prompt", ""))

        if index % 250 == 0:
            print(f"processed {index}/{len(task_ids)}", flush=True)

    fields = [
        "task_id", "account", "global_id", "prompt_id", "shot_id", "category", "resolution",
        "prompt_zh", "enhanced_prompt", "negative_prompt",
        "requested_width", "requested_height", "actual_width", "actual_height",
        "num_frames", "frame_rate", "duration_seconds",
        "actual_frame_rate", "actual_duration_seconds", "actual_num_frames",
        "media_metadata_source",
        "source_model", "generation_api", "video_id", "status",
        "started_at", "completed_at", "retries", "repair_stage",
        "file_name", "shard", "file_size", "sha256",
    ]
    metadata_csv = release_dir / "metadata.csv"
    write_csv(metadata_csv, rows, fields)

    metadata_jsonl = release_dir / "metadata.jsonl"
    with metadata_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    prompt_rows = []
    for gid, group in sorted(prompt_groups.items()):
        variants = sorted(group["prompt_variants"])
        prompt_rows.append({
            "global_id": gid,
            "prompt_id": group["prompt_id"],
            "shot_id": group["shot_id"],
            "category": group["category"],
            "prompt_zh": canonical_prompt_overrides.get(
                gid, variants[0] if variants else ""
            ),
            "was_policy_rewritten": gid in canonical_prompt_overrides,
            "prompt_variant_count": len(variants),
            "prompt_variants_json": json.dumps(variants, ensure_ascii=False),
            "task_ids_json": json.dumps(sorted(group["task_ids"]), ensure_ascii=False),
        })
    prompts_csv = release_dir / "prompts.csv"
    write_csv(prompts_csv, prompt_rows, [
        "global_id", "prompt_id", "shot_id", "category", "prompt_zh",
        "was_policy_rewritten",
        "prompt_variant_count", "prompt_variants_json", "task_ids_json",
    ])

    checksums_path = release_dir / "checksums.sha256"
    if checksums:
        checksums_path.write_text("\n".join(checksums) + "\n", encoding="utf-8")

    parquet_ok = maybe_write_parquet(metadata_csv, release_dir / "metadata.parquet")
    print(f"rows={len(rows)} prompts={len(prompt_rows)}")
    print(f"reused_checksums={reused_checksums}")
    print(f"metadata_csv={metadata_csv}")
    print(f"metadata_jsonl={metadata_jsonl}")
    print(f"prompts_csv={prompts_csv}")
    if checksums:
        print(f"checksums={checksums_path}")
    print(f"metadata_parquet={'written' if parquet_ok else 'skipped'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
