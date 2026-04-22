import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import {
  approveSyncRequest,
  rejectSyncRequest,
  resolveDmToSharedApprover,
} from "./sync-approvals.js";
import { createDmToProjectSyncRequest } from "./sync-requests.js";
import type { CollaborationPrivateSpace, CollaborationProjectSpace } from "./types.js";

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

describe("collaboration sync approvals", () => {
  it("routes approval to the space default agent by default", () => {
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UPM12345",
      content: "Share this",
    });

    expect(resolveDmToSharedApprover({ cfg: {}, request })).toEqual({
      kind: "agent",
      id: "product",
    });
  });

  it("routes approval to an explicit Slack user when configured", () => {
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UPM12345",
      content: "Share this",
    });

    const cfg: OpenClawConfig = {
      collaboration: {
        sync: {
          dmToShared: {
            approver: "UAPPROVER1",
          },
        },
      },
    };

    expect(resolveDmToSharedApprover({ cfg, request })).toEqual({
      kind: "slack-user",
      id: "UAPPROVER1",
    });
  });

  it("marks approved and rejected requests explicitly", () => {
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UPM12345",
      content: "Share this",
    });

    expect(approveSyncRequest({ request }).status).toBe("approved");
    expect(rejectSyncRequest({ request }).status).toBe("rejected");
  });
});
