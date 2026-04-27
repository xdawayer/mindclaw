import { resolveAgentWorkspaceDir } from "../agents/agent-scope.js";
import { readCollaborationAuditEvents } from "../collaboration/audit.js";
import {
  explainCollaborationConfig,
  type CollaborationExplainPayload,
} from "../collaboration/runtime.js";
import { danger } from "../globals.js";
import type { RuntimeEnv } from "../runtime.js";
import { writeRuntimeJson } from "../runtime.js";
import { requireValidConfigSnapshot } from "./config-validation.js";

type CollaborationAuditTypeOption = "route" | "memory-published" | "handoff-run";

const COLLABORATION_AUDIT_TYPE_VALUES = ["route", "memory-published", "handoff-run"] as const;

type CollaborationAuditOptions = {
  agent?: string;
  account?: string;
  user?: string;
  channel?: string;
  thread?: string;
  type?: CollaborationAuditTypeOption | string;
  correlation?: string;
  limit: number;
  json: boolean;
};

type CollaborationAuditFilterType =
  | "collaboration.route.resolved"
  | "collaboration.memory.published"
  | "collaboration.handoff.run.started";

function parseFilterType(
  value: CollaborationAuditOptions["type"],
): { ok: true; value?: CollaborationAuditFilterType } | { ok: false; reason: string } {
  if (value === undefined || value === "") {
    return { ok: true };
  }
  if (value === "route") {
    return { ok: true, value: "collaboration.route.resolved" };
  }
  if (value === "memory-published") {
    return { ok: true, value: "collaboration.memory.published" };
  }
  if (value === "handoff-run") {
    return { ok: true, value: "collaboration.handoff.run.started" };
  }
  return {
    ok: false,
    reason: `Invalid --type "${value}". Expected one of: ${COLLABORATION_AUDIT_TYPE_VALUES.join(", ")}.`,
  };
}

function parseLimit(value: number): { ok: true; value: number } | { ok: false; reason: string } {
  if (!Number.isFinite(value)) {
    return { ok: false, reason: "Invalid --limit (must be a finite number >= 1)" };
  }
  const floored = Math.floor(value);
  if (floored < 1) {
    return { ok: false, reason: "Invalid --limit (must be >= 1)" };
  }
  return { ok: true, value: floored };
}

function formatRouteEvent(
  event: Extract<
    Awaited<ReturnType<typeof readCollaborationAuditEvents>>[number],
    { type: "collaboration.route.resolved" }
  >,
): string {
  const routeSummary = `${event.legacyAgentId} -> ${event.effectiveAgentId ?? event.collaborationAgentId ?? event.legacyAgentId}`;
  const handoffSummary =
    event.handoffStatus && event.handoffTargetRole
      ? ` handoff=${event.handoffStatus}:${event.handoffTargetRole}`
      : "";
  const correlationSummary = event.handoffCorrelationId
    ? ` correlation=${event.handoffCorrelationId}`
    : "";
  const warningSummary =
    event.warningCodes.length > 0 ? ` warnings=${event.warningCodes.join(",")}` : "";
  return `${event.timestamp} ${event.type} mode=${event.mode} route=${routeSummary} changed=${event.routeChanged}${handoffSummary}${correlationSummary}${warningSummary}`;
}

function formatMemoryPublishedEvent(
  event: Extract<
    Awaited<ReturnType<typeof readCollaborationAuditEvents>>[number],
    { type: "collaboration.memory.published" }
  >,
): string {
  const scopeSummary = event.spaceId
    ? `${event.scope}:${event.spaceId}`
    : event.effectiveRole
      ? `${event.scope}:${event.effectiveRole}`
      : event.scope;
  return `${event.timestamp} ${event.type} source=${event.source} scope=${scopeSummary} path=${event.path}`;
}

function formatHandoffRunStartedEvent(
  event: Extract<
    Awaited<ReturnType<typeof readCollaborationAuditEvents>>[number],
    { type: "collaboration.handoff.run.started" }
  >,
): string {
  return `${event.timestamp} ${event.type} run=${event.runId} task=${event.taskId} correlation=${event.correlationId} owner=${event.ownerSessionKey} child=${event.childSessionKey} agent=${event.agentId} target=${event.targetRole}`;
}

function formatAuditText(params: {
  agentId: string;
  workspaceDir: string;
  filterType?: CollaborationAuditFilterType;
  correlation?: string;
  events: Awaited<ReturnType<typeof readCollaborationAuditEvents>>;
}): string {
  const lines = [
    "Collaboration audit",
    `Agent: ${params.agentId}`,
    `Workspace: ${params.workspaceDir}`,
    `Filter type: ${params.filterType ?? "all"}`,
    `Correlation: ${params.correlation ?? "all"}`,
    `Events: ${params.events.length}`,
  ];

  if (params.events.length > 0) {
    lines.push("Recent:");
    for (const event of params.events) {
      if (event.type === "collaboration.route.resolved") {
        lines.push(`- ${formatRouteEvent(event)}`);
        continue;
      }
      if (event.type === "collaboration.memory.published") {
        lines.push(`- ${formatMemoryPublishedEvent(event)}`);
        continue;
      }
      if (event.type === "collaboration.handoff.run.started") {
        lines.push(`- ${formatHandoffRunStartedEvent(event)}`);
      }
    }
  }

  return lines.join("\n");
}

function resolveAgentIdFromExplain(payload: CollaborationExplainPayload): string | undefined {
  return payload.route?.ownerAgentId;
}

