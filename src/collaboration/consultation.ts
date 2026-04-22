export type CollaborationConsultationScope =
  | {
      kind: "project";
      scope: string;
    }
  | {
      kind: "role";
      scope: string;
    };

export type CollaborationConsultationRequest = {
  ownerAgentId: string;
  targetAgentId: string;
  question: string;
  threadSummary?: string;
  sharedScopes: CollaborationConsultationScope[];
};

export type CollaborationConsultationResult = {
  ownerAgentId: string;
  targetAgentId: string;
  answer: string;
};

function appendSharedScope(
  target: CollaborationConsultationScope[],
  next: CollaborationConsultationScope | null | undefined,
): void {
  if (!next?.scope) {
    return;
  }
  if (target.some((entry) => entry.scope === next.scope)) {
    return;
  }
  target.push(next);
}

export function buildConsultationRequest(params: {
  ownerAgentId: string;
  targetAgentId: string;
  question: string;
  threadSummary?: string;
  projectScope?: string | null;
  roleScope?: string | null;
  privateScope?: string | null;
}): CollaborationConsultationRequest {
  const sharedScopes: CollaborationConsultationScope[] = [];
  appendSharedScope(
    sharedScopes,
    params.projectScope
      ? {
          kind: "project",
          scope: params.projectScope,
        }
      : null,
  );
  appendSharedScope(
    sharedScopes,
    params.roleScope
      ? {
          kind: "role",
          scope: params.roleScope,
        }
      : null,
  );

  return {
    ownerAgentId: params.ownerAgentId,
    targetAgentId: params.targetAgentId,
    question: params.question,
    ...(params.threadSummary ? { threadSummary: params.threadSummary } : {}),
    sharedScopes,
  };
}

export function buildConsultationResult(params: {
  request: CollaborationConsultationRequest;
  answer: string;
}): CollaborationConsultationResult {
  return {
    ownerAgentId: params.request.ownerAgentId,
    targetAgentId: params.request.targetAgentId,
    answer: params.answer,
  };
}
