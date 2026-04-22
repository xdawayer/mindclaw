import { describe, expect, it } from "vitest";
import { OpenClawSchema } from "./zod-schema.js";

describe("collaboration config schema", () => {
  it("accepts collaboration identities, spaces, routing, and sync policy", () => {
    const res = OpenClawSchema.safeParse({
      agents: {
        list: [{ id: "ops" }, { id: "product" }, { id: "ceo" }],
      },
      collaboration: {
        identities: {
          users: {
            UPM12345: { roles: ["product"] },
            UOPS1234: { roles: ["ops"], slackGroups: ["SRE"] },
            UCEO1234: { roles: ["ceo"] },
          },
        },
        spaces: {
          projects: {
            "proj-a": {
              channelId: "C123PROJECT",
              defaultAgent: "product",
              defaultDmRecipient: "UPM12345",
              roleDmRecipients: {
                ops: "UOPS1234",
                ceo: "UCEO1234",
              },
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
          autoClassifyWhenUnspecified: true,
          stickyThreadOwner: true,
          internalConsultationChangesOwner: false,
        },
        sync: {
          dmToShared: {
            mode: "request-approval",
            approver: "space-default-agent",
          },
        },
      },
    });

    expect(res.success).toBe(true);
    if (!res.success) {
      throw new Error("expected collaboration config to parse");
    }
    expect(res.data.collaboration?.spaces?.projects?.["proj-a"]?.defaultAgent).toBe("product");
    expect(res.data.collaboration?.spaces?.roles?.ops?.agentId).toBe("ops");
  });

  it("accepts a Slack user approver override for DM-to-shared sync", () => {
    const res = OpenClawSchema.safeParse({
      agents: {
        list: [{ id: "product" }],
      },
      collaboration: {
        spaces: {
          projects: {
            "proj-a": {
              channelId: "C123PROJECT",
              defaultAgent: "product",
              defaultDmRecipient: "UPM12345",
            },
          },
        },
        sync: {
          dmToShared: {
            mode: "request-approval",
            approver: "UAPPROVER1",
          },
        },
      },
    });

    expect(res.success).toBe(true);
  });

  it("rejects project defaultAgent values that do not exist in agents.list", () => {
    const res = OpenClawSchema.safeParse({
      agents: {
        list: [{ id: "product" }],
      },
      collaboration: {
        spaces: {
          projects: {
            "proj-a": {
              channelId: "C123PROJECT",
              defaultAgent: "ghost",
              defaultDmRecipient: "U_PM_1",
            },
          },
        },
      },
    });

    expect(res.success).toBe(false);
  });

  it("rejects malformed Slack user and channel ids", () => {
    const res = OpenClawSchema.safeParse({
      agents: {
        list: [{ id: "product" }],
      },
      collaboration: {
        identities: {
          users: {
            "not-a-slack-id": { roles: ["product"] },
          },
        },
        spaces: {
          projects: {
            "proj-a": {
              channelId: "project-channel",
              defaultAgent: "product",
              defaultDmRecipient: "pm-user",
            },
          },
        },
      },
    });

    expect(res.success).toBe(false);
  });
});
