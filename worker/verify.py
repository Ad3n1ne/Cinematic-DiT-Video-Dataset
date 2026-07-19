"""
verify.py - 视频完整性验证
扫描 output/ 下所有 mp4，检查：
1. 文件大小符合该档位预期
2. MP4 box 结构完整（ftyp / moov / mdat 顶层齐全）
3. state 里 done 的任务有对应文件

用法: python3 verify.py
"""

import json
import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
STATE = ROOT / "state"

# 各档最小文件大小（字节）—— 低于此值视为损坏/截断
# 基于实测：1080p/7s 约 500KB+，720p/17s 约 1-15MB，480p/40s 约 2-30MB
MIN_SIZE = {
    "1080p": 150_000,   # 150 KB（保守下限）
    "720p":  300_000,   # 300 KB
    "480p":  500_000,   # 500 KB
}


def parse_top_boxes(path: Path, max_bytes=4096):
    """解析 MP4 顶层 box（只读头部 + 扫描足够字节找 moov 位置）。"""
    boxes = []
    try:
        with open(path, "rb") as f:
            # 先读前 4KB 找 ftyp + 后续 box 头
            head = f.read(min(max_bytes, path.stat().st_size))
            offset = 0
            while offset + 8 <= len(head):
                size = struct.unpack(">I", head[offset:offset + 4])[0]
                btype = head[offset + 4:offset + 8].decode("ascii", errors="replace")
                boxes.append((btype, offset, size))
                if size == 0:  # box 到文件尾
                    break
                if size == 1:  # 64-bit size, 跳过（罕见）
                    break
                offset += size
        # 如果 moov 不在前 4KB，扫整个文件找它的偏移
        if not any(b[0] == "moov" for b in boxes):
            with open(path, "rb") as f:
                data = f.read()
            pos = data.find(b"moov")
            if pos >= 0:
                boxes.append(("moov", pos - 4, 0))
    except Exception:
        pass
    return boxes


def verify_one(path: Path) -> tuple[bool, list]:
    """验证单个 mp4。返回 (ok, 问题列表)。"""
    issues = []
    if not path.exists() or path.stat().st_size == 0:
        return False, ["文件不存在或为空"]

    size = path.stat().st_size
    name = path.stem  # A_g0000_720p
    parts = name.split("_")
    res = parts[-1] if parts else ""

    # 大小检查
    min_size = MIN_SIZE.get(res, 100_000)
    if size < min_size:
        issues.append(f"文件过小 {size}B < {min_size}B")

    # MP4 box 检查
    boxes = parse_top_boxes(path)
    types = [b[0] for b in boxes]

    if "ftyp" not in types:
        issues.append("无 ftyp box（非有效 MP4）")
    if "moov" not in types:
        issues.append("无 moov box（元数据缺失，可能下载截断）")
    if "mdat" not in types and size > 200_000:
        # mdat 在前 4KB 之外也算可疑（除非文件很小）
        issues.append("前 4KB 无 mdat（媒体数据可能缺失）")

    return len(issues) == 0, issues


def main():
    if not OUTPUT.exists():
        print("output/ 不存在")
        return []

    mp4s = sorted(OUTPUT.glob("*.mp4"))
    if not mp4s:
        print("output/ 里没有 mp4 文件")
        return []

    print(f"扫描 {len(mp4s)} 个 mp4 文件...\n")

    ok_count = 0
    bad = []
    size_stats = {"1080p": [], "720p": [], "480p": []}

    for p in mp4s:
        ok, issues = verify_one(p)
        if ok:
            ok_count += 1
            res = p.stem.split("_")[-1]
            if res in size_stats:
                size_stats[res].append(p.stat().st_size)
        else:
            bad.append((p.name, issues))

    print(f"=== 完整性验证: {ok_count}/{len(mp4s)} 通过 ===")
    if bad:
        print(f"\n损坏/可疑文件 ({len(bad)} 个):")
        for name, issues in bad[:30]:
            print(f"  {name}: {'; '.join(issues)}")
        if len(bad) > 30:
            print(f"  ... 还有 {len(bad) - 30} 个")

    # 大小统计
    print(f"\n=== 各档文件大小分布 ===")
    for res in ["1080p", "720p", "480p"]:
        sizes = size_stats[res]
        if not sizes:
            continue
        sizes.sort()
        avg = sum(sizes) // len(sizes)
        med = sizes[len(sizes) // 2]
        print(f"  {res}: 数量={len(sizes)}, "
              f"中位数={med / 1024:.0f}KB, 均值={avg / 1024:.0f}KB, "
              f"范围={sizes[0] / 1024:.0f}-{sizes[-1] / 1024:.0f}KB")

    # state/output 一致性
    print(f"\n=== state/output 一致性 ===")
    mismatches = 0
    if STATE.exists():
        for sf in STATE.glob("*.json"):
            if sf.name.startswith("worker_"):
                continue
            try:
                s = json.loads(sf.read_text())
            except json.JSONDecodeError:
                continue
            if s.get("status") == "done":
                out = s.get("output_path", "")
                if not out or not Path(out).exists():
                    print(f"  ⚠ {s.get('task_id')}: state=done 但文件缺失")
                    mismatches += 1
    if mismatches == 0:
        print("  ✓ 所有 done 状态都有对应文件")

    return bad


if __name__ == "__main__":
    main()
