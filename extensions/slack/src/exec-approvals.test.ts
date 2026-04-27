import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import { describe, expect, it } from "vitest";
import { clearSessionStoreCacheForTest } from "../../../src/config/sessions/store.js";
import {
  getSlackExecApprovalApprovers,
  hasSlackExecApprovalApprovers,
  isSlackExecApprovalApprover,
  isSlackExecApprovalAuthorizedSender,
  isSlackExecApprovalClientEnabled,
  isSlackExecApprovalTargetRecipient,
  normalizeSlackApproverId,
  resolveSlackExecApprovalTarget,
  shouldHandleSlackExecApprovalRequest,
  shouldSuppressLocalSlackExecApprovalPrompt,
} from "./exec-approvals.js";

const STORE_PATH = path.join(os.tmpdir(), "openclaw-slack-exec-approvals-collab-test.json");
const SESSION_KEY = "agent:product:slack:channel:c123:thread:1712345678.123456";

function buildConfig(
  execApprovals?: NonNullable<NonNullable<OpenClawConfig["channels"]>["slack"]>["execApprovals"],
  channelOverrides?: Partial<NonNullable<NonNullable<OpenClawConfig["channels"]>["slack"]>>,
): OpenClawConfig {
  return {
    channels: {
      slack: {
        botToken: "xoxb-test",
        appToken: "xapp-test",
        ...channelOverrides,
        execApprovals,
      },
    },
  } as OpenClawConfig;
}

function writeStore(store: Record<string, unknown>) {
  fs.writeFileSync(STORE_PATH, `${JSON.stringify(store, null, 2)}\n`, "utf8");
  clearSessionStoreCacheForTest();
}

function buildCollaborationConfig(): OpenClawConfig {
  return {
    session: { store: STORE_PATH },
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
          permissions: [],
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
  } as OpenClawConfig;
}

