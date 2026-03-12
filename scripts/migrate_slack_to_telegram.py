#!/usr/bin/env python3
# input: data/sessions/, data/cron_tasks.json
# output: 迁移 Slack session 到 Telegram，更新 cron 配置
# pos: 一次性迁移脚本 (Slack → Telegram)
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Migrate MindClaw data from Slack to Telegram.

Handles three migration tasks:
1. Copy Slack session JSONL files → Telegram session keys
2. Update cron tasks: notify_channel "slack" → "telegram"
3. Generate a migration report

Usage:
    python scripts/migrate_slack_to_telegram.py --telegram-chat-id YOUR_CHAT_ID [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
CRON_FILE = DATA_DIR / "cron_tasks.json"


def migrate_sessions(
    telegram_chat_id: str,
    slack_dm_id: str | None,
    dry_run: bool,
) -> list[str]:
    """Copy Slack DM session file to Telegram session key.

    Only migrates DM sessions (slack_D*) by default, as channel sessions
    (slack_C*) are group/channel conversations that map to Telegram groups.
    """
    actions: list[str] = []

    if not SESSIONS_DIR.exists():
        actions.append("[SKIP] No sessions directory found")
        return actions

    slack_files = sorted(SESSIONS_DIR.glob("slack_*.jsonl"))
    if not slack_files:
        actions.append("[SKIP] No Slack session files found")
        return actions

    # Track created targets for correct dry-run simulation
    created_targets: set[str] = set()

    for src in slack_files:
        if src.name.endswith(".bak"):
            continue

        # Determine target session key
        # DM sessions (slack_D*) → telegram_{chat_id}
        # Channel sessions (slack_C*) → keep as-is (historical)
        stem = src.stem  # e.g. "slack_D0AL0CFMZK3"
        if stem.startswith("slack_D"):
            if slack_dm_id and not stem.endswith(slack_dm_id):
                actions.append(f"[SKIP] {src.name} (not primary DM {slack_dm_id})")
                continue
            target_name = f"telegram_{telegram_chat_id}.jsonl"
        elif stem.startswith("slack_C"):
            actions.append(f"[KEEP] {src.name} (channel session, kept as historical)")
            continue
        else:
            actions.append(f"[SKIP] {src.name} (unrecognized format)")
            continue

        target = SESSIONS_DIR / target_name
        already_exists = target.exists() or target_name in created_targets

        if already_exists:
            # Merge: append Slack messages after existing content
            actions.append(f"[MERGE] {src.name} → {target_name}")
            if not dry_run:
                with target.open("a", encoding="utf-8") as fh:
                    fh.write(src.read_text(encoding="utf-8"))
        else:
            actions.append(f"[COPY] {src.name} → {target_name}")
            if not dry_run:
                shutil.copy2(src, target)
            created_targets.add(target_name)

    return actions


def migrate_cron(telegram_chat_id: str, dry_run: bool) -> list[str]:
    """Update cron tasks: notify_channel "slack" → "telegram"."""
    actions: list[str] = []

    if not CRON_FILE.exists():
        actions.append("[SKIP] No cron_tasks.json found")
        return actions

    with CRON_FILE.open("r", encoding="utf-8") as f:
        cron_data = json.load(f)

    changed = False
    for task_id, task in cron_data.items():
        name = task.get("name", task_id)
        channel = task.get("notify_channel", "")
        chat_id = task.get("notify_chat_id", "")

        if channel == "slack":
            old_chat_id = chat_id
            task["notify_channel"] = "telegram"
            task["notify_chat_id"] = telegram_chat_id
            actions.append(
                f"[UPDATE] {name}: "
                f"slack/{old_chat_id} → telegram/{telegram_chat_id}"
            )
            changed = True
        else:
            actions.append(f"[KEEP] {name}: already on {channel}")

    if changed and not dry_run:
        # Backup original
        backup = CRON_FILE.with_suffix(".json.bak")
        shutil.copy2(CRON_FILE, backup)
        actions.append(f"[BACKUP] cron_tasks.json → {backup.name}")

        with CRON_FILE.open("w", encoding="utf-8") as f:
            json.dump(cron_data, f, indent=2, ensure_ascii=False)
        actions.append("[SAVED] cron_tasks.json updated")

    return actions


def update_cron_action_text(dry_run: bool) -> list[str]:
    """Update cron action text: replace Slack references with Telegram."""
    actions: list[str] = []

    if not CRON_FILE.exists():
        return actions

    with CRON_FILE.open("r", encoding="utf-8") as f:
        cron_data = json.load(f)

    changed = False
    for task_id, task in cron_data.items():
        action_text = task.get("action", "")
        if "Slack" in action_text or "slack" in action_text.lower():
            new_action = action_text.replace(
                "通过Slack发送", "通过Telegram发送"
            ).replace(
                "通过slack发送", "通过Telegram发送"
            )
            if new_action != action_text:
                task["action"] = new_action
                actions.append(f"[UPDATE] {task.get('name', task_id)}: action text updated")
                changed = True

    if changed and not dry_run:
        with CRON_FILE.open("w", encoding="utf-8") as f:
            json.dump(cron_data, f, indent=2, ensure_ascii=False)

    return actions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate MindClaw data from Slack to Telegram"
    )
    parser.add_argument(
        "--telegram-chat-id",
        required=True,
        help="Your Telegram numeric chat ID (get from @userinfobot)",
    )
    parser.add_argument(
        "--slack-dm-id",
        default=None,
        help="Your primary Slack DM channel ID to migrate (e.g. D0AL0CFMZK3). "
             "If not set, migrates all DM sessions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files",
    )
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n=== MindClaw Slack → Telegram Migration ({mode}) ===")
    print(f"Telegram chat ID: {args.telegram_chat_id}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # 1. Migrate sessions
    print("--- Session Migration ---")
    for action in migrate_sessions(
        args.telegram_chat_id, args.slack_dm_id, args.dry_run
    ):
        print(f"  {action}")

    # 2. Migrate cron config
    print("\n--- Cron Task Migration ---")
    for action in migrate_cron(args.telegram_chat_id, args.dry_run):
        print(f"  {action}")

    # 3. Update cron action text
    print("\n--- Cron Action Text ---")
    for action in update_cron_action_text(args.dry_run):
        print(f"  {action}")

    print("\n=== Migration Complete ===")
    if args.dry_run:
        print("(No files were modified. Run without --dry-run to apply changes)")
    else:
        print("Done! Start MindClaw with: mindclaw serve --channels gateway,telegram")


if __name__ == "__main__":
    main()
