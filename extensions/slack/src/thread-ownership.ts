import type { ResolvedAgentRoute } from "openclaw/plugin-sdk/routing";
import {
  readSlackThreadOwnership,
  touchSlackThreadOwnership,
  writeSlackThreadOwnership,
  type SlackThreadOwnershipRecord,
} from "./thread-ownership.store.js";

export type SlackThreadOwnershipResolution = {
  route: ResolvedAgentRoute;
  ownership: SlackThreadOwnershipRecord | null;
};

export function resolveSlackThreadOwnedRoute(params: {
  route: ResolvedAgentRoute;
  isThreadReply: boolean;
  accountId?: string | null;
  channelId: string;
  threadTs?: string;
  buildRouteForAgent: (
    agentId: string,
    matchedBy: ResolvedAgentRoute["matchedBy"],
  ) => ResolvedAgentRoute;
}): SlackThreadOwnershipResolution {
  if (!params.isThreadReply || !params.threadTs) {
    return {
      route: params.route,
      ownership: null,
    };
  }

  const shouldPinOwner =
    params.route.matchedBy === "collaboration.project.default" ||
    params.route.matchedBy === "collaboration.project.mention" ||
    params.route.matchedBy === "collaboration.role";
  if (!shouldPinOwner) {
    return {
      route: params.route,
      ownership: null,
    };
  }

  if (params.route.matchedBy === "collaboration.project.mention") {
    const ownership = writeSlackThreadOwnership({
      accountId: params.accountId,
      channelId: params.channelId,
      threadTs: params.threadTs,
      ownerAgentId: params.route.agentId,
      explicitSwitch: true,
    });
    return {
      route: params.route,
      ownership,
    };
  }

  const existing = readSlackThreadOwnership({
    accountId: params.accountId,
    channelId: params.channelId,
    threadTs: params.threadTs,
  });
  if (existing) {
    touchSlackThreadOwnership({
      accountId: params.accountId,
      channelId: params.channelId,
      threadTs: params.threadTs,
    });
    return {
      route: params.buildRouteForAgent(existing.ownerAgentId, "collaboration.thread.owner"),
      ownership: existing,
    };
  }

  const ownership = writeSlackThreadOwnership({
    accountId: params.accountId,
    channelId: params.channelId,
    threadTs: params.threadTs,
    ownerAgentId: params.route.agentId,
  });
  return {
    route: params.route,
    ownership,
  };
}
