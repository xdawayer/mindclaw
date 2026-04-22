import {
  resolveProjectSpaceBySlackChannelId,
  resolveRoleSpaceBySlackChannelId,
} from "../collaboration/spaces.js";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import { normalizeOptionalString } from "../shared/string-coerce.js";
import { escapeRegExp } from "../utils.js";

export type SlackCollaborationMatchedBy =
  | "collaboration.project.default"
  | "collaboration.project.mention"
  | "collaboration.role";

export type ResolvedSlackCollaborationRoute = {
  agentId: string;
  matchedBy: SlackCollaborationMatchedBy;
};

type SlackCollaborationPeer = {
  kind: string;
  id: string;
};

function isSlackRoomPeer(
  peer: SlackCollaborationPeer | null | undefined,
): peer is SlackCollaborationPeer {
  return (peer?.kind === "channel" || peer?.kind === "group") && peer.id.length > 0;
}

function resolveRoleMentionIndex(text: string, roleId: string): number {
  const pattern = new RegExp(`(^|[^\\w-])@${escapeRegExp(roleId)}(?=$|[^\\w-])`, "i");
  return text.search(pattern);
}

function resolveExplicitRoleMention(params: {
  cfg: OpenClawConfig;
  messageText?: string | null;
}): string | null {
  if (!params.cfg.collaboration?.routing?.explicitMentionsOverride) {
    return null;
  }

  const text = normalizeOptionalString(params.messageText);
  if (!text) {
    return null;
  }

  const roles = params.cfg.collaboration?.spaces?.roles ?? {};
  let bestMatch: { roleId: string; index: number } | null = null;
  for (const roleId of Object.keys(roles).toSorted()) {
    const index = resolveRoleMentionIndex(text, roleId);
    if (index < 0) {
      continue;
    }
    if (!bestMatch || index < bestMatch.index) {
      bestMatch = { roleId, index };
    }
  }

  return bestMatch?.roleId ?? null;
}

export function resolveSlackCollaborationRoute(params: {
  cfg: OpenClawConfig;
  peer?: SlackCollaborationPeer | null;
  messageText?: string | null;
}): ResolvedSlackCollaborationRoute | null {
  if (!isSlackRoomPeer(params.peer)) {
    return null;
  }

  const roleSpace = resolveRoleSpaceBySlackChannelId(params.cfg, params.peer.id);
  if (roleSpace) {
    return {
      agentId: roleSpace.agentId,
      matchedBy: "collaboration.role",
    };
  }

  const projectSpace = resolveProjectSpaceBySlackChannelId(params.cfg, params.peer.id);
  if (!projectSpace) {
    return null;
  }

  const mentionedRoleId = resolveExplicitRoleMention({
    cfg: params.cfg,
    messageText: params.messageText,
  });
  if (mentionedRoleId) {
    const mentionedRoleSpace = params.cfg.collaboration?.spaces?.roles?.[mentionedRoleId];
    if (mentionedRoleSpace?.agentId) {
      return {
        agentId: mentionedRoleSpace.agentId,
        matchedBy: "collaboration.project.mention",
      };
    }
  }

  return {
    agentId: projectSpace.defaultAgent,
    matchedBy: "collaboration.project.default",
  };
}
