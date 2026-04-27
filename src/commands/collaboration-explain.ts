import { resolveAgentWorkspaceDir } from "../agents/agent-scope.js";
import { readCollaborationAuditEvents } from "../collaboration/audit.js";
import {
  explainCollaborationConfig,
  type CollaborationExplainPayload,
} from "../collaboration/runtime.js";
import type { OpenClawConfig } from "../config/types.js";
import { danger } from "../globals.js";
import type { RuntimeEnv } from "../runtime.js";
import { writeRuntimeJson } from "../runtime.js";
import { requireValidConfigSnapshot } from "./config-validation.js";

type CollaborationExplainOptions = {
  account?: string;
  user?: string;
  channel?: string;
  thread?: string;
  json: boolean;
};

async function resolveLatestObservedRouteEvent(params: {
  config: OpenClawConfig;
  payload: CollaborationExplainPayload;
}): Promise<
  | Extract<
      Awaited<ReturnType<typeof readCollaborationAuditEvents>>[number],
      { type: "collaboration.route.resolved" }
    >
  | undefined
> {
  const ownerAgentId = params.payload.route?.ownerAgentId;
  if (!ownerAgentId || !params.payload.delivery.managedSurface) {
    return undefined;
  }
  // Enforced handoffs land their route events in the EFFECTIVE agent's
  // workspace. Surface-based explain must read both the owner's and any
  // configured handoff target workspaces to surface the latest observation.
  const candidateAgentIds = new Set<string>([ownerAgentId]);
  const space = params.payload.space?.spaceId
    ? params.config.collaboration?.spaces?.[params.payload.space.spaceId]
    : undefined;
  for (const targetRoleId of space?.handoffs?.allowedTargets ?? []) {
    const targetAgentId = params.config.collaboration?.roles?.[targetRoleId]?.defaultAgentId;
    if (targetAgentId) {
      candidateAgentIds.add(targetAgentId);
    }
  }
  const workspaceDirs: string[] = [];
  for (const candidateAgentId of candidateAgentIds) {
    const dir = resolveAgentWorkspaceDir(params.config, candidateAgentId)?.trim();
    if (dir) {
      workspaceDirs.push(dir);
    }
  }
  if (workspaceDirs.length === 0) {
    return undefined;
  }
  const eventBatches = await Promise.all(
    workspaceDirs.map((workspaceDir) => readCollaborationAuditEvents({ workspaceDir, limit: 100 })),
  );
  const events = eventBatches.flat().toSorted((a, b) => a.timestamp.localeCompare(b.timestamp));
  return events
    .toReversed()
    .find(
      (
        event,
      ): event is Extract<(typeof events)[number], { type: "collaboration.route.resolved" }> =>
        event.type === "collaboration.route.resolved" &&
        event.senderUserId === params.payload.surface.senderUserId &&
        (!params.payload.surface.accountId ||
          event.accountId === params.payload.surface.accountId) &&
        (!params.payload.surface.channelId ||
          event.channelId === params.payload.surface.channelId) &&
        (!params.payload.surface.threadTs || event.threadTs === params.payload.surface.threadTs),
    );
}

function formatExplainText(
  payload: CollaborationExplainPayload,
  observedRouteEvent?: Extract<
    Awaited<ReturnType<typeof readCollaborationAuditEvents>>[number],
    { type: "collaboration.route.resolved" }
  >,
): string {
  const lines = [
    "Collaboration explain",
    `Mode: ${payload.mode ?? "none"}`,
    `Slack user: ${payload.surface.senderUserId}`,
    `Slack account: ${payload.surface.accountId ?? "none"}`,
    `Slack channel: ${payload.surface.channelId ?? "none"}`,
    `Thread: ${payload.surface.threadTs ?? "none"}`,
    `Identity: ${payload.identity?.identityId ?? "unresolved"}`,
    `Effective role: ${payload.identity?.effectiveRole ?? "unresolved"}`,
    `Space: ${payload.space ? `${payload.space.spaceId} (${payload.space.kind})` : "unresolved"}`,
    `Owner agent: ${payload.route?.ownerAgentId ?? "unresolved"}`,
    `Owner bot: ${payload.route?.ownerBotId ?? "unresolved"}`,
    `Managed surface: ${payload.delivery.managedSurface ? "yes" : "no"}`,
    `Reply thread mode: ${payload.delivery.replyThreadMode ?? "none"}`,
    `Readable scopes: ${payload.memory?.readableScopes.join(", ") ?? "none"}`,
    `Publishable scopes: ${payload.memory?.publishableScopes.join(", ") ?? "none"}`,
    `Granted permissions: ${payload.permissions.granted.join(", ") || "none"}`,
    `Denied permissions: ${payload.permissions.denied.join(", ") || "none"}`,
    `Handoff targets: ${payload.handoff?.allowedTargets.join(", ") ?? "none"}`,
    `Audit event: ${payload.trace.auditEvent ?? "none"}`,
    `Audit journal path: ${payload.trace.auditJournalPath}`,
    `Audit journal events: ${payload.trace.auditJournalEventTypes.join(", ")}`,
    `Handoff correlation field: ${payload.trace.handoffCorrelationField}`,
    `Handoff artifact field: ${payload.trace.handoffArtifactField}`,
    `Handoff artifact root: ${payload.trace.handoffArtifactRoot ?? "none"}`,
    `Memory audit events: ${payload.trace.memoryEventTypes.join(", ")}`,
  ];

  if (observedRouteEvent) {
    lines.push(
      `Latest observed route warnings: ${observedRouteEvent.warningCodes.join(", ") || "none"}`,
    );
    lines.push(
      `Latest observed handoff correlation: ${observedRouteEvent.handoffCorrelationId ?? "none"}`,
    );
  }

  if (payload.warnings.length > 0) {
    lines.push("Warnings:");
    for (const warning of payload.warnings) {
      lines.push(`- ${warning.code}: ${warning.message}`);
    }
  }

  return lines.join("\n");
}

export async function collaborationExplainCommand(
  opts: CollaborationExplainOptions,
  runtime: RuntimeEnv,
): Promise<void> {
  const userId = (opts.user ?? "").trim();
  if (!userId) {
    runtime.error(danger("--user is required"));
    runtime.exit(1);
    return;
  }

  try {
    const config = await requireValidConfigSnapshot(runtime);
    if (!config) {
      return;
    }

    const payload = explainCollaborationConfig(config, {
      accountId: opts.account?.trim() || undefined,
      userId,
      channelId: opts.channel?.trim() || undefined,
      threadTs: opts.thread?.trim() || undefined,
    });

    if (opts.json) {
      writeRuntimeJson(runtime, payload, 2);
    } else {
      const observedRouteEvent = await resolveLatestObservedRouteEvent({
        config,
        payload,
      });
      runtime.log(formatExplainText(payload, observedRouteEvent));
    }

    if (!payload.ok) {
      runtime.exit(1);
    }
  } catch (err) {
    runtime.error(danger(`Collaboration explain error: ${String(err)}`));
    runtime.exit(1);
  }
}
