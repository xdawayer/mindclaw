import { describe, expect, it } from "vitest";
import {
  createApprovedSharedSyncPayload,
  createDmToProjectSyncRequest,
  createDmToRoleSyncRequest,
} from "./sync-requests.js";
import type {
  CollaborationPrivateSpace,
  CollaborationProjectSpace,
  CollaborationRoleSpace,
} from "./types.js";

const privateSpace: CollaborationPrivateSpace = {
  kind: "private",
  userId: "UPM12345",
  scope: "private:UPM12345",
};

const projectSpace: CollaborationProjectSpace = {
  kind: "project",
  id: "proj-a",
  channelId: "CPROJ1234",
  defaultAgent: "product",
  defaultDmRecipient: "UPM12345",
  roleDmRecipients: { ops: "UOPS1234" },
  scope: "project:proj-a",
};

const roleSpace: CollaborationRoleSpace = {
  kind: "role",
  id: "ops",
  channelId: "COPS12345",
  agentId: "ops",
  scope: "role:ops",
};

describe("collaboration sync requests", () => {
  it("creates pending DM-to-project sync requests", () => {
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UPM12345",
      content: "Ship the roadmap note",
    });

    expect(request.status).toBe("pending");
    expect(request.target).toMatchObject({
      kind: "project",
      id: "proj-a",
      scope: "project:proj-a",
    });
  });

  it("creates pending DM-to-role sync requests", () => {
    const request = createDmToRoleSyncRequest({
      source: privateSpace,
      role: roleSpace,
      requesterSlackUserId: "UPM12345",
      content: "Need ops input",
    });

    expect(request.status).toBe("pending");
    expect(request.target).toMatchObject({
      kind: "role",
      id: "ops",
      scope: "role:ops",
    });
  });

  it("builds a shared sync payload only from selected request content", () => {
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UPM12345",
      content: "Only this excerpt should enter shared memory",
    });

    expect(createApprovedSharedSyncPayload({ request })).toEqual({
      scope: "project:proj-a",
      content: "Only this excerpt should enter shared memory",
      sourceSlackUserId: "UPM12345",
      sourceScope: "private:UPM12345",
      targetKind: "project",
      targetId: "proj-a",
    });
  });
});
