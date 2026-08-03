#!/usr/bin/env python3
"""OS 无关的 detect-secrets pre-commit wrapper（修 Windows/Linux 路径不一致）。

问题：detect-secrets 用 os.sep 存路径（Windows `\`、Linux `/`）。共享的 baseline
只在生成它的那个 OS 上匹配——POSIX baseline（CI 生成）在 Windows 上扫描会全判
"新密钥"；反斜杠 baseline（Windows 生成）在 Linux CI 上同样炸。

本 wrapper 的做法：跑 `detect-secrets scan` 拿到本机扫描结果，**把路径统一归一为
POSIX**，再和（始终 POSIX 的）baseline 按 (posix_path, hashed_secret) 比对。baseline
文件本身不动，CI 也不动——同一份 POSIX baseline 全平台通用。

入口（pre-commit）：python tools/hooks/detect_secrets_local.py [files...]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# tools/hooks/detect_secrets_local.py → 上两级 = 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / ".secrets.baseline"


def _to_posix(path: str) -> str:
    """统一路径分隔符为 POSIX（正斜杠）。"""
    return path.replace("\\", "/")


def main() -> int:
    # baseline 文件本身含 hashed_secret（hex/keyword 命中），不能扫它——detect-secrets-hook
    # 同样会跳过自己的 baseline。按 basename 排除（兼容正反斜杠）。
    files = [
        f
        for f in sys.argv[1:]
        if f and f.replace("\\", "/").rstrip("/").split("/")[-1] != ".secrets.baseline"
    ]
    if not files:
        return 0  # 无暂存文件（或只剩 baseline 自身），直接放行

    if not BASELINE.exists():
        sys.stderr.write(
            f"detect-secrets baseline 不存在：{BASELINE}\n"
            "请先 `detect-secrets scan --all-files > .secrets.baseline` 生成（POSIX）。\n"
        )
        return 1

    # 1) 扫描暂存文件（detect-secrets 在 scan 阶段已应用 plugins/filters）
    proc = subprocess.run(
        ["detect-secrets", "scan", *files],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout)
        return proc.returncode

    try:
        scan = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.stderr.write("detect-secrets scan 输出解析失败。\n")
        return 1

    # 2) 读 baseline（POSIX），建 (posix_path, hashed_secret) 已知集合
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    known: set[tuple[str, str]] = set()
    for path, secrets in baseline.get("results", {}).items():
        posix = _to_posix(path)
        for s in secrets:
            h = s.get("hashed_secret")
            if h:
                known.add((posix, h))

    # 3) 比对：扫描里任何 baseline 没收录的密钥 → 视为新增 → 失败
    new_secrets: list[tuple[str, str | int, str]] = []
    for path, secrets in scan.get("results", {}).items():
        posix = _to_posix(path)
        for s in secrets:
            h = s.get("hashed_secret")
            if h and (posix, h) not in known:
                new_secrets.append((posix, s.get("line_number", "?"), s.get("type", "?")))

    if new_secrets:
        for p, ln, t in new_secrets:
            sys.stderr.write(f"  {p}:{ln}  [{t}]\n")
        sys.stderr.write(
            f"\n发现 {len(new_secrets)} 个 baseline 未收录的疑似密钥。\n"
            "- 真密钥：从源码删除/改用环境变量。\n"
            "- 假阳性：重生成 baseline 并提交（POSIX 路径）——\n"
            "  detect-secrets scan --all-files > .secrets.baseline\n"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
