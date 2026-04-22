import { resolveProjectDmRecipient } from "../collaboration/slack-targets.js";
import { resolveProjectSpaceBySlackChannelId } from "../collaboration/spaces.js";
import type { OpenClawConfig } from "../config/types.openclaw.js";
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
