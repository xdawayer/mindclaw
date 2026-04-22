export type CollaborationSpaceKind = "private" | "project" | "role";

export type CollaborationPrivateSpace = {
  kind: "private";
  userId: string;
  scope: string;
};

export type CollaborationProjectSpace = {
  kind: "project";
  id: string;
  channelId: string;
  defaultAgent: string;
  defaultDmRecipient: string;
  roleDmRecipients: Record<string, string>;
  scope: string;
};

export type CollaborationRoleSpace = {
  kind: "role";
  id: string;
  channelId: string;
  agentId: string;
  scope: string;
};

export type CollaborationSpace =
  | CollaborationPrivateSpace
  | CollaborationProjectSpace
  | CollaborationRoleSpace;
