import type { PrefixMapping } from "../routing/command-prefix-routing.js";

export type SpecializedAgent = {
  id: string;
  name: string;
  description: string;
  commandPrefixes: string[];
  toolIds: string[];
  /** Teams this agent is bound to. Empty array or ["*"] means available to all teams. */
  teamBindings: string[];
};

const DEFAULT_AGENTS: SpecializedAgent[] = [
  {
    id: "writing",
    name: "写作 Agent",
    description: "Document writing, editing, and formatting",
    commandPrefixes: ["写作", "write", "writing"],
    toolIds: ["doc-gen", "search", "template-render"],
    teamBindings: ["*"],
  },
  {
    id: "data-analysis",
    name: "数据分析 Agent",
    description: "Data queries, visualization, and reporting",
    commandPrefixes: ["数据", "data", "analysis"],
    toolIds: ["data-query", "data-analysis", "search"],
    teamBindings: ["*"],
  },
  {
    id: "scheduling",
    name: "排期 Agent",
    description: "Project scheduling, task tracking, and timeline management",
    commandPrefixes: ["排期", "schedule", "plan"],
    toolIds: ["schedule", "calendar", "search"],
    teamBindings: ["*"],
  },
  {
    id: "knowledge",
    name: "知识检索 Agent",
    description: "Knowledge base search and Q&A",
    commandPrefixes: ["知识", "knowledge", "kb", "search"],
    toolIds: ["search", "rag-query"],
    teamBindings: ["*"],
  },
  {
    id: "sales-assistant",
    name: "销售助手 Agent",
    description: "CRM queries, sales scripts, and customer follow-up",
    commandPrefixes: ["销售", "sales", "crm"],
    toolIds: ["crm-query", "script-library", "email-gen", "search"],
    teamBindings: ["sales"],
  },
];

export function getDefaultAgents(): SpecializedAgent[] {
  return DEFAULT_AGENTS.map((a) => ({
    ...a,
    commandPrefixes: [...a.commandPrefixes],
    toolIds: [...a.toolIds],
    teamBindings: [...a.teamBindings],
  }));
}

export function getAgentById(id: string, agents: SpecializedAgent[]): SpecializedAgent | undefined {
  return agents.find((a) => a.id === id);
}

export function getAgentPrefixMappings(agents: SpecializedAgent[]): PrefixMapping[] {
  const mappings: PrefixMapping[] = [];
  for (const agent of agents) {
    for (const prefix of agent.commandPrefixes) {
      mappings.push({ prefix, agentId: agent.id });
    }
  }
  return mappings;
}

export function getAgentsByTeam(teamId: string, agents: SpecializedAgent[]): SpecializedAgent[] {
  return agents.filter((a) => a.teamBindings.includes("*") || a.teamBindings.includes(teamId));
}
