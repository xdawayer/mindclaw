import { describe, expect, it } from "vitest";
import {
  type FeishuUserInfo,
  type DepartmentAgentMapping,
  mapFeishuUsersToBindings,
} from "./feishu-directory-mapping.js";

const salesAgent = "agent-sales";
const engAgent = "agent-engineering";
const defaultAgent = "agent-default";

const baseMappings: DepartmentAgentMapping[] = [
  { department: "销售部", agentId: salesAgent },
  { department: "工程部", agentId: engAgent },
];

function makeUser(overrides: Partial<FeishuUserInfo> & { userId: string }): FeishuUserInfo {
  return {
    name: "Test User",
    department: "未分配",
    ...overrides,
  };
}

describe("mapFeishuUsersToBindings", () => {
  it("maps user in 销售部 to sales agent", () => {
    const users = [makeUser({ userId: "ou_user_001", department: "销售部" })];
    const result = mapFeishuUsersToBindings({
      users,
      departmentMappings: baseMappings,
      defaultAgentId: defaultAgent,
    });

    expect(result).toEqual([
      {
        agentId: salesAgent,
        match: { channel: "feishu", peer: { kind: "direct", id: "ou_user_001" } },
      },
    ]);
  });

  it("maps user in 工程部 to engineering agent", () => {
    const users = [makeUser({ userId: "ou_user_002", department: "工程部" })];
    const result = mapFeishuUsersToBindings({
      users,
      departmentMappings: baseMappings,
      defaultAgentId: defaultAgent,
    });

    expect(result).toEqual([
      {
        agentId: engAgent,
        match: { channel: "feishu", peer: { kind: "direct", id: "ou_user_002" } },
      },
    ]);
  });

  it("falls back to default agent for unmapped department", () => {
    const users = [makeUser({ userId: "ou_user_003", department: "法务部" })];
    const result = mapFeishuUsersToBindings({
      users,
      departmentMappings: baseMappings,
      defaultAgentId: defaultAgent,
    });

    expect(result).toEqual([
      {
        agentId: defaultAgent,
        match: { channel: "feishu", peer: { kind: "direct", id: "ou_user_003" } },
      },
    ]);
  });

  it("returns empty bindings for empty user list", () => {
    const result = mapFeishuUsersToBindings({
      users: [],
      departmentMappings: baseMappings,
      defaultAgentId: defaultAgent,
    });

    expect(result).toEqual([]);
  });

  it("maps multiple users in same department to same agent", () => {
    const users = [
      makeUser({ userId: "ou_user_010", name: "Alice", department: "销售部" }),
      makeUser({ userId: "ou_user_011", name: "Bob", department: "销售部" }),
    ];
    const result = mapFeishuUsersToBindings({
      users,
      departmentMappings: baseMappings,
      defaultAgentId: defaultAgent,
    });

    expect(result).toHaveLength(2);
    expect(result[0].agentId).toBe(salesAgent);
    expect(result[1].agentId).toBe(salesAgent);
    expect(result[0].match.peer.id).toBe("ou_user_010");
    expect(result[1].match.peer.id).toBe("ou_user_011");
  });

  it("supports regex department matching", () => {
    const regexMappings: DepartmentAgentMapping[] = [{ department: "销售.*", agentId: salesAgent }];
    const users = [
      makeUser({ userId: "ou_user_020", department: "销售一部" }),
      makeUser({ userId: "ou_user_021", department: "销售二部" }),
      makeUser({ userId: "ou_user_022", department: "工程部" }),
    ];
    const result = mapFeishuUsersToBindings({
      users,
      departmentMappings: regexMappings,
      defaultAgentId: defaultAgent,
    });

    expect(result[0].agentId).toBe(salesAgent);
    expect(result[1].agentId).toBe(salesAgent);
    // Unmatched department falls back to default
    expect(result[2].agentId).toBe(defaultAgent);
  });

  it("handles invalid regex pattern in department mapping gracefully", () => {
    const badMappings: DepartmentAgentMapping[] = [
      { department: "(unclosed", agentId: salesAgent },
      { department: "工程部", agentId: engAgent },
    ];
    const users = [
      makeUser({ userId: "ou_user_040", department: "(unclosed" }),
      makeUser({ userId: "ou_user_041", department: "工程部" }),
    ];
    // Should not throw, invalid pattern just won't match
    const result = mapFeishuUsersToBindings({
      users,
      departmentMappings: badMappings,
      defaultAgentId: defaultAgent,
    });
    expect(result).toHaveLength(2);
    // Invalid regex falls back to empty pattern, won't match anything
    expect(result[0].agentId).toBe(defaultAgent);
    // Valid mapping still works
    expect(result[1].agentId).toBe(engAgent);
  });

  it("does not create duplicate bindings for the same user", () => {
    const users = [
      makeUser({ userId: "ou_user_030", department: "销售部" }),
      makeUser({ userId: "ou_user_030", department: "销售部" }),
    ];
    const result = mapFeishuUsersToBindings({
      users,
      departmentMappings: baseMappings,
      defaultAgentId: defaultAgent,
    });

    expect(result).toHaveLength(1);
    expect(result[0].match.peer.id).toBe("ou_user_030");
  });
});
