#!/usr/bin/env python3
"""Create tar shards for the video dataset without copying videos first."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tarfile
from pathlib import Path


def detect_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "release" / "metadata.jsonl").exists() and (cwd / "output").is_dir():
        return cwd
    if (cwd / "worker" / "release" / "metadata.jsonl").exists():
        return cwd / "worker"
    return cwd


def parse_size(value: str) -> int:
    raw = value.strip().lower()
    units = {
        "k": 1024,
        "kb": 1024,
        "m": 1024**2,
        "mb": 1024**2,
        "g": 1024**3,
        "gb": 1024**3,
        "t": 1024**4,
        "tb": 1024**4,
    }
    for suffix, factor in sorted(units.items(), key=lambda item: -len(item[0])):
        if raw.endswith(suffix):
            return int(float(raw[: -len(suffix)]) * factor)
    return int(raw)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_metadata(path: Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}:{line_no}: {exc}") from exc
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def plan_shards(rows: list[dict], output_dir: Path, max_bytes: int) -> list[list[dict]]:
    shards: list[list[dict]] = []
    current: list[dict] = []
    current_size = 0

    for row in sorted(rows, key=lambda item: item["task_id"]):
        video_path = output_dir / f"{row['task_id']}.mp4"
        if not video_path.exists():
            raise SystemExit(f"Missing video file: {video_path}")
        size = video_path.stat().st_size
        if current and current_size + size > max_bytes:
            shards.append(current)
            current = []
            current_size = 0
        current.append(row)
        current_size += size

    if current:
        shards.append(current)
    return shards


def copy_light_release_files(source_release: Path, dest: Path) -> None:
    for name in (
        "validation_report.json",
        "prompts.csv",
        "build_metadata.log",
    ):
        src = source_release / name
        if src.exists():
            shutil.copy2(src, dest / name)

def refresh_metadata(source_release: Path, dest: Path) -> None:
    existing_path = dest / "metadata.jsonl"
    if not existing_path.exists():
        raise SystemExit(f"Existing staged metadata not found: {existing_path}")

    source_rows = read_metadata(source_release / "metadata.jsonl")
    existing_rows = read_metadata(existing_path)
    locations = {
        row["task_id"]: {
            "file_name": row.get("file_name", ""),
            "shard": row.get("shard", ""),
        }
        for row in existing_rows
    }
    source_ids = {row["task_id"] for row in source_rows}
    if source_ids != set(locations):
        missing = sorted(source_ids - set(locations))[:10]
        extra = sorted(set(locations) - source_ids)[:10]
        raise SystemExit(f"Staged/source task mismatch: missing={missing} extra={extra}")

    out_rows = []
    checksums = []
    for row in sorted(source_rows, key=lambda item: item["task_id"]):
        out_row = dict(row)
        out_row.update(locations[row["task_id"]])
        if not out_row["file_name"] or not out_row["shard"]:
            raise SystemExit(f"Missing staged location for {row['task_id']}")
        out_rows.append(out_row)
        checksums.append(f"{out_row['sha256']}  {out_row['file_name']}")

    fields = list(out_rows[0].keys())
    with existing_path.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_csv(dest / "metadata.csv", out_rows, fields)
    (dest / "checksums.sha256").write_text(
        "\n".join(checksums) + "\n",
        encoding="utf-8",
    )
    copy_light_release_files(source_release, dest)
    print(f"refreshed metadata rows={len(out_rows)} without rebuilding shards")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=detect_root())
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--max-shard-size", default="2g")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--refresh-metadata-only",
        action="store_true",
        help="Refresh metadata/checksums in an existing staging directory",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    source_release = root / "release"
    output_dir = root / "output"
    dest = args.dest.resolve()
    shards_dir = dest / "shards"
    max_bytes = parse_size(args.max_shard_size)

    if args.refresh_metadata_only:
        refresh_metadata(source_release, dest)
        return 0

    if dest.exists() and any(dest.iterdir()) and not args.force:
        raise SystemExit(f"Destination is not empty: {dest} (use --force)")
    dest.mkdir(parents=True, exist_ok=True)
    shards_dir.mkdir(parents=True, exist_ok=True)

    rows = read_metadata(source_release / "metadata.jsonl")
    shards = plan_shards(rows, output_dir, max_bytes)
    row_by_task_id = {row["task_id"]: dict(row) for row in rows}
    shard_index = []
    release_checksums = []

    print(f"root={root}")
    print(f"dest={dest}")
    print(f"rows={len(rows)} max_shard_size={max_bytes} planned_shards={len(shards)}")

    for shard_no, shard_rows in enumerate(shards):
        shard_name = f"train-{shard_no:05d}.tar"
        shard_path = shards_dir / shard_name
        tmp_path = shard_path.with_suffix(".tar.tmp")
        if tmp_path.exists():
            tmp_path.unlink()
        if shard_path.exists():
            shard_path.unlink()

        with tarfile.open(tmp_path, "w") as tar:
            for row in shard_rows:
                task_id = row["task_id"]
                video_path = output_dir / f"{task_id}.mp4"
                arcname = f"videos/{task_id}.mp4"
                tar.add(video_path, arcname=arcname)
                out_row = row_by_task_id[task_id]
                out_row["file_name"] = arcname
                out_row["shard"] = f"shards/{shard_name}"
                release_checksums.append(f"{out_row['sha256']}  {arcname}")

        tmp_path.rename(shard_path)
        shard_size = shard_path.stat().st_size
        shard_sha256 = sha256_file(shard_path)
        shard_index.append({
            "shard": f"shards/{shard_name}",
            "num_videos": len(shard_rows),
            "size_bytes": shard_size,
            "sha256": shard_sha256,
            "first_task_id": shard_rows[0]["task_id"],
            "last_task_id": shard_rows[-1]["task_id"],
        })
        print(
            f"wrote {shard_name} videos={len(shard_rows)} "
            f"size={shard_size / 1024**3:.2f}GiB"
        )

    out_rows = [row_by_task_id[row["task_id"]] for row in sorted(rows, key=lambda item: item["task_id"])]
    fields = list(out_rows[0].keys())
    metadata_jsonl = dest / "metadata.jsonl"
    with metadata_jsonl.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_csv(dest / "metadata.csv", out_rows, fields)
    (dest / "checksums.sha256").write_text("\n".join(release_checksums) + "\n", encoding="utf-8")
    (dest / "shard_index.json").write_text(
        json.dumps(shard_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    copy_light_release_files(source_release, dest)

    total_size = sum(item["size_bytes"] for item in shard_index)
    print(f"done shards={len(shard_index)} total_shard_size={total_size / 1024**3:.2f}GiB")
    print(f"metadata={metadata_jsonl}")
    print(f"shard_index={dest / 'shard_index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
