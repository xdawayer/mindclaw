import type {
  CollaborationConfig,
  CollaborationMemoryScope,
  CollaborationPermission,
  OpenClawConfig,
} from "../config/types.js";

const ALL_COLLABORATION_PERMISSIONS: CollaborationPermission[] = [
  "memory.read.private",
  "memory.read.role_shared",
  "memory.read.space_shared",
  "memory.write.private",
  "memory.publish.role_shared",
  "memory.publish.space_shared",
  "schedule.read",
  "schedule.create",
  "schedule.edit",
  "schedule.delete",
  "agent.handoff",
  "agent.mention",
  "exec.approve",
  "config.edit",
];

const DEFAULT_READABLE_SCOPES: CollaborationMemoryScope[] = [
  "private",
  "role_shared",
  "space_shared",
];

type CollaborationWarningCode =
  | "COLLAB_CONFIG_MISSING"
  | "COLLAB_IDENTITY_UNRESOLVED"
  | "COLLAB_SPACE_UNRESOLVED"
  | "COLLAB_ROLE_UNRESOLVED"
  | "COLLAB_ACCOUNT_UNRESOLVED";

export type CollaborationExplainWarning = {
  code: CollaborationWarningCode;
  message: string;
};

export type CollaborationExplainParams = {
  accountId?: string;
  userId: string;
  channelId?: string;
  threadTs?: string;
};

type CollaborationResolvedIdentity = {
  identityId: string;
  resolvedBy: "collaboration.identities.users";
  roles: string[];
  defaultRole: string;
  effectiveRole: string;
};

type CollaborationResolvedSpace = {
  spaceId: string;
  kind: "dm" | "role" | "project";
  resolvedBy: "slack.channel" | "slack.user";
};

type CollaborationResolvedRoute = {
  ownerRole: string;
  ownerAgentId: string;
  ownerBotId: string;
  reason: "identity_default_role" | "space_owner_role";
};

export type CollaborationExplainPayload = {
  ok: boolean;
  mode: CollaborationConfig["mode"] | null;
  surface: {
    provider: "slack";
    accountId?: string;
    channelId?: string;
    threadTs?: string;
    senderUserId: string;
  };
  identity: CollaborationResolvedIdentity | null;
  space: CollaborationResolvedSpace | null;
  route: CollaborationResolvedRoute | null;
  permissions: {
    granted: CollaborationPermission[];
    denied: CollaborationPermission[];
  };
  memory: {
    readableScopes: CollaborationMemoryScope[];
    writeDefaultScope: CollaborationMemoryScope;
    publishableScopes: Array<Exclude<CollaborationMemoryScope, "private">>;
  } | null;
  handoff: {
    allowedTargets: string[];
    maxDepth: number | null;
    allowBotAuthoredReentry: boolean;
  } | null;
  trace: {
    auditEvent: "slack-collaboration-shadow" | "slack-collaboration-enforced" | null;
    auditJournalPath: "collaboration/.audit/events.jsonl";
    auditJournalEventTypes: Array<
      | "collaboration.route.resolved"
      | "collaboration.memory.published"
      | "collaboration.handoff.run.started"
    >;
    handoffCorrelationField: "collaboration.handoff.correlationId";
    handoffArtifactField: "collaboration.handoff.artifactPath";
    handoffArtifactRoot: "collaboration/handoffs" | null;
    memoryEventTypes: Array<"memory.collaboration.handoff" | "memory.collaboration.published">;
  };
  delivery: {
    replyThreadMode: "owner" | "free" | "strict_owner" | null;
    managedSurface: boolean;
  };
  warnings: CollaborationExplainWarning[];
};

function sortedEntries<T>(record: Record<string, T>): Array<[string, T]> {
  return Object.entries(record).sort(([left], [right]) => left.localeCompare(right));
}

function hasSlackAccount(config: OpenClawConfig, accountId: string): boolean {
  return Object.prototype.hasOwnProperty.call(config.channels?.slack?.accounts ?? {}, accountId);
}

