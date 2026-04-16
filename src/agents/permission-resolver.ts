export type PermissionContext = {
  chatType: "p2p" | "group";
  roleToolWhitelist: string[];
  orgDenyList: string[];
  groupAllowedTools?: string[];
};

import { DEFAULT_GROUP_SAFE_TOOLS } from "./group-tool-whitelist.js";

export function intersectToolSets(a: string[], b: string[]): string[] {
  const setB = new Set(b);
  return a.filter((tool) => setB.has(tool));
}

export function resolveToolPermissions(ctx: PermissionContext): string[] {
  // Step 1: Start with role whitelist
  let tools = [...ctx.roleToolWhitelist];

  // Step 2: Remove org-denied tools (org always wins)
  const denySet = new Set(ctx.orgDenyList);
  tools = tools.filter((t) => !denySet.has(t));

  // Step 3: For group chat, intersect with group allowed tools (降权)
  if (ctx.chatType === "group") {
    const groupAllowed = ctx.groupAllowedTools ?? DEFAULT_GROUP_SAFE_TOOLS;
    tools = intersectToolSets(tools, groupAllowed);
  }

  return tools;
}