export async function collaborationAuditCommand(
  opts: CollaborationAuditOptions,
  runtime: RuntimeEnv,
): Promise<void> {
  const explicitAgentId = opts.agent?.trim() || undefined;
  const userId = opts.user?.trim() || undefined;
  const filterTypeResult = parseFilterType(opts.type);
  if (!filterTypeResult.ok) {
    runtime.error(danger(filterTypeResult.reason));
    runtime.exit(1);
    return;
  }
  const filterType = filterTypeResult.value;
  const correlationId = opts.correlation?.trim() || undefined;
  const limitResult = parseLimit(opts.limit);
  if (!limitResult.ok) {
    runtime.error(danger(limitResult.reason));
    runtime.exit(1);
    return;
  }
  const normalizedLimit = limitResult.value;

  if (!explicitAgentId && !userId) {
    runtime.error(danger("Either --agent or --user is required"));
    runtime.exit(1);
    return;
  }

  try {
    const config = await requireValidConfigSnapshot(runtime);
    if (!config) {
      return;
    }

    const payload =
      explicitAgentId || !userId
        ? null
        : explainCollaborationConfig(config, {
            accountId: opts.account?.trim() || undefined,
            userId,
            channelId: opts.channel?.trim() || undefined,
            threadTs: opts.thread?.trim() || undefined,
          });

    const agentId = explicitAgentId ?? (payload ? resolveAgentIdFromExplain(payload) : undefined);
    if (!agentId) {
      runtime.error(
        danger("Unable to resolve an agent workspace for the requested collaboration surface"),
      );
      if (payload?.warnings.length) {
        for (const warning of payload.warnings) {
          runtime.error(`- ${warning.code}: ${warning.message}`);
        }
      }
      runtime.exit(1);
      return;
    }

    const ownerWorkspaceDir = resolveAgentWorkspaceDir(config, agentId)?.trim();
    if (!ownerWorkspaceDir) {
      runtime.error(danger(`Workspace not configured for agent "${agentId}"`));
      runtime.exit(1);
      return;
    }

    // After an enforced handoff the route event is written to the EFFECTIVE
    // agent's workspace, not the owner's. Always scan all candidate workspaces
    // (owner + handoff target agents in any space the agent owns) so that an
    // explicit --agent for the owner still surfaces continuation events.
    const candidateWorkspaces = new Set<string>([ownerWorkspaceDir]);
    const collaboration = config.collaboration;
    const candidateSpaceIds = new Set<string>();
    if (payload?.space?.spaceId) {
      candidateSpaceIds.add(payload.space.spaceId);
    }
    if (collaboration && agentId) {
      // For an explicit --agent, treat the agent as a potential owner: any
      // space whose ownerRole's defaultAgent equals this agent is in scope.
      for (const [spaceId, space] of Object.entries(collaboration.spaces)) {
        if (!space.ownerRole) continue;
        const ownerAgentForSpace = collaboration.roles?.[space.ownerRole]?.defaultAgentId;
        if (ownerAgentForSpace === agentId) {
          candidateSpaceIds.add(spaceId);
        }
      }
    }
    for (const spaceId of candidateSpaceIds) {
      const space = collaboration?.spaces?.[spaceId];
      for (const targetRoleId of space?.handoffs?.allowedTargets ?? []) {
        const targetAgentId = collaboration?.roles?.[targetRoleId]?.defaultAgentId;
        if (!targetAgentId) continue;
        const targetWorkspace = resolveAgentWorkspaceDir(config, targetAgentId)?.trim();
        if (targetWorkspace) {
          candidateWorkspaces.add(targetWorkspace);
        }
      }
    }
    // Read each workspace WITHOUT a per-workspace limit, then filter, sort, and
    // slice. Slicing pre-filter would let owner-side noise hide matching
    // continuation events sitting in a target workspace.
    const eventBatches = await Promise.all(
      [...candidateWorkspaces].map((workspaceDir) =>
        readCollaborationAuditEvents({ workspaceDir }),
      ),
    );
    const workspaceDir = ownerWorkspaceDir;
    let events = eventBatches.flat();

    if (filterType) {
      events = events.filter((event) => event.type === filterType);
    }

    if (userId) {
      events = events.filter(
        (event) => event.type !== "collaboration.route.resolved" || event.senderUserId === userId,
      );
    }
    if (opts.account?.trim()) {
      const accountId = opts.account.trim();
      events = events.filter(
        (event) => event.type !== "collaboration.route.resolved" || event.accountId === accountId,
      );
    }
    if (opts.channel?.trim()) {
      const channelId = opts.channel.trim();
      events = events.filter(
        (event) => event.type !== "collaboration.route.resolved" || event.channelId === channelId,
      );
    }
    if (opts.thread?.trim()) {
      const threadTs = opts.thread.trim();
      events = events.filter(
        (event) => event.type !== "collaboration.route.resolved" || event.threadTs === threadTs,
      );
    }
    if (correlationId) {
      events = events.filter(
        (event) =>
          (event.type === "collaboration.route.resolved" &&
            event.handoffCorrelationId === correlationId) ||
          (event.type === "collaboration.handoff.run.started" &&
            event.correlationId === correlationId),
      );
    }
    events = events
      .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
      .slice(-normalizedLimit);

    if (opts.json) {
      writeRuntimeJson(
        runtime,
        {
          agentId,
          workspaceDir,
          filterType: filterType ?? null,
          correlation: correlationId ?? null,
          events,
        },
        2,
      );
      return;
    }

    runtime.log(
      formatAuditText({
        agentId,
        workspaceDir,
        filterType,
        correlation: correlationId,
        events,
      }),
    );
  } catch (err) {
    runtime.error(danger(`Collaboration audit error: ${String(err)}`));
    runtime.exit(1);
  }
}
