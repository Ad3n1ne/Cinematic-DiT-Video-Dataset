"""
summarize.py — 扫 state/ 生成 stats.csv + 打印进度统计
用法: python3 summarize.py
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "state"
TASKS_DIR = ROOT / "tasks"
STATS_FILE = ROOT / "stats.csv"


def load_task_counts():
    counts = {}
    total = 0
    if not TASKS_DIR.exists():
        return counts, total
    for p in sorted(TASKS_DIR.glob("tasks_*.jsonl")):
        letter = p.stem.rsplit("_", 1)[-1]
        n = sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
        counts[letter] = n
        total += n
    return counts, total


def main():
    if not STATE_DIR.exists():
        print("state/ 目录不存在，没跑过任何任务")
        return

    # 扫所有 task 状态（排除 worker_*.log 和临时文件）
    states = []
    for p in sorted(STATE_DIR.glob("*.json")):
        try:
            s = json.loads(p.read_text())
            states.append(s)
        except json.JSONDecodeError:
            pass

    if not states:
        print("state/ 里没有状态文件")
        return

    # 写 stats.csv
    fields = ["task_id", "account", "status", "video_id", "output_path",
              "started_at", "completed_at", "retries", "error"]
    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in states:
            row = {k: s.get(k, "") for k in fields}
            w.writerow(row)

    # 汇总。总任务数来自 tasks/*.jsonl；state/*.json 只是已经触达的任务。
    task_counts, expected_total = load_task_counts()
    by_status = Counter(s.get("status", "?") for s in states)
    by_account = defaultdict(lambda: Counter())
    for s in states:
        tid = s.get("task_id", "?_?_?")
        parts = tid.split("_")
        acc = parts[0] if parts else "?"
        by_account[acc][s.get("status", "?")] += 1

    touched_total = len(states)
    total = expected_total or touched_total
    done = by_status.get("done", 0)
    print(f"\n=== 总进度: {done}/{total} ({done/total*100:.1f}%) ===\n")
    if expected_total:
        pending_total = max(0, expected_total - touched_total)
        print(f"已触达任务: {touched_total}/{expected_total} | 未触达: {pending_total}\n")

    print(f"{'账号':<6}{'done':<8}{'running':<10}{'failed':<10}{'perm_fail':<12}{'pending':<10}{'完成率':<10}")
    for L in "ABCDEFGHIJ":
        c = by_account.get(L, Counter())
        touched_L = sum(c.values())
        total_L = task_counts.get(L, touched_L)
        if total_L == 0: continue
        done_L = c.get("done", 0)
        rate = done_L / total_L * 100 if total_L else 0
        pending_L = max(0, total_L - touched_L)
        print(f"  {L}   {c.get('done',0):<6}"
              f"{c.get('running',0):<8}{c.get('failed',0):<10}"
              f"{c.get('permanent_failed',0):<12}{pending_L:<10}"
              f"{rate:.1f}%")

    print(f"\n=== 失败任务清单（前 20）===")
    fails = [s for s in states if s.get("status") in ("failed", "permanent_failed")]
    for s in fails[:20]:
        print(f"  {s.get('task_id')}: {s.get('error')}")

    if len(fails) > 20:
        print(f"  ... 还有 {len(fails) - 20} 个失败任务")

    print(f"\n详细数据 → {STATS_FILE}")


if __name__ == "__main__":
    main()
