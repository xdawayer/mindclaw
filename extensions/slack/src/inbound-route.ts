import {
  resolveAgentRoute,
  type RoutePeer,
} from "openclaw/plugin-sdk/routing";
import type { OpenClawConfig } from "./channel-api.js";

export function resolveSlackInboundRoute(params: {
  cfg: OpenClawConfig;
  accountId?: string | null;
  teamId?: string | null;
  peer: RoutePeer;
  messageText?: string | null;
}) {
  return resolveAgentRoute({
    cfg: params.cfg,
    channel: "slack",
    accountId: params.accountId,
    teamId: params.teamId,
    peer: params.peer,
    messageText: params.messageText,
  });
}
