import { describe, expect, it } from "vitest";
import {
  resolveUserIdentity,
  registerUser,
  listRegisteredUsers,
  createUserRegistry,
} from "./user-registry-mt.js";

describe("user-registry-mt", () => {
  describe("createUserRegistry", () => {
    it("starts empty", () => {
      const registry = createUserRegistry();
      expect(listRegisteredUsers(registry)).toEqual([]);
    });
  });

  describe("registerUser", () => {
    it("adds a user entry", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_abc123",
        displayName: "王玲 (Lynne)",
        roleId: "ceo",
        teamId: "general",
        isAdmin: true,
      });
      expect(listRegisteredUsers(registry)).toHaveLength(1);
    });

    it("overwrites existing entry for same userId", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_abc123",
        displayName: "Lynne",
        roleId: "pm",
        teamId: "product",
      });
      registerUser(registry, {
        userId: "ou_abc123",
        displayName: "王玲 (Lynne)",
        roleId: "ceo",
        teamId: "general",
        isAdmin: true,
      });
      const users = listRegisteredUsers(registry);
      expect(users).toHaveLength(1);
      expect(users[0].roleId).toBe("ceo");
    });
  });

  describe("resolveUserIdentity", () => {
    it("returns full identity for registered user", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_abc123",
        displayName: "王玲 (Lynne)",
        roleId: "ceo",
        teamId: "general",
        isAdmin: true,
      });

      const identity = resolveUserIdentity(registry, "ou_abc123");
      expect(identity).toEqual({
        userId: "ou_abc123",
        displayName: "王玲 (Lynne)",
        roleId: "ceo",
        teamId: "general",
        isAdmin: true,
        agentId: "default",
      });
    });

    it("returns guest identity for unregistered user", () => {
      const registry = createUserRegistry();
      const identity = resolveUserIdentity(registry, "ou_unknown");
      expect(identity).toEqual({
        userId: "ou_unknown",
        displayName: "ou_unknown",
        roleId: "default",
        teamId: "general",
        isAdmin: false,
        agentId: "default",
      });
    });

    it("resolves custom agentId when set", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_sales1",
        displayName: "Sales Rep",
        roleId: "sales",
        teamId: "sales",
        agentId: "sales-assistant",
      });

      const identity = resolveUserIdentity(registry, "ou_sales1");
      expect(identity.agentId).toBe("sales-assistant");
    });

    it("works the same regardless of message context (DM vs group)", () => {
      const registry = createUserRegistry();
      registerUser(registry, {
        userId: "ou_pm1",
        displayName: "PM",
        roleId: "pm",
        teamId: "product",
      });

      // Same userId resolves the same identity no matter what
      const fromDM = resolveUserIdentity(registry, "ou_pm1");
      const fromGroup = resolveUserIdentity(registry, "ou_pm1");
      expect(fromDM).toEqual(fromGroup);
    });
  });

  describe("bulk registration", () => {
    it("registers multiple users", () => {
      const registry = createUserRegistry([
        { userId: "ou_ceo", displayName: "彪哥", roleId: "ceo", teamId: "general", isAdmin: true },
        {
          userId: "ou_lynne",
          displayName: "王玲",
          roleId: "ceo",
          teamId: "general",
          isAdmin: true,
        },
        { userId: "ou_pm1", displayName: "PM", roleId: "pm", teamId: "product" },
        { userId: "ou_seo1", displayName: "SEO", roleId: "seo-ops", teamId: "growth" },
        {
          userId: "ou_content1",
          displayName: "内容专员",
          roleId: "content-creator",
          teamId: "growth",
        },
      ]);
      expect(listRegisteredUsers(registry)).toHaveLength(5);

      // Each resolves correctly
      expect(resolveUserIdentity(registry, "ou_lynne").roleId).toBe("ceo");
      expect(resolveUserIdentity(registry, "ou_lynne").isAdmin).toBe(true);
      expect(resolveUserIdentity(registry, "ou_pm1").teamId).toBe("product");
      expect(resolveUserIdentity(registry, "ou_seo1").teamId).toBe("growth");
    });
  });
});
