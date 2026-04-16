export type PrefixMapping = {
  prefix: string;
  agentId: string;
};

export type ParsedPrefix = {
  prefix: string;
  rest: string;
};

const PREFIX_RE = /^\/([a-zA-Z\u4e00-\u9fff]+)(?:\s+(.*))?$/;

export function parseCommandPrefix(message: string): ParsedPrefix | null {
  const trimmed = message.trim();
  if (!trimmed) {
    return null;
  }

  const match = PREFIX_RE.exec(trimmed);
  if (!match) {
    return null;
  }

  return {
    prefix: match[1],
    rest: (match[2] ?? "").trim(),
  };
}

export function resolveAgentByPrefix(
  prefix: string,
  mappings: PrefixMapping[],
): string | undefined {
  const lower = prefix.toLowerCase();
  const mapping = mappings.find((m) => m.prefix.toLowerCase() === lower);
  return mapping?.agentId;
}
