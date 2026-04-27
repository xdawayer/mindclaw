import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.js";
import { explainCollaborationConfig } from "./runtime.js";

function buildConfig(): OpenClawConfig {
  return {
    agents: {
      list: [{ id: "product" }, { id: "ops" }],
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
          U111OPS01: {
            identityId: "carol",
            roles: ["ops"],
            defaultRole: "ops",
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
          memoryPolicy: {
            defaultWriteScope: "private",
            readableScopes: ["private", "space_shared"],
            publishableScopes: ["space_shared"],
          },
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
            allowBotMessages: "handoff_only",
          },
          handoffs: {
            allowedTargets: ["ops"],
            maxDepth: 4,
          },
        },
        dm_product_alice: {
          kind: "dm",
          slack: {
            users: ["U111PM001"],
          },
        },
      },
    },
  };
}

describe("explainCollaborationConfig", () => {
  it("explains a managed project channel route", () => {
    const payload = explainCollaborationConfig(buildConfig(), {
      accountId: "product",
      userId: "U111PM001",
      channelId: "C111PROJ01",
      threadTs: "1713891000.123456",
    });

    expect(payload.ok).toBe(true);
    expect(payload.identity?.identityId).toBe("alice");
    expect(payload.space).toEqual({
      spaceId: "project_main",
      kind: "project",
      resolvedBy: "slack.channel",
    });
    expect(payload.route).toEqual({
      ownerRole: "product",
      ownerAgentId: "product",
      ownerBotId: "product_bot",
      reason: "space_owner_role",
    });
    expect(payload.memory).toEqual({
      readableScopes: ["private", "space_shared"],
      writeDefaultScope: "private",
      publishableScopes: ["space_shared"],
    });
    expect(payload.handoff).toEqual({
      allowedTargets: ["ops"],
      maxDepth: 4,
      allowBotAuthoredReentry: false,
    });
    expect(payload.trace).toEqual({
      auditEvent: "slack-collaboration-shadow",
      auditJournalPath: "collaboration/.audit/events.jsonl",
      auditJournalEventTypes: [
        "collaboration.route.resolved",
        "collaboration.memory.published",
        "collaboration.handoff.run.started",
      ],
      handoffCorrelationField: "collaboration.handoff.correlationId",
      handoffArtifactField: "collaboration.handoff.artifactPath",
      handoffArtifactRoot: "collaboration/handoffs",
      memoryEventTypes: ["memory.collaboration.handoff", "memory.collaboration.published"],
    });
    expect(payload.delivery).toEqual({
      replyThreadMode: "owner",
      managedSurface: true,
    });
    expect(payload.warnings).toEqual([]);
  });

  it("returns warnings for unresolved identity and space", () => {
    const payload = explainCollaborationConfig(buildConfig(), {
      accountId: "missing",
      userId: "U404",
      channelId: "C404",
    });

    expect(payload.ok).toBe(false);
    expect(payload.identity).toBeNull();
    expect(payload.space).toBeNull();
    expect(payload.route).toBeNull();
    expect(payload.trace).toEqual({
      auditEvent: "slack-collaboration-shadow",
      auditJournalPath: "collaboration/.audit/events.jsonl",
      auditJournalEventTypes: [
        "collaboration.route.resolved",
        "collaboration.memory.published",
        "collaboration.handoff.run.started",
      ],
      handoffCorrelationField: "collaboration.handoff.correlationId",
      handoffArtifactField: "collaboration.handoff.artifactPath",
      handoffArtifactRoot: null,
      memoryEventTypes: ["memory.collaboration.handoff", "memory.collaboration.published"],
    });
    expect(payload.warnings.map((warning) => warning.code)).toEqual([
      "COLLAB_ACCOUNT_UNRESOLVED",
      "COLLAB_IDENTITY_UNRESOLVED",
      "COLLAB_SPACE_UNRESOLVED",
    ]);
  });
});
