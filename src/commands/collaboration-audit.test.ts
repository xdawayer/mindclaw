import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appendCollaborationAuditEvent } from "../collaboration/audit.js";
import type { OpenClawConfig } from "../config/types.js";
import { collaborationAuditCommand } from "./collaboration-audit.js";

type CollaborationAuditTypeOption = "route" | "memory-published" | "handoff-run";

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

async function createWorkspaceFixture() {
  const rootDir = await fs.mkdtemp(path.join(os.tmpdir(), "collaboration-audit-command-"));
  const productWorkspace = path.join(rootDir, "workspace-product");
  const opsWorkspace = path.join(rootDir, "workspace-ops");
  await fs.mkdir(productWorkspace, { recursive: true });
  await fs.mkdir(opsWorkspace, { recursive: true });
  return {
    rootDir,
    productWorkspace,
    opsWorkspace,
  };
}

function buildConfig(params: { productWorkspace: string; opsWorkspace: string }): OpenClawConfig {
  return {
    agents: {
      list: [
        { id: "product", workspace: params.productWorkspace },
        { id: "ops", workspace: params.opsWorkspace },
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
      mode: "enforced",
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

const tempRoots: string[] = [];

afterEach(async () => {
  vi.clearAllMocks();
  await Promise.all(tempRoots.splice(0).map((dir) => fs.rm(dir, { recursive: true, force: true })));
});

describe("collaborationAuditCommand", () => {
  it("prints JSON audit events for an explicitly selected agent", async () => {
    const fixture = await createWorkspaceFixture();
    tempRoots.push(fixture.rootDir);
    await appendCollaborationAuditEvent(fixture.productWorkspace, {
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
      effectiveAgentId: "product",
      routeChanged: true,
      warningCodes: [],
    });
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig(fixture));
    const { logs, runtime } = createRuntime();

    await collaborationAuditCommand(
      {
        agent: "product",
        limit: 10,
        json: true,
      },
      runtime,
    );

    const payload = JSON.parse(logs[0] ?? "") as {
      agentId: string;
      workspaceDir: string;
      events: Array<{ type: string; channelId?: string }>;
    };
    expect(payload.agentId).toBe("product");
    expect(payload.workspaceDir).toBe(fixture.productWorkspace);
    expect(payload.events).toEqual([
      expect.objectContaining({
        type: "collaboration.route.resolved",
        channelId: "C111PROJ01",
      }),
    ]);
  });

  it("resolves the owner agent from collaboration explain inputs and filters route events", async () => {
    const fixture = await createWorkspaceFixture();
    tempRoots.push(fixture.rootDir);
    await appendCollaborationAuditEvent(fixture.productWorkspace, {
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
      handoffArtifactPath: "collaboration/handoffs/2026-04-23/handoff-1.json",
      routeChanged: true,
      warningCodes: ["COLLAB_CONFLICT_BINDING_OVERRIDDEN"],
    });
    await appendCollaborationAuditEvent(fixture.productWorkspace, {
      type: "collaboration.route.resolved",
      timestamp: "2026-04-23T10:01:00.000Z",
      surface: "slack",
      mode: "enforced",
      accountId: "product",
      senderUserId: "U999",
      channelId: "COTHER",
      legacyAgentId: "main",
      collaborationAgentId: "product",
      effectiveAgentId: "product",
      routeChanged: true,
      warningCodes: [],
    });
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig(fixture));
    const { logs, runtime } = createRuntime();

    await collaborationAuditCommand(
      {
        user: "U111PM001",
        account: "product",
        channel: "C111PROJ01",
        thread: "1713891000.123456",
        type: "route",
        limit: 20,
        json: false,
      },
      runtime,
    );

    const output = logs[0] ?? "";
    expect(output).toContain("Agent: product");
    expect(output).toContain("Events: 1");
    expect(output).toContain("handoff=accepted:ops");
    expect(output).toContain("correlation=handoff-1");
    expect(output).toContain("warnings=COLLAB_CONFLICT_BINDING_OVERRIDDEN");
    expect(output).not.toContain("U999");
  });

  it("merges audit events from handoff target workspaces when querying by surface", async () => {
    const fixture = await createWorkspaceFixture();
    tempRoots.push(fixture.rootDir);
    // Owner-side workspace has the original (pre-handoff) route event.
    await appendCollaborationAuditEvent(fixture.productWorkspace, {
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
      effectiveAgentId: "product",
      routeChanged: true,
      warningCodes: [],
    });
    // Handoff continuation: route event ends up in the EFFECTIVE agent's
    // workspace (ops), not the owner's. Surface-based audit must still find it.
    await appendCollaborationAuditEvent(fixture.opsWorkspace, {
      type: "collaboration.route.resolved",
      timestamp: "2026-04-23T10:01:00.000Z",
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
      handoffCorrelationId: "handoff-merge-1",
      routeChanged: true,
      warningCodes: [],
    });
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig(fixture));
    const { logs, runtime } = createRuntime();

    await collaborationAuditCommand(
      {
        user: "U111PM001",
        account: "product",
        channel: "C111PROJ01",
        thread: "1713891000.123456",
        type: "route",
        limit: 20,
        json: true,
      },
      runtime,
    );

    const output = JSON.parse(logs[0] ?? "{}") as {
      events: Array<{ type: string; handoffCorrelationId?: string }>;
    };
    expect(output.events).toHaveLength(2);
    expect(output.events.some((event) => event.handoffCorrelationId === "handoff-merge-1")).toBe(
      true,
    );
  });

  it("filters route events by handoff correlation id", async () => {
    const fixture = await createWorkspaceFixture();
    tempRoots.push(fixture.rootDir);
    await appendCollaborationAuditEvent(fixture.productWorkspace, {
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
      handoffArtifactPath: "collaboration/handoffs/2026-04-23/handoff-1.json",
      routeChanged: true,
      warningCodes: [],
    });
    await appendCollaborationAuditEvent(fixture.productWorkspace, {
      type: "collaboration.route.resolved",
      timestamp: "2026-04-23T10:01:00.000Z",
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
      handoffCorrelationId: "handoff-2",
      handoffArtifactPath: "collaboration/handoffs/2026-04-23/handoff-2.json",
      routeChanged: true,
      warningCodes: [],
    });
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig(fixture));
    const { logs, runtime } = createRuntime();

    await collaborationAuditCommand(
      {
        agent: "product",
        type: "route",
        correlation: "handoff-1",
        limit: 20,
        json: true,
      },
      runtime,
    );

    const payload = JSON.parse(logs[0] ?? "") as {
      filterType: string | null;
      correlation: string | null;
      events: Array<{ handoffCorrelationId?: string }>;
    };
    expect(payload.filterType).toBe("collaboration.route.resolved");
    expect(payload.correlation).toBe("handoff-1");
    expect(payload.events).toHaveLength(1);
    expect(payload.events[0]?.handoffCorrelationId).toBe("handoff-1");
  });

  it("prints handoff run audit events with the dedicated filter", async () => {
    const fixture = await createWorkspaceFixture();
    tempRoots.push(fixture.rootDir);
    await appendCollaborationAuditEvent(fixture.opsWorkspace, {
      type: "collaboration.handoff.run.started",
      timestamp: "2026-04-23T10:02:00.000Z",
      correlationId: "handoff-1",
      runId: "run-handoff-1",
      taskId: "task-handoff-1",
      ownerSessionKey: "agent:product:slack:channel:c111proj01",
      childSessionKey: "agent:ops:slack:channel:c111proj01",
      agentId: "ops",
      targetRole: "ops",
    });
    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig(fixture));
    const { logs, runtime } = createRuntime();

    await collaborationAuditCommand(
      {
        agent: "ops",
        type: "handoff-run",
        correlation: "handoff-1",
        limit: 20,
        json: false,
      },
      runtime,
    );

    const output = logs[0] ?? "";
    expect(output).toContain("Agent: ops");
    expect(output).toContain("Filter type: collaboration.handoff.run.started");
    expect(output).toContain("Correlation: handoff-1");
    expect(output).toContain("run=run-handoff-1");
    expect(output).toContain("task=task-handoff-1");
  });

  it("does not drop matching cross-workspace events when limit is small and owner has noise", async () => {
    const fixture = await createWorkspaceFixture();
    tempRoots.push(fixture.rootDir);

    // Owner workspace has many noisy events that DON'T match the target
    // correlation filter. With a small --limit they would otherwise win the
    // pre-filter slice and hide the cross-workspace event.
    for (let i = 0; i < 5; i += 1) {
      await appendCollaborationAuditEvent(fixture.productWorkspace, {
        type: "collaboration.route.resolved",
        timestamp: `2026-04-23T11:0${i}:00.000Z`,
        surface: "slack",
        mode: "enforced",
        accountId: "product",
        senderUserId: "U111PM001",
        channelId: "C111PROJ01",
        threadTs: "1713891000.123456",
        spaceId: "project_main",
        legacyAgentId: "main",
        collaborationAgentId: "product",
        effectiveAgentId: "product",
        routeChanged: false,
        warningCodes: [],
      });
    }
    // Target workspace has the matching handoff event (older timestamp).
    await appendCollaborationAuditEvent(fixture.opsWorkspace, {
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
      handoffCorrelationId: "handoff-deep-1",
      routeChanged: true,
      warningCodes: [],
    });

    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig(fixture));
    const { logs, runtime } = createRuntime();

    await collaborationAuditCommand(
      {
        user: "U111PM001",
        account: "product",
        channel: "C111PROJ01",
        thread: "1713891000.123456",
        type: "route",
        correlation: "handoff-deep-1",
        // Small limit to ensure filtering happens before slicing.
        limit: 3,
        json: true,
      },
      runtime,
    );

    const output = JSON.parse(logs[0] ?? "{}") as {
      events: Array<{ handoffCorrelationId?: string }>;
    };
    expect(output.events.some((event) => event.handoffCorrelationId === "handoff-deep-1")).toBe(
      true,
    );
  });

  it("merges target workspaces even when --agent is explicit and the agent owns a managed space", async () => {
    const fixture = await createWorkspaceFixture();
    tempRoots.push(fixture.rootDir);

    // Target workspace has the only event of interest.
    await appendCollaborationAuditEvent(fixture.opsWorkspace, {
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
      handoffCorrelationId: "handoff-explicit-agent-1",
      routeChanged: true,
      warningCodes: [],
    });

    requireValidConfigSnapshot.mockResolvedValueOnce(buildConfig(fixture));
    const { logs, runtime } = createRuntime();

    await collaborationAuditCommand(
      {
        // Explicit owner agent. Codex re-review flagged that --agent skipped
        // the cross-workspace merge, hiding handoff continuations.
        agent: "product",
        type: "route",
        correlation: "handoff-explicit-agent-1",
        limit: 20,
        json: true,
      },
      runtime,
    );

    const output = JSON.parse(logs[0] ?? "{}") as {
      events: Array<{ handoffCorrelationId?: string }>;
    };
    expect(
      output.events.some((event) => event.handoffCorrelationId === "handoff-explicit-agent-1"),
    ).toBe(true);
  });

  it("rejects unknown --type values instead of silently ignoring the filter", async () => {
    requireValidConfigSnapshot.mockResolvedValueOnce({} as OpenClawConfig);
    const { errors, runtime } = createRuntime();
    await expect(
      collaborationAuditCommand(
        {
          agent: "product",
          // intentional invalid value
          type: "bogus" as unknown as CollaborationAuditTypeOption,
          limit: 20,
          json: false,
        },
        runtime,
      ),
    ).rejects.toThrow(/__exit__/);
    expect(errors.join("\n")).toMatch(/Invalid --type/);
  });

  it("rejects non-positive --limit values instead of falling back silently", async () => {
    requireValidConfigSnapshot.mockResolvedValueOnce({} as OpenClawConfig);
    const { errors, runtime } = createRuntime();
    await expect(
      collaborationAuditCommand(
        {
          agent: "product",
          limit: Number.NaN,
          json: false,
        },
        runtime,
      ),
    ).rejects.toThrow(/__exit__/);
    expect(errors.join("\n")).toMatch(/Invalid --limit/);
  });

  it("requires either --agent or --user", async () => {
    const { errors, runtime } = createRuntime();

    await expect(
      collaborationAuditCommand(
        {
          limit: 20,
          json: false,
        },
        runtime,
      ),
    ).rejects.toThrow("__exit__:1");

    expect(errors[0]).toContain("Either --agent or --user is required");
  });
});
