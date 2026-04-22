import { resolveProjectDmRecipient } from "../collaboration/slack-targets.js";
import { resolveProjectSpaceBySlackChannelId } from "../collaboration/spaces.js";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import { parseAgentSessionKey } from "../routing/session-key.js";
import { normalizeOptionalString } from "../shared/string-coerce.js";
import type { CronCollaborationTarget, CronMessageChannel } from "./types.js";

export type CronCollaborationAnnounceTarget = {
  channel: CronMessageChannel;
  to: string;
};

function resolveCronCollaborationProject(params: {
  cfg: OpenClawConfig | undefined;
  collaborationTarget: CronCollaborationTarget | undefined;
}) {
  const projectChannelId = params.collaborationTarget?.projectChannelId;
  if (!projectChannelId) {
    return null;
  }
  return resolveProjectSpaceBySlackChannelId(params.cfg, projectChannelId);
}

export function resolveCronCollaborationTarget(params: {
  cfg: OpenClawConfig | undefined;
  agentId?: string;
  sessionKey?: string;
}): CronCollaborationTarget | null {
  const parsed = parseAgentSessionKey(params.sessionKey);
  const rest = parsed?.rest?.trim();
  if (!rest) {
    return null;
  }

  const parts = rest.split(":");
  if (parts[0] !== "slack" || (parts[1] !== "channel" && parts[1] !== "group")) {
    return null;
  }

  const projectChannelId = parts[2]?.trim();
  if (!projectChannelId) {
    return null;
  }

  let roleId: string | undefined;
  const roles = params.cfg?.collaboration?.spaces?.roles ?? {};
  for (const [candidateRoleId, role] of Object.entries(roles)) {
    if (role.agentId === params.agentId) {
      roleId = candidateRoleId;
      break;
    }
  }

  return {
    projectChannelId,
    ...(roleId ? { roleId } : {}),
  };
}

function toSlackUserTarget(userId: string): string | null {
  const normalized = normalizeOptionalString(userId);
  if (!normalized) {
    return null;
  }
  return `user:${normalized.replace(/^(?:slack:|user:)/i, "")}`;
}

function toSlackChannelTarget(channelId: string): string | null {
  const normalized = normalizeOptionalString(channelId);
  if (!normalized) {
    return null;
  }
  return `channel:${normalized.replace(/^(?:slack:|channel:)/i, "")}`;
}

export function resolveCronCollaborationDeliveryTarget(params: {
  cfg: OpenClawConfig | undefined;
  collaborationTarget: CronCollaborationTarget | undefined;
}): CronCollaborationAnnounceTarget | null {
  const project = resolveCronCollaborationProject(params);
  if (!project) {
    return null;
  }

  const to = toSlackUserTarget(
    resolveProjectDmRecipient({
      project,
      roleId: params.collaborationTarget?.roleId,
    }),
  );
  if (!to) {
    return null;
  }

  return {
    channel: "slack",
    to,
  };
}

export function resolveCronCollaborationFailureTarget(params: {
  cfg: OpenClawConfig | undefined;
  collaborationTarget: CronCollaborationTarget | undefined;
}): CronCollaborationAnnounceTarget | null {
  const project = resolveCronCollaborationProject(params);
  if (!project) {
    return null;
  }

  const to = toSlackChannelTarget(project.channelId);
  if (!to) {
    return null;
  }

  return {
    channel: "slack",
    to,
  };
}
