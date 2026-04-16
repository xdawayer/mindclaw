export type GroupToolPolicy = {
  groupId: string;
  allowedTools: string[];
};

export const DEFAULT_GROUP_SAFE_TOOLS: string[] = ["search", "doc-gen", "knowledge"];

/**
 * Resolve which tools are allowed in a specific group chat.
 * Falls back to DEFAULT_GROUP_SAFE_TOOLS when no policy matches.
 * Always ensures "search" is included as a baseline safe tool.
 */
export function resolveGroupAllowedTools(groupId: string, policies: GroupToolPolicy[]): string[] {
  const lower = groupId.toLowerCase();
  const match = policies.find((p) => p.groupId.toLowerCase() === lower);

  if (!match) {
    return [...DEFAULT_GROUP_SAFE_TOOLS];
  }

  const tools = new Set(match.allowedTools);
  // search is always safe
  tools.add("search");
  return [...tools];
}