describe("slack exec approvals", () => {
  it("auto-enables when owner approvers resolve and disables only when forced off", () => {
    expect(isSlackExecApprovalClientEnabled({ cfg: buildConfig() })).toBe(false);
    expect(
      isSlackExecApprovalClientEnabled({
        cfg: buildConfig({ enabled: true }),
      }),
    ).toBe(false);
    expect(
      isSlackExecApprovalClientEnabled({
        cfg: buildConfig({ approvers: ["U123"] }),
      }),
    ).toBe(true);
    expect(
      isSlackExecApprovalClientEnabled({
        cfg: {
          ...buildConfig(),
          commands: { ownerAllowFrom: ["slack:U123OWNER"] },
        } as OpenClawConfig,
      }),
    ).toBe(true);
    expect(
      isSlackExecApprovalClientEnabled({
        cfg: buildConfig({ enabled: false, approvers: ["U123"] }),
      }),
    ).toBe(false);
  });

  it("prefers explicit approvers when configured", () => {
    const cfg = buildConfig(
      { approvers: ["U456"] },
      { allowFrom: ["U123"], defaultTo: "user:U789" },
    );

    expect(getSlackExecApprovalApprovers({ cfg })).toEqual(["U456"]);
    expect(isSlackExecApprovalApprover({ cfg, senderId: "U456" })).toBe(true);
    expect(isSlackExecApprovalApprover({ cfg, senderId: "U123" })).toBe(false);
  });

  it("does not infer approvers from allowFrom or DM default routes", () => {
    const cfg = buildConfig(
      { enabled: true },
      {
        allowFrom: ["slack:U123"],
        dm: { allowFrom: ["<@U456>"] },
        defaultTo: "user:U789",
      },
    );

    expect(getSlackExecApprovalApprovers({ cfg })).toEqual([]);
    expect(isSlackExecApprovalApprover({ cfg, senderId: "U789" })).toBe(false);
  });

  it("falls back to commands.ownerAllowFrom for exec approvers", () => {
    const cfg = {
      ...buildConfig({ enabled: true }),
      commands: { ownerAllowFrom: ["slack:U123", "user:U456", "<@U789>"] },
    } as OpenClawConfig;

    expect(getSlackExecApprovalApprovers({ cfg })).toEqual(["U123", "U456", "U789"]);
    expect(isSlackExecApprovalApprover({ cfg, senderId: "U456" })).toBe(true);
  });

  it("returns collaboration approvers only when scoped to a matching request", () => {
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

    const cfg = buildCollaborationConfig();
    const request = {
      id: "req-collab-1",
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
    };

    // Without request, the per-request approver set is unknowable, so we must
    // not authorize anyone — even though collaboration policy approvers exist.
    expect(getSlackExecApprovalApprovers({ cfg })).toEqual([]);
    // Auto-enable still detects collaboration approvers via the count probe.
    expect(hasSlackExecApprovalApprovers({ cfg })).toBe(true);
    expect(isSlackExecApprovalClientEnabled({ cfg })).toBe(true);
    // With request, approvers are policy-scoped.
    expect(getSlackExecApprovalApprovers({ cfg, request })).toEqual(["U111CEO01", "U111OPS01"]);
    expect(shouldHandleSlackExecApprovalRequest({ cfg, request })).toBe(true);
  });

  it("does not authorize a collaboration approver against a request governed by a different policy", () => {
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

    // Two policies. ceo-only policy approves high-risk exec; ops-only policy
    // approves a different (low-risk) request type. Build a request that
    // matches the ceo-only policy. A user who is approver only in the ops
    // policy must not be authorized.
    const cfg = buildCollaborationConfig();
    cfg.collaboration!.approvals = {
      policies: {
        ceo_only_high_risk: {
          when: ["tool:exec", "risk:high"],
          approverRoles: ["ceo"],
          delivery: ["dm"],
          agentFilter: ["product"],
          spaceFilter: ["project_main"],
        },
        ops_only_other: {
          when: ["tool:exec"],
          approverRoles: ["ops"],
          delivery: ["dm"],
          agentFilter: ["other-agent"],
          spaceFilter: ["project_main"],
        },
      },
    };

    const ceoRequest = {
      id: "req-policy-x",
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
    };

    // Request is governed only by ceo policy -> only U111CEO01 should authorize.
    expect(getSlackExecApprovalApprovers({ cfg, request: ceoRequest })).toEqual(["U111CEO01"]);

    // Without scoping a request, no one is authorized.
    expect(isSlackExecApprovalApprover({ cfg, senderId: "U111OPS01" })).toBe(false);
    expect(isSlackExecApprovalApprover({ cfg, senderId: "U111CEO01" })).toBe(false);
    expect(isSlackExecApprovalAuthorizedSender({ cfg, senderId: "U111OPS01" })).toBe(false);

    // U111OPS01 is approver in ops policy but NOT for ceoRequest. The
    // collaboration union must not bypass per-policy scoping.
    expect(getSlackExecApprovalApprovers({ cfg })).toEqual([]);
  });

  it("does not handle collaboration approvals when no policy matches the request", () => {
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
      shouldHandleSlackExecApprovalRequest({
        cfg: buildCollaborationConfig(),
        request: {
          id: "req-collab-2",
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
    ).toBe(false);
  });

  it("defaults target to dm", () => {
    expect(
      resolveSlackExecApprovalTarget({ cfg: buildConfig({ enabled: true, approvers: ["U1"] }) }),
    ).toBe("dm");
  });

  it("matches slack target recipients from generic approval forwarding targets", () => {
    const cfg = {
      channels: {
        slack: {
          botToken: "xoxb-test",
          appToken: "xapp-test",
        },
      },
      approvals: {
        exec: {
          enabled: true,
          mode: "targets",
          targets: [
            { channel: "slack", to: "user:U123TARGET" },
            { channel: "slack", to: "channel:C123" },
          ],
        },
      },
    } as OpenClawConfig;

    expect(isSlackExecApprovalTargetRecipient({ cfg, senderId: "U123TARGET" })).toBe(true);
    expect(isSlackExecApprovalTargetRecipient({ cfg, senderId: "U999OTHER" })).toBe(false);
    expect(isSlackExecApprovalAuthorizedSender({ cfg, senderId: "U123TARGET" })).toBe(true);
  });

  it("keeps the local Slack approval prompt path active", () => {
    const payload = {
      channelData: {
        execApproval: {
          approvalId: "req-1",
          approvalSlug: "req-1",
        },
      },
    };

    expect(
      shouldSuppressLocalSlackExecApprovalPrompt({
        cfg: buildConfig({ enabled: true, approvers: ["U123"] }),
        payload,
      }),
    ).toBe(true);

    expect(
      shouldSuppressLocalSlackExecApprovalPrompt({
        cfg: buildConfig(),
        payload,
      }),
    ).toBe(false);
  });

  it("normalizes wrapped sender ids", () => {
    expect(normalizeSlackApproverId("user:U123OWNER")).toBe("U123OWNER");
    expect(normalizeSlackApproverId("<@U123OWNER>")).toBe("U123OWNER");
  });

  it("applies agent and session filters to request handling", () => {
    const cfg = buildConfig({
      enabled: true,
      approvers: ["U123"],
      agentFilter: ["ops-agent"],
      sessionFilter: ["slack:direct:", "tail$"],
    });

    expect(
      shouldHandleSlackExecApprovalRequest({
        cfg,
        request: {
          id: "req-1",
          request: {
            command: "echo hi",
            agentId: "ops-agent",
            sessionKey: "agent:ops-agent:slack:direct:U123:tail",
          },
          createdAtMs: 0,
          expiresAtMs: 1000,
        },
      }),
    ).toBe(true);

    expect(
      shouldHandleSlackExecApprovalRequest({
        cfg,
        request: {
          id: "req-2",
          request: {
            command: "echo hi",
            agentId: "other-agent",
            sessionKey: "agent:other-agent:slack:direct:U123:tail",
          },
          createdAtMs: 0,
          expiresAtMs: 1000,
        },
      }),
    ).toBe(false);

    expect(
      shouldHandleSlackExecApprovalRequest({
        cfg,
        request: {
          id: "req-3",
          request: {
            command: "echo hi",
            agentId: "ops-agent",
            sessionKey: "agent:ops-agent:discord:channel:123",
          },
          createdAtMs: 0,
          expiresAtMs: 1000,
        },
      }),
    ).toBe(false);
  });

  it("rejects requests bound to another channel or Slack account", () => {
    const cfg = buildConfig({
      enabled: true,
      approvers: ["U123"],
    });

    expect(
      shouldHandleSlackExecApprovalRequest({
        cfg,
        accountId: "work",
        request: {
          id: "req-1",
          request: {
            command: "echo hi",
            turnSourceChannel: "discord",
            turnSourceAccountId: "work",
          },
          createdAtMs: 0,
          expiresAtMs: 1000,
        },
      }),
    ).toBe(false);

    expect(
      shouldHandleSlackExecApprovalRequest({
        cfg,
        accountId: "work",
        request: {
          id: "req-2",
          request: {
            command: "echo hi",
            turnSourceChannel: "slack",
            turnSourceAccountId: "other",
            sessionKey: "agent:ops-agent:missing",
          },
          createdAtMs: 0,
          expiresAtMs: 1000,
        },
      }),
    ).toBe(false);

    expect(
      shouldHandleSlackExecApprovalRequest({
        cfg,
        accountId: "work",
        request: {
          id: "req-3",
          request: {
            command: "echo hi",
            turnSourceChannel: "slack",
            turnSourceAccountId: "work",
            sessionKey: "agent:ops-agent:missing",
          },
          createdAtMs: 0,
          expiresAtMs: 1000,
        },
      }),
    ).toBe(true);
  });
});
