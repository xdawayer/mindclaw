import { describe, test, expect } from "vitest";
import { buildMultiTenantBootstrapContext, type BootstrapInput } from "./multi-tenant-bootstrap.js";

function makeInput(overrides?: Partial<BootstrapInput>): BootstrapInput {
  return {
    chatType: "p2p",
    userId: "user-001",
    teamId: "engineering",
    roleId: "engineer",
    ...overrides,
  };
}

describe("multi-tenant-bootstrap", () => {
  test("p2p session returns full context with user memory enabled", () => {
    const ctx = buildMultiTenantBootstrapContext(makeInput({ chatType: "p2p" }));
    expect(ctx.tiers).toEqual(["org", "team", "role", "user"]);
    expect(ctx.loadUserMemory).toBe(true);
    expect(ctx.sessionKey).toBe("user:user-001");
    expect(ctx.tokenBudget.org).toBe(500);
    expect(ctx.tokenBudget.user).toBe(300);
  });

  test("group session returns restricted context without user memory", () => {
    const ctx = buildMultiTenantBootstrapContext(
      makeInput({ chatType: "group", chatId: "chat-abc" }),
    );
    expect(ctx.tiers).toEqual(["org", "team"]);
    expect(ctx.loadUserMemory).toBe(false);
    expect(ctx.sessionKey).toBe("group:chat-abc");
  });

  test("includes tool permissions from role + chat context", () => {
    const ctx = buildMultiTenantBootstrapContext(
      makeInput({
        chatType: "p2p",
        roleId: "engineer",
        roleToolWhitelist: ["exec", "bash", "git", "search"],
        orgDenyList: [],
      }),
    );
    expect(ctx.allowedTools).toContain("exec");
    expect(ctx.allowedTools).toContain("bash");
  });

  test("group chat tool permissions are downgraded", () => {
    const ctx = buildMultiTenantBootstrapContext(
      makeInput({
        chatType: "group",
        roleToolWhitelist: ["exec", "bash", "git", "search"],
        orgDenyList: [],
        groupAllowedTools: ["search", "git"],
      }),
    );
    expect(ctx.allowedTools).toContain("search");
    expect(ctx.allowedTools).toContain("git");
    expect(ctx.allowedTools).not.toContain("exec");
  });

  test("total token budget does not exceed 1500", () => {
    const ctx = buildMultiTenantBootstrapContext(makeInput());
    const total =
      ctx.tokenBudget.org + ctx.tokenBudget.team + ctx.tokenBudget.role + ctx.tokenBudget.user;
    expect(total).toBeLessThanOrEqual(1500);
  });
});
