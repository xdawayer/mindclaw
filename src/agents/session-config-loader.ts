import type { ConfigTier } from "./config-cascade.js";

export type SessionContext = {
  chatType: "p2p" | "group";
  userId: string;
  teamId?: string;
  roleId?: string;
  chatId?: string;
};

export type ConfigLayerSet = {
  tiers: ConfigTier[];
  loadUserMemory: boolean;
  loadTeamMemory: boolean;
  teamMemoryReadOnly: boolean;
  sessionKey: string;
};

export function resolveConfigLayers(ctx: SessionContext): ConfigLayerSet {
  if (ctx.chatType === "group") {
    return {
      tiers: ["org", "team"],
      loadUserMemory: false,
      loadTeamMemory: true,
      teamMemoryReadOnly: false,
      sessionKey: `group:${ctx.chatId ?? ctx.teamId ?? "unknown"}`,
    };
  }

  // p2p: load all 4 layers
  return {
    tiers: ["org", "team", "role", "user"],
    loadUserMemory: true,
    loadTeamMemory: true,
    teamMemoryReadOnly: true,
    sessionKey: `user:${ctx.userId}`,
  };
}
