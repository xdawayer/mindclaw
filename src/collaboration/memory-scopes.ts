import type { OpenClawConfig } from "../config/types.openclaw.js";
import { resolvePrivateSpaceForSlackUser, resolveSlackSpaceByChannelId } from "./spaces.js";

export type CollaborationMemoryScope =
  | {
      kind: "private";
      scope: string;
      slackUserId: string;
    }
  | {
      kind: "project";
      scope: string;
      projectId: string;
      slackChannelId: string;
    }
  | {
      kind: "role";
      scope: string;
      roleId: string;
      slackChannelId: string;
    };

export function resolveCollaborationMemoryScope(params: {
  cfg?: OpenClawConfig;
  slackChannelType?: "direct" | "channel" | "group";
  slackChannelId?: string | null;
  slackUserId?: string | null;
}): CollaborationMemoryScope | null {
  if (params.slackChannelType === "direct") {
    const space = resolvePrivateSpaceForSlackUser(params.slackUserId);
    return space
      ? {
          kind: "private",
          scope: space.scope,
          slackUserId: space.userId,
        }
      : null;
  }

  if (params.slackChannelType !== "channel" && params.slackChannelType !== "group") {
    return null;
  }

  const space = resolveSlackSpaceByChannelId(params.cfg, params.slackChannelId);
  if (!space) {
    return null;
  }
  if (space.kind === "project") {
    return {
      kind: "project",
      scope: space.scope,
      projectId: space.id,
      slackChannelId: space.channelId,
    };
  }
  return {
    kind: "role",
    scope: space.scope,
    roleId: space.id,
    slackChannelId: space.channelId,
  };
}
