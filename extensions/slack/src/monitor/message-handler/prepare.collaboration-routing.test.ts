import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import { describe, expect, it } from "vitest";
import type { SlackMessageEvent } from "../../types.js";
import { prepareSlackMessage } from "./prepare.js";
import { createSlackTestAccount, createInboundSlackTestContext } from "./prepare.test-helpers.js";

const cfg: OpenClawConfig = {
  agents: {
    list: [{ id: "main" }, { id: "ops" }, { id: "product" }, { id: "ceo" }],
  },
  bindings: [
    {
      agentId: "main",
      match: {
        channel: "slack",
        accountId: "default",
      },
    },
  ],
  channels: {
    slack: {
      enabled: true,
      groupPolicy: "open",
    },
  },
  collaboration: {
    spaces: {
      projects: {
        "proj-a": {
          channelId: "CPROJ1234",
          defaultAgent: "product",
          defaultDmRecipient: "UPM12345",
        },
      },
      roles: {
        ops: { channelId: "COPS12345", agentId: "ops" },
        product: { channelId: "CPROD1234", agentId: "product" },
        ceo: { channelId: "CCEO12345", agentId: "ceo" },
      },
    },
    routing: {
      explicitMentionsOverride: true,
    },
  },
};

function createCtx() {
  const ctx = createInboundSlackTestContext({
    cfg,
    defaultRequireMention: false,
  });
  ctx.resolveUserName = async () => ({ name: "Alice" });
  ctx.resolveChannelName = async (channelId: string) => ({
    name: channelId,
    type: channelId.startsWith("D") ? "im" : "channel",
  });
  return ctx;
}

function createMessage(overrides: Partial<SlackMessageEvent>): SlackMessageEvent {
  return {
    channel: "CPROJ1234",
    channel_type: "channel",
    user: "U1",
    text: "hello",
    ts: "1.000",
    ...overrides,
  } as SlackMessageEvent;
}

describe("prepareSlackMessage collaboration routing", () => {
  it("routes project channels to the configured default agent", async () => {
    const prepared = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        channel: "CPROJ1234",
        text: "Can someone triage this?",
      }),
      opts: { source: "message" },
    });

    expect(prepared).toBeTruthy();
    expect(prepared!.route.agentId).toBe("product");
    expect(prepared!.route.matchedBy).toBe("collaboration.project.default");
  });

  it("routes role channels directly to the role agent", async () => {
    const prepared = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        channel: "COPS12345",
        text: "I am on it",
      }),
      opts: { source: "message" },
    });

    expect(prepared).toBeTruthy();
    expect(prepared!.route.agentId).toBe("ops");
    expect(prepared!.route.matchedBy).toBe("collaboration.role");
  });

  it("honors explicit @ops mentions in project channels for real Slack inbound messages", async () => {
    const prepared = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        channel: "CPROJ1234",
        text: "Need @ops to dig into this incident",
      }),
      opts: { source: "message" },
    });

    expect(prepared).toBeTruthy();
    expect(prepared!.route.agentId).toBe("ops");
    expect(prepared!.route.matchedBy).toBe("collaboration.project.mention");
  });

  it("keeps existing routing for non-collaboration channels", async () => {
    const prepared = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        channel: "CGENERAL1",
        text: "hello everyone",
      }),
      opts: { source: "message" },
    });

    expect(prepared).toBeTruthy();
    expect(prepared!.route.agentId).toBe("main");
    expect(prepared!.route.matchedBy).toBe("binding.account");
  });
});
