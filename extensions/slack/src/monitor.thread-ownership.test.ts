import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import { beforeEach, describe, expect, it } from "vitest";
import { prepareSlackMessage } from "./monitor/message-handler/prepare.js";
import {
  createSlackTestAccount,
  createInboundSlackTestContext,
} from "./monitor/message-handler/prepare.test-helpers.js";
import { clearSlackThreadOwnershipStoreForTest } from "./thread-ownership.store.js";
import type { SlackMessageEvent } from "./types.js";

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
      stickyThreadOwner: true,
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
    thread_ts: "0.999",
    ...overrides,
  } as SlackMessageEvent;
}

describe("Slack thread ownership routing", () => {
  beforeEach(() => {
    clearSlackThreadOwnershipStoreForTest();
  });

  it("sticks a thread to the first collaboration owner", async () => {
    const first = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        text: "Please triage this thread",
        thread_ts: "1710000000.000100",
      }),
      opts: { source: "message" },
    });

    expect(first?.route.agentId).toBe("product");

    const second = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        text: "following up without explicit role",
        thread_ts: "1710000000.000100",
      }),
      opts: { source: "message" },
    });

    expect(second?.route.agentId).toBe("product");
    expect(second?.route.matchedBy).toBe("collaboration.thread.owner");
  });

  it("switches thread owner on explicit role mention", async () => {
    await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        text: "Need a first pass here",
        thread_ts: "1710000000.000100",
      }),
      opts: { source: "message" },
    });

    const switched = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        text: "Need @ops on this thread now",
        thread_ts: "1710000000.000100",
      }),
      opts: { source: "message" },
    });

    expect(switched?.route.agentId).toBe("ops");
    expect(switched?.route.matchedBy).toBe("collaboration.project.mention");

    const after = await prepareSlackMessage({
      ctx: createCtx(),
      account: createSlackTestAccount(),
      message: createMessage({
        text: "follow-up after switch",
        thread_ts: "1710000000.000100",
      }),
      opts: { source: "message" },
    });

    expect(after?.route.agentId).toBe("ops");
    expect(after?.route.matchedBy).toBe("collaboration.thread.owner");
  });
});
