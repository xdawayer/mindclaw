import { listUserMemoryFiles } from "./user-memory.js";

export type AuditContext = {
  requesterId: string;
  targetUserId: string;
  requesterRole: string;
  isAdmin?: boolean;
};

export type AuditLogEntry = {
  requesterId: string;
  targetUserId: string;
  action: string;
  denied: boolean;
  timestamp: string;
};

export type AuditListResult = {
  authorized: boolean;
  files: string[];
  auditEntry: AuditLogEntry | undefined;
};

export function canAuditUserMemory(ctx: AuditContext): boolean {
  // isAdmin flag is the source of truth (supports ceo, admin, any role with admin rights)
  // Fall back to role string "admin" for backwards compatibility
  return ctx.isAdmin === true || ctx.requesterRole === "admin";
}

export function buildAuditEntry(params: {
  requesterId: string;
  targetUserId: string;
  action: string;
  denied: boolean;
}): AuditLogEntry {
  return {
    ...params,
    timestamp: new Date().toISOString(),
  };
}

export async function auditListUserMemory(params: {
  requesterId: string;
  targetUserId: string;
  requesterRole: string;
  workspaceDir: string;
  agentId: string;
}): Promise<AuditListResult> {
  const authorized = canAuditUserMemory({
    requesterId: params.requesterId,
    targetUserId: params.targetUserId,
    requesterRole: params.requesterRole,
  });

  const auditEntry = buildAuditEntry({
    requesterId: params.requesterId,
    targetUserId: params.targetUserId,
    action: "list-user-memory",
    denied: !authorized,
  });

  if (!authorized) {
    return { authorized: false, files: [], auditEntry };
  }

  const files = await listUserMemoryFiles({
    workspaceDir: params.workspaceDir,
    userId: params.targetUserId,
    agentId: params.agentId,
  });

  return { authorized: true, files, auditEntry };
}
