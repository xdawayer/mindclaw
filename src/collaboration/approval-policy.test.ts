import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { clearSessionStoreCacheForTest } from "../config/sessions/store.js";
import type { OpenClawConfig } from "../config/types.js";
import {
  resolveCollaborationApprovalApproverUserIds,
  resolveCollaborationExecApprovalPolicy,
} from "./approval-policy.js";

const STORE_PATH = path.join(os.tmpdir(), "openclaw-collaboration-approval-policy-test.json");
const SESSION_KEY = "agent:product:slack:channel:c123:thread:1712345678.123456";

function writeStore(store: Record<string, unknown>) {
  fs.writeFileSync(STORE_PATH, `${JSON.stringify(store, null, 2)}\n`, "utf8");
  clearSessionStoreCacheForTest();
}

function buildConfig(): OpenClawConfig {
  return {
    session: { store: STORE_PATH },
    agents: {
      list: [{ id: "product" }, { id: "ceo" }, { id: "ops" }],
    },
    channels: {
      slack: {
        botToken: "xoxb-test",
        appToken: "xapp-test",
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
          },
          U111OPS01: {
            identityId: "carol",
            roles: ["ops"],
            defaultRole: "ops",
          },
          U111PM001: {
            identityId: "alice",
            roles: ["product"],
            defaultRole: "product",
          },
        },
      },
      bots: {
        ceo_bot: {
          slackAccountId: "default",
          agentId: "ceo",
          role: "ceo",
        },
        ops_bot: {
          slackAccountId: "default",
          agentId: "ops",
          role: "ops",
        },
        product_bot: {
          slackAccountId: "default",
          agentId: "product",
          role: "product",
        },
      },
      roles: {
        ceo: {
          defaultAgentId: "ceo",
          defaultBotId: "ceo_bot",
          permissions: ["exec.approve"],
        },
        ops: {
          defaultAgentId: "ops",
          defaultBotId: "ops_bot",
          permissions: ["exec.approve"],
        },
        product: {
          defaultAgentId: "product",
          defaultBotId: "product_bot",
          permissions: ["memory.read.private"],
        },
      },
      spaces: {
        project_main: {
          kind: "project",
          ownerRole: "product",
          memberRoles: ["ceo", "ops", "product"],
          slack: {
            channels: ["C123"],
          },
        },
      },
      approvals: {
        policies: {
          high_risk_exec: {
            when: ["tool:exec", "risk:high"],
            approverRoles: ["ceo", "ops"],
            delivery: ["dm", "origin_thread"],
            agentFilter: ["product"],
            spaceFilter: ["project_main"],
          },
        },
      },
    },
  };
}

afterEach(() => {
  clearSessionStoreCacheForTest();
  try {
    fs.unlinkSync(STORE_PATH);
  } catch {}
});

describe("collaboration approval policy", () => {
  it("resolves approver roles and delivery for managed high-risk exec requests", () => {
    writeStore({
      [SESSION_KEY]: {
        sessionId: "sess-1",
        updatedAt: Date.now(),
        collaboration: {
          mode: "enforced",
          managedSurface: true,
          spaceId: "project_main",
          ownerRole: "product",
          effectiveRole: "product",
          readableScopes: ["private"],
          publishableScopes: [],
        },
      },
    });

    const cfg = buildConfig();
    expect(resolveCollaborationApprovalApproverUserIds({ cfg })).toEqual([
      "U111CEO01",
      "U111OPS01",
    ]);

    expect(
      resolveCollaborationExecApprovalPolicy({
        cfg,
        request: {
          id: "req-1",
          request: {
            command: "rm -rf /tmp/demo",
            ask: "always",
            security: "full",
            agentId: "product",
            sessionKey: SESSION_KEY,
            turnSourceChannel: "slack",
            turnSourceTo: "channel:C123",
            turnSourceAccountId: "default",
          },
          createdAtMs: 0,
          expiresAtMs: 1_000,
        },
      }),
    ).toMatchObject({
      policyIds: ["high_risk_exec"],
      approverRoles: ["ceo", "ops"],
      approverSlackUserIds: ["U111CEO01", "U111OPS01"],
      delivery: ["dm", "origin_thread"],
      spaceId: "project_main",
      effectiveRole: "product",
    });
  });

  it("ignores requests that do not satisfy the collaboration policy", () => {
    writeStore({
      [SESSION_KEY]: {
        sessionId: "sess-1",
        updatedAt: Date.now(),
        collaboration: {
          mode: "enforced",
          managedSurface: true,
          spaceId: "project_main",
          ownerRole: "product",
          effectiveRole: "product",
          readableScopes: ["private"],
          publishableScopes: [],
        },
      },
    });

    expect(
      resolveCollaborationExecApprovalPolicy({
        cfg: buildConfig(),
        request: {
          id: "req-2",
          request: {
            command: "echo ok",
            ask: "off",
            security: "allowlist",
            agentId: "product",
            sessionKey: SESSION_KEY,
            turnSourceChannel: "slack",
            turnSourceAccountId: "default",
          },
          createdAtMs: 0,
          expiresAtMs: 1_000,
        },
      }),
    ).toBeNull();
  });
});
