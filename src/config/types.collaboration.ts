export type CollaborationMode = "disabled" | "shadow" | "enforced";

export type CollaborationRoleId = string;
export type CollaborationBotId = string;
export type CollaborationSpaceId = string;
export type CollaborationIdentityId = string;
export type CollaborationSlackUserId = string;
export type CollaborationSlackChannelId = string;

export type CollaborationMemoryScope = "private" | "role_shared" | "space_shared";

export type CollaborationPermission =
  | "memory.read.private"
  | "memory.read.role_shared"
  | "memory.read.space_shared"
  | "memory.write.private"
  | "memory.publish.role_shared"
  | "memory.publish.space_shared"
  | "schedule.read"
  | "schedule.create"
  | "schedule.edit"
  | "schedule.delete"
  | "agent.handoff"
  | "agent.mention"
  | "exec.approve"
  | "config.edit";

export type CollaborationIdentityBinding = {
  identityId: CollaborationIdentityId;
  displayName?: string;
  roles: CollaborationRoleId[];
  defaultRole?: CollaborationRoleId;
  scheduleDelivery?: {
    preferDm?: boolean;
    fallbackBotId?: CollaborationBotId;
  };
};

export type CollaborationIdentitiesConfig = {
  users: Record<CollaborationSlackUserId, CollaborationIdentityBinding>;
};

export type CollaborationBotConfig = {
  slackAccountId: string;
  agentId: string;
  role: CollaborationRoleId;
  displayName?: string;
  identityStyle?: "role" | "agent";
  allowedSpaces?: CollaborationSpaceId[];
  canInitiateHandoffs?: boolean;
  canReceiveHandoffs?: boolean;
};

export type CollaborationRoleConfig = {
  defaultAgentId: string;
  defaultBotId: CollaborationBotId;
  permissions: CollaborationPermission[];
  memoryPolicy?: {
    defaultWriteScope?: CollaborationMemoryScope;
    readableScopes?: CollaborationMemoryScope[];
    publishableScopes?: Exclude<CollaborationMemoryScope, "private">[];
  };
  schedulePolicy?: {
    canCreate?: boolean;
    canEdit?: boolean;
    canDelete?: boolean;
    allowedAudienceKinds?: Array<"identity" | "role" | "space">;
    allowPrivateDigest?: boolean;
  };
};

export type CollaborationDeliveryTarget =
  | { kind: "slack_dm"; identityId?: CollaborationIdentityId; roleId?: CollaborationRoleId }
  | { kind: "slack_channel"; channelId: CollaborationSlackChannelId }
  | { kind: "space_default"; spaceId: CollaborationSpaceId };

export type CollaborationSpaceConfig = {
  kind: "dm" | "role" | "project";
  displayName?: string;
  ownerRole?: CollaborationRoleId;
  memberRoles?: CollaborationRoleId[];
  slack?: {
    channels?: CollaborationSlackChannelId[];
    users?: CollaborationSlackUserId[];
    requireMention?: boolean;
    replyThreadMode?: "owner" | "free" | "strict_owner";
    allowBotMessages?: "none" | "handoff_only";
  };
  memory?: {
    sharedScopeId?: string;
    readableByRoles?: CollaborationRoleId[];
    writableByRoles?: CollaborationRoleId[];
    publishRequires?: CollaborationPermission[];
  };
  handoffs?: {
    allowedTargets?: CollaborationRoleId[];
    requireExplicitMention?: boolean;
    maxDepth?: number;
  };
  schedules?: {
    allowed?: boolean;
    defaultDestinations?: CollaborationDeliveryTarget[];
    quietHours?: {
      tz: string;
      start: string;
      end: string;
    };
  };
};

export type CollaborationMemoryConfig = {
  scopes?: {
    private?: { default?: boolean };
    role_shared?: { partitionBy: "role" };
    space_shared?: { partitionBy: "space" };
  };
  rules?: {
    requireProvenance?: boolean;
    requireExplicitPublish?: boolean;
    denyGlobalSearchByDefault?: boolean;
  };
};

export type CollaborationRoutingConfig = {
  ownerSelection?: {
    dm?: "identity_default_role";
    role?: "space_owner_role";
    project?: "space_owner_role";
  };
  mentionRouting?: {
    explicitAgentMention?: boolean;
    fallbackToOwner?: boolean;
  };
  handoff?: {
    mode?: "structured";
    dedupeWindow?: string;
    maxDepth?: number;
    allowBotAuthoredReentry?: boolean;
  };
};

export type CollaborationScheduleAudience =
  | { kind: "identity"; id: CollaborationIdentityId }
  | { kind: "role"; id: CollaborationRoleId }
  | { kind: "space"; id: CollaborationSpaceId };

export type CollaborationScheduleJob = {
  id: string;
  enabled?: boolean;
  audience: CollaborationScheduleAudience;
  sourceSpaces: CollaborationSpaceId[];
  at?: string;
  every?: string;
  cron?: string;
  tz?: string;
  delivery: CollaborationDeliveryTarget[];
  memoryReadScopes?: CollaborationMemoryScope[];
  template?: string;
  systemPrompt?: string;
  ownerRole?: CollaborationRoleId;
};

export type CollaborationSchedulesConfig = {
  jobs: CollaborationScheduleJob[];
};

export type CollaborationApprovalPolicy = {
  when: string[];
  approverRoles: CollaborationRoleId[];
  delivery: Array<"dm" | "origin_thread">;
  visibility?: "summary_only" | "full_context";
  agentFilter?: string[];
  spaceFilter?: CollaborationSpaceId[];
};

export type CollaborationApprovalConfig = {
  policies: Record<string, CollaborationApprovalPolicy>;
};

export type CollaborationAuditConfig = {
  enabled?: boolean;
  retainDays?: number;
  redactBodies?: boolean;
  explainMode?: boolean;
};

export type CollaborationConfig = {
  version: 1;
  mode?: CollaborationMode;
  identities: CollaborationIdentitiesConfig;
  bots: Record<CollaborationBotId, CollaborationBotConfig>;
  roles: Record<CollaborationRoleId, CollaborationRoleConfig>;
  spaces: Record<CollaborationSpaceId, CollaborationSpaceConfig>;
  memory?: CollaborationMemoryConfig;
  routing?: CollaborationRoutingConfig;
  schedules?: CollaborationSchedulesConfig;
  approvals?: CollaborationApprovalConfig;
  audit?: CollaborationAuditConfig;
};
