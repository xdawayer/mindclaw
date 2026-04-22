import type { OpenClawConfig } from "../config/types.openclaw.js";
import type { CollaborationSyncRequest } from "./sync-requests.js";

export type CollaborationSyncApprover =
  | {
      kind: "agent";
      id: string;
    }
  | {
      kind: "slack-user";
      id: string;
    };

export function resolveDmToSharedApprover(params: {
  cfg: OpenClawConfig | undefined;
  request: CollaborationSyncRequest;
}): CollaborationSyncApprover | null {
  const policy = params.cfg?.collaboration?.sync?.dmToShared;
  const configuredApprover = policy?.approver?.trim();

  if (!configuredApprover || configuredApprover === "space-default-agent") {
    return {
      kind: "agent",
      id: params.request.approverHint,
    };
  }

  return {
    kind: "slack-user",
    id: configuredApprover,
  };
}

export function approveSyncRequest(params: {
  request: CollaborationSyncRequest;
}): CollaborationSyncRequest {
  return {
    ...params.request,
    status: "approved",
  };
}

export function rejectSyncRequest(params: {
  request: CollaborationSyncRequest;
}): CollaborationSyncRequest {
  return {
    ...params.request,
    status: "rejected",
  };
}
