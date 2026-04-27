import { randomUUID } from "node:crypto";
import {
  appendCollaborationAuditEventForAgent,
  buildAgentMainSessionKey,
  buildAgentSessionKey,
  deriveLastRoutePolicy,
  explainCollaborationConfig,
  persistCollaborationHandoffArtifact,
  readPersistedCollaborationSessionMeta,
  type CollaborationExplainPayload,
  type RoutePeer,
  sanitizeAgentId,
} from "openclaw/plugin-sdk/collaboration-runtime";
import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import type { ResolvedAgentRoute } from "openclaw/plugin-sdk/routing";
import type { SlackMonitorContext } from "./context.js";

type CollaborationMemoryScope = "private" | "role_shared" | "space_shared";
type CollaborationPublishScope = "role_shared" | "space_shared";

type SlackCollaborationHandoffStatus = "accepted" | "rejected";

type SlackCollaborationHandoffReasonCode =
  | "COLLAB_HANDOFF_PERMISSION_DENIED"
  | "COLLAB_HANDOFF_MAX_DEPTH_EXCEEDED"
  | "COLLAB_HANDOFF_TARGET_NOT_ALLOWED"
  | "COLLAB_HANDOFF_RECEIVER_DISABLED"
  | "COLLAB_HANDOFF_INITIATOR_DISABLED";

export type SlackCollaborationHandoff = {
  correlationId: string;
  depth: number;
  status: SlackCollaborationHandoffStatus;
  trigger: "explicit_mention";
  sourceRole: string;
  targetRole: string;
  targetAgentId: string;
  targetBotId: string;
  artifactPath?: string;
  reasonCode?: SlackCollaborationHandoffReasonCode;
};

export type SlackCollaborationMemory = {
  effectiveReadableScopes: CollaborationMemoryScope[];
  effectivePublishableScopes: CollaborationPublishScope[];
};

export type SlackCollaborationAudit = {
  event: "slack-collaboration-shadow" | "slack-collaboration-enforced";
  accountId: string;
  channelId?: string;
  threadTs?: string;
  senderUserId: string;
  spaceId?: string;
  legacyAgentId: string;
  collaborationAgentId?: string;
  effectiveAgentId?: string;
  handoffStatus?: SlackCollaborationHandoffStatus;
  handoffTargetRole?: string;
  handoffCorrelationId?: string;
  handoffDepth?: number;
  handoffArtifactPath?: string;
  memoryReadableScopes?: CollaborationMemoryScope[];
  routeChanged: boolean;
  warningCodes: string[];
};

type SlackCollaborationBaseState = {
  explain: CollaborationExplainPayload;
  audit: SlackCollaborationAudit;
  memory: SlackCollaborationMemory;
  handoff: SlackCollaborationHandoff | null;
  ownerRoute?: ResolvedAgentRoute;
  systemPrompt?: string;
};

export type SlackCollaborationShadowState = SlackCollaborationBaseState & {
  mode: "shadow";
};

export type SlackCollaborationEnforcedState = SlackCollaborationBaseState & {
  mode: "enforced";
  effectiveRoute: ResolvedAgentRoute;
};

export type SlackCollaborationState =
  | SlackCollaborationShadowState
  | SlackCollaborationEnforcedState;

export function isBotMessageBlockedByCollaboration(params: {
  cfg: OpenClawConfig;
  channelId?: string;
  isBotMessage: boolean;
}): boolean {
  if (!params.isBotMessage) {
    return false;
  }
  const collaboration = params.cfg.collaboration;
  if (!collaboration || !params.channelId) {
    return false;
  }
  let managedSurface = false;
  for (const space of Object.values(collaboration.spaces)) {
    if (!space.slack?.channels?.includes(params.channelId)) {
      continue;
    }
    managedSurface = true;
    if (space.slack.allowBotMessages === "none") {
      return true;
    }
    // "handoff_only" gate is enforced by allowBotAuthoredReentry below in V1
    // because handoff-continuation detection is not yet plumbed into this seam.
  }
  if (!managedSurface) {
    return false;
  }
  // Default: managed surfaces drop bot-authored re-entries to prevent loops.
  // Operators can opt back in by setting routing.handoff.allowBotAuthoredReentry=true.
  return collaboration.routing?.handoff?.allowBotAuthoredReentry !== true;
}

