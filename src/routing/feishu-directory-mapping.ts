// Feishu address book → agent binding mapper.
// Transforms pre-fetched Feishu user data into OpenClaw binding rules
// for multi-tenant department-based agent routing.

export type FeishuUserInfo = {
  userId: string;
  name: string;
  department: string;
  jobTitle?: string;
};

export type DepartmentAgentMapping = {
  department: string; // exact string or regex pattern
  agentId: string;
};

export type FeishuBindingRule = {
  agentId: string;
  match: {
    channel: "feishu";
    peer: { kind: "direct"; id: string };
  };
};

/**
 * Map Feishu users to agent binding rules based on department mappings.
 * First matching department mapping wins; unmatched users get the default agent.
 * Deduplicates by userId so each user appears at most once.
 */
export function mapFeishuUsersToBindings(params: {
  users: FeishuUserInfo[];
  departmentMappings: DepartmentAgentMapping[];
  defaultAgentId: string;
}): FeishuBindingRule[] {
  const { users, departmentMappings, defaultAgentId } = params;

  // Pre-compile regex patterns. Patterns come from admin config, not user input.
  // Validate each pattern at compile time to catch invalid regex early.
  const compiled = departmentMappings.map((m) => {
    try {
      return { pattern: new RegExp(`^${m.department}$`), agentId: m.agentId };
    } catch {
      return { pattern: new RegExp(`^$`), agentId: m.agentId };
    }
  });

  const seen = new Set<string>();
  const bindings: FeishuBindingRule[] = [];

  for (const user of users) {
    if (seen.has(user.userId)) {
      continue;
    }
    seen.add(user.userId);

    // Find first matching department mapping
    const matched = compiled.find((c) => c.pattern.test(user.department));
    const agentId = matched?.agentId ?? defaultAgentId;

    bindings.push({
      agentId,
      match: {
        channel: "feishu",
        peer: { kind: "direct", id: user.userId },
      },
    });
  }

  return bindings;
}
