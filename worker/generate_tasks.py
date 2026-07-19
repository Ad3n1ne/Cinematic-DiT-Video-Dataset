"""
任务生成器 V2（修复 task_id 唯一性）
- 给每条 prompt 一个全局 ID（0-2999），保证 task_id 唯一
- 按全局 ID 取模分配账号（均匀）
- 三档交替排列（避免某账号前期全跑短任务、后期全跑长任务）
"""

import csv
import json
from pathlib import Path
from collections import Counter

# 三档分辨率配置（顶到该档帧数上限）
RESOLUTIONS = [
    {"resolution": "1080p", "width": 1920, "height": 1080, "num_frames": 169},
    {"resolution": "720p",  "width": 1152, "height": 768,  "num_frames": 409},
    {"resolution": "480p",  "width": 640,  "height": 480,  "num_frames": 961},
]
FRAME_RATE = 24

CSV_PATH = Path(__file__).parent.parent / "dit_prompts.csv"
TASKS_DIR = Path(__file__).parent / "tasks"
ACCOUNTS = list("ABCDEFGHIJ")


def main():
    assert CSV_PATH.exists(), f"找不到 {CSV_PATH}"

    # 读 CSV（处理 BOM + 表头）
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    data = [r for r in rows if r[0] not in ("category", "﻿category") and len(r) >= 3]
    print(f"读取 {len(data)} 条原始 prompt")

    # 重组：给每条 prompt 全局 ID（按 CSV 行号）
    prompts = []
    for idx, r in enumerate(data):
        try:
            pid = int(r[1])
        except ValueError:
            continue
        prompts.append({
            "global_id": idx,        # 0-2999，唯一
            "prompt_id": pid,        # CSV 内的 prompt_id（1-10，每 category 重复）
            "category": r[0],
            "raw_prompt": r[2],
        })
    prompts.sort(key=lambda x: x["global_id"])
    print(f"有效 prompt: {len(prompts)}，全局 ID 范围 0-{prompts[-1]['global_id']}")

    # 展开 9000 任务
    TASKS_DIR.mkdir(exist_ok=True)
    by_account = {L: [] for L in ACCOUNTS}

    for p in prompts:
        account = ACCOUNTS[p["global_id"] % 10]  # 均匀分配
        for res in RESOLUTIONS:
            task = {
                # task_id 用 global_id 保证唯一
                "task_id":     f"{account}_g{p['global_id']:04d}_{res['resolution']}",
                "account":     account,
                "global_id":   p["global_id"],
                "prompt_id":   p["prompt_id"],
                "category":    p["category"],
                "raw_prompt":  p["raw_prompt"],
                "resolution":  res["resolution"],
                "width":       res["width"],
                "height":      res["height"],
                "num_frames":  res["num_frames"],
                "frame_rate":  FRAME_RATE,
            }
            by_account[account].append(task)

    # 写 10 个 jsonl
    for L in ACCOUNTS:
        path = TASKS_DIR / f"tasks_{L}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for t in by_account[L]:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")

    # 验证：task_id 唯一性
    all_ids = [t["task_id"] for tasks in by_account.values() for t in tasks]
    dup = [k for k, v in Counter(all_ids).items() if v > 1]
    assert not dup, f"task_id 重复: {dup[:5]}"
    print(f"\n✓ task_id 全部唯一 ({len(all_ids)} 个)")

    # 统计
    print(f"\n=== 生成 {len(all_ids)} 个任务 ===")
    print(f"{'账号':<6}{'1080p':<8}{'720p':<8}{'480p':<8}{'总任务':<10}{'总帧数':<12}")
    for L in ACCOUNTS:
        cnt = Counter(t["resolution"] for t in by_account[L])
        total_frames = sum(t["num_frames"] for t in by_account[L])
        print(f"  {L}   {cnt['1080p']:<6}{cnt['720p']:<8}{cnt['480p']:<8}"
              f"{sum(cnt.values()):<10}{total_frames}")

    # 抽样
    print(f"\n=== 账号 A 前 6 个任务（验证三档交替 + ID 唯一）===")
    for t in by_account["A"][:6]:
        print(f"  {t['task_id']}  [{t['category']}]  frames={t['num_frames']}")


if __name__ == "__main__":
    main()