export type SlackCollaborationSessionMeta = {
  mode: "shadow" | "enforced";
  managedSurface: true;
  spaceId?: string;
  ownerRole?: string;
  effectiveRole?: string;
  readableScopes: CollaborationMemoryScope[];
  publishableScopes: CollaborationPublishScope[];
  handoff?: {
    correlationId?: string;
    depth?: number;
    status: SlackCollaborationHandoffStatus;
    sourceRole?: string;
    targetRole?: string;
    targetAgentId?: string;
    targetBotId?: string;
    artifactPath?: string;
    reasonCode?: SlackCollaborationHandoffReasonCode;
  };
};

const DEFAULT_READABLE_SCOPES: CollaborationMemoryScope[] = [
  "private",
  "role_shared",
  "space_shared",
];

function buildManagedRoute(params: {
  cfg: OpenClawConfig;
  legacyRoute: ResolvedAgentRoute;
  ownerAgentId: string;
  peer: RoutePeer;
  kind: "owner" | "handoff";
}): ResolvedAgentRoute {
  const agentId = sanitizeAgentId(params.ownerAgentId);
  const sessionKey = buildAgentSessionKey({
    agentId,
    channel: params.legacyRoute.channel,
    accountId: params.legacyRoute.accountId,
    peer: params.peer,
    dmScope: params.cfg.session?.dmScope,
    identityLinks: params.cfg.session?.identityLinks,
  });
  const mainSessionKey = buildAgentMainSessionKey({ agentId });
  return {
    ...params.legacyRoute,
    agentId,
    sessionKey,
    mainSessionKey,
    lastRoutePolicy: deriveLastRoutePolicy({
      sessionKey,
      mainSessionKey,
    }),
    matchedBy:
      params.kind === "handoff"
        ? "collaboration.handoff"
        : params.peer.kind === "direct"
          ? "collaboration.dm"
          : "collaboration.space",
  };
}

function resolveRoleReadableScopes(params: {
  cfg: OpenClawConfig;
  roleId: string;
  spaceId?: string;
}): CollaborationMemoryScope[] {
  const collaboration = params.cfg.collaboration;
  const role = collaboration?.roles?.[params.roleId];
  if (!role) {
    return [];
  }
  const permissions = new Set(role.permissions ?? []);
  const allowedByRole = role.memoryPolicy?.readableScopes ?? DEFAULT_READABLE_SCOPES;
  const spaceReadableRoles = params.spaceId
    ? collaboration?.spaces?.[params.spaceId]?.memory?.readableByRoles
    : undefined;
  return allowedByRole.filter((scope) => {
    if (scope === "private") {
      return permissions.has("memory.read.private");
    }
    if (scope === "role_shared") {
      return permissions.has("memory.read.role_shared");
    }
    if (scope === "space_shared") {
      if (!permissions.has("memory.read.space_shared")) {
        return false;
      }
      if (spaceReadableRoles?.length) {
        return spaceReadableRoles.includes(params.roleId);
      }
      return true;
    }
    return false;
  });
}

