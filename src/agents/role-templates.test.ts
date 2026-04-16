import { describe, test, expect } from "vitest";
import {
  getDefaultRoles,
  getRoleById,
  getRoleToolWhitelist,
  resolveRoleForUser,
} from "./role-templates.js";

describe("role-templates", () => {
  describe("getDefaultRoles", () => {
    test("returns predefined roles: pm, engineer, sales, ops", () => {
      const roles = getDefaultRoles();
      const ids = roles.map((r) => r.id);
      expect(ids).toContain("pm");
      expect(ids).toContain("engineer");
      expect(ids).toContain("sales");
      expect(ids).toContain("ops");
    });

    test("each role has non-empty toolWhitelist", () => {
      const roles = getDefaultRoles();
      for (const role of roles) {
        expect(role.toolWhitelist.length).toBeGreaterThan(0);
      }
    });

    test("each role has a description", () => {
      const roles = getDefaultRoles();
      for (const role of roles) {
        expect(typeof role.description).toBe("string");
        expect(role.description.length).toBeGreaterThan(0);
      }
    });
  });

  describe("getRoleById", () => {
    test("returns role when id matches", () => {
      const roles = getDefaultRoles();
      const pm = getRoleById("pm", roles);
      expect(pm).toBeDefined();
      expect(pm!.id).toBe("pm");
    });

    test("returns undefined for unknown id", () => {
      const roles = getDefaultRoles();
      const result = getRoleById("nonexistent", roles);
      expect(result).toBeUndefined();
    });
  });

  describe("getRoleToolWhitelist", () => {
    test("returns tools for a valid role", () => {
      const roles = getDefaultRoles();
      const tools = getRoleToolWhitelist("engineer", roles);
      expect(tools).toContain("exec");
      expect(tools).toContain("bash");
    });

    test("returns empty array for unknown role", () => {
      const roles = getDefaultRoles();
      const tools = getRoleToolWhitelist("ghost", roles);
      expect(tools).toEqual([]);
    });
  });

  describe("resolveRoleForUser", () => {
    test("maps job title containing '产品' to pm role", () => {
      const role = resolveRoleForUser({ jobTitle: "产品经理", department: "产品部" });
      expect(role).toBe("pm");
    });

    test("maps job title containing 'engineer' to engineer role", () => {
      const role = resolveRoleForUser({ jobTitle: "Senior Engineer", department: "Engineering" });
      expect(role).toBe("engineer");
    });

    test("maps job title containing '销售' to sales role", () => {
      const role = resolveRoleForUser({ jobTitle: "销售总监", department: "销售部" });
      expect(role).toBe("sales");
    });

    test("maps job title containing '运营' to ops role", () => {
      const role = resolveRoleForUser({ jobTitle: "运营专员", department: "运营部" });
      expect(role).toBe("ops");
    });

    test("falls back to department when job title has no match", () => {
      const role = resolveRoleForUser({ jobTitle: "总裁助理", department: "Engineering" });
      expect(role).toBe("engineer");
    });

    test("returns 'default' when no match found", () => {
      const role = resolveRoleForUser({ jobTitle: "实习生", department: "行政部" });
      expect(role).toBe("default");
    });
  });
});
