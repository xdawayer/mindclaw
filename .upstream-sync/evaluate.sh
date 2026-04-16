#!/usr/bin/env bash
# Evaluate diff between recorded upstream base and current upstream/main.
# Emits GitHub Actions outputs + writes .upstream-sync/report.md.
set -euo pipefail

BASE_FILE=".upstream-sync/base.sha"
REPORT=".upstream-sync/report.md"

BASE=$(tr -d '\n\r \t' < "$BASE_FILE")
NEW_HEAD=$(git rev-parse upstream/main)
NEW_HEAD_SHORT=$(git rev-parse --short=7 upstream/main)

out() { echo "$1=$2" >> "${GITHUB_OUTPUT:-/dev/stdout}"; }

if [ "$BASE" = "$NEW_HEAD" ]; then
  out has_updates false
  echo "no upstream updates (base == $NEW_HEAD)"
  exit 0
fi

commits=$(git log --oneline "$BASE..upstream/main" 2>/dev/null || echo "")
commit_count=$(printf '%s\n' "$commits" | grep -c . || true)

upstream_files=$(git diff --name-only "$BASE" upstream/main | sort -u)
local_files=$(git diff --name-only "$BASE" HEAD 2>/dev/null | sort -u || true)

conflicts=$(comm -12 <(printf '%s\n' "$upstream_files") <(printf '%s\n' "$local_files"))
clean=$(comm -23 <(printf '%s\n' "$upstream_files") <(printf '%s\n' "$local_files"))

conflict_count=$(printf '%s\n' "$conflicts" | grep -c . || true)
clean_count=$(printf '%s\n' "$clean" | grep -c . || true)
upstream_count=$(printf '%s\n' "$upstream_files" | grep -c . || true)
local_count=$(printf '%s\n' "$local_files" | grep -c . || true)

{
  echo "## 上游同步报告"
  echo
  echo "- 上游新提交: **${commit_count}** 个"
  echo "- 上游 HEAD: \`${NEW_HEAD_SHORT}\` (${NEW_HEAD})"
  echo "- 当前基线: \`$(printf '%s' "$BASE" | cut -c1-7)\` (${BASE})"
  echo
  echo "### 文件变化统计"
  echo "- 上游改动文件: ${upstream_count}"
  echo "- 本地 fork 差异: ${local_count}"
  echo "- **可能冲突** (双方均动过): ${conflict_count}"
  echo "- **纯上游** (理论可直合并): ${clean_count}"
  echo
  if [ "$conflict_count" -gt 0 ]; then
    echo "### 冲突文件 (需人工确认)"
    echo '```'
    printf '%s\n' "$conflicts"
    echo '```'
    echo
  fi
  echo "### 提交列表"
  echo '```'
  printf '%s\n' "$commits"
  echo '```'
} > "$REPORT"

out has_updates true
out commit_count "$commit_count"
out conflict_count "$conflict_count"
out clean_count "$clean_count"
out new_head "$NEW_HEAD"
out new_head_short "$NEW_HEAD_SHORT"
