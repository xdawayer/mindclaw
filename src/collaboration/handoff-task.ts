import type { OpenClawConfig } from "../config/types.js";
import { createRunningTaskRun } from "../tasks/task-executor.js";
import { appendCollaborationAuditEventForAgent } from "./audit.js";

const COLLABORATION_HANDOFF_TASK_KIND = "collaboration_handoff";
const COLLABORATION_HANDOFF_TASK_LABEL = "Collaboration handoff";

export async function registerCollaborationHandoffRun(params: {
  cfg: OpenClawConfig;
  runId: string;
  agentId: string;
  ownerSessionKey: string;
  childSessionKey: string;
  correlationId: string;
  sourceRole: string;
  targetRole: string;
  startedAt?: number;
}): Promise<{ taskId: string; auditPath?: string }> {
  const startedAt = params.startedAt ?? Date.now();
  const task = createRunningTaskRun({
    runtime: "subagent",
    taskKind: COLLABORATION_HANDOFF_TASK_KIND,
    sourceId: params.correlationId,
    requesterSessionKey: params.ownerSessionKey,
    ownerKey: params.ownerSessionKey,
    scopeKind: "session",
    childSessionKey: params.childSessionKey,
    agentId: params.agentId,
    runId: params.runId,
    label: COLLABORATION_HANDOFF_TASK_LABEL,
    task: `Slack collaboration handoff to ${params.targetRole}`,
    preferMetadata: true,
    notifyPolicy: "done_only",
    deliveryStatus: "pending",
    startedAt,
    lastEventAt: startedAt,
  });

  const auditPath = await appendCollaborationAuditEventForAgent({
    cfg: params.cfg,
    agentId: params.agentId,
    event: {
      type: "collaboration.handoff.run.started",
      timestamp: new Date(startedAt).toISOString(),
      correlationId: params.correlationId,
      runId: params.runId,
      taskId: task.taskId,
      ownerSessionKey: params.ownerSessionKey,
      childSessionKey: params.childSessionKey,
      agentId: params.agentId,
      sourceRole: params.sourceRole,
      targetRole: params.targetRole,
    },
  });

  return {
    taskId: task.taskId,
    ...(auditPath ? { auditPath } : {}),
  };
}
