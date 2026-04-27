import fs from "node:fs/promises";
import path from "node:path";
import { resolveAgentWorkspaceDir } from "../agents/agent-scope.js";
import type { OpenClawConfig } from "../config/types.js";

export const COLLABORATION_AUDIT_LOG_RELATIVE_PATH = path.posix.join(
  "collaboration",
  ".audit",
  "events.jsonl",
);

export type CollaborationRouteResolvedAuditEvent = {
  type: "collaboration.route.resolved";
  timestamp: string;
  surface: "slack";
  mode: "shadow" | "enforced";
  accountId: string;
  senderUserId: string;
  channelId?: string;
  threadTs?: string;
  spaceId?: string;
  legacyAgentId: string;
  collaborationAgentId?: string;
  effectiveAgentId?: string;
  handoffStatus?: "accepted" | "rejected";
  handoffTargetRole?: string;
  handoffCorrelationId?: string;
  handoffDepth?: number;
  handoffArtifactPath?: string;
  memoryReadableScopes?: Array<"private" | "role_shared" | "space_shared">;
  routeChanged: boolean;
  warningCodes: string[];
};

export type CollaborationMemoryPublishedAuditEvent = {
  type: "collaboration.memory.published";
  timestamp: string;
  source: "memory_publish";
  scope: "role_shared" | "space_shared";
  path: string;
  effectiveRole?: string;
  spaceId?: string;
};

export type CollaborationHandoffRunStartedAuditEvent = {
  type: "collaboration.handoff.run.started";
  timestamp: string;
  correlationId: string;
  runId: string;
  taskId: string;
  ownerSessionKey: string;
  childSessionKey: string;
  agentId: string;
  sourceRole?: string;
  targetRole: string;
};

export type CollaborationAuditEvent =
  | CollaborationRouteResolvedAuditEvent
  | CollaborationMemoryPublishedAuditEvent
  | CollaborationHandoffRunStartedAuditEvent;

export function resolveCollaborationAuditLogPath(workspaceDir: string): string {
  return path.join(workspaceDir, COLLABORATION_AUDIT_LOG_RELATIVE_PATH);
}

export async function appendCollaborationAuditEvent(
  workspaceDir: string,
  event: CollaborationAuditEvent,
): Promise<void> {
  const eventLogPath = resolveCollaborationAuditLogPath(workspaceDir);
  await fs.mkdir(path.dirname(eventLogPath), { recursive: true });
  await fs.appendFile(eventLogPath, `${JSON.stringify(event)}\n`, "utf8");
}

export async function appendCollaborationAuditEventForAgent(params: {
  cfg: OpenClawConfig;
  agentId: string;
  event: CollaborationAuditEvent;
}): Promise<string | undefined> {
  const workspaceDir = resolveAgentWorkspaceDir(params.cfg, params.agentId)?.trim();
  if (!workspaceDir) {
    return undefined;
  }
  await appendCollaborationAuditEvent(workspaceDir, params.event);
  return COLLABORATION_AUDIT_LOG_RELATIVE_PATH;
}

export async function readCollaborationAuditEvents(params: {
  workspaceDir: string;
  limit?: number;
}): Promise<CollaborationAuditEvent[]> {
  const eventLogPath = resolveCollaborationAuditLogPath(params.workspaceDir);
  const raw = await fs.readFile(eventLogPath, "utf8").catch((err: unknown) => {
    if ((err as NodeJS.ErrnoException)?.code === "ENOENT") {
      return "";
    }
    throw err;
  });
  if (!raw.trim()) {
    return [];
  }
  const events = raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line) as CollaborationAuditEvent];
      } catch {
        return [];
      }
    });
  if (!Number.isFinite(params.limit)) {
    return events;
  }
  const limit = Math.max(0, Math.floor(params.limit as number));
  return limit === 0 ? [] : events.slice(-limit);
}
