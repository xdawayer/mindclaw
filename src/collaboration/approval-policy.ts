import type { OpenClawConfig } from "../config/types.openclaw.js";
import { resolvePersistedApprovalRequestSessionEntry } from "../infra/approval-request-account-binding.js";
import type { ExecApprovalRequest } from "../infra/exec-approvals.js";
import { parseAgentSessionKey } from "../routing/session-key.js";
import {
  normalizeOptionalLowercaseString,
  normalizeOptionalString,
} from "../shared/string-coerce.js";

export type CollaborationExecApprovalResolution = {
  policyIds: string[];
  approverRoles: string[];
  approverSlackUserIds: string[];
  delivery: Array<"dm" | "origin_thread">;
  spaceId?: string;
  ownerRole?: string;
  effectiveRole?: string;
};

function sortedEntries<T>(record: Record<string, T>): Array<[string, T]> {
  return Object.entries(record).sort(([left], [right]) => left.localeCompare(right));
}

function resolveManagedCollaborationMeta(params: {
  cfg: OpenClawConfig;
  request: ExecApprovalRequest;
}) {
  const persisted = resolvePersistedApprovalRequestSessionEntry(params);
  const collaboration = persisted?.entry.collaboration;
  if (
    !collaboration ||
    collaboration.mode !== "enforced" ||
    collaboration.managedSurface !== true
  ) {
    return null;
  }
  return collaboration;
}

export function hasManagedCollaborationApprovalContext(params: {
  cfg: OpenClawConfig;
  request: ExecApprovalRequest;
}): boolean {
  return resolveManagedCollaborationMeta(params) !== null;
}

function resolveRequestAgentId(request: ExecApprovalRequest): string | undefined {
  return (
    normalizeOptionalString(request.request.agentId) ??
    parseAgentSessionKey(request.request.sessionKey)?.agentId ??
    undefined
  );
}

function isHighRiskExecRequest(request: ExecApprovalRequest): boolean {
  const ask = normalizeOptionalLowercaseString(request.request.ask);
  const security = normalizeOptionalLowercaseString(request.request.security);
  return ask === "always" || security === "full";
}

function matchesWhenClause(token: string, request: ExecApprovalRequest): boolean {
  switch (token) {
    case "tool:exec":
      return true;
    case "risk:high":
      return isHighRiskExecRequest(request);
    default:
      return false;
  }
}

function matchesPolicy(params: {
  policy: NonNullable<
    NonNullable<OpenClawConfig["collaboration"]>["approvals"]
  >["policies"][string];
  request: ExecApprovalRequest;
  spaceId?: string;
}) {
  if (params.policy.when.some((token) => !matchesWhenClause(token, params.request))) {
    return false;
  }
  const agentId = resolveRequestAgentId(params.request);
  if (
    params.policy.agentFilter?.length &&
    (!agentId || !params.policy.agentFilter.includes(agentId))
  ) {
    return false;
  }
  if (
    params.policy.spaceFilter?.length &&
    (!params.spaceId || !params.policy.spaceFilter.includes(params.spaceId))
  ) {
    return false;
  }
  return true;
}

function resolveSlackUsersForRoles(params: { cfg: OpenClawConfig; roles: string[] }): string[] {
  const collaboration = params.cfg.collaboration;
  if (!collaboration || params.roles.length === 0) {
    return [];
  }
  const wantedRoles = new Set(params.roles);
  const slackUserIds: string[] = [];
  for (const [slackUserId, binding] of sortedEntries(collaboration.identities.users)) {
    if (binding.roles.some((roleId) => wantedRoles.has(roleId))) {
      slackUserIds.push(slackUserId);
    }
  }
  return slackUserIds;
}

function pushUnique<T>(target: T[], values: readonly T[]) {
  for (const value of values) {
    if (!target.includes(value)) {
      target.push(value);
    }
  }
}

export function resolveCollaborationApprovalApproverUserIds(params: {
  cfg: OpenClawConfig;
}): string[] {
  const collaboration = params.cfg.collaboration;
  if (!collaboration || collaboration.mode !== "enforced") {
    return [];
  }
  const approverRoles: string[] = [];
  for (const [, policy] of sortedEntries(collaboration.approvals?.policies ?? {})) {
    pushUnique(approverRoles, policy.approverRoles);
  }
  return resolveSlackUsersForRoles({
    cfg: params.cfg,
    roles: approverRoles,
  });
}

export function resolveCollaborationExecApprovalPolicy(params: {
  cfg: OpenClawConfig;
  request: ExecApprovalRequest;
}): CollaborationExecApprovalResolution | null {
  const collaboration = params.cfg.collaboration;
  if (!collaboration || collaboration.mode !== "enforced") {
    return null;
  }
  const managed = resolveManagedCollaborationMeta(params);
  if (!managed) {
    return null;
  }

  const policyIds: string[] = [];
  const approverRoles: string[] = [];
  const delivery: Array<"dm" | "origin_thread"> = [];

  for (const [policyId, policy] of sortedEntries(collaboration.approvals?.policies ?? {})) {
    if (!matchesPolicy({ policy, request: params.request, spaceId: managed.spaceId })) {
      continue;
    }
    policyIds.push(policyId);
    pushUnique(approverRoles, policy.approverRoles);
    pushUnique(delivery, policy.delivery);
  }

  if (policyIds.length === 0) {
    return null;
  }

  return {
    policyIds,
    approverRoles,
    approverSlackUserIds: resolveSlackUsersForRoles({
      cfg: params.cfg,
      roles: approverRoles,
    }),
    delivery,
    ...(managed.spaceId ? { spaceId: managed.spaceId } : {}),
    ...(managed.ownerRole ? { ownerRole: managed.ownerRole } : {}),
    ...(managed.effectiveRole ? { effectiveRole: managed.effectiveRole } : {}),
  };
}
