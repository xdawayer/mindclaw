import type { CollaborationUserIdentityConfig } from "../config/types.collaboration.js";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import { normalizeLowercaseStringOrEmpty } from "../shared/string-coerce.js";

function normalizeSlackUserId(value: string | undefined | null): string {
  return normalizeLowercaseStringOrEmpty(value);
}

export function resolveCollaborationUserIdentity(
  cfg: OpenClawConfig | undefined,
  slackUserId: string | undefined | null,
): CollaborationUserIdentityConfig | null {
  const targetId = normalizeSlackUserId(slackUserId);
  if (!targetId) {
    return null;
  }

  const users = cfg?.collaboration?.identities?.users ?? {};
  for (const [userId, identity] of Object.entries(users)) {
    if (normalizeSlackUserId(userId) === targetId) {
      return identity;
    }
  }

  return null;
}

export function resolveCollaborationUserRoles(
  cfg: OpenClawConfig | undefined,
  slackUserId: string | undefined | null,
): string[] {
  const identity = resolveCollaborationUserIdentity(cfg, slackUserId);
  if (!identity?.roles) {
    return [];
  }

  const seen = new Set<string>();
  const roles: string[] = [];
  for (const rawRole of identity.roles) {
    const role = rawRole.trim();
    if (!role || seen.has(role)) {
      continue;
    }
    seen.add(role);
    roles.push(role);
  }
  return roles;
}
