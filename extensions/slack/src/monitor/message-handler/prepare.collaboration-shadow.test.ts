import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { readCollaborationAuditEvents } from "openclaw/plugin-sdk/collaboration-runtime";
import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import { readMemoryHostEvents } from "openclaw/plugin-sdk/memory-host-events";
import { describe, expect, it, vi } from "vitest";
import type { SlackMessageEvent } from "../../types.js";
import type { SlackMonitorContext } from "../context.js";
import { prepareSlackMessage } from "./prepare.js";
import { createInboundSlackTestContext, createSlackTestAccount } from "./prepare.test-helpers.js";

function buildCollaborationConfig(mode: "shadow" | "enforced" = "shadow"): OpenClawConfig {
  return {
    agents: {
      list: [
        { id: "main" },
        { id: "product", identity: { name: "Product Bot" } },
        { id: "ops", identity: { name: "Ops Bot" } },
      ],
    },
    channels: {
      slack: {
        enabled: true,
        accounts: {
          default: {},
        },
      },
    },
    collaboration: {
      version: 1,
      mode,
      identities: {
        users: {
          U1: {
            identityId: "alice",
            roles: ["product"],
            defaultRole: "product",
          },
        },
      },
      bots: {
        product_bot: {
          slackAccountId: "default",
          agentId: "product",
          role: "product",
        },
        ops_bot: {
          slackAccountId: "default",
          agentId: "ops",
          role: "ops",
        },
      },
      roles: {
        product: {
          defaultAgentId: "product",
          defaultBotId: "product_bot",
          permissions: [
            "memory.read.private",
            "memory.write.private",
            "memory.read.space_shared",
            "memory.publish.space_shared",
            "agent.handoff",
          ],
          memoryPolicy: {
            defaultWriteScope: "private",
            readableScopes: ["private", "space_shared"],
            publishableScopes: ["space_shared"],
          },
        },
        ops: {
          defaultAgentId: "ops",
          defaultBotId: "ops_bot",
          permissions: ["memory.read.private", "memory.write.private", "memory.read.role_shared"],
          memoryPolicy: {
            defaultWriteScope: "private",
            readableScopes: ["private", "role_shared", "space_shared"],
          },
        },
      },
      spaces: {
        project_main: {
          kind: "project",
          ownerRole: "product",
          memberRoles: ["product", "ops"],
          slack: {
            channels: ["C123"],
            requireMention: false,
            replyThreadMode: "owner",
            allowBotMessages: "handoff_only",
          },
          memory: {
            readableByRoles: ["product"],
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

function createSlackCtx(cfg: OpenClawConfig): SlackMonitorContext {
  const ctx = createInboundSlackTestContext({
    cfg,
    defaultRequireMention: false,
    channelsConfig:
      cfg.channels?.slack?.accounts?.default?.channels ?? cfg.channels?.slack?.channels,
  });
  ctx.resolveUserName = async () => ({ name: "Alice" }) as never;
  ctx.resolveChannelName = async () => ({ name: "general", type: "channel" as const });
  ctx.logger = {
    info: vi.fn(),
    warn: vi.fn(),
  } as never;
  return ctx;
}

function createChannelMessage(channel: string): SlackMessageEvent {
  return {
    channel,
    channel_type: "channel",
    user: "U1",
    text: "hello",
    ts: "1.000",
  } as SlackMessageEvent;
}

function createTextMessage(channel: string, text: string): SlackMessageEvent {
  return {
    channel,
    channel_type: "channel",
    user: "U1",
    text,
    ts: "1.000",
  } as SlackMessageEvent;
}

function configureAgentWorkspaces(params: {
  cfg: OpenClawConfig;
  rootDir: string;
  storePath: string;
}): {
  productWorkspace: string;
  opsWorkspace: string;
} {
  const productWorkspace = path.join(params.rootDir, "workspace-product");
  const opsWorkspace = path.join(params.rootDir, "workspace-ops");
  fs.mkdirSync(productWorkspace, { recursive: true });
  fs.mkdirSync(opsWorkspace, { recursive: true });
  params.cfg.session = { store: params.storePath };
  const mainAgent = params.cfg.agents?.list?.find((entry) => entry.id === "main");
  if (mainAgent) {
    mainAgent.workspace = path.join(params.rootDir, "workspace-main");
    fs.mkdirSync(mainAgent.workspace, { recursive: true });
  }
  const productAgent = params.cfg.agents?.list?.find((entry) => entry.id === "product");
  if (productAgent) {
    productAgent.workspace = productWorkspace;
  }
  const opsAgent = params.cfg.agents?.list?.find((entry) => entry.id === "ops");
  if (opsAgent) {
    opsAgent.workspace = opsWorkspace;
  }
  return {
    productWorkspace,
    opsWorkspace,
  };
}

describe("prepareSlackMessage collaboration shadow mode", () => {
  it("records collaboration explain and audit data on managed Slack surfaces", async () => {
    const ctx = createSlackCtx(buildCollaborationConfig());

    const prepared = await prepareSlackMessage({
      ctx,
      account: createSlackTestAccount(),
      message: createChannelMessage("C123"),
      opts: { source: "message", wasMentioned: true },
    });

    expect(prepared).not.toBeNull();
    expect(prepared?.route.agentId).toBe("main");
    expect(prepared?.collaboration).toMatchObject({
      mode: "shadow",
      explain: {
        ok: true,
        route: {
          ownerAgentId: "product",
        },
        delivery: {
          managedSurface: true,
        },
      },
      audit: {
        event: "slack-collaboration-shadow",
        routeChanged: true,
        legacyAgentId: "main",
        collaborationAgentId: "product",
      },
      memory: {
        effectivePublishableScopes: ["space_shared"],
      },
    });
    expect(ctx.logger.info).toHaveBeenCalledWith(
      expect.objectContaining({
        event: "slack-collaboration-shadow",
        routeChanged: true,
        legacyAgentId: "main",
        collaborationAgentId: "product",
      }),
      "slack collaboration shadow",
    );
  });

  it("skips collaboration shadow state on unmanaged Slack surfaces", async () => {
    const ctx = createSlackCtx(buildCollaborationConfig());

    const prepared = await prepareSlackMessage({
      ctx,
      account: createSlackTestAccount(),
      message: createChannelMessage("C999"),
      opts: { source: "message", wasMentioned: true },
    });

    expect(prepared).not.toBeNull();
    expect(prepared?.collaboration).toBeUndefined();
    expect(ctx.logger.info).not.toHaveBeenCalled();
  });

  it("overrides the owner route on managed Slack surfaces in enforced mode", async () => {
    const ctx = createSlackCtx(buildCollaborationConfig("enforced"));

    const prepared = await prepareSlackMessage({
      ctx,
      account: createSlackTestAccount(),
      message: createChannelMessage("C123"),
      opts: { source: "message", wasMentioned: true },
    });

    expect(prepared).not.toBeNull();
    expect(prepared?.route).toMatchObject({
      agentId: "product",
      accountId: "default",
      sessionKey: "agent:product:slack:channel:c123",
      mainSessionKey: "agent:product:main",
      matchedBy: "collaboration.space",
    });
    expect(prepared?.ctxPayload.SessionKey).toBe("agent:product:slack:channel:c123");
    expect(prepared?.collaboration).toMatchObject({
      mode: "enforced",
      explain: {
        ok: true,
        route: {
          ownerAgentId: "product",
        },
      },
      audit: {
        event: "slack-collaboration-enforced",
        routeChanged: true,
        legacyAgentId: "main",
        collaborationAgentId: "product",
        effectiveAgentId: "product",
      },
    });
    expect(ctx.logger.info).toHaveBeenCalledWith(
      expect.objectContaining({
        event: "slack-collaboration-enforced",
        routeChanged: true,
        legacyAgentId: "main",
        collaborationAgentId: "product",
        effectiveAgentId: "product",
      }),
      "slack collaboration enforced",
    );
  });

  it("keeps unmanaged Slack surfaces on the legacy route in enforced mode", async () => {
    const ctx = createSlackCtx(buildCollaborationConfig("enforced"));

    const prepared = await prepareSlackMessage({
      ctx,
      account: createSlackTestAccount(),
      message: createChannelMessage("C999"),
      opts: { source: "message", wasMentioned: true },
    });

    expect(prepared).not.toBeNull();
    expect(prepared?.route.agentId).toBe("main");
    expect(prepared?.collaboration).toBeUndefined();
    expect(ctx.logger.info).not.toHaveBeenCalled();
  });

  it("routes explicit allowed collaboration handoffs to the target agent in enforced mode", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slack-collab-handoff-"));
    const config = buildCollaborationConfig("enforced");
    const storePath = path.join(tmpDir, "sessions.json");
    const { opsWorkspace } = configureAgentWorkspaces({
      cfg: config,
      rootDir: tmpDir,
      storePath,
    });
    const ctx = createSlackCtx(config);

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createTextMessage("C123", "@Ops Bot please investigate the logs"),
        opts: { source: "message", wasMentioned: true },
      });

      expect(prepared).not.toBeNull();
      expect(prepared?.route).toMatchObject({
        agentId: "ops",
        matchedBy: "collaboration.handoff",
      });
      expect(prepared?.collaboration).toMatchObject({
        mode: "enforced",
        handoff: {
          depth: 1,
          status: "accepted",
          targetRole: "ops",
          targetAgentId: "ops",
          trigger: "explicit_mention",
          correlationId: expect.any(String),
          artifactPath: expect.stringContaining("collaboration/handoffs/"),
        },
        memory: {
          effectiveReadableScopes: ["private", "role_shared"],
        },
        audit: {
          event: "slack-collaboration-enforced",
          handoffStatus: "accepted",
          handoffTargetRole: "ops",
          handoffDepth: 1,
          effectiveAgentId: "ops",
          handoffCorrelationId: expect.any(String),
          handoffArtifactPath: expect.stringContaining("collaboration/handoffs/"),
        },
      });
      expect(prepared?.collaboration?.handoff?.correlationId).toBe(
        prepared?.collaboration?.audit.handoffCorrelationId,
      );
      expect(prepared?.ctxPayload.GroupSystemPrompt).toContain(
        "Structured collaboration handoff from role product to role ops.",
      );
      expect(prepared?.ctxPayload.GroupSystemPrompt).toContain(
        "Readable collaboration memory scopes: private, role_shared.",
      );
      // Correlation IDs must NOT appear in the system prompt: they are
      // randomized per turn and would defeat prompt cache reuse on retry.
      expect(prepared?.ctxPayload.GroupSystemPrompt).not.toContain("Handoff correlation ID");
      expect(prepared?.ctxPayload.GroupSystemPrompt).not.toContain(
        prepared?.collaboration?.handoff?.correlationId ?? "",
      );
      expect(prepared?.ctxPayload.GroupSystemPrompt).not.toContain("space_shared");
      expect(prepared?.ctxPayload.ParentSessionKey).toBe("agent:product:slack:channel:c123");

      const artifactPath = prepared?.collaboration?.handoff?.artifactPath;
      expect(artifactPath).toBeTruthy();
      const artifactBody = JSON.parse(
        fs.readFileSync(path.join(opsWorkspace, artifactPath ?? ""), "utf8"),
      ) as Record<string, unknown>;
      expect(artifactBody).toMatchObject({
        status: "accepted",
        depth: 1,
        sourceRole: "product",
        targetRole: "ops",
        effectiveAgentId: "ops",
        senderUserId: "U1",
        channelId: "C123",
      });
      expect(artifactBody.correlationId).toBe(prepared?.collaboration?.handoff?.correlationId);

      await vi.waitFor(() => {
        const sessionStore = JSON.parse(fs.readFileSync(storePath, "utf8")) as Record<
          string,
          Record<string, unknown>
        >;
        expect(sessionStore["agent:ops:slack:channel:c123"]).toMatchObject({
          spawnedBy: "agent:product:slack:channel:c123",
          parentSessionKey: "agent:product:slack:channel:c123",
          spawnDepth: 1,
          collaboration: {
            managedSurface: true,
            effectiveRole: "ops",
            handoff: {
              status: "accepted",
              correlationId: prepared?.collaboration?.handoff?.correlationId,
              depth: 1,
              targetRole: "ops",
            },
          },
        });
      });

      const events = await readMemoryHostEvents({ workspaceDir: opsWorkspace });
      expect(events.at(-1)).toMatchObject({
        type: "memory.collaboration.handoff",
        depth: 1,
        status: "accepted",
        artifactPath,
      });
      const auditEvents = await readCollaborationAuditEvents({ workspaceDir: opsWorkspace });
      expect(auditEvents.at(-1)).toMatchObject({
        type: "collaboration.route.resolved",
        mode: "enforced",
        surface: "slack",
        handoffStatus: "accepted",
        handoffTargetRole: "ops",
        handoffDepth: 1,
        handoffCorrelationId: prepared?.collaboration?.handoff?.correlationId,
        handoffArtifactPath: artifactPath,
        effectiveAgentId: "ops",
      });
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("records rejected collaboration handoffs without overriding the route", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slack-collab-handoff-"));
    const config = buildCollaborationConfig("enforced");
    config.collaboration!.spaces.project_main.handoffs = {
      allowedTargets: [],
      maxDepth: 4,
    };
    const storePath = path.join(tmpDir, "sessions.json");
    const { productWorkspace } = configureAgentWorkspaces({
      cfg: config,
      rootDir: tmpDir,
      storePath,
    });
    const ctx = createSlackCtx(config);

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createTextMessage("C123", "@Ops Bot please investigate the logs"),
        opts: { source: "message", wasMentioned: true },
      });

      expect(prepared).not.toBeNull();
      expect(prepared?.route.agentId).toBe("product");
      expect(prepared?.collaboration).toMatchObject({
        mode: "enforced",
        handoff: {
          depth: 1,
          status: "rejected",
          targetRole: "ops",
          reasonCode: "COLLAB_HANDOFF_TARGET_NOT_ALLOWED",
          correlationId: expect.any(String),
          artifactPath: expect.stringContaining("collaboration/handoffs/"),
        },
        audit: {
          handoffStatus: "rejected",
          handoffTargetRole: "ops",
          handoffDepth: 1,
          effectiveAgentId: "product",
          handoffCorrelationId: expect.any(String),
          handoffArtifactPath: expect.stringContaining("collaboration/handoffs/"),
        },
      });
      expect(prepared?.ctxPayload.GroupSystemPrompt).not.toContain(
        "Structured collaboration handoff from role product to role ops.",
      );

      const artifactPath = prepared?.collaboration?.handoff?.artifactPath;
      expect(artifactPath).toBeTruthy();
      const artifactBody = JSON.parse(
        fs.readFileSync(path.join(productWorkspace, artifactPath ?? ""), "utf8"),
      ) as Record<string, unknown>;
      expect(artifactBody).toMatchObject({
        status: "rejected",
        depth: 1,
        reasonCode: "COLLAB_HANDOFF_TARGET_NOT_ALLOWED",
        sourceRole: "product",
        targetRole: "ops",
        effectiveAgentId: "product",
      });
      expect(artifactBody.correlationId).toBe(prepared?.collaboration?.handoff?.correlationId);

      const events = await readMemoryHostEvents({ workspaceDir: productWorkspace });
      expect(events.at(-1)).toMatchObject({
        type: "memory.collaboration.handoff",
        depth: 1,
        status: "rejected",
        artifactPath,
      });
      const auditEvents = await readCollaborationAuditEvents({ workspaceDir: productWorkspace });
      expect(auditEvents.at(-1)).toMatchObject({
        type: "collaboration.route.resolved",
        mode: "enforced",
        surface: "slack",
        handoffStatus: "rejected",
        handoffTargetRole: "ops",
        handoffDepth: 1,
        handoffCorrelationId: prepared?.collaboration?.handoff?.correlationId,
        handoffArtifactPath: artifactPath,
        effectiveAgentId: "product",
      });
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("records runtime warnings when managed Slack surfaces override legacy bindings and channel policy", async () => {
    const config = buildCollaborationConfig("enforced");
    config.bindings = [{ agentId: "main", match: { channel: "slack" } }];
    config.channels!.slack = {
      ...config.channels!.slack,
      accounts: {
        default: {
          channels: {
            C123: {
              requireMention: true,
              users: ["U1"],
            },
          },
        },
      },
    };
    const ctx = createSlackCtx(config);

    const prepared = await prepareSlackMessage({
      ctx,
      account: createSlackTestAccount({
        config: config.channels?.slack?.accounts?.default,
      }),
      message: createChannelMessage("C123"),
      opts: { source: "message", wasMentioned: true },
    });

    expect(prepared).not.toBeNull();
    expect(prepared?.collaboration?.audit.warningCodes).toEqual([
      "COLLAB_CONFLICT_BINDING_OVERRIDDEN",
      "COLLAB_CONFLICT_SLACK_CHANNEL_POLICY_OVERRIDDEN",
    ]);
    expect(ctx.logger.info).toHaveBeenCalledWith(
      expect.objectContaining({
        warningCodes: [
          "COLLAB_CONFLICT_BINDING_OVERRIDDEN",
          "COLLAB_CONFLICT_SLACK_CHANNEL_POLICY_OVERRIDDEN",
        ],
      }),
      "slack collaboration enforced",
    );
  });

  it("rejects collaboration handoffs that exceed the configured maxDepth", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slack-collab-handoff-depth-"));
    const config = buildCollaborationConfig("enforced");
    config.collaboration!.spaces.project_main.handoffs = {
      allowedTargets: ["ops"],
      maxDepth: 1,
    };
    const storePath = path.join(tmpDir, "sessions.json");
    const { productWorkspace } = configureAgentWorkspaces({
      cfg: config,
      rootDir: tmpDir,
      storePath,
    });
    fs.writeFileSync(
      storePath,
      `${JSON.stringify(
        {
          "agent:ops:slack:channel:c123": {
            sessionId: "sess-ops",
            updatedAt: Date.now(),
            collaboration: {
              mode: "enforced",
              managedSurface: true,
              spaceId: "project_main",
              ownerRole: "product",
              effectiveRole: "ops",
              readableScopes: ["private", "role_shared"],
              publishableScopes: [],
              handoff: {
                correlationId: "handoff-prev",
                depth: 1,
                status: "accepted",
                sourceRole: "product",
                targetRole: "ops",
                targetAgentId: "ops",
                targetBotId: "ops_bot",
              },
            },
          },
        },
        null,
        2,
      )}\n`,
      "utf8",
    );
    const ctx = createSlackCtx(config);

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createTextMessage("C123", "@Ops Bot please investigate again"),
        opts: { source: "message", wasMentioned: true },
      });

      expect(prepared).not.toBeNull();
      expect(prepared?.route.agentId).toBe("product");
      expect(prepared?.collaboration).toMatchObject({
        mode: "enforced",
        handoff: {
          depth: 2,
          status: "rejected",
          targetRole: "ops",
          reasonCode: "COLLAB_HANDOFF_MAX_DEPTH_EXCEEDED",
          correlationId: expect.any(String),
          artifactPath: expect.stringContaining("collaboration/handoffs/"),
        },
        audit: {
          handoffStatus: "rejected",
          handoffTargetRole: "ops",
          handoffDepth: 2,
          effectiveAgentId: "product",
          handoffCorrelationId: expect.any(String),
          handoffArtifactPath: expect.stringContaining("collaboration/handoffs/"),
        },
      });
      expect(prepared?.ctxPayload.GroupSystemPrompt).not.toContain(
        "Structured collaboration handoff from role product to role ops.",
      );

      const artifactPath = prepared?.collaboration?.handoff?.artifactPath;
      expect(artifactPath).toBeTruthy();
      const artifactBody = JSON.parse(
        fs.readFileSync(path.join(productWorkspace, artifactPath ?? ""), "utf8"),
      ) as Record<string, unknown>;
      expect(artifactBody).toMatchObject({
        status: "rejected",
        depth: 2,
        reasonCode: "COLLAB_HANDOFF_MAX_DEPTH_EXCEEDED",
        sourceRole: "product",
        targetRole: "ops",
        effectiveAgentId: "product",
      });

      const events = await readMemoryHostEvents({ workspaceDir: productWorkspace });
      expect(events.at(-1)).toMatchObject({
        type: "memory.collaboration.handoff",
        depth: 2,
        status: "rejected",
        artifactPath,
      });
      const auditEvents = await readCollaborationAuditEvents({ workspaceDir: productWorkspace });
      expect(auditEvents.at(-1)).toMatchObject({
        type: "collaboration.route.resolved",
        mode: "enforced",
        surface: "slack",
        handoffStatus: "rejected",
        handoffTargetRole: "ops",
        handoffDepth: 2,
        handoffCorrelationId: prepared?.collaboration?.handoff?.correlationId,
        handoffArtifactPath: artifactPath,
        effectiveAgentId: "product",
      });
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("rejects handoffs when the source bot has canInitiateHandoffs disabled", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slack-collab-no-initiate-"));
    const config = buildCollaborationConfig("enforced");
    config.collaboration!.bots.product_bot.canInitiateHandoffs = false;
    const storePath = path.join(tmpDir, "sessions.json");
    configureAgentWorkspaces({ cfg: config, rootDir: tmpDir, storePath });
    const ctx = createSlackCtx(config);

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createTextMessage("C123", "@Ops Bot please investigate the logs"),
        opts: { source: "message", wasMentioned: true },
      });

      expect(prepared?.collaboration?.handoff).toMatchObject({
        status: "rejected",
        reasonCode: "COLLAB_HANDOFF_INITIATOR_DISABLED",
      });
      // Owner route must remain intact when the handoff is denied.
      expect(prepared?.route.agentId).toBe("product");
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("does not write audit events or handoff artifacts when collaboration.audit.enabled is false", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slack-collab-audit-disabled-"));
    const config = buildCollaborationConfig("enforced");
    config.collaboration!.audit = { enabled: false };
    const storePath = path.join(tmpDir, "sessions.json");
    const { opsWorkspace } = configureAgentWorkspaces({
      cfg: config,
      rootDir: tmpDir,
      storePath,
    });
    const ctx = createSlackCtx(config);

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createTextMessage("C123", "@Ops Bot please investigate the logs"),
        opts: { source: "message", wasMentioned: true },
      });

      expect(prepared).not.toBeNull();
      expect(prepared?.collaboration?.handoff?.status).toBe("accepted");
      // Artifact path is intentionally absent because the artifact was never persisted.
      expect(prepared?.collaboration?.handoff?.artifactPath).toBeUndefined();

      // No audit events file should have been created in the ops workspace.
      const auditEvents = await readCollaborationAuditEvents({ workspaceDir: opsWorkspace });
      expect(auditEvents).toEqual([]);

      // No handoff artifact directory should exist either.
      const handoffsDir = path.join(opsWorkspace, "collaboration", "handoffs");
      expect(fs.existsSync(handoffsDir)).toBe(false);
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("redacts message bodies from the handoff artifact when collaboration.audit.redactBodies is true", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slack-collab-redact-"));
    const config = buildCollaborationConfig("enforced");
    config.collaboration!.audit = { redactBodies: true };
    const storePath = path.join(tmpDir, "sessions.json");
    const { opsWorkspace } = configureAgentWorkspaces({
      cfg: config,
      rootDir: tmpDir,
      storePath,
    });
    const ctx = createSlackCtx(config);

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createTextMessage("C123", "@Ops Bot password=super-secret-12345"),
        opts: { source: "message", wasMentioned: true },
      });

      expect(prepared?.collaboration?.handoff?.status).toBe("accepted");
      const artifactPath = prepared?.collaboration?.handoff?.artifactPath;
      expect(artifactPath).toBeTruthy();

      const fullArtifactPath = path.join(opsWorkspace, artifactPath!);
      const artifactBody = JSON.parse(fs.readFileSync(fullArtifactPath, "utf8")) as {
        textPreview?: string;
      };
      expect(artifactBody.textPreview).toBeUndefined();
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });

  it("does not propagate audit-write failures to the prepare result in shadow mode", async () => {
    const cfg = buildCollaborationConfig("shadow");
    const ctx = createSlackCtx(cfg);

    // Force audit writes to fail by pointing the owner agent's workspace at a
    // file (not a directory), so any mkdir under it fails with ENOTDIR.
    const tmpFile = path.join(os.tmpdir(), `slack-collab-blocked-audit-${Date.now()}.bin`);
    fs.writeFileSync(tmpFile, "");
    const productAgent = cfg.agents?.list?.find((entry) => entry.id === "product");
    if (!productAgent) {
      throw new Error("product agent missing in collaboration config fixture");
    }
    productAgent.workspace = tmpFile;

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createChannelMessage("C123"),
        opts: { source: "message", wasMentioned: true },
      });

      // Delivery must NOT be blocked by an audit-write failure: shadow mode is
      // observation-only, so a disk error here should fall back to a warn log.
      expect(prepared).not.toBeNull();
      expect(prepared?.collaboration?.mode).toBe("shadow");
      expect(ctx.logger.warn).toHaveBeenCalledWith(
        expect.objectContaining({ error: expect.any(String) }),
        expect.stringMatching(/collaboration audit/i),
      );
    } finally {
      fs.rmSync(tmpFile, { force: true });
    }
  });

  it("does not propagate handoff-artifact write failures to the prepare result in enforced mode", async () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slack-collab-handoff-fail-"));
    const config = buildCollaborationConfig("enforced");
    const storePath = path.join(tmpDir, "sessions.json");
    configureAgentWorkspaces({
      cfg: config,
      rootDir: tmpDir,
      storePath,
    });
    const ctx = createSlackCtx(config);

    // Block the ops workspace by replacing it with a file. Both the handoff
    // artifact and the audit event write under that workspace will fail.
    const opsAgent = config.agents?.list?.find((entry) => entry.id === "ops");
    if (!opsAgent?.workspace) {
      throw new Error("ops workspace missing in fixture");
    }
    fs.rmSync(opsAgent.workspace, { recursive: true, force: true });
    fs.writeFileSync(opsAgent.workspace, "");

    try {
      const prepared = await prepareSlackMessage({
        ctx,
        account: createSlackTestAccount(),
        message: createTextMessage("C123", "@Ops Bot please investigate the logs"),
        opts: { source: "message", wasMentioned: true },
      });

      expect(prepared).not.toBeNull();
      expect(prepared?.collaboration?.mode).toBe("enforced");
      expect(ctx.logger.warn).toHaveBeenCalledWith(
        expect.objectContaining({ error: expect.any(String) }),
        expect.stringMatching(/collaboration (handoff artifact|audit)/i),
      );
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });
});
