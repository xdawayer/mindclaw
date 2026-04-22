import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import {
  resolveProjectDmRecipient,
  resolveProjectDmRecipientBySlackChannel,
} from "./slack-targets.js";
import { resolveProjectSpaceBySlackChannelId } from "./spaces.js";

const cfg: OpenClawConfig = {
  collaboration: {
    spaces: {
      projects: {
        "proj-a": {
          channelId: "CPROJ1234",
          defaultAgent: "product",
          defaultDmRecipient: "UPM12345",
          roleDmRecipients: {
            ops: "UOPS1234",
            ceo: "UCEO12345",
          },
        },
      },
    },
  },
};

describe("collaboration Slack targets", () => {
  it("uses the per-role DM override when one is configured", () => {
    const project = resolveProjectSpaceBySlackChannelId(cfg, "CPROJ1234");
    if (!project) {
      throw new Error("expected project");
    }

    expect(resolveProjectDmRecipient({ project, roleId: "ops" })).toBe("UOPS1234");
  });

  it("falls back to the project default DM recipient when no role override exists", () => {
    const project = resolveProjectSpaceBySlackChannelId(cfg, "CPROJ1234");
    if (!project) {
      throw new Error("expected project");
    }

    expect(resolveProjectDmRecipient({ project, roleId: "product" })).toBe("UPM12345");
  });

  it("resolves project DM recipients directly from Slack channel id", () => {
    expect(
      resolveProjectDmRecipientBySlackChannel({
        cfg,
        slackChannelId: "CPROJ1234",
        roleId: "ceo",
      }),
    ).toBe("UCEO12345");
  });

  it("returns null when no project space matches the Slack channel", () => {
    expect(
      resolveProjectDmRecipientBySlackChannel({
        cfg,
        slackChannelId: "CUNKNOWN1",
        roleId: "ops",
      }),
    ).toBeNull();
  });
});
