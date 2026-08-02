#!/usr/bin/env bash
# commit-msg 钩子：校验提交信息遵循 Conventional Commits
# 用法：check_commit_msg.sh <commit-msg-file>
# release-please 依赖此格式生成语义化版本 + changelog。
set -euo pipefail

msg_file="${1:?用法: check_commit_msg.sh <commit-msg-file>}"
first_line=$(head -1 "$msg_file")

# 允许的 type：feat fix docs style refactor perf test build ci chore revert
pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?: .+'

if ! grep -qE "$pattern" <<<"$first_line"; then
  echo "❌ 提交信息不符合 Conventional Commits:" >&2
  echo "    $first_line" >&2
  echo "期望: <type>(<scope>): <description>" >&2
  echo "type: feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert" >&2
  echo "示例: feat(knowledge): 支持按标签过滤检索" >&2
  exit 1
fi
