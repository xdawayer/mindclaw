// Narrow collaboration explain/runtime helpers for bundled channel plugins.

export {
  buildAgentMainSessionKey,
  buildAgentSessionKey,
  deriveLastRoutePolicy,
  sanitizeAgentId,
  type RoutePeer,
} from "./routing.js";
export {
  explainCollaborationConfig,
  type CollaborationExplainParams,
  type CollaborationExplainPayload,
  type CollaborationExplainWarning,
} from "../collaboration/runtime.js";
export { readPersistedCollaborationSessionMeta } from "../collaboration/session-meta.js";
export { persistCollaborationHandoffArtifact } from "../collaboration/handoff-artifacts.js";
export { registerCollaborationHandoffRun } from "../collaboration/handoff-task.js";
export {
  COLLABORATION_AUDIT_LOG_RELATIVE_PATH,
  appendCollaborationAuditEventForAgent,
  readCollaborationAuditEvents,
  type CollaborationAuditEvent,
  type CollaborationHandoffRunStartedAuditEvent,
  type CollaborationMemoryPublishedAuditEvent,
  type CollaborationRouteResolvedAuditEvent,
} from "../collaboration/audit.js";
export {
  hasManagedCollaborationApprovalContext,
  resolveCollaborationApprovalApproverUserIds,
  resolveCollaborationExecApprovalPolicy,
  type CollaborationExecApprovalResolution,
} from "../collaboration/approval-policy.js";
