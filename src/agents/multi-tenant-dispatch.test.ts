import { describe, expect, it } from "vitest";
import { dispatchMultiTenantMessage } from "./multi-tenant-dispatch.js";
import { createUserRegistry } from "./user-registry-mt.js";

const registry = createUserRegistry([
  {
    userId: "ou_ceo",
    displayName: "彪哥",
    roleId: "ceo",
    teamId: "general",
    isAdmin: true,
  },
  {
    userId: "ou_lynne",
    displayName: "王玲 (Lynne)",
    roleId: "ceo",
    teamId: "general",
    isAdmin: true,
  },
  {
    userId: "ou_pm1",
    displayName: "PM",
    roleId: "pm",
    teamId: "product",
  },
  {
    userId: "ou_seo1",
    displayName: "SEO 运营",
    roleId: "seo-ops",
    teamId: "growth",
  },
  {
    userId: "ou_content1",
    displayName: "内容专员",
    roleId: "content-creator",
    teamId: "growth",
  },
]);

describe("multi-tenant-dispatch", () => {
  describe("user identity is always resolved by senderId", () => {
    it("Lynne in DM gets CEO config", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_lynne",
        message: "帮我看一下本周数据",
        channelId: "feishu",
        chatType: "p2p",
        chatId: undefined,
      });
      expect(result.identity.roleId).toBe("ceo");
      expect(result.identity.isAdmin).toBe(true);
      expect(result.identity.teamId).toBe("general");
    });

    it("Lynne in group chat gets SAME CEO config", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_lynne",
        message: "帮我看一下本周数据",
        channelId: "feishu",
        chatType: "group",
        chatId: "oc_group123",
      });
      expect(result.identity.roleId).toBe("ceo");
      expect(result.identity.isAdmin).toBe(true);
      expect(result.identity.teamId).toBe("general");
    });

    it("PM in DM gets product team config", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_pm1",
        message: "写个 PRD",
        channelId: "feishu",
        chatType: "p2p",
        chatId: undefined,
      });
      expect(result.identity.roleId).toBe("pm");
      expect(result.identity.teamId).toBe("product");
    });

    it("PM in group chat gets SAME product config", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_pm1",
        message: "写个 PRD",
        channelId: "feishu",
        chatType: "group",
        chatId: "oc_group456",
      });
      expect(result.identity.roleId).toBe("pm");
      expect(result.identity.teamId).toBe("product");
    });

    it("unknown user gets guest defaults", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_stranger",
        message: "你好",
        channelId: "feishu",
        chatType: "p2p",
        chatId: undefined,
      });
      expect(result.identity.roleId).toBe("default");
      expect(result.identity.isAdmin).toBe(false);
      expect(result.identity.teamId).toBe("general");
    });
  });

  describe("context-dependent behavior (DM vs group)", () => {
    it("DM loads user memory", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_lynne",
        message: "test",
        channelId: "feishu",
        chatType: "p2p",
        chatId: undefined,
      });
      expect(result.bootstrap.loadUserMemory).toBe(true);
      expect(result.bootstrap.tiers).toContain("user");
    });

    it("group chat does NOT load user memory", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_lynne",
        message: "test",
        channelId: "feishu",
        chatType: "group",
        chatId: "oc_group123",
      });
      expect(result.bootstrap.loadUserMemory).toBe(false);
      expect(result.bootstrap.tiers).not.toContain("user");
    });

    it("group chat applies tool downgrading", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_ceo",
        message: "test",
        channelId: "feishu",
        chatType: "group",
        chatId: "oc_group123",
      });
      // CEO has all tools, but group chat restricts to safe set
      expect(result.bootstrap.allowedTools).not.toContain("exec");
      expect(result.bootstrap.allowedTools).toContain("search");
    });
  });

  describe("routing", () => {
    it("command prefix routes regardless of user", () => {
      const result = dispatchMultiTenantMessage(registry, {
        senderId: "ou_content1",
        message: "/写作 帮我写小红书文案",
        channelId: "feishu",
        chatType: "p2p",
        chatId: undefined,
      });
      expect(result.routing.agentId).toBe("writing");
      expect(result.routing.matchedBy).toBe("command-prefix");
    });
  });
});