function resolveRolePublishableScopes(params: {
  cfg: OpenClawConfig;
  roleId: string;
  spaceId?: string;
}): CollaborationPublishScope[] {
  const collaboration = params.cfg.collaboration;
  const role = collaboration?.roles?.[params.roleId];
  if (!role) {
    return [];
  }
  const permissions = new Set(role.permissions ?? []);
  const publishRequires = params.spaceId
    ? (collaboration?.spaces?.[params.spaceId]?.memory?.publishRequires ?? [])
    : [];
  const satisfiesSpaceRequirements = publishRequires.every((permission) =>
    permissions.has(permission),
  );
  const allowedByRole = role.memoryPolicy?.publishableScopes ?? [];
  return allowedByRole.filter((scope) => {
    if (scope === "role_shared") {
      return permissions.has("memory.publish.role_shared");
    }
    if (scope === "space_shared") {
      return permissions.has("memory.publish.space_shared") && satisfiesSpaceRequirements;
    }
    return false;
  });
}

function resolveMentionedRole(params: {
  cfg: OpenClawConfig;
  ownerRole: string;
  text: string;
  matchAgentMention: (agentId: string) => boolean;
}): { roleId: string; agentId: string; botId: string } | null {
  const collaboration = params.cfg.collaboration;
  if (!collaboration) {
    return null;
  }

  for (const roleId of Object.keys(collaboration.roles).sort()) {
    if (roleId === params.ownerRole) {
      continue;
    }
    const role = collaboration.roles[roleId];
    if (!role?.defaultAgentId || !role.defaultBotId) {
      continue;
    }
    if (!params.matchAgentMention(role.defaultAgentId)) {
      continue;
    }
    return {
      roleId,
      agentId: role.defaultAgentId,
      botId: role.defaultBotId,
    };
  }

  return null;
}

function resolveHandoff(params: {
  cfg: OpenClawConfig;
  explain: CollaborationExplainPayload;
  candidate: { roleId: string; agentId: string; botId: string } | null;
  priorHandoffDepth?: number;
}): SlackCollaborationHandoff | null {
  const collaboration = params.cfg.collaboration;
  if (!collaboration || !params.explain.route || !params.explain.space || !params.explain.handoff) {
    return null;
  }

  const candidate = params.candidate;
  if (!candidate) {
    return null;
  }
  const nextDepth = Math.max(0, params.priorHandoffDepth ?? 0) + 1;
  const maxDepth = params.explain.handoff.maxDepth;
  if (typeof maxDepth === "number" && nextDepth > maxDepth) {
    return {
      correlationId: randomUUID(),
      depth: nextDepth,
      status: "rejected",
      trigger: "explicit_mention",
      sourceRole: params.explain.route.ownerRole,
      targetRole: candidate.roleId,
      targetAgentId: candidate.agentId,
      targetBotId: candidate.botId,
      reasonCode: "COLLAB_HANDOFF_MAX_DEPTH_EXCEEDED",
    };
  }

  if (!params.explain.permissions.granted.includes("agent.handoff")) {
    return {
      correlationId: randomUUID(),
      depth: nextDepth,
      status: "rejected",
      trigger: "explicit_mention",
      sourceRole: params.explain.route.ownerRole,
      targetRole: candidate.roleId,
      targetAgentId: candidate.agentId,
      targetBotId: candidate.botId,
      reasonCode: "COLLAB_HANDOFF_PERMISSION_DENIED",
    };
  }

  const sourceBotId = params.explain.route.ownerBotId;
  const sourceBot = sourceBotId ? collaboration.bots[sourceBotId] : undefined;
  if (sourceBot?.canInitiateHandoffs === false) {
    return {
      correlationId: randomUUID(),
      depth: nextDepth,
      status: "rejected",
      trigger: "explicit_mention",
      sourceRole: params.explain.route.ownerRole,
      targetRole: candidate.roleId,
      targetAgentId: candidate.agentId,
      targetBotId: candidate.botId,
      reasonCode: "COLLAB_HANDOFF_INITIATOR_DISABLED",
    };
  }

  const targetBot = collaboration.bots[candidate.botId];
  if (targetBot?.canReceiveHandoffs === false) {
    return {
      correlationId: randomUUID(),
      depth: nextDepth,
      status: "rejected",
      trigger: "explicit_mention",
      sourceRole: params.explain.route.ownerRole,
      targetRole: candidate.roleId,
      targetAgentId: candidate.agentId,
      targetBotId: candidate.botId,
      reasonCode: "COLLAB_HANDOFF_RECEIVER_DISABLED",
    };
  }

  const allowedTargets = new Set(params.explain.handoff.allowedTargets);
  const allowedSpaces = targetBot?.allowedSpaces;
  const spaceAllowed =
    !allowedSpaces?.length ||
    (params.explain.space && allowedSpaces.includes(params.explain.space.spaceId));
  if (!allowedTargets.has(candidate.roleId) || !spaceAllowed) {
    return {
      correlationId: randomUUID(),
      depth: nextDepth,
      status: "rejected",
      trigger: "explicit_mention",
      sourceRole: params.explain.route.ownerRole,
      targetRole: candidate.roleId,
      targetAgentId: candidate.agentId,
      targetBotId: candidate.botId,
      reasonCode: "COLLAB_HANDOFF_TARGET_NOT_ALLOWED",
    };
  }

  return {
    correlationId: randomUUID(),
    depth: nextDepth,
    status: "accepted",
    trigger: "explicit_mention",
    sourceRole: params.explain.route.ownerRole,
    targetRole: candidate.roleId,
    targetAgentId: candidate.agentId,
    targetBotId: candidate.botId,
  };
}

