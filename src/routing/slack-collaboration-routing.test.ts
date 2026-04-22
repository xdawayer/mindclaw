import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import { resolveSlackCollaborationRoute } from "./slack-collaboration-routing.js";

const cfg: OpenClawConfig = {
  agents: {
    list: [{ id: "main" }, { id: "ops" }, { id: "product" }, { id: "ceo" }],
  },
  collaboration: {
    spaces: {
      projects: {
        "proj-a": {
          channelId: "CPROJ1234",
          defaultAgent: "product",
          defaultDmRecipient: "UPM12345",
          roleDmRecipients: {
            ops: "UOPS1234",
            ceo: "UCEO1234",
          },
        },
      },
      roles: {
        ops: {
          channelId: "COPS12345",
          agentId: "ops",
        },
        product: {
          channelId: "CPROD1234",
          agentId: "product",
        },
        ceo: {
          channelId: "CCEO12345",
          agentId: "ceo",
        },
      },
    },
    routing: {
      explicitMentionsOverride: true,
    },
  },
};

describe("resolveSlackCollaborationRoute", () => {
  it("falls back to the configured project default agent", () => {
    expect(
      resolveSlackCollaborationRoute({
        cfg,
        peer: { kind: "channel", id: "CPROJ1234" },
        messageText: "Can someone pick this up?",
      }),
    ).toEqual({
      agentId: "product",
      matchedBy: "collaboration.project.default",
    });
  });

  it("routes role channels directly to the role agent", () => {
    expect(
      resolveSlackCollaborationRoute({
        cfg,
        peer: { kind: "channel", id: "COPS12345" },
        messageText: "Investigating now",
      }),
    ).toEqual({
      agentId: "ops",
      matchedBy: "collaboration.role",
    });
  });

  it("lets explicit role mentions override the project default", () => {
    expect(
      resolveSlackCollaborationRoute({
        cfg,
        peer: { kind: "channel", id: "CPROJ1234" },
        messageText: "Need help from @ceo on this approval",
      }),
    ).toEqual({
      agentId: "ceo",
      matchedBy: "collaboration.project.mention",
    });
  });

  it("returns null for non-collaboration channels", () => {
    expect(
      resolveSlackCollaborationRoute({
        cfg,
        peer: { kind: "channel", id: "CGENERAL1" },
        messageText: "hello",
      }),
    ).toBeNull();
  });
});
