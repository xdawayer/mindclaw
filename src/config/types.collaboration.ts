export type CollaborationUserIdentityConfig = {
  roles?: string[];
  slackGroups?: string[];
};

export type CollaborationIdentitiesConfig = {
  users?: Record<string, CollaborationUserIdentityConfig>;
};

export type CollaborationProjectSpaceConfig = {
  channelId: string;
  defaultAgent: string;
  defaultDmRecipient: string;
  roleDmRecipients?: Record<string, string>;
};

export type CollaborationRoleSpaceConfig = {
  channelId: string;
  agentId: string;
};

export type CollaborationSpacesConfig = {
  projects?: Record<string, CollaborationProjectSpaceConfig>;
  roles?: Record<string, CollaborationRoleSpaceConfig>;
};

export type CollaborationRoutingConfig = {
  explicitMentionsOverride?: boolean;
  autoClassifyWhenUnspecified?: boolean;
  stickyThreadOwner?: boolean;
  internalConsultationChangesOwner?: boolean;
};

export type CollaborationDmToSharedSyncConfig = {
  mode?: "request-approval";
  approver?: string;
};

export type CollaborationSyncConfig = {
  dmToShared?: CollaborationDmToSharedSyncConfig;
};

export type CollaborationConfig = {
  identities?: CollaborationIdentitiesConfig;
  spaces?: CollaborationSpacesConfig;
  routing?: CollaborationRoutingConfig;
  sync?: CollaborationSyncConfig;
};
