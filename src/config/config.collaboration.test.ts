import { describe, expect, it } from "vitest";
import { computeBaseConfigSchemaResponse } from "./schema-base.js";
import { validateConfigObjectRaw } from "./validation.js";
import { OpenClawSchema } from "./zod-schema.js";

function buildValidCollaborationConfig() {
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
            allowBotMessages: "handoff_only",
          },
          handoffs: {
            allowedTargets: ["ops"],
          },
        },
        dm_product_alice: {
          kind: "dm",
          slack: {
            users: ["U111PM001"],
          },
        },
      },
      memory: {
        scopes: {
          private: { default: true },
          role_shared: { partitionBy: "role" },
          space_shared: { partitionBy: "space" },
        },
        rules: {
          requireProvenance: true,
          requireExplicitPublish: true,
          denyGlobalSearchByDefault: true,
        },
      },
      routing: {
        ownerSelection: {
          dm: "identity_default_role",
          role: "space_owner_role",
          project: "space_owner_role",
        },
        mentionRouting: {
          explicitAgentMention: true,
          fallbackToOwner: true,
        },
        handoff: {
          mode: "structured",
          dedupeWindow: "90s",
          maxDepth: 4,
          allowBotAuthoredReentry: false,
        },
      },
      schedules: {
        jobs: [
          {
            id: "product_daily_digest",
            audience: { kind: "role", id: "product" },
            sourceSpaces: ["project_main"],
            cron: "0 9 * * 1-5",
            delivery: [{ kind: "slack_channel", channelId: "C111PROJ01" }],
            memoryReadScopes: ["role_shared", "space_shared"],
          },
        ],
      },
      approvals: {
        policies: {
          high_risk_exec: {
            when: ["tool:exec", "risk:high"],
            approverRoles: ["ops"],
            delivery: ["dm"],
          },
        },
      },
      audit: {
        enabled: true,
        retainDays: 30,
        redactBodies: false,
        explainMode: true,
      },
    },
  };
}

describe("collaboration config schema", () => {
  it("accepts a valid collaboration config", () => {
    const result = OpenClawSchema.safeParse(buildValidCollaborationConfig());

    expect(result.success).toBe(true);
  });

  it("includes collaboration in the computed base config schema", () => {
    const schema = computeBaseConfigSchemaResponse().schema as {
      properties?: Record<string, unknown>;
    };

    expect(schema.properties?.collaboration).toBeDefined();
  });

  it("rejects schedule definitions that set multiple time selectors", () => {
    const config = buildValidCollaborationConfig();
    config.collaboration.schedules.jobs[0] = {
      ...config.collaboration.schedules.jobs[0],
      at: "09:00",
      cron: "0 9 * * 1-5",
    } as unknown as (typeof config.collaboration.schedules.jobs)[number];

    const result = OpenClawSchema.safeParse(config);

    expect(result.success).toBe(false);
    if (result.success) {
      return;
    }
    expect(result.error.issues).toContainEqual(
      expect.objectContaining({
        path: ["collaboration", "schedules", "jobs", 0],
      }),
    );
  });

  it("rejects identities whose defaultRole is not in roles", () => {
    const config = buildValidCollaborationConfig();
    config.collaboration.identities.users.U111PM001.defaultRole = "ops";

    const result = OpenClawSchema.safeParse(config);

    expect(result.success).toBe(false);
    if (result.success) {
      return;
    }
    expect(result.error.issues).toContainEqual(
      expect.objectContaining({
        path: ["collaboration", "identities", "users", "U111PM001", "defaultRole"],
      }),
    );
  });
});

describe("collaboration config validation", () => {
  it("accepts a valid collaboration config during raw validation", () => {
    const result = validateConfigObjectRaw(buildValidCollaborationConfig());

    expect(result.ok).toBe(true);
  });

  it("rejects bots that reference missing agents", () => {
    const config = buildValidCollaborationConfig();
    config.collaboration.bots.product_bot.agentId = "missing-agent";

    const result = validateConfigObjectRaw(config);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.issues).toContainEqual({
      path: "collaboration.bots.product_bot.agentId",
      message: 'agent not found: "missing-agent"',
    });
  });

  it("rejects bots that reference missing Slack accounts", () => {
    const config = buildValidCollaborationConfig();
    config.collaboration.bots.product_bot.slackAccountId = "missing-account";

    const result = validateConfigObjectRaw(config);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.issues).toContainEqual({
      path: "collaboration.bots.product_bot.slackAccountId",
      message: 'Slack account not found: "missing-account"',
    });
  });

  it("rejects spaces whose ownerRole is not a member", () => {
    const config = buildValidCollaborationConfig();
    config.collaboration.spaces.project_main.memberRoles = ["ops"];

    const result = validateConfigObjectRaw(config);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.issues).toContainEqual({
      path: "collaboration.spaces.project_main.memberRoles",
      message: 'ownerRole "product" must be included in memberRoles',
    });
  });

  it("rejects roles whose default bot is missing", () => {
    const config = buildValidCollaborationConfig();
    config.collaboration.roles.product.defaultBotId = "missing-bot";

    const result = validateConfigObjectRaw(config);

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.issues).toContainEqual({
      path: "collaboration.roles.product.defaultBotId",
      message: 'bot not found: "missing-bot"',
    });
  });
});
