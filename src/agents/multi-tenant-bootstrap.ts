import type { ConfigTier } from "./config-cascade.js";
import { allocateBudget, type LayerBudget } from "./context-budget.js";
import { resolveToolPermissions } from "./permission-resolver.js";
import { resolveConfigLayers } from "./session-config-loader.js";

export type BootstrapInput = {
  chatType: "p2p" | "group";
  userId: string;
  teamId?: string;
  roleId?: string;
  chatId?: string;
  roleToolWhitelist?: string[];
  orgDenyList?: string[];
  groupAllowedTools?: string[];
};

export type MultiTenantBootstrapContext = {
  tiers: ConfigTier[];
  loadUserMemory: boolean;
  loadTeamMemory: boolean;
  teamMemoryReadOnly: boolean;
  sessionKey: string;
  allowedTools: string[];
  tokenBudget: LayerBudget;
};

export function buildMultiTenantBootstrapContext(
  input: BootstrapInput,
): MultiTenantBootstrapContext {
  const layers = resolveConfigLayers({
    chatType: input.chatType,
    userId: input.userId,
    teamId: input.teamId,
    roleId: input.roleId,
    chatId: input.chatId,
  });

  const allowedTools = resolveToolPermissions({
    chatType: input.chatType,
    roleToolWhitelist: input.roleToolWhitelist ?? [],
    orgDenyList: input.orgDenyList ?? [],
    groupAllowedTools: input.groupAllowedTools,
  });

  const tokenBudget = allocateBudget();

  return {
    tiers: layers.tiers,
    loadUserMemory: layers.loadUserMemory,
    loadTeamMemory: layers.loadTeamMemory,
    teamMemoryReadOnly: layers.teamMemoryReadOnly,
    sessionKey: layers.sessionKey,
    allowedTools,
    tokenBudget,
  };
}
