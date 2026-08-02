#!/usr/bin/env python3
"""校验 YAML/JSON 文件可解析（拦截写坏的 ci.yml / .pre-commit-config.yaml 等）。

pre-commit 钩子，files: \\.(yaml|yml|json)$。用 PyYAML + stdlib json。
"""
import json
import sys

try:
    import yaml  # type: ignore[import-not-found]
except ImportError:
    print("PyYAML 未安装：pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def check(path: str) -> bool:
    try:
        if path.endswith((".yml", ".yaml")):
            with open(path, encoding="utf-8") as f:
                yaml.safe_load(f)
        elif path.endswith(".json"):
            with open(path, encoding="utf-8") as f:
                json.load(f)
        else:
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"{path}: {exc}", file=sys.stderr)
        return False
    return True


def main() -> int:
    ok = True
    for p in sys.argv[1:]:
        if not check(p):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
