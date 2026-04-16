import { describe, test, expect } from "vitest";
import {
  resolveToolPermissions,
  intersectToolSets,
  type PermissionContext,
} from "./permission-resolver.js";

describe("permission-resolver", () => {
  describe("resolveToolPermissions", () => {
    test("p2p returns full role tool whitelist", () => {
      const ctx: PermissionContext = {
        chatType: "p2p",
        roleToolWhitelist: ["exec", "bash", "git", "search"],
        orgDenyList: [],
      };
      const tools = resolveToolPermissions(ctx);
      expect(tools).toEqual(["exec", "bash", "git", "search"]);
    });

    test("org deny list removes tools from role whitelist", () => {
      const ctx: PermissionContext = {
        chatType: "p2p",
        roleToolWhitelist: ["exec", "bash", "git", "search"],
        orgDenyList: ["exec"],
      };
      const tools = resolveToolPermissions(ctx);
      expect(tools).not.toContain("exec");
      expect(tools).toContain("bash");
    });

    test("group chat intersects with group allowed tools (降权)", () => {
      const ctx: PermissionContext = {
        chatType: "group",
        roleToolWhitelist: ["exec", "bash", "git", "search"],
        orgDenyList: [],
        groupAllowedTools: ["search", "git"],
      };
      const tools = resolveToolPermissions(ctx);
      // Only tools in BOTH role whitelist AND group allowed
      expect(tools).toEqual(expect.arrayContaining(["search", "git"]));
      expect(tools).not.toContain("exec");
      expect(tools).not.toContain("bash");
    });

    test("group chat with no groupAllowedTools uses safe defaults", () => {
      const ctx: PermissionContext = {
        chatType: "group",
        roleToolWhitelist: ["exec", "bash", "git", "search"],
        orgDenyList: [],
      };
      const tools = resolveToolPermissions(ctx);
      // Only safe tools (search) allowed by default in group
      expect(tools).toContain("search");
      expect(tools).not.toContain("exec");
    });

    test("org deny list applied before group intersection", () => {
      const ctx: PermissionContext = {
        chatType: "group",
        roleToolWhitelist: ["exec", "bash", "git", "search"],
        orgDenyList: ["git"],
        groupAllowedTools: ["search", "git"],
      };
      const tools = resolveToolPermissions(ctx);
      // git is org-denied, so even though group allows it, it's removed
      expect(tools).not.toContain("git");
      expect(tools).toContain("search");
    });

    test("empty role whitelist returns empty", () => {
      const ctx: PermissionContext = {
        chatType: "p2p",
        roleToolWhitelist: [],
        orgDenyList: [],
      };
      expect(resolveToolPermissions(ctx)).toEqual([]);
    });
  });

  describe("intersectToolSets", () => {
    test("returns intersection of two arrays", () => {
      expect(intersectToolSets(["a", "b", "c"], ["b", "c", "d"])).toEqual(["b", "c"]);
    });

    test("returns empty for disjoint sets", () => {
      expect(intersectToolSets(["a", "b"], ["c", "d"])).toEqual([]);
    });

    test("returns empty when one set is empty", () => {
      expect(intersectToolSets(["a", "b"], [])).toEqual([]);
    });
  });
});
