import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import { resolveCollaborationUserIdentity, resolveCollaborationUserRoles } from "./identities.js";

const cfg: OpenClawConfig = {
  collaboration: {
    identities: {
      users: {
        UPM12345: { roles: ["product", "product"] },
        UOPS1234: { roles: ["ops"], slackGroups: ["SRE"] },
      },
    },
  },
};

describe("collaboration identities", () => {
  it("resolves a Slack user to its identity record", () => {
    expect(resolveCollaborationUserIdentity(cfg, "UPM12345")).toEqual({
      roles: ["product", "product"],
    });
  });

  it("matches Slack user ids case-insensitively", () => {
    expect(resolveCollaborationUserIdentity(cfg, "upm12345")).toEqual({
      roles: ["product", "product"],
    });
  });

  it("returns distinct trimmed roles in stable order", () => {
    expect(resolveCollaborationUserRoles(cfg, "UPM12345")).toEqual(["product"]);
  });

  it("returns an empty role list for unknown users", () => {
    expect(resolveCollaborationUserRoles(cfg, "UUNKNOWN1")).toEqual([]);
  });
});