function resolvePersistedHandoffDepth(
  meta:
    | ReturnType<typeof readPersistedCollaborationSessionMeta>
    | SlackCollaborationSessionMeta
    | undefined,
): number {
  const depth = meta?.handoff?.depth;
  return typeof depth === "number" && Number.isFinite(depth) && depth > 0 ? depth : 0;
}

function buildCollaborationSystemPrompt(params: {
  explain: CollaborationExplainPayload;
  effectiveRole: string;
  effectiveReadableScopes: CollaborationMemoryScope[];
  effectivePublishableScopes: CollaborationPublishScope[];
  handoff: SlackCollaborationHandoff | null;
}): string | undefined {
  if (!params.explain.space) {
    return undefined;
  }
  const lines: string[] = [];
  if (params.handoff?.status === "accepted") {
    lines.push(
      `Structured collaboration handoff from role ${params.handoff.sourceRole} to role ${params.handoff.targetRole}.`,
    );
    // Correlation IDs are deliberately omitted from the system prompt: they
    // are randomized per turn and would defeat prompt cache reuse. The id is
    // available via metadata, audit events, and the artifact file.
    lines.push("Respond in the current Slack thread and treat this turn as an explicit handoff.");
  }
  lines.push(`Current collaboration role: ${params.effectiveRole}.`);
  lines.push(
    `Readable collaboration memory scopes: ${params.effectiveReadableScopes.join(", ") || "none"}.`,
  );
  lines.push(
    `Publishable collaboration memory scopes: ${params.effectivePublishableScopes.join(", ") || "none"}.`,
  );
  lines.push("Do not assume access to any other collaboration memory scopes.");
  return lines.join(" ");
}

