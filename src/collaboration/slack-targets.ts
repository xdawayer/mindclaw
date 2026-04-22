import type { OpenClawConfig } from "../config/types.openclaw.js";
import { normalizeOptionalString } from "../shared/string-coerce.js";
import { resolveProjectSpaceBySlackChannelId } from "./spaces.js";
import type { CollaborationProjectSpace } from "./types.js";

export function resolveProjectDmRecipient(params: {
  project: CollaborationProjectSpace;
  roleId?: string | null;
}): string {
  const normalizedRoleId = normalizeOptionalString(params.roleId);
  if (normalizedRoleId) {
    const override = normalizeOptionalString(params.project.roleDmRecipients[normalizedRoleId]);
    if (override) {
      return override;
    }
  }
  return params.project.defaultDmRecipient;
}

export function resolveProjectDmRecipientBySlackChannel(params: {
  cfg: OpenClawConfig | undefined;
  slackChannelId: string | undefined | null;
  roleId?: string | null;
}): string | null {
  const project = resolveProjectSpaceBySlackChannelId(params.cfg, params.slackChannelId);
  if (!project) {
    return null;
  }
  return resolveProjectDmRecipient({
    project,
    roleId: params.roleId,
  });
}
