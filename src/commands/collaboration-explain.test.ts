import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { appendCollaborationAuditEvent } from "../collaboration/audit.js";
import type { OpenClawConfig } from "../config/types.js";
import { collaborationExplainCommand } from "./collaboration-explain.js";

const requireValidConfigSnapshot = vi.fn<(runtime: unknown) => Promise<OpenClawConfig | null>>();

vi.mock("./config-validation.js", async () => {
  const actual =
    await vi.importActual<typeof import("./config-validation.js")>("./config-validation.js");
  return {
    ...actual,
    requireValidConfigSnapshot: (runtime: unknown) => requireValidConfigSnapshot(runtime),
  };
});

function createRuntime() {
  const logs: string[] = [];
  const errors: string[] = [];
  return {
    logs,
    errors,
    runtime: {
      log: vi.fn((value: string) => logs.push(value)),
      error: vi.fn((value: string) => errors.push(value)),
      exit: vi.fn((code: number) => {
        throw new Error(`__exit__:${code}`);
      }),
    },
  };
}

function buildConfig(workspaces?: { product?: string; ops?: string }): OpenClawConfig {
  return {
    agents: {
      list: [
        { id: "product", ...(workspaces?.product ? { workspace: workspaces.product } : {}) },
        { id: "ops", ...(workspaces?.ops ? { workspace: workspaces.ops } : {}) },
      ],
    },
    channels: {
      slack: {
        accounts: {
          product: {},
          ops: {},
        },
      },
    },
    collaboration: {
      version: 1,
      mode: "shadow",
      identities: {
        users: {
          U111PM001: {
            identityId: "alice",
            roles: ["product"],
            defaultRole: "product",
          },
        },
      },
      bots: {
        product_bot: {
          slackAccountId: "product",
          agentId: "product",
          role: "product",
        },
        ops_bot: {
          slackAccountId: "ops",
          agentId: "ops",
          role: "ops",
        },
      },
      roles: {
        product: {
          defaultAgentId: "product",
          defaultBotId: "product_bot",
          permissions: ["memory.read.private", "memory.write.private", "agent.handoff"],
        },
        ops: {
          defaultAgentId: "ops",
          defaultBotId: "ops_bot",
          permissions: ["memory.read.private", "memory.write.private"],
        },
      },
      spaces: {
        project_main: {
          kind: "project",
          ownerRole: "product",
          memberRoles: ["product", "ops"],
          slack: {
            channels: ["C111PROJ01"],
            replyThreadMode: "owner",
          },
          handoffs: {
            allowedTargets: ["ops"],
            maxDepth: 4,
          },
        },
      },
    },
  };
}

describe("collaborationExplainCommand", () => {
  it("prints JSON explain output", async () => {
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig());
    const { logs, runtime } = createRuntime();

    await collaborationExplainCommand(
      {
        user: "U111PM001",
        channel: "C111PROJ01",
        account: "product",
        thread: "1713891000.123456",
        json: true,
      },
      runtime,
    );

    const payload = JSON.parse(logs[0] ?? "") as {
      ok: boolean;
      route?: { ownerAgentId?: string };
      space?: { spaceId?: string };
      trace?: { handoffArtifactRoot?: string; auditJournalPath?: string };
    };
    expect(payload.ok).toBe(true);
    expect(payload.space?.spaceId).toBe("project_main");
    expect(payload.route?.ownerAgentId).toBe("product");
    expect(payload.trace?.auditJournalPath).toBe("collaboration/.audit/events.jsonl");
    expect(payload.trace?.handoffArtifactRoot).toBe("collaboration/handoffs");
  });

  it("prints trace contract details in text mode", async () => {
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig());
    const { logs, runtime } = createRuntime();

    await collaborationExplainCommand(
      {
        user: "U111PM001",
        channel: "C111PROJ01",
        account: "product",
        json: false,
      },
      runtime,
    );

    const output = logs[0] ?? "";
    expect(output).toContain("Audit event: slack-collaboration-shadow");
    expect(output).toContain("Audit journal path: collaboration/.audit/events.jsonl");
    expect(output).toContain(
      "Audit journal events: collaboration.route.resolved, collaboration.memory.published, collaboration.handoff.run.started",
    );
    expect(output).toContain("Handoff correlation field: collaboration.handoff.correlationId");
    expect(output).toContain("Handoff artifact field: collaboration.handoff.artifactPath");
    expect(output).toContain("Handoff artifact root: collaboration/handoffs");
    expect(output).toContain(
      "Memory audit events: memory.collaboration.handoff, memory.collaboration.published",
    );
  });

  it("surfaces latest observed route warning codes in text mode", async () => {
    const rootDir = await fs.mkdtemp(path.join(os.tmpdir(), "collaboration-explain-command-"));
    const productWorkspace = path.join(rootDir, "workspace-product");
    await fs.mkdir(productWorkspace, { recursive: true });
    await appendCollaborationAuditEvent(productWorkspace, {
      type: "collaboration.route.resolved",
      timestamp: "2026-04-23T10:00:00.000Z",
      surface: "slack",
      mode: "enforced",
      accountId: "product",
      senderUserId: "U111PM001",
      channelId: "C111PROJ01",
      threadTs: "1713891000.123456",
      spaceId: "project_main",
      legacyAgentId: "main",
      collaborationAgentId: "product",
      effectiveAgentId: "ops",
      handoffStatus: "accepted",
      handoffTargetRole: "ops",
      handoffCorrelationId: "handoff-1",
      routeChanged: true,
      warningCodes: [
        "COLLAB_CONFLICT_BINDING_OVERRIDDEN",
        "COLLAB_CONFLICT_SLACK_CHANNEL_POLICY_OVERRIDDEN",
      ],
    });
    requireValidConfigSnapshot.mockResolvedValueOnce(
      buildConfig({
        product: productWorkspace,
      }),
    );
    const { logs, runtime } = createRuntime();

    try {
      await collaborationExplainCommand(
        {
          user: "U111PM001",
          channel: "C111PROJ01",
          account: "product",
          thread: "1713891000.123456",
          json: false,
        },
        runtime,
      );
    } finally {
      await fs.rm(rootDir, { recursive: true, force: true });
    }

    const output = logs[0] ?? "";
    expect(output).toContain(
      "Latest observed route warnings: COLLAB_CONFLICT_BINDING_OVERRIDDEN, COLLAB_CONFLICT_SLACK_CHANNEL_POLICY_OVERRIDDEN",
    );
    expect(output).toContain("Latest observed handoff correlation: handoff-1");
  });

  it("exits with code 1 when the explain payload is unresolved", async () => {
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig());
    const { logs, runtime } = createRuntime();

    await expect(
      collaborationExplainCommand(
        {
          user: "U404",
          channel: "C404",
          json: true,
        },
        runtime,
      ),
    ).rejects.toThrow("__exit__:1");

    const payload = JSON.parse(logs[0] ?? "") as { ok: boolean; warnings: Array<{ code: string }> };
    expect(payload.ok).toBe(false);
    expect(payload.warnings.map((warning) => warning.code)).toContain("COLLAB_IDENTITY_UNRESOLVED");
  });

  it("requires --user", async () => {
    const { errors, runtime } = createRuntime();

    await expect(
      collaborationExplainCommand(
        {
          user: "",
          json: false,
        },
        runtime,
      ),
    ).rejects.toThrow("__exit__:1");

    expect(errors[0]).toContain("--user is required");
  });
});
