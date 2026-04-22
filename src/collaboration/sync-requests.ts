import type {
  CollaborationPrivateSpace,
  CollaborationProjectSpace,
  CollaborationRoleSpace,
} from "./types.js";

export type CollaborationSharedTarget =
  | {
      kind: "project";
      id: string;
      scope: string;
      channelId: string;
    }
  | {
      kind: "role";
      id: string;
      scope: string;
      channelId: string;
    };

export type CollaborationSyncRequestStatus = "pending" | "approved" | "rejected";

export type CollaborationSyncRequest = {
  id: string;
  direction: "dm_to_shared";
  requesterSlackUserId: string;
  source: CollaborationPrivateSpace;
  target: CollaborationSharedTarget;
  content: string;
  createdAtMs: number;
  status: CollaborationSyncRequestStatus;
  approvalRule: "space-default-agent" | "explicit-user";
  approverHint: string;
};

function randomSyncId(): string {
  return `sync_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function toProjectTarget(project: CollaborationProjectSpace): CollaborationSharedTarget {
  return {
    kind: "project",
    id: project.id,
    scope: project.scope,
    channelId: project.channelId,
  };
}

function toRoleTarget(role: CollaborationRoleSpace): CollaborationSharedTarget {
  return {
    kind: "role",
    id: role.id,
    scope: role.scope,
    channelId: role.channelId,
  };
}

export function createDmToProjectSyncRequest(params: {
  source: CollaborationPrivateSpace;
  project: CollaborationProjectSpace;
  requesterSlackUserId: string;
  content: string;
}): CollaborationSyncRequest {
  return {
    id: randomSyncId(),
    direction: "dm_to_shared",
    requesterSlackUserId: params.requesterSlackUserId,
    source: params.source,
    target: toProjectTarget(params.project),
    content: params.content,
    createdAtMs: Date.now(),
    status: "pending",
    approvalRule: "space-default-agent",
    approverHint: params.project.defaultAgent,
  };
}

export function createDmToRoleSyncRequest(params: {
  source: CollaborationPrivateSpace;
  role: CollaborationRoleSpace;
  requesterSlackUserId: string;
  content: string;
}): CollaborationSyncRequest {
  return {
    id: randomSyncId(),
    direction: "dm_to_shared",
    requesterSlackUserId: params.requesterSlackUserId,
    source: params.source,
    target: toRoleTarget(params.role),
    content: params.content,
    createdAtMs: Date.now(),
    status: "pending",
    approvalRule: "space-default-agent",
    approverHint: params.role.id,
  };
}

export function createApprovedSharedSyncPayload(params: { request: CollaborationSyncRequest }): {
  scope: string;
  content: string;
  sourceSlackUserId: string;
  sourceScope: string;
  targetKind: CollaborationSharedTarget["kind"];
  targetId: string;
} {
  return {
    scope: params.request.target.scope,
    content: params.request.content,
    sourceSlackUserId: params.request.requesterSlackUserId,
    sourceScope: params.request.source.scope,
    targetKind: params.request.target.kind,
    targetId: params.request.target.id,
  };
}
