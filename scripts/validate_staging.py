#!/usr/bin/env python3
"""Validate a staged tar-sharded dataset release without hashing video payloads."""

from __future__ import annotations

import argparse
import csv
import json
import tarfile
from collections import Counter, defaultdict
from pathlib import Path


EXPECTED_PROFILES = {
    "1080p": (1920, 1088, 169, 24.0, 7.041667),
    "720p": (1088, 832, 409, 24.0, 17.041667),
    "480p": (704, 512, 961, 24.0, 40.041667),
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON in {path}:{line_no}: {exc}") from exc
    return rows


def count_csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    staging = args.staging.resolve()
    metadata = read_jsonl(staging / "metadata.jsonl")
    shard_index = json.loads((staging / "shard_index.json").read_text(encoding="utf-8"))
    task_ids = [row["task_id"] for row in metadata]
    errors = []

    if len(metadata) != 9000:
        errors.append(f"metadata rows: expected 9000, got {len(metadata)}")
    if len(set(task_ids)) != len(task_ids):
        errors.append("metadata contains duplicate task_id values")
    if count_csv_rows(staging / "metadata.csv") != len(metadata):
        errors.append("metadata.csv row count does not match metadata.jsonl")
    if count_csv_rows(staging / "prompts.csv") != 3000:
        errors.append("prompts.csv row count is not 3000")

    prompt_counts = Counter(row.get("prompt_id") for row in metadata)
    if len(prompt_counts) != 3000 or set(prompt_counts.values()) != {3}:
        errors.append("prompt_id values do not form 3000 groups of 3 videos")
    shot_counts = Counter(row.get("shot_id") for row in metadata)
    if set(shot_counts) != set(range(1, 11)) or set(shot_counts.values()) != {900}:
        errors.append("shot_id values do not form 10 groups of 900 videos")

    profile_counts = Counter()
    for row in metadata:
        profile = row.get("resolution")
        profile_counts[profile] += 1
        expected = EXPECTED_PROFILES.get(profile)
        actual = (
            row.get("actual_width"),
            row.get("actual_height"),
            row.get("actual_num_frames"),
            float(row.get("actual_frame_rate")),
            float(row.get("actual_duration_seconds")),
        )
        if expected is None or actual != expected:
            errors.append(f"unexpected media profile for {row['task_id']}: {actual}")
            if len(errors) >= 20:
                break
        if row.get("media_metadata_source") != "ffprobe_cache":
            errors.append(f"non-ffprobe media metadata for {row['task_id']}")
            if len(errors) >= 20:
                break
    if set(profile_counts.values()) != {3000} or set(profile_counts) != set(EXPECTED_PROFILES):
        errors.append(f"unexpected profile counts: {dict(profile_counts)}")

    expected_by_shard: dict[str, set[str]] = defaultdict(set)
    for row in metadata:
        expected_by_shard[row["shard"]].add(row["file_name"])

    indexed_shards = {item["shard"]: item for item in shard_index}
    if set(indexed_shards) != set(expected_by_shard):
        errors.append("metadata shard paths do not match shard_index.json")

    tar_video_count = 0
    for shard_name, item in indexed_shards.items():
        shard_path = staging / shard_name
        if not shard_path.exists():
            errors.append(f"missing shard: {shard_name}")
            continue
        if shard_path.stat().st_size != item["size_bytes"]:
            errors.append(f"shard size mismatch: {shard_name}")
        with tarfile.open(shard_path, "r") as archive:
            members = {member.name for member in archive.getmembers() if member.isfile()}
        tar_video_count += len(members)
        if members != expected_by_shard[shard_name]:
            missing = sorted(expected_by_shard[shard_name] - members)[:3]
            extra = sorted(members - expected_by_shard[shard_name])[:3]
            errors.append(f"tar member mismatch {shard_name}: missing={missing} extra={extra}")

    checksum_rows = {}
    with (staging / "checksums.sha256").open(encoding="utf-8") as f:
        for line in f:
            digest, file_name = line.rstrip("\n").split("  ", 1)
            checksum_rows[file_name] = digest
    metadata_checksums = {row["file_name"]: row["sha256"] for row in metadata}
    if checksum_rows != metadata_checksums:
        errors.append("checksums.sha256 does not match metadata checksums")

    report = {
        "ok": not errors,
        "errors": errors,
        "num_videos": len(metadata),
        "num_prompts": len(prompt_counts),
        "num_shards": len(indexed_shards),
        "tar_video_count": tar_video_count,
        "profile_counts": dict(sorted(profile_counts.items())),
        "metadata_csv_rows": count_csv_rows(staging / "metadata.csv"),
        "prompts_csv_rows": count_csv_rows(staging / "prompts.csv"),
        "checksums_rows": len(checksum_rows),
        "parquet_exists": (staging / "metadata.parquet").exists(),
        "parquet_size_bytes": (
            (staging / "metadata.parquet").stat().st_size
            if (staging / "metadata.parquet").exists()
            else 0
        ),
        "full_media_probe_rows": sum(
            1 for row in metadata if row.get("media_metadata_source") == "ffprobe_cache"
        ),
    }
    output = args.output or staging / "staging_validation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