function resolveIdentity(
  collaboration: CollaborationConfig,
  userId: string,
): CollaborationResolvedIdentity | null {
  const binding = collaboration.identities.users[userId];
  if (!binding) {
    return null;
  }
  const defaultRole = binding.defaultRole ?? binding.roles[0] ?? "";
  if (!defaultRole) {
    return null;
  }
  return {
    identityId: binding.identityId,
    resolvedBy: "collaboration.identities.users",
    roles: [...binding.roles],
    defaultRole,
    effectiveRole: defaultRole,
  };
}

function resolveSpace(
  collaboration: CollaborationConfig,
  params: CollaborationExplainParams,
): CollaborationResolvedSpace | null {
  if (params.channelId) {
    for (const [spaceId, space] of sortedEntries(collaboration.spaces)) {
      if (space.slack?.channels?.includes(params.channelId)) {
        return {
          spaceId,
          kind: space.kind,
          resolvedBy: "slack.channel",
        };
      }
    }
  }

  for (const [spaceId, space] of sortedEntries(collaboration.spaces)) {
    if (space.kind !== "dm") {
      continue;
    }
    if (space.slack?.users?.includes(params.userId)) {
      return {
        spaceId,
        kind: space.kind,
        resolvedBy: "slack.user",
      };
    }
  }

  return null;
}

function resolveRoute(
  collaboration: CollaborationConfig,
  identity: CollaborationResolvedIdentity | null,
  space: CollaborationResolvedSpace | null,
): CollaborationResolvedRoute | null {
  if (!identity || !space) {
    return null;
  }

  const ownerRole =
    space.kind === "dm" ? identity.defaultRole : collaboration.spaces[space.spaceId]?.ownerRole;
  if (!ownerRole) {
    return null;
  }

  const role = collaboration.roles[ownerRole];
  if (!role) {
    return null;
  }

  return {
    ownerRole,
    ownerAgentId: role.defaultAgentId,
    ownerBotId: role.defaultBotId,
    reason: space.kind === "dm" ? "identity_default_role" : "space_owner_role",
  };
}

function resolveTraceContract(params: {
  collaboration: CollaborationConfig | null | undefined;
  spaceResolved: boolean;
  mode: CollaborationConfig["mode"] | null;
}) {
  const normalizedMode = params.mode ?? "enforced";
  return {
    auditEvent: (normalizedMode === "shadow"
      ? "slack-collaboration-shadow"
      : normalizedMode === "enforced"
        ? "slack-collaboration-enforced"
        : null) as "slack-collaboration-shadow" | "slack-collaboration-enforced" | null,
    auditJournalPath: "collaboration/.audit/events.jsonl" as const,
    auditJournalEventTypes: [
      "collaboration.route.resolved",
      "collaboration.memory.published",
      "collaboration.handoff.run.started",
    ] as Array<
      "collaboration.route.resolved" | "collaboration.memory.published" | "collaboration.handoff.run.started"
    >,
    handoffCorrelationField: "collaboration.handoff.correlationId" as const,
    handoffArtifactField: "collaboration.handoff.artifactPath" as const,
    handoffArtifactRoot:
      params.collaboration && params.spaceResolved ? ("collaboration/handoffs" as const) : null,
    memoryEventTypes: [
      "memory.collaboration.handoff",
      "memory.collaboration.published",
    ] as Array<"memory.collaboration.handoff" | "memory.collaboration.published">,
  };
}

