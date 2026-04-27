import { resolveStorePath } from "../config/sessions/paths.js";
import { loadSessionStore } from "../config/sessions/store-load.js";
import type { SessionCollaborationMeta } from "../config/sessions/types.js";
import type { OpenClawConfig } from "../config/types.js";

export function readPersistedCollaborationSessionMeta(params: {
  cfg: OpenClawConfig;
  agentId: string;
  sessionKey: string;
}): SessionCollaborationMeta | undefined {
  const storePath = resolveStorePath(params.cfg.session?.store, {
    agentId: params.agentId,
  });
  const entry = loadSessionStore(storePath)[params.sessionKey];
  const collaboration = entry?.collaboration;
  if (!collaboration) {
    return undefined;
  }
  return {
    ...collaboration,
    readableScopes: [...collaboration.readableScopes],
    ...(collaboration.publishableScopes
      ? { publishableScopes: [...collaboration.publishableScopes] }
      : {}),
    ...(collaboration.handoff
      ? {
          handoff: {
            ...collaboration.handoff,
          },
        }
      : {}),
  };
}