export function buildSlackCollaborationSessionMeta(
  state: SlackCollaborationState | null | undefined,
): SlackCollaborationSessionMeta | undefined {
  if (!state?.explain.delivery.managedSurface) {
    return undefined;
  }
  return {
    mode: state.mode,
    managedSurface: true,
    ...(state.explain.space?.spaceId ? { spaceId: state.explain.space.spaceId } : {}),
    ...(state.explain.route?.ownerRole ? { ownerRole: state.explain.route.ownerRole } : {}),
    ...(state.handoff?.status === "accepted"
      ? { effectiveRole: state.handoff.targetRole }
      : state.explain.route?.ownerRole
        ? { effectiveRole: state.explain.route.ownerRole }
        : {}),
    readableScopes: [...state.memory.effectiveReadableScopes],
    publishableScopes: [...state.memory.effectivePublishableScopes],
    ...(state.handoff
      ? {
          handoff: {
            correlationId: state.handoff.correlationId,
            depth: state.handoff.depth,
            status: state.handoff.status,
            ...(state.handoff.sourceRole ? { sourceRole: state.handoff.sourceRole } : {}),
            ...(state.handoff.targetRole ? { targetRole: state.handoff.targetRole } : {}),
            ...(state.handoff.targetAgentId ? { targetAgentId: state.handoff.targetAgentId } : {}),
            ...(state.handoff.targetBotId ? { targetBotId: state.handoff.targetBotId } : {}),
            ...(state.handoff.artifactPath ? { artifactPath: state.handoff.artifactPath } : {}),
            ...(state.handoff.reasonCode ? { reasonCode: state.handoff.reasonCode } : {}),
          },
        }
      : {}),
  };
}

export function resolveSlackCollaborationState(params: {
  cfg: OpenClawConfig;
  accountId: string;
  senderUserId: string;
  channelId?: string;
  threadTs?: string;
  peer: RoutePeer;
  legacyRoute: ResolvedAgentRoute;
  text?: string;
  matchAgentMention?: (agentId: string) => boolean;
  resolvePersistedSessionMeta?: (
    route: ResolvedAgentRoute,
  ) => SlackCollaborationSessionMeta | undefined;
}): SlackCollaborationState | null {
  const explain = explainCollaborationConfig(params.cfg, {
    accountId: params.accountId,
    userId: params.senderUserId,
    channelId: params.channelId,
    threadTs: params.threadTs,
  });

  if (
    (explain.mode !== "shadow" && explain.mode !== "enforced") ||
    !explain.delivery.managedSurface
  ) {
    return null;
  }

  const collaborationAgentId = explain.route?.ownerAgentId;
  const candidate =
    explain.route && explain.space && params.text?.trim() && params.matchAgentMention
      ? resolveMentionedRole({
          cfg: params.cfg,
          ownerRole: explain.route.ownerRole,
          text: params.text,
          matchAgentMention: params.matchAgentMention,
        })
      : null;
  const ownerManagedRoute =
    collaborationAgentId && explain.route
      ? buildManagedRoute({
          cfg: params.cfg,
          legacyRoute: params.legacyRoute,
          ownerAgentId: collaborationAgentId,
          peer: params.peer,
          kind: "owner",
        })
      : null;
  const candidateManagedRoute = candidate
    ? buildManagedRoute({
        cfg: params.cfg,
        legacyRoute: params.legacyRoute,
        ownerAgentId: candidate.agentId,
        peer: params.peer,
        kind: "handoff",
      })
    : null;
  const priorHandoffDepth = Math.max(
    resolvePersistedHandoffDepth(
      ownerManagedRoute ? params.resolvePersistedSessionMeta?.(ownerManagedRoute) : undefined,
    ),
    resolvePersistedHandoffDepth(
      candidateManagedRoute
        ? params.resolvePersistedSessionMeta?.(candidateManagedRoute)
        : undefined,
    ),
  );
  const handoff = resolveHandoff({
    cfg: params.cfg,
    explain,
    candidate,
    priorHandoffDepth,
  });
  const effectiveRole =
    handoff?.status === "accepted" ? handoff.targetRole : (explain.route?.ownerRole ?? "");
  const effectiveAgentId =
    handoff?.status === "accepted" ? handoff.targetAgentId : collaborationAgentId;
  const effectiveReadableScopes = effectiveRole
    ? resolveRoleReadableScopes({
        cfg: params.cfg,
        roleId: effectiveRole,
        spaceId: explain.space?.spaceId,
      })
    : [];
  const effectivePublishableScopes = effectiveRole
    ? resolveRolePublishableScopes({
        cfg: params.cfg,
        roleId: effectiveRole,
        spaceId: explain.space?.spaceId,
      })
    : [];
  const systemPrompt = effectiveRole
    ? buildCollaborationSystemPrompt({
        explain,
        effectiveRole,
        effectiveReadableScopes,
        effectivePublishableScopes,
        handoff,
      })
    : undefined;

  const effectiveRoute =
    explain.mode === "enforced" && effectiveAgentId
      ? buildManagedRoute({
          cfg: params.cfg,
          legacyRoute: params.legacyRoute,
          ownerAgentId: effectiveAgentId,
          peer: params.peer,
          kind: handoff?.status === "accepted" ? "handoff" : "owner",
        })
      : params.legacyRoute;
  const routeChanged =
    explain.mode === "enforced"
      ? effectiveRoute.agentId !== params.legacyRoute.agentId
      : Boolean(effectiveAgentId && effectiveAgentId !== params.legacyRoute.agentId);
  const audit: SlackCollaborationAudit = {
    event:
      explain.mode === "enforced" ? "slack-collaboration-enforced" : "slack-collaboration-shadow",
    accountId: params.accountId,
    ...(params.channelId ? { channelId: params.channelId } : {}),
    ...(params.threadTs ? { threadTs: params.threadTs } : {}),
    senderUserId: params.senderUserId,
    ...(explain.space?.spaceId ? { spaceId: explain.space.spaceId } : {}),
    legacyAgentId: params.legacyRoute.agentId,
    ...(collaborationAgentId ? { collaborationAgentId } : {}),
    ...(explain.mode === "enforced" ? { effectiveAgentId: effectiveRoute.agentId } : {}),
    ...(handoff
      ? {
          handoffStatus: handoff.status,
          handoffTargetRole: handoff.targetRole,
          handoffCorrelationId: handoff.correlationId,
          handoffDepth: handoff.depth,
        }
      : {}),
    ...(effectiveReadableScopes.length > 0
      ? { memoryReadableScopes: [...effectiveReadableScopes] }
      : {}),
    routeChanged,
    warningCodes: explain.warnings.map((warning) => warning.code),
  };

  if (explain.mode === "enforced") {
    return {
      mode: "enforced",
      explain,
      audit,
      memory: {
        effectiveReadableScopes,
        effectivePublishableScopes,
      },
      handoff,
      ...(ownerManagedRoute ? { ownerRoute: ownerManagedRoute } : {}),
      ...(systemPrompt ? { systemPrompt } : {}),
      effectiveRoute,
    };
  }

  return {
    mode: "shadow",
    explain,
    audit,
    memory: {
      effectiveReadableScopes,
      effectivePublishableScopes,
    },
    handoff,
    ...(ownerManagedRoute ? { ownerRoute: ownerManagedRoute } : {}),
    ...(systemPrompt ? { systemPrompt } : {}),
  };
}

