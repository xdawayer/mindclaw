#!/usr/bin/env bash
# Create a sync branch + PR for upstream changes.
# Requires: GH_TOKEN env, git remote "upstream" already fetched, evaluate.sh has run.
set -euo pipefail

BASE_FILE=".upstream-sync/base.sha"
REPORT=".upstream-sync/report.md"

NEW_HEAD=$(git rev-parse upstream/main)
SHORT=$(git rev-parse --short=7 upstream/main)
DATE=$(date -u +%Y-%m-%d)
BRANCH="upstream-sync/${DATE}-${SHORT}"

git config user.name "mindclaw-sync-bot"
git config user.email "mindclaw-sync-bot@users.noreply.github.com"

# Reuse existing sync branch of the same day+sha if it exists on remote
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  echo "[create-pr] branch $BRANCH already exists on remote; skipping"
  existing_pr=$(gh pr list --head "$BRANCH" --state open --json url --jq '.[0].url' || true)
  {
    echo "merge_status=existing"
    echo "branch=$BRANCH"
    echo "pr_url=${existing_pr:-}"
  } >> "${GITHUB_OUTPUT:-/dev/stdout}"
  exit 0
fi

git checkout -b "$BRANCH"

merge_status=clean
if ! git merge upstream/main --allow-unrelated-histories --no-ff --no-edit \
      -m "sync: upstream ${SHORT}"; then
  merge_status=conflict
  # Commit the tree with conflict markers so humans can resolve in the PR UI.
  git add -A
  git commit --no-verify -m "sync: upstream ${SHORT} [MERGE CONFLICTS]"
fi

# Always advance base.sha to the upstream SHA we are trying to absorb.
# When the PR merges, main will carry both the resolved content and the new base.
printf '%s\n' "$NEW_HEAD" > "$BASE_FILE"
if ! git diff --cached --quiet "$BASE_FILE" 2>/dev/null \
    || ! git diff --quiet "$BASE_FILE" 2>/dev/null; then
  git add "$BASE_FILE"
  git commit --no-verify -m "chore(upstream-sync): advance base to ${SHORT}"
fi

git push origin "$BRANCH"

title="sync: upstream ${DATE} (${SHORT})"
if [ "$merge_status" = "conflict" ]; then
  title="sync: upstream ${DATE} (${SHORT}) — NEEDS MANUAL RESOLUTION"
fi

pr_url=$(gh pr create \
  --base main --head "$BRANCH" \
  --title "$title" \
  --body-file "$REPORT")

{
  echo "merge_status=$merge_status"
  echo "branch=$BRANCH"
  echo "pr_url=$pr_url"
} >> "${GITHUB_OUTPUT:-/dev/stdout}"

echo "[create-pr] status=$merge_status branch=$BRANCH pr=$pr_url"
