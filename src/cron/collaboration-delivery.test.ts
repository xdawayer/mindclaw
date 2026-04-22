import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import {
  resolveCronCollaborationDeliveryTarget,
  resolveCronCollaborationFailureTarget,
} from "./collaboration-delivery.js";

const cfg: OpenClawConfig = {
  collaboration: {
    spaces: {
      projects: {
        alpha: {
          channelId: "CPROJ1234",
          defaultAgent: "product",
          defaultDmRecipient: "UPM12345",
          roleDmRecipients: {
            ops: "UOPS1234",
          },
        },
      },
    },
  },
};

describe("cron collaboration delivery defaults", () => {
  it("defaults success-like delivery to the project DM recipient", () => {
    expect(
      resolveCronCollaborationDeliveryTarget({
        cfg,
        collaborationTarget: {
          projectChannelId: "CPROJ1234",
        },
      }),
    ).toEqual({
      channel: "slack",
      to: "user:UPM12345",
    });
  });

  it("prefers role-specific DM overrides over the project default recipient", () => {
    expect(
      resolveCronCollaborationDeliveryTarget({
        cfg,
        collaborationTarget: {
          projectChannelId: "CPROJ1234",
          roleId: "ops",
        },
      }),
    ).toEqual({
      channel: "slack",
      to: "user:UOPS1234",
    });
  });

  it("defaults failure-like delivery to the project channel", () => {
    expect(
      resolveCronCollaborationFailureTarget({
        cfg,
        collaborationTarget: {
          projectChannelId: "CPROJ1234",
          roleId: "ops",
        },
      }),
    ).toEqual({
      channel: "slack",
      to: "channel:CPROJ1234",
    });
  });

  it("prefixes private-channel targets with channel: for Slack group conversations", () => {
    const privateChannelConfig: OpenClawConfig = {
      collaboration: {
        spaces: {
          projects: {
            beta: {
              channelId: "GPROJ5678",
              defaultAgent: "ops",
              defaultDmRecipient: "UOPS9999",
            },
          },
        },
      },
    };

    expect(
      resolveCronCollaborationFailureTarget({
        cfg: privateChannelConfig,
        collaborationTarget: {
          projectChannelId: "GPROJ5678",
        },
      }),
    ).toEqual({
      channel: "slack",
      to: "channel:GPROJ5678",
    });
  });

  it("returns null when the collaboration target does not resolve to a configured project", () => {
    expect(
      resolveCronCollaborationDeliveryTarget({
        cfg,
        collaborationTarget: {
          projectChannelId: "CUNKNOWN",
        },
      }),
    ).toBeNull();
    expect(
      resolveCronCollaborationFailureTarget({
        cfg,
        collaborationTarget: {
          projectChannelId: "CUNKNOWN",
        },
      }),
    ).toBeNull();
  });
});