export function emitSlackCollaborationAudit(
  logger: Pick<SlackMonitorContext["logger"], "info">,
  state: SlackCollaborationState,
): void {
  logger.info(
    state.audit,
    state.mode === "enforced" ? "slack collaboration enforced" : "slack collaboration shadow",
  );
}

export async function persistSlackCollaborationHandoffArtifact(params: {
  cfg: OpenClawConfig;
  state: SlackCollaborationEnforcedState;
  accountId: string;
  senderUserId: string;
  channelId?: string;
  threadTs?: string;
  messageTs?: string;
  text?: string;
}): Promise<void> {
  const handoff = params.state.handoff;
  if (!handoff) {
    return;
  }
  const auditConfig = params.cfg.collaboration?.audit;
  if (auditConfig?.enabled === false) {
    return;
  }
  params.state.audit.handoffCorrelationId = handoff.correlationId;
  params.state.audit.handoffDepth = handoff.depth;
  const sourceAgentId =
    params.state.explain.route?.ownerAgentId ?? params.state.effectiveRoute.agentId;
  const includeBody = auditConfig?.redactBodies !== true;
  const artifactPath = await persistCollaborationHandoffArtifact({
    cfg: params.cfg,
    agentId: params.state.effectiveRoute.agentId,
    correlationId: handoff.correlationId,
    depth: handoff.depth,
    status: handoff.status,
    trigger: handoff.trigger,
    sourceRole: handoff.sourceRole,
    targetRole: handoff.targetRole,
    sourceAgentId,
    targetAgentId: handoff.targetAgentId,
    targetBotId: handoff.targetBotId,
    effectiveAgentId: params.state.effectiveRoute.agentId,
    senderUserId: params.senderUserId,
    accountId: params.accountId,
    ...(params.channelId ? { channelId: params.channelId } : {}),
    ...(params.threadTs ? { threadTs: params.threadTs } : {}),
    ...(params.messageTs ? { messageTs: params.messageTs } : {}),
    ...(params.state.explain.space?.spaceId ? { spaceId: params.state.explain.space.spaceId } : {}),
    ...(handoff.reasonCode ? { reasonCode: handoff.reasonCode } : {}),
    ...(includeBody && params.text?.trim() ? { text: params.text } : {}),
  });
  if (!artifactPath) {
    return;
  }
  handoff.artifactPath = artifactPath;
  params.state.audit.handoffArtifactPath = artifactPath;
}

