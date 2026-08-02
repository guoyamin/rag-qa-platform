#!/usr/bin/env bash
# .env 提交守卫：阻止环境文件被强加进仓库（.gitignore 的二道防线）。
# 拦 .env / .env.local / .env.*.local；放行 .env.example / .env.container（模板）。
set -euo pipefail

blocked=0
for f in "$@"; do
  base=$(basename "$f")
  case "$base" in
    .env|.env.local|.env.*.local)
      echo "❌ 禁止提交环境文件: $f（真实凭据应放本地 .env，见 .gitignore）" >&2
      blocked=1
      ;;
  esac
done
exit $blocked