export function explainCollaborationConfig(
  config: OpenClawConfig,
  params: CollaborationExplainParams,
): CollaborationExplainPayload {
  const collaboration = config.collaboration;
  const warnings: CollaborationExplainWarning[] = [];
  const accountId = params.accountId?.trim() || undefined;

  if (!collaboration) {
    warnings.push({
      code: "COLLAB_CONFIG_MISSING",
      message: "collaboration config is not defined",
    });
    return {
      ok: false,
      mode: null,
      surface: {
        provider: "slack",
        ...(accountId ? { accountId } : {}),
        ...(params.channelId ? { channelId: params.channelId } : {}),
        ...(params.threadTs ? { threadTs: params.threadTs } : {}),
        senderUserId: params.userId,
      },
      identity: null,
      space: null,
      route: null,
      permissions: {
        granted: [],
        denied: [...ALL_COLLABORATION_PERMISSIONS],
      },
      memory: null,
      handoff: null,
      trace: resolveTraceContract({
        collaboration: null,
        spaceResolved: false,
        mode: null,
      }),
      delivery: {
        replyThreadMode: null,
        managedSurface: false,
      },
      warnings,
    };
  }

  if (accountId && !hasSlackAccount(config, accountId)) {
    warnings.push({
      code: "COLLAB_ACCOUNT_UNRESOLVED",
      message: `Slack account "${accountId}" is not configured`,
    });
  }

  const identity = resolveIdentity(collaboration, params.userId);
  if (!identity) {
    warnings.push({
      code: "COLLAB_IDENTITY_UNRESOLVED",
      message: `Slack user "${params.userId}" is not mapped in collaboration.identities.users`,
    });
  }

  const space = resolveSpace(collaboration, params);
  if (!space) {
    warnings.push({
      code: "COLLAB_SPACE_UNRESOLVED",
      message: params.channelId
        ? `Slack channel "${params.channelId}" is not mapped to a collaboration space`
        : `No DM collaboration space matched Slack user "${params.userId}"`,
    });
  }

  const route = resolveRoute(collaboration, identity, space);
  if ((identity || space) && !route) {
    warnings.push({
      code: "COLLAB_ROLE_UNRESOLVED",
      message: "Unable to resolve an owner route from the collaboration config",
    });
  }

  const grantedPermissions = route
    ? [...(collaboration.roles[route.ownerRole]?.permissions ?? [])]
    : [];
  const deniedPermissions = ALL_COLLABORATION_PERMISSIONS.filter(
    (permission) => !grantedPermissions.includes(permission),
  );
  const roleConfig = route ? collaboration.roles[route.ownerRole] : null;
  const spaceConfig = space ? collaboration.spaces[space.spaceId] : null;

  return {
    ok: warnings.length === 0,
    mode: collaboration.mode ?? "enforced",
    surface: {
      provider: "slack",
      ...(accountId ? { accountId } : {}),
      ...(params.channelId ? { channelId: params.channelId } : {}),
      ...(params.threadTs ? { threadTs: params.threadTs } : {}),
      senderUserId: params.userId,
    },
    identity,
    space,
    route,
    permissions: {
      granted: grantedPermissions,
      denied: deniedPermissions,
    },
    memory: roleConfig
      ? {
          readableScopes: [...(roleConfig.memoryPolicy?.readableScopes ?? DEFAULT_READABLE_SCOPES)],
          writeDefaultScope: roleConfig.memoryPolicy?.defaultWriteScope ?? "private",
          publishableScopes: [...(roleConfig.memoryPolicy?.publishableScopes ?? [])],
        }
      : null,
    handoff:
      route && spaceConfig
        ? {
            allowedTargets: [...(spaceConfig.handoffs?.allowedTargets ?? [])],
            maxDepth:
              spaceConfig.handoffs?.maxDepth ?? collaboration.routing?.handoff?.maxDepth ?? null,
            allowBotAuthoredReentry:
              collaboration.routing?.handoff?.allowBotAuthoredReentry ?? false,
          }
        : null,
    trace: resolveTraceContract({
      collaboration,
      spaceResolved: Boolean(spaceConfig),
      mode: collaboration.mode ?? "enforced",
    }),
    delivery: {
      replyThreadMode: spaceConfig?.slack?.replyThreadMode ?? null,
      managedSurface: Boolean(spaceConfig),
    },
    warnings,
  };
}
