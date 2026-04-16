import {
  listRegisteredUsers,
  type UserRegistryEntry,
  type UserRegistry,
} from "./user-registry-mt.js";

export type UserMdInput = Pick<
  UserRegistryEntry,
  "userId" | "displayName" | "roleId" | "teamId" | "isAdmin"
> & {
  language?: string;
};

export function generateTeamRoster(registry: UserRegistry): string {
  const users = listRegisteredUsers(registry);
  if (users.length === 0) {
    return "# 团队名册\n\n暂无注册成员。\n";
  }

  const lines = [
    "# 团队名册",
    "",
    "当你收到消息时，根据 SenderName 或 SenderId 匹配下方名册，了解发言人的身份和偏好。",
    "",
    "| userId | 姓名 | 角色 | 团队 | 管理员 |",
    "|--------|------|------|------|--------|",
  ];

  for (const u of users) {
    const admin = u.isAdmin ? "是" : "否";
    const escapePipe = (s: string) => s.replace(/\|/g, "\\|");
    lines.push(
      `| ${escapePipe(u.userId)} | ${escapePipe(u.displayName)} | ${escapePipe(u.roleId)} | ${escapePipe(u.teamId)} | ${admin} |`,
    );
  }

  lines.push("");
  return lines.join("\n");
}

export function generateUserMd(input: UserMdInput): string {
  const lines = [
    "# USER.md - About Your Human",
    "",
    `- **Name:** ${input.displayName}`,
    `- **What to call them:** ${input.displayName}`,
    "- **Timezone:** Asia/Shanghai (UTC+8)",
  ];

  if (input.language) {
    lines.push(`- **Language:** ${input.language}`);
  }

  lines.push("");
  lines.push("## 角色");
  lines.push("");

  if (input.isAdmin) {
    lines.push(`${input.roleId.toUpperCase()} / 创始人。团队：${input.teamId}。`);
    lines.push(
      `团队角色：${input.roleId.toUpperCase()}（isAdmin，拥有所有工具和团队的完整访问权限）。`,
    );
  } else {
    lines.push(`${input.roleId}。团队：${input.teamId}。`);
  }

  lines.push("");
  lines.push("## 偏好");
  lines.push("");
  lines.push("- 简明扼要，直接给结论");
  lines.push("- 安全第一");
  lines.push("");

  return lines.join("\n");
}

export type AgentEntry = {
  id: string;
  name?: string;
  workspace: string;
};

export type BindingEntry = {
  agentId: string;
  match: {
    channel: string;
    peer: { kind: string; id: string };
  };
};

export function buildPerUserAgentEntries(registry: UserRegistry): {
  agents: AgentEntry[];
  bindings: BindingEntry[];
} {
  const users = listRegisteredUsers(registry);
  const agents: AgentEntry[] = [];
  const bindings: BindingEntry[] = [];

  for (const u of users) {
    const agentId = `feishu-${u.userId}`;
    agents.push({
      id: agentId,
      name: `小虾米`,
      workspace: `~/.openclaw/workspace-${agentId}`,
    });
    bindings.push({
      agentId,
      match: {
        channel: "feishu",
        peer: { kind: "direct", id: u.userId },
      },
    });
  }

  return { agents, bindings };
}
