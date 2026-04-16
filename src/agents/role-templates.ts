export type RoleTemplate = {
  id: string;
  description: string;
  toolWhitelist: string[];
  defaultWorkflow?: string[];
};

const DEFAULT_ROLES: RoleTemplate[] = [
  {
    id: "pm",
    description: "Product Manager: docs, scheduling, data queries",
    toolWhitelist: ["doc-gen", "schedule", "data-query", "search"],
    defaultWorkflow: ["requirement-analysis", "prd-gen", "scheduling"],
  },
  {
    id: "engineer",
    description: "Engineer: code execution, shell, git, database",
    toolWhitelist: ["exec", "bash", "git", "database", "search"],
    defaultWorkflow: ["bug-analysis", "code-fix", "review"],
  },
  {
    id: "sales",
    description: "Sales: CRM, scripts, email generation",
    toolWhitelist: ["crm-query", "script-library", "email-gen", "search"],
    defaultWorkflow: ["customer-research", "script-match", "followup"],
  },
  {
    id: "ops",
    description: "Operations: data analysis, content gen, social media",
    toolWhitelist: ["data-analysis", "content-gen", "social-media", "search"],
    defaultWorkflow: ["data-pull", "analysis", "content-output"],
  },
];

export function getDefaultRoles(): RoleTemplate[] {
  return [...DEFAULT_ROLES];
}

export function getRoleById(id: string, roles: RoleTemplate[]): RoleTemplate | undefined {
  return roles.find((r) => r.id === id);
}

export function getRoleToolWhitelist(roleId: string, roles: RoleTemplate[]): string[] {
  const role = getRoleById(roleId, roles);
  return role ? [...role.toolWhitelist] : [];
}

type UserInfo = {
  jobTitle: string;
  department: string;
};

const TITLE_PATTERNS: [RegExp, string][] = [
  [/产品|product/i, "pm"],
  [/工程|engineer|开发|dev/i, "engineer"],
  [/销售|sales|商务/i, "sales"],
  [/运营|ops|operation/i, "ops"],
];

const DEPT_PATTERNS: [RegExp, string][] = [
  [/产品|product/i, "pm"],
  [/工程|engineer|技术|dev/i, "engineer"],
  [/销售|sales|商务/i, "sales"],
  [/运营|ops|operation/i, "ops"],
];

export function resolveRoleForUser(info: UserInfo): string {
  for (const [pattern, roleId] of TITLE_PATTERNS) {
    if (pattern.test(info.jobTitle)) {
      return roleId;
    }
  }
  for (const [pattern, roleId] of DEPT_PATTERNS) {
    if (pattern.test(info.department)) {
      return roleId;
    }
  }
  return "default";
}