export async function persistSlackCollaborationAuditEvent(params: {
  cfg: OpenClawConfig;
  state: SlackCollaborationState;
}): Promise<void> {
  if (params.cfg.collaboration?.audit?.enabled === false) {
    return;
  }
  const agentId =
    params.state.mode === "enforced"
      ? params.state.effectiveRoute.agentId
      : params.state.handoff?.status === "accepted"
        ? params.state.handoff.targetAgentId
        : (params.state.explain.route?.ownerAgentId ?? params.state.audit.collaborationAgentId);
  if (!agentId) {
    return;
  }
  await appendCollaborationAuditEventForAgent({
    cfg: params.cfg,
    agentId,
    event: {
      type: "collaboration.route.resolved",
      timestamp: new Date().toISOString(),
      surface: "slack",
      mode: params.state.mode,
      accountId: params.state.audit.accountId,
      senderUserId: params.state.audit.senderUserId,
      ...(params.state.audit.channelId ? { channelId: params.state.audit.channelId } : {}),
      ...(params.state.audit.threadTs ? { threadTs: params.state.audit.threadTs } : {}),
      ...(params.state.audit.spaceId ? { spaceId: params.state.audit.spaceId } : {}),
      legacyAgentId: params.state.audit.legacyAgentId,
      ...(params.state.audit.collaborationAgentId
        ? { collaborationAgentId: params.state.audit.collaborationAgentId }
        : {}),
      ...(params.state.audit.effectiveAgentId
        ? { effectiveAgentId: params.state.audit.effectiveAgentId }
        : {}),
      ...(params.state.audit.handoffStatus
        ? { handoffStatus: params.state.audit.handoffStatus }
        : {}),
      ...(params.state.audit.handoffTargetRole
        ? { handoffTargetRole: params.state.audit.handoffTargetRole }
        : {}),
      ...(params.state.audit.handoffCorrelationId
        ? { handoffCorrelationId: params.state.audit.handoffCorrelationId }
        : {}),
      ...(typeof params.state.audit.handoffDepth === "number"
        ? { handoffDepth: params.state.audit.handoffDepth }
        : {}),
      ...(params.state.audit.handoffArtifactPath
        ? { handoffArtifactPath: params.state.audit.handoffArtifactPath }
        : {}),
      ...(params.state.audit.memoryReadableScopes
        ? { memoryReadableScopes: params.state.audit.memoryReadableScopes }
        : {}),
      routeChanged: params.state.audit.routeChanged,
      warningCodes: [...params.state.audit.warningCodes],
    },
  });
}
