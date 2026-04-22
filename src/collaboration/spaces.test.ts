import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import {
  resolvePrivateSpaceForSlackUser,
  resolveProjectSpaceBySlackChannelId,
  resolveRoleSpaceBySlackChannelId,
  resolveSlackSpaceByChannelId,
} from "./spaces.js";

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
          },
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

describe("collaboration spaces", () => {
  it("resolves a project space from a Slack channel id", () => {
    expect(resolveProjectSpaceBySlackChannelId(cfg, "CPROJ1234")).toEqual({
      kind: "project",
      id: "proj-a",
      channelId: "CPROJ1234",
      defaultAgent: "product",
      defaultDmRecipient: "UPM12345",
      roleDmRecipients: { ops: "UOPS1234" },
      scope: "project:proj-a",
    });
  });

  it("resolves a role space from a Slack channel id", () => {
    expect(resolveRoleSpaceBySlackChannelId(cfg, "COPS12345")).toEqual({
      kind: "role",
      id: "ops",
      channelId: "COPS12345",
      agentId: "ops",
      scope: "role:ops",
    });
  });

  it("keeps project and role descriptors separated", () => {
    const project = resolveSlackSpaceByChannelId(cfg, "CPROJ1234");
    const role = resolveSlackSpaceByChannelId(cfg, "COPS12345");

    expect(project?.kind).toBe("project");
    expect(project && "agentId" in project).toBe(false);
    expect(role?.kind).toBe("role");
    expect(role && "defaultAgent" in role).toBe(false);
  });

  it("creates a private DM space from a Slack user id", () => {
    expect(resolvePrivateSpaceForSlackUser("UPM12345")).toEqual({
      kind: "private",
      userId: "UPM12345",
      scope: "private:UPM12345",
    });
  });
});
