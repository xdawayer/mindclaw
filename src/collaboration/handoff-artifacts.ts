import fs from "node:fs/promises";
import path from "node:path";
import { resolveAgentWorkspaceDir } from "../agents/agent-scope.js";
import type { OpenClawConfig } from "../config/types.js";
import {
  appendMemoryHostEvent,
  type MemoryHostCollaborationHandoffEvent,
} from "../memory-host-sdk/events.js";

export type PersistCollaborationHandoffArtifactParams = {
  cfg: OpenClawConfig;
  agentId: string;
  correlationId: string;
  depth: number;
  status: "accepted" | "rejected";
  trigger: "explicit_mention";
  sourceRole: string;
  targetRole: string;
  sourceAgentId: string;
  targetAgentId: string;
  targetBotId: string;
  effectiveAgentId: string;
  senderUserId: string;
  accountId: string;
  channelId?: string;
  threadTs?: string;
  messageTs?: string;
  spaceId?: string;
  reasonCode?: string;
  text?: string;
};

function resolveCreatedAtIso(messageTs?: string): string {
  const numericTs = Number(messageTs);
  if (Number.isFinite(numericTs) && numericTs > 0) {
    return new Date(numericTs * 1000).toISOString();
  }
  return new Date().toISOString();
}

function buildHandoffArtifactPath(createdAtIso: string, correlationId: string): string {
  return path.posix.join(
    "collaboration",
    "handoffs",
    createdAtIso.slice(0, 10),
    `${correlationId}.json`,
  );
}

function buildTextPreview(text?: string): string | undefined {
  const normalized = text?.trim().replace(/\s+/g, " ");
  if (!normalized) {
    return undefined;
  }
  return normalized.slice(0, 280);
}

function toAbsoluteWorkspacePath(workspaceDir: string, relativePath: string): string {
  return path.join(workspaceDir, ...relativePath.split("/"));
}

export async function persistCollaborationHandoffArtifact(
  params: PersistCollaborationHandoffArtifactParams,
): Promise<string | undefined> {
  const workspaceDir = resolveAgentWorkspaceDir(params.cfg, params.agentId)?.trim();
  if (!workspaceDir) {
    return undefined;
  }

  const createdAt = resolveCreatedAtIso(params.messageTs);
  const artifactPath = buildHandoffArtifactPath(createdAt, params.correlationId);
  const absoluteArtifactPath = toAbsoluteWorkspacePath(workspaceDir, artifactPath);
  const textPreview = buildTextPreview(params.text);
  const artifactBody = {
    correlationId: params.correlationId,
    depth: params.depth,
    createdAt,
    status: params.status,
    trigger: params.trigger,
    sourceRole: params.sourceRole,
    targetRole: params.targetRole,
    sourceAgentId: params.sourceAgentId,
    targetAgentId: params.targetAgentId,
    targetBotId: params.targetBotId,
    effectiveAgentId: params.effectiveAgentId,
    senderUserId: params.senderUserId,
    accountId: params.accountId,
    ...(params.channelId ? { channelId: params.channelId } : {}),
    ...(params.threadTs ? { threadTs: params.threadTs } : {}),
    ...(params.messageTs ? { messageTs: params.messageTs } : {}),
    ...(params.spaceId ? { spaceId: params.spaceId } : {}),
    ...(params.reasonCode ? { reasonCode: params.reasonCode } : {}),
    ...(textPreview ? { textPreview } : {}),
  };

  await fs.mkdir(path.dirname(absoluteArtifactPath), { recursive: true });
  await fs.writeFile(absoluteArtifactPath, `${JSON.stringify(artifactBody, null, 2)}\n`, "utf8");

  const event: MemoryHostCollaborationHandoffEvent = {
    type: "memory.collaboration.handoff",
    timestamp: createdAt,
    correlationId: params.correlationId,
    depth: params.depth,
    status: params.status,
    artifactPath,
    sourceRole: params.sourceRole,
    targetRole: params.targetRole,
    effectiveAgentId: params.effectiveAgentId,
    ...(params.reasonCode ? { reasonCode: params.reasonCode } : {}),
    ...(params.spaceId ? { spaceId: params.spaceId } : {}),
  };
  await appendMemoryHostEvent(workspaceDir, event);
  return artifactPath;
}
