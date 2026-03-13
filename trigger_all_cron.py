#!/usr/bin/env python3
"""Manually trigger cron tasks to test end-to-end execution + push.

Usage:
  uv run python trigger_all_cron.py                # one task per unique channel
  uv run python trigger_all_cron.py <task_name>    # trigger a specific task by name

Runs tasks through the full agent loop (LLM + tools), sends results to Feishu.
"""

import asyncio
import json
import sys
from pathlib import Path

from loguru import logger


async def main() -> None:
    from mindclaw.app import MindClawApp
    from mindclaw.config.loader import load_config

    # Setup logging to console
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")

    cfg = load_config(None)
    app = MindClawApp(cfg)
    app._register_tools()
    app._setup_channels(["feishu"])

    # Load cron tasks
    cron_file = Path("data/cron_tasks.json")
    if not cron_file.exists():
        logger.error("data/cron_tasks.json not found")
        return

    tasks_data = json.loads(cron_file.read_text())

    # If a task name is given as argument, trigger only that task
    target_name = sys.argv[1] if len(sys.argv) > 1 else None

    if target_name:
        tasks_to_run: list[tuple[str, dict]] = []
        for task_id, task in tasks_data.items():
            if task.get("name") == target_name:
                tasks_to_run.append((task_id, task))
                break
        else:
            logger.error(f"Task '{target_name}' not found. Available: {[t.get('name') for t in tasks_data.values()]}")
            return
    else:
        # Pick one task per unique notify_chat_id
        seen_channels: set[str] = set()
        tasks_to_run = []
        for task_id, task in tasks_data.items():
            chat_id = task.get("notify_chat_id", "")
            if chat_id and chat_id not in seen_channels:
                seen_channels.add(chat_id)
                tasks_to_run.append((task_id, task))

    logger.info(f"Will trigger {len(tasks_to_run)} tasks (one per channel):")
    for task_id, task in tasks_to_run:
        logger.info(f"  - {task['name']} -> chat_id={task['notify_chat_id']}")

    # Start background routers
    router_task = asyncio.create_task(app._message_router())
    outbound_task = asyncio.create_task(app._outbound_router())
    channel_task = asyncio.create_task(app.channel_manager.start_all())

    # Give telegram channel a moment to connect
    await asyncio.sleep(2)

    # Trigger all cron tasks
    for task_id, task in tasks_to_run:
        logger.info(f"Triggering: {task['name']}")
        await app._on_cron_trigger(task_id, task)

    # Wait for all active tasks to complete (poll every 5s)
    logger.info("Waiting for all tasks to complete...")
    max_wait = 900  # 15 minutes max
    elapsed = 0
    while elapsed < max_wait:
        await asyncio.sleep(5)
        elapsed += 5
        active = len(app._active_tasks)
        if active == 0:
            # Check if bus is also empty
            await asyncio.sleep(3)
            if len(app._active_tasks) == 0:
                break
        if elapsed % 30 == 0:
            logger.info(f"  ... {active} tasks still running ({elapsed}s elapsed)")

    if app._active_tasks:
        logger.warning(f"Timeout: {len(app._active_tasks)} tasks still running after {max_wait}s")
    else:
        logger.info("All tasks completed successfully!")

    # Cleanup
    router_task.cancel()
    outbound_task.cancel()
    channel_task.cancel()
    for t in [router_task, outbound_task, channel_task]:
        try:
            await t
        except asyncio.CancelledError:
            pass
    await app.channel_manager.stop_all()


if __name__ == "__main__":
    asyncio.run(main())
