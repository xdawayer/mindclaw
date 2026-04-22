export type CollaborationHandoff = {
  ownerAgentId: string;
  nextAgentId: string;
  reason: string;
  requestedBy?: string;
};

export function createHandoff(params: {
  ownerAgentId: string;
  nextAgentId: string;
  reason: string;
  requestedBy?: string;
}): CollaborationHandoff {
  return {
    ownerAgentId: params.ownerAgentId,
    nextAgentId: params.nextAgentId,
    reason: params.reason,
    ...(params.requestedBy ? { requestedBy: params.requestedBy } : {}),
  };
}

export function applyHandoff(params: {
  currentOwnerAgentId: string;
  handoff: CollaborationHandoff;
}): string {
  if (params.handoff.ownerAgentId !== params.currentOwnerAgentId) {
    return params.currentOwnerAgentId;
  }
  return params.handoff.nextAgentId;
}
