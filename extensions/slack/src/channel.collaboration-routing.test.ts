import { describe, expect, it } from "vitest";
import { resolveSlackInboundRoute } from "./channel.js";
import type { OpenClawConfig } from "./runtime-api.js";

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

describe("resolveSlackInboundRoute", () => {
  it("uses the project default agent for collaboration channels", () => {
    const route = resolveSlackInboundRoute({
      cfg,
      accountId: "default",
      teamId: "T1",
      peer: { kind: "channel", id: "CPROJ1234" },
      messageText: "What should we ship next?",
    });

    expect(route.agentId).toBe("product");
    expect(route.matchedBy).toBe("collaboration.project.default");
  });

  it("passes explicit role mentions through to collaboration-aware routing", () => {
    const route = resolveSlackInboundRoute({
      cfg,
      accountId: "default",
      teamId: "T1",
      peer: { kind: "channel", id: "CPROJ1234" },
      messageText: "Need @ops to look at this deploy",
    });

    expect(route.agentId).toBe("ops");
    expect(route.matchedBy).toBe("collaboration.project.mention");
  });

  it("preserves existing non-collaboration Slack routing behavior", () => {
    const route = resolveSlackInboundRoute({
      cfg,
      accountId: "default",
      teamId: "T1",
      peer: { kind: "channel", id: "CGENERAL1" },
      messageText: "hello team",
    });

    expect(route.agentId).toBe("main");
    expect(route.matchedBy).toBe("binding.account");
  });

  it("lets an explicit peer binding override collaboration routing for the same Slack channel", () => {
    const route = resolveSlackInboundRoute({
      cfg: {
        ...cfg,
        bindings: [
          {
            agentId: "main",
            match: {
              channel: "slack",
              accountId: "default",
              peer: { kind: "channel", id: "CPROJ1234" },
            },
          },
        ],
      },
      accountId: "default",
      teamId: "T1",
      peer: { kind: "channel", id: "CPROJ1234" },
      messageText: "Need @ops to look at this deploy",
    });

    expect(route.agentId).toBe("main");
    expect(route.matchedBy).toBe("binding.peer");
  });
});
