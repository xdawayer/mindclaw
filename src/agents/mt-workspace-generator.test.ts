import { describe, expect, it } from "vitest";
import {
  generateTeamRoster,
  generateUserMd,
  buildPerUserAgentEntries,
} from "./mt-workspace-generator.js";
import { createUserRegistry, registerUser } from "./user-registry-mt.js";

describe("mt-workspace-generator", () => {
  describe("generateTeamRoster", () => {
    it("generates markdown roster with all registered users", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_abc",
        displayName: "彪哥",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
      });
      registerUser(registry, {
        userId: "ou_def",
        displayName: "王玲",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
      });

      const result = generateTeamRoster(registry);

      expect(result).toContain("ou_abc");
      expect(result).toContain("彪哥");
      expect(result).toContain("ceo");
      expect(result).toContain("ou_def");
      expect(result).toContain("王玲");
    });

    it("includes admin flag in roster", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_abc",
        displayName: "彪哥",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
      });
      registerUser(registry, {
        userId: "ou_xyz",
        displayName: "小明",
        roleId: "pm",
        teamId: "product",
        isAdmin: false,
      });

      const result = generateTeamRoster(registry);

      // CEO row should have admin=是
      const ceoLine = result.split("\n").find((l) => l.includes("ou_abc"));
      expect(ceoLine).toContain("是");

      // PM row should have admin=否
      const pmLine = result.split("\n").find((l) => l.includes("ou_xyz"));
      expect(pmLine).toContain("否");
    });

    it("returns empty roster note for empty registry", () => {
      const registry = createUserRegistry();
      const result = generateTeamRoster(registry);

      expect(result).toContain("暂无注册成员");
    });
  });

  describe("generateUserMd", () => {
    it("generates USER.md with user name, role, and team", () => {
      const result = generateUserMd({
        userId: "ou_abc",
        displayName: "彪哥",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
      });

      expect(result).toContain("彪哥");
      expect(result).toContain("CEO");
      expect(result).toContain("product");
    });

    it("includes language preference when provided", () => {
      const result = generateUserMd({
        userId: "ou_abc",
        displayName: "彪哥",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
        language: "中文",
      });

      expect(result).toContain("中文");
    });

    it("marks admin users", () => {
      const adminMd = generateUserMd({
        userId: "ou_abc",
        displayName: "彪哥",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
      });
      const regularMd = generateUserMd({
        userId: "ou_xyz",
        displayName: "小明",
        roleId: "pm",
        teamId: "product",
        isAdmin: false,
      });

      expect(adminMd).toContain("isAdmin");
      expect(regularMd).not.toContain("isAdmin");
    });

    it("uses default language when not provided", () => {
      const result = generateUserMd({
        userId: "ou_abc",
        displayName: "Test",
        roleId: "pm",
        teamId: "general",
        isAdmin: false,
      });

      // Should still be valid markdown with a name section
      expect(result).toContain("Test");
      expect(result).toContain("pm");
    });
  });

  describe("buildPerUserAgentEntries", () => {
    it("creates agent entry and binding for each user", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_abc",
        displayName: "彪哥",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
      });
      registerUser(registry, {
        userId: "ou_def",
        displayName: "王玲",
        roleId: "ceo",
        teamId: "product",
        isAdmin: true,
      });

      const result = buildPerUserAgentEntries(registry);

      expect(result.agents).toHaveLength(2);
      expect(result.bindings).toHaveLength(2);

      // Agent IDs follow feishu-{openId} pattern
      expect(result.agents[0].id).toBe("feishu-ou_abc");
      expect(result.agents[1].id).toBe("feishu-ou_def");

      // Each agent has its own workspace
      expect(result.agents[0].workspace).toContain("ou_abc");
      expect(result.agents[1].workspace).toContain("ou_def");

      // Bindings map direct peer to agent
      expect(result.bindings[0]).toEqual({
        agentId: "feishu-ou_abc",
        match: { channel: "feishu", peer: { kind: "direct", id: "ou_abc" } },
      });
    });

    it("returns empty arrays for empty registry", () => {
      const registry = createUserRegistry();
      const result = buildPerUserAgentEntries(registry);

      expect(result.agents).toHaveLength(0);
      expect(result.bindings).toHaveLength(0);
    });
  });
});
