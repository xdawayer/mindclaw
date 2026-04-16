/**
 * Multi-tenant message dispatch — the universal entry point.
 *
 * Core principle: senderId (userId) uniquely determines identity, role, team,
 * permissions, and agent config. This is CONTEXT-INDEPENDENT — the same user
 * gets the same identity whether they send a DM or speak in a group chat.
 *
 * What IS context-dependent: memory loading (DM = personal, group = team-only)
 * and tool downgrading (group chat applies safety intersection).
 */

import { resolveMultiTenantRoute } from "../routing/multi-tenant-routing.js";
import { getDefaultAgents, getAgentPrefixMappings, getAgentsByTeam } from "./agent-registry-mt.js";
import { resolveGroupAllowedTools } from "./group-tool-whitelist.js";
import type { GroupToolPolicy } from "./group-tool-whitelist.js";
import {
  buildMultiTenantBootstrapContext,
  type MultiTenantBootstrapContext,
} from "./multi-tenant-bootstrap.js";
import { getRoleToolWhitelist, getDefaultRoles } from "./role-templates.js";
import { resolveUserIdentity, type UserIdentity, type UserRegistry } from "./user-registry-mt.js";

export type InboundMessage = {
  senderId: string;
  message: string;
  channelId: string;
  chatType: "p2p" | "group";
  chatId: string | undefined;
  groupToolPolicies?: GroupToolPolicy[];
  orgDenyList?: string[];
};

export type DispatchResult = {
  /** User's identity — always the same for the same senderId */
  identity: UserIdentity;
  /** Bootstrap context — config tiers, memory flags, tools, budget */
  bootstrap: MultiTenantBootstrapContext;
  /** Routing result — which agent handles the message */
  routing: {
    agentId: string;
    matchedBy: "command-prefix" | "binding" | "intent";
  };
};

export function dispatchMultiTenantMessage(
  registry: UserRegistry,
  msg: InboundMessage,
): DispatchResult {
  // Step 1: Resolve identity from senderId (context-independent)
  const identity = resolveUserIdentity(registry, msg.senderId);

  // Step 2: Resolve role tools
  // When role has no registered whitelist (e.g. ceo, custom roles),
  // use all available agent tools as the base — org deny list still applies.
  const roles = getDefaultRoles();
  const agents = getDefaultAgents();
  let roleToolWhitelist = getRoleToolWhitelist(identity.roleId, roles);
  if (roleToolWhitelist.length === 0) {
    const allTools = new Set<string>();
    for (const agent of agents) {
      for (const t of agent.toolIds) {
        allTools.add(t);
      }
    }
    for (const role of roles) {
      for (const t of role.toolWhitelist) {
        allTools.add(t);
      }
    }
    roleToolWhitelist = [...allTools];
  }

  // Step 3: Resolve group tool downgrading (context-dependent)
  const groupAllowedTools =
    msg.chatType === "group" && msg.chatId
      ? resolveGroupAllowedTools(msg.chatId, msg.groupToolPolicies ?? [])
      : undefined;

  // Step 4: Build bootstrap (uses chatType for memory/tier decisions)
  const bootstrap = buildMultiTenantBootstrapContext({
    chatType: msg.chatType,
    userId: identity.userId,
    teamId: identity.teamId,
    roleId: identity.roleId,
    chatId: msg.chatId,
    roleToolWhitelist,
    orgDenyList: msg.orgDenyList ?? [],
    groupAllowedTools,
  });

  // Step 5: Route the message
  const teamAgents = getAgentsByTeam(identity.teamId, agents);
  const defaultAgentId =
    identity.agentId !== "default" ? identity.agentId : (teamAgents[0]?.id ?? "knowledge");

  const prefixMappings = getAgentPrefixMappings(teamAgents);

  const routeResult = resolveMultiTenantRoute({
    message: msg.message,
    resolvedAgentId: defaultAgentId,
    channelId: msg.channelId,
    chatType: msg.chatType,
    peerId: msg.senderId,
    prefixMappings,
  });

  return {
    identity,
    bootstrap,
    routing: {
      agentId: routeResult.agentId,
      matchedBy: routeResult.matchedBy,
    },
  };
}
