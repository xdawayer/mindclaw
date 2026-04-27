import { describe, expect, it, vi } from "vitest";
import type { OpenClawConfig } from "../config/types.js";
import { CronService } from "./service.js";
import {
  createCronStoreHarness,
  createNoopLogger,
  installCronTestHooks,
} from "./service.test-harness.js";

const logger = createNoopLogger();
const { makeStorePath } = createCronStoreHarness({ prefix: "openclaw-cron-collaboration-" });
installCronTestHooks({ logger });

function createCollaborationConfig(): OpenClawConfig {
  return {
    agents: {
      list: [{ id: "ceo", workspace: "/tmp/agent-ceo" }],
    },
    channels: {
      slack: {
        accounts: {
          ceo: {},
        },
      },
    },
    collaboration: {
      version: 1,
      mode: "enforced",
      identities: {
        users: {
          U111CEO01: {
            identityId: "bob",
            roles: ["ceo"],
            defaultRole: "ceo",
            scheduleDelivery: { preferDm: true, fallbackBotId: "ceo_bot" },
          },
        },
      },
      bots: {
        ceo_bot: {
          slackAccountId: "ceo",
          agentId: "ceo",
          role: "ceo",
        },
      },
      roles: {
        ceo: {
          defaultAgentId: "ceo",
          defaultBotId: "ceo_bot",
          permissions: [
            "memory.read.private",
            "memory.read.role_shared",
            "memory.write.private",
            "schedule.read",
          ],
          memoryPolicy: {
            readableScopes: ["private", "role_shared"],
            publishableScopes: [],
          },
        },
      },
      spaces: {
        role_ceo: {
          kind: "role",
          ownerRole: "ceo",
          memberRoles: ["ceo"],
          slack: {
            channels: ["C111CEO001"],
            replyThreadMode: "owner",
          },
        },
      },
      schedules: {
        jobs: [
          {
            id: "ceo_daily_digest",
            enabled: true,
            audience: { kind: "identity", id: "bob" },
            sourceSpaces: ["role_ceo"],
            cron: "0 9 * * 1-5",
            tz: "America/Los_Angeles",
            ownerRole: "ceo",
            delivery: [{ kind: "slack_dm", identityId: "bob" }],
            memoryReadScopes: ["private", "role_shared"],
            template: "daily_exec_digest",
          },
        ],
      },
    },
  };
}

function createCronService(storePath: string, cfg: OpenClawConfig, runIsolatedAgentJob?: unknown) {
  return new CronService({
    storePath,
    cronEnabled: false,
    log: logger,
    collaborationConfig: cfg.collaboration,
    enqueueSystemEvent: vi.fn(),
    requestHeartbeatNow: vi.fn(),
    runIsolatedAgentJob:
      (runIsolatedAgentJob as Parameters<typeof CronService>[0]["runIsolatedAgentJob"]) ??
      (vi.fn(async () => ({ status: "ok" as const, summary: "digest done" })) as never),
  });
}

describe("CronService collaboration schedules", () => {
  it("lists and resolves collaboration schedules as virtual cron jobs", async () => {
    const { storePath } = await makeStorePath();
    const cfg = createCollaborationConfig();
    const cron = createCronService(storePath, cfg);
    await cron.start();

    try {
      const jobs = await cron.list({ includeDisabled: true });
      expect(jobs).toEqual([
        expect.objectContaining({
          id: "collab:ceo_daily_digest",
          name: "ceo_daily_digest",
          agentId: "ceo",
          sessionTarget: "isolated",
          delivery: {
            mode: "announce",
            channel: "slack",
            to: "user:U111CEO01",
            accountId: "ceo",
          },
          payload: expect.objectContaining({
            kind: "agentTurn",
            message: expect.stringContaining("daily_exec_digest"),
          }),
          collaboration: expect.objectContaining({
            source: "collaboration",
            sourceJobId: "ceo_daily_digest",
            ownerRole: "ceo",
            effectiveRole: "ceo",
            readableScopes: ["private", "role_shared"],
            sourceSpaces: ["role_ceo"],
          }),
        }),
      ]);
      expect(cron.getJob("collab:ceo_daily_digest")).toMatchObject({
        id: "collab:ceo_daily_digest",
        agentId: "ceo",
      });
    } finally {
      cron.stop();
    }
  });

  it("runs collaboration schedules through isolated cron execution", async () => {
    const { storePath } = await makeStorePath();
    const cfg = createCollaborationConfig();
    const runIsolatedAgentJob = vi.fn(async () => ({ status: "ok" as const, summary: "done" }));
    const cron = createCronService(storePath, cfg, runIsolatedAgentJob);
    await cron.start();

    try {
      const result = await cron.run("collab:ceo_daily_digest", "force");
      expect(result).toEqual({ ok: true, ran: true });
      expect(runIsolatedAgentJob).toHaveBeenCalledWith(
        expect.objectContaining({
          job: expect.objectContaining({
            id: "collab:ceo_daily_digest",
            collaboration: expect.objectContaining({
              sourceJobId: "ceo_daily_digest",
              effectiveRole: "ceo",
            }),
          }),
          message: expect.stringContaining("daily_exec_digest"),
        }),
      );
    } finally {
      cron.stop();
    }
  });

  it("treats collaboration schedules as read-only jobs", async () => {
    const { storePath } = await makeStorePath();
    const cfg = createCollaborationConfig();
    const cron = createCronService(storePath, cfg);
    await cron.start();

    try {
      await expect(
        cron.update("collab:ceo_daily_digest", { description: "edited" }),
      ).rejects.toThrow("cron collaboration job is read-only: collab:ceo_daily_digest");
      await expect(cron.remove("collab:ceo_daily_digest")).rejects.toThrow(
        "cron collaboration job is read-only: collab:ceo_daily_digest",
      );
    } finally {
      cron.stop();
    }
  });
});
