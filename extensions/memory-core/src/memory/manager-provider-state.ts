import type {
  OpenClawConfig,
  ResolvedMemorySearchConfig,
} from "openclaw/plugin-sdk/memory-core-host-engine-foundation";
import type { MemorySearchManager } from "openclaw/plugin-sdk/memory-core-host-engine-storage";
import {
  resolveEmbeddingProviderFallbackModel,
  type EmbeddingProviderResult,
  type EmbeddingProviderRuntime,
} from "./embeddings.js";

const MEMORY_SCOPE_MARKER = ":memory-scope:";

export type ResolvedMemoryCollaborationScope =
  | {
      kind: "private";
      scope: string;
    }
  | {
      kind: "project";
      scope: string;
    }
  | {
      kind: "role";
      scope: string;
    };

export type ResolvedScopedMemoryRuntimeContext = {
  agentId: string;
  agentSessionKey?: string;
  collaborationScope?: ResolvedMemoryCollaborationScope;
  collaborationParticipantAgentIds?: string[];
};

function parseScopedId(
  scope: string | undefined,
  expectedPrefix: "project" | "role",
): string | undefined {
  const trimmed = scope?.trim();
  if (!trimmed?.startsWith(`${expectedPrefix}:`)) {
    return undefined;
  }
  const id = trimmed.slice(expectedPrefix.length + 1).trim();
  return id || undefined;
}

export function resolveScopedMemoryManagerContext(params: {
  cfg?: OpenClawConfig;
  agentId: string;
  collaborationScope?: ResolvedMemoryCollaborationScope;
}): {
  agentId: string;
  collaborationParticipantAgentIds?: string[];
} {
  const scope = params.collaborationScope;
  if (!scope || scope.kind === "private") {
    return {
      agentId: params.agentId,
    };
  }

  if (scope.kind === "project") {
    const projectId = parseScopedId(scope.scope, "project");
    const project =
      projectId && params.cfg?.collaboration?.spaces?.projects
        ? params.cfg.collaboration.spaces.projects[projectId]
        : undefined;
    const agentId = project?.defaultAgent?.trim() || params.agentId;
    const roleAgentIds = Object.values(params.cfg?.collaboration?.spaces?.roles ?? {})
      .map((role) => role.agentId?.trim())
      .filter((value): value is string => Boolean(value));
    return {
      agentId,
      collaborationParticipantAgentIds: [agentId, ...roleAgentIds].filter(
        (value, index, array) => array.indexOf(value) === index,
      ),
    };
  }

  const roleId = parseScopedId(scope.scope, "role");
  const role =
    roleId && params.cfg?.collaboration?.spaces?.roles
      ? params.cfg.collaboration.spaces.roles[roleId]
      : undefined;
  const agentId = role?.agentId?.trim() || params.agentId;
  return {
    agentId,
    collaborationParticipantAgentIds: [agentId],
  };
}

function normalizeLookup(value: string | undefined | null): string {
  return (value ?? "").trim().toLowerCase();
}

function parseSlackConversationContext(agentSessionKey?: string): {
  channelType: "direct" | "channel" | "group";
  slackChannelId?: string;
  slackUserId?: string;
} | null {
  const raw = agentSessionKey?.trim();
  if (!raw) {
    return null;
  }

  const rawParts = raw.split(":").filter(Boolean);
  const bodyStart = rawParts.length >= 3 && normalizeLookup(rawParts[0]) === "agent" ? 2 : 0;
  const body = rawParts.slice(bodyStart);
  if (normalizeLookup(body[0]) !== "slack") {
    return null;
  }

  const conversationKind = normalizeLookup(body[1]);
  const conversationId = body[2]?.trim();
  if (!conversationId) {
    return null;
  }

  if (conversationKind === "dm" || conversationKind === "direct") {
    return {
      channelType: "direct",
      slackUserId: conversationId,
    };
  }
  if (conversationKind === "channel" || conversationKind === "group") {
    return {
      channelType: conversationKind,
      slackChannelId: conversationId,
    };
  }
  return null;
}

export function resolveMemoryCollaborationScope(params: {
  cfg?: OpenClawConfig;
  agentSessionKey?: string;
}): ResolvedMemoryCollaborationScope | null {
  const conversation = parseSlackConversationContext(params.agentSessionKey);
  if (!conversation) {
    return null;
  }

  if (conversation.channelType === "direct") {
    return conversation.slackUserId
      ? {
          kind: "private",
          scope: `private:${conversation.slackUserId}`,
        }
      : null;
  }

  const slackChannelId = normalizeLookup(conversation.slackChannelId);
  if (!slackChannelId) {
    return null;
  }

  const projects = params.cfg?.collaboration?.spaces?.projects ?? {};
  for (const [projectId, project] of Object.entries(projects)) {
    if (normalizeLookup(project.channelId) === slackChannelId) {
      return {
        kind: "project",
        scope: `project:${projectId}`,
      };
    }
  }

  const roles = params.cfg?.collaboration?.spaces?.roles ?? {};
  for (const [roleId, role] of Object.entries(roles)) {
    if (normalizeLookup(role.channelId) === slackChannelId) {
      return {
        kind: "role",
        scope: `role:${roleId}`,
      };
    }
  }

  return null;
}

