import type { OpenClawConfig } from "../config/types.openclaw.js";
import { normalizeLowercaseStringOrEmpty } from "../shared/string-coerce.js";
import type {
  CollaborationPrivateSpace,
  CollaborationProjectSpace,
  CollaborationRoleSpace,
  CollaborationSpace,
} from "./types.js";

function normalizeSlackChannelId(value: string | undefined | null): string {
  return normalizeLowercaseStringOrEmpty(value);
}

function buildProjectScope(projectId: string): string {
  return `project:${projectId}`;
}

function buildRoleScope(roleId: string): string {
  return `role:${roleId}`;
}

function buildPrivateScope(slackUserId: string): string {
  return `private:${slackUserId}`;
}

export function resolvePrivateSpaceForSlackUser(
  slackUserId: string | undefined | null,
): CollaborationPrivateSpace | null {
  const normalizedUserId = slackUserId?.trim();
  if (!normalizedUserId) {
    return null;
  }
  return {
    kind: "private",
    userId: normalizedUserId,
    scope: buildPrivateScope(normalizedUserId),
  };
}

export function resolveProjectSpaceBySlackChannelId(
  cfg: OpenClawConfig | undefined,
  slackChannelId: string | undefined | null,
): CollaborationProjectSpace | null {
  const targetId = normalizeSlackChannelId(slackChannelId);
  if (!targetId) {
    return null;
  }

  const projects = cfg?.collaboration?.spaces?.projects ?? {};
  for (const [projectId, project] of Object.entries(projects)) {
    if (normalizeSlackChannelId(project.channelId) !== targetId) {
      continue;
    }
    return {
      kind: "project",
      id: projectId,
      channelId: project.channelId,
      defaultAgent: project.defaultAgent,
      defaultDmRecipient: project.defaultDmRecipient,
      roleDmRecipients: { ...project.roleDmRecipients },
      scope: buildProjectScope(projectId),
    };
  }

  return null;
}

export function resolveRoleSpaceBySlackChannelId(
  cfg: OpenClawConfig | undefined,
  slackChannelId: string | undefined | null,
): CollaborationRoleSpace | null {
  const targetId = normalizeSlackChannelId(slackChannelId);
  if (!targetId) {
    return null;
  }

  const roles = cfg?.collaboration?.spaces?.roles ?? {};
  for (const [roleId, role] of Object.entries(roles)) {
    if (normalizeSlackChannelId(role.channelId) !== targetId) {
      continue;
    }
    return {
      kind: "role",
      id: roleId,
      channelId: role.channelId,
      agentId: role.agentId,
      scope: buildRoleScope(roleId),
    };
  }

  return null;
}

export function resolveSlackSpaceByChannelId(
  cfg: OpenClawConfig | undefined,
  slackChannelId: string | undefined | null,
): CollaborationSpace | null {
  return (
    resolveProjectSpaceBySlackChannelId(cfg, slackChannelId) ??
    resolveRoleSpaceBySlackChannelId(cfg, slackChannelId)
  );
}
