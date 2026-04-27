import type { OpenClawConfig } from "../config/types.openclaw.js";

function normalizeId(value: string | undefined): string {
  return value?.trim().toLowerCase() ?? "";
}

export function resolveCollaborationMemoryIndexPaths(params: {
  cfg: OpenClawConfig;
  agentId: string;
}): string[] {
  const collaboration = params.cfg.collaboration;
  if (!collaboration) {
    return [];
  }

  const normalizedAgentId = normalizeId(params.agentId);
  if (!normalizedAgentId) {
    return [];
  }

  const roleIds = new Set<string>();
  for (const [roleId, role] of Object.entries(collaboration.roles ?? {})) {
    if (normalizeId(role.defaultAgentId) === normalizedAgentId) {
      roleIds.add(normalizeId(roleId));
    }
  }
  for (const bot of Object.values(collaboration.bots ?? {})) {
    const botRole = normalizeId(bot.role);
    if (normalizeId(bot.agentId) === normalizedAgentId && botRole) {
      roleIds.add(botRole);
    }
  }

  if (roleIds.size === 0) {
    return [];
  }

  const paths = new Set<string>();
  for (const roleId of [...roleIds].sort()) {
    paths.add(`collaboration/role_shared/${roleId}`);
  }
  for (const [spaceId, space] of Object.entries(collaboration.spaces ?? {}).sort(([a], [b]) =>
    a.localeCompare(b),
  )) {
    const memberRoles = new Set((space.memberRoles ?? []).map((roleId) => normalizeId(roleId)));
    if ([...roleIds].some((roleId) => memberRoles.has(roleId))) {
      paths.add(`collaboration/space_shared/${normalizeId(spaceId)}`);
    }
  }

  return [...paths].sort((a, b) => a.localeCompare(b));
}