export function scopeMemorySessionKey(params: {
  agentSessionKey?: string;
  collaborationScope?: Pick<ResolvedMemoryCollaborationScope, "scope"> | null;
}): string | undefined {
  const sessionKey = params.agentSessionKey?.trim();
  const scope = params.collaborationScope?.scope?.trim();
  if (!sessionKey || !scope) {
    return sessionKey;
  }
  if (sessionKey.includes(MEMORY_SCOPE_MARKER)) {
    return sessionKey;
  }
  return `${sessionKey}${MEMORY_SCOPE_MARKER}${scope}`;
}

export function resolveScopedMemoryRuntimeContext(params: {
  cfg?: OpenClawConfig;
  agentId: string;
  agentSessionKey?: string;
}): ResolvedScopedMemoryRuntimeContext {
  const collaborationScope = resolveMemoryCollaborationScope(params) ?? undefined;
  const managerContext = resolveScopedMemoryManagerContext({
    cfg: params.cfg,
    agentId: params.agentId,
    collaborationScope,
  });
  return {
    agentId: managerContext.agentId,
    collaborationScope,
    collaborationParticipantAgentIds: managerContext.collaborationParticipantAgentIds,
    agentSessionKey: scopeMemorySessionKey({
      agentSessionKey: params.agentSessionKey,
      collaborationScope,
    }),
  };
}

function resolveScopedSearchSessionKey(params: {
  sessionKey?: string;
  fallbackSessionKey?: string;
  collaborationScope?: ResolvedMemoryCollaborationScope;
}): string | undefined {
  return scopeMemorySessionKey({
    agentSessionKey: params.sessionKey?.trim() ? params.sessionKey : params.fallbackSessionKey,
    collaborationScope: params.collaborationScope,
  });
}

export function wrapMemorySearchManager(params: {
  manager: MemorySearchManager;
  fallbackSessionKey?: string;
  collaborationScope?: ResolvedMemoryCollaborationScope;
}): MemorySearchManager {
  if (!params.fallbackSessionKey && !params.collaborationScope) {
    return params.manager;
  }

  return {
    async search(query, opts) {
      const sessionKey = resolveScopedSearchSessionKey({
        sessionKey: opts?.sessionKey,
        fallbackSessionKey: params.fallbackSessionKey,
        collaborationScope: params.collaborationScope,
      });
      return await params.manager.search(query, sessionKey ? { ...opts, sessionKey } : opts);
    },
    async readFile(readParams) {
      return await params.manager.readFile(readParams);
    },
    status() {
      return params.manager.status();
    },
    async sync(syncParams) {
      await params.manager.sync?.(syncParams);
    },
    async probeEmbeddingAvailability() {
      return await params.manager.probeEmbeddingAvailability();
    },
    async probeVectorAvailability() {
      return await params.manager.probeVectorAvailability();
    },
    async close() {
      await params.manager.close?.();
    },
  };
}

export type MemoryResolvedProviderState = {
  provider: EmbeddingProviderResult["provider"];
  fallbackFrom?: string;
  fallbackReason?: string;
  providerUnavailableReason?: string;
  providerRuntime?: EmbeddingProviderRuntime;
};

export function resolveMemoryPrimaryProviderRequest(params: {
  settings: ResolvedMemorySearchConfig;
}): {
  provider: string;
  model: string;
  remote: ResolvedMemorySearchConfig["remote"];
  outputDimensionality: ResolvedMemorySearchConfig["outputDimensionality"];
  fallback: ResolvedMemorySearchConfig["fallback"];
  local: ResolvedMemorySearchConfig["local"];
} {
  return {
    provider: params.settings.provider,
    model: params.settings.model,
    remote: params.settings.remote,
    outputDimensionality: params.settings.outputDimensionality,
    fallback: params.settings.fallback,
    local: params.settings.local,
  };
}

export function resolveMemoryProviderState(
  result: Pick<
    EmbeddingProviderResult,
    "provider" | "fallbackFrom" | "fallbackReason" | "providerUnavailableReason" | "runtime"
  >,
): MemoryResolvedProviderState {
  return {
    provider: result.provider,
    fallbackFrom: result.fallbackFrom,
    fallbackReason: result.fallbackReason,
    providerUnavailableReason: result.providerUnavailableReason,
    providerRuntime: result.runtime,
  };
}

export function applyMemoryFallbackProviderState(params: {
  current: MemoryResolvedProviderState;
  fallbackFrom: string;
  reason: string;
  result: Pick<EmbeddingProviderResult, "provider" | "runtime">;
}): MemoryResolvedProviderState {
  return {
    ...params.current,
    fallbackFrom: params.fallbackFrom,
    fallbackReason: params.reason,
    provider: params.result.provider,
    providerRuntime: params.result.runtime,
  };
}

export function resolveMemoryFallbackProviderRequest(params: {
  cfg: OpenClawConfig;
  settings: ResolvedMemorySearchConfig;
  currentProviderId: string | null;
}): {
  provider: string;
  model: string;
  remote: ResolvedMemorySearchConfig["remote"];
  outputDimensionality: ResolvedMemorySearchConfig["outputDimensionality"];
  fallback: "none";
  local: ResolvedMemorySearchConfig["local"];
} | null {
  const fallback = params.settings.fallback;
  if (
    !fallback ||
    fallback === "none" ||
    !params.currentProviderId ||
    fallback === params.currentProviderId
  ) {
    return null;
  }
  return {
    provider: fallback,
    model: resolveEmbeddingProviderFallbackModel(fallback, params.settings.model, params.cfg),
    remote: params.settings.remote,
    outputDimensionality: params.settings.outputDimensionality,
    fallback: "none",
    local: params.settings.local,
  };
}
