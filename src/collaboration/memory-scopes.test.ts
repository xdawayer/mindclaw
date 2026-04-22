import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import { resolveCollaborationMemoryScope } from "./memory-scopes.js";

const cfg: OpenClawConfig = {
  collaboration: {
    spaces: {
      projects: {
        "proj-a": {
          channelId: "CPROJ1234",
          defaultAgent: "product",
          defaultDmRecipient: "UPM12345",
          roleDmRecipients: {},
        },
      },
      roles: {
        ops: {
          channelId: "COPS12345",
          agentId: "ops",
        },
      },
    },
  },
};

describe("collaboration memory scopes", () => {
  it("maps direct messages to a private user scope", () => {
    expect(
      resolveCollaborationMemoryScope({
        cfg,
        slackChannelType: "direct",
        slackUserId: "UPM12345",
      }),
    ).toEqual({
      kind: "private",
      scope: "private:UPM12345",
      slackUserId: "UPM12345",
    });
  });

  it("maps project channels to a project scope", () => {
    expect(
      resolveCollaborationMemoryScope({
        cfg,
        slackChannelType: "channel",
        slackChannelId: "CPROJ1234",
      }),
    ).toEqual({
      kind: "project",
      scope: "project:proj-a",
      projectId: "proj-a",
      slackChannelId: "CPROJ1234",
    });
  });

  it("maps role channels to a role scope", () => {
    expect(
      resolveCollaborationMemoryScope({
        cfg,
        slackChannelType: "channel",
        slackChannelId: "COPS12345",
      }),
    ).toEqual({
      kind: "role",
      scope: "role:ops",
      roleId: "ops",
      slackChannelId: "COPS12345",
    });
  });

  it("never auto-promotes a DM into project or role memory", () => {
    expect(
      resolveCollaborationMemoryScope({
        cfg,
        slackChannelType: "direct",
        slackChannelId: "CPROJ1234",
        slackUserId: "UPM12345",
      }),
    ).toEqual({
      kind: "private",
      scope: "private:UPM12345",
      slackUserId: "UPM12345",
    });
  });
});
