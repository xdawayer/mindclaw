import { describe, test, expect } from "vitest";
import { mergeConfigLayers, type ConfigLayer } from "./config-cascade.js";

function makeLayer(overrides: Partial<ConfigLayer>): ConfigLayer {
  return {
    tier: "org",
    security: {},
    features: {},
    ...overrides,
  };
}

describe("config-cascade", () => {
  describe("mergeConfigLayers", () => {
    test("returns org defaults when only org layer provided", () => {
      const org = makeLayer({
        tier: "org",
        security: { dangerousOpsBlocked: true },
        features: { defaultModel: "sonnet-4.6" },
      });

      const result = mergeConfigLayers([org]);

      expect(result.security.dangerousOpsBlocked).toBe(true);
      expect(result.features.defaultModel).toBe("sonnet-4.6");
    });

    test("security keys: org always wins over lower tiers", () => {
      const org = makeLayer({
        tier: "org",
        security: { dangerousOpsBlocked: true, auditEnabled: true },
      });
      const user = makeLayer({
        tier: "user",
        security: { dangerousOpsBlocked: false, auditEnabled: false },
      });

      const result = mergeConfigLayers([org, user]);

      // Org security wins
      expect(result.security.dangerousOpsBlocked).toBe(true);
      expect(result.security.auditEnabled).toBe(true);
    });

    test("feature keys: most specific tier wins (user > role > team > org)", () => {
      const org = makeLayer({
        tier: "org",
        features: { defaultModel: "sonnet-4.6", language: "zh-CN" },
      });
      const team = makeLayer({
        tier: "team",
        features: { language: "en-US" },
      });
      const user = makeLayer({
        tier: "user",
        features: { language: "ja-JP" },
      });

      const result = mergeConfigLayers([org, team, user]);

      // User overrides team overrides org
      expect(result.features.language).toBe("ja-JP");
      // Org default preserved when not overridden
      expect(result.features.defaultModel).toBe("sonnet-4.6");
    });

    test("role layer sits between team and user", () => {
      const org = makeLayer({ tier: "org", features: { style: "formal" } });
      const team = makeLayer({ tier: "team", features: { style: "casual" } });
      const role = makeLayer({ tier: "role", features: { style: "technical" } });

      const result = mergeConfigLayers([org, team, role]);

      expect(result.features.style).toBe("technical");
    });

    test("empty layers array returns empty config", () => {
      const result = mergeConfigLayers([]);
      expect(result.security).toEqual({});
      expect(result.features).toEqual({});
    });

    test("layers can be provided in any order (sorted internally by tier)", () => {
      const user = makeLayer({ tier: "user", features: { theme: "dark" } });
      const org = makeLayer({ tier: "org", features: { theme: "light" } });

      const result = mergeConfigLayers([user, org]);

      // User still wins on features regardless of input order
      expect(result.features.theme).toBe("dark");
    });

    test("lower tiers cannot add new security keys not defined by org", () => {
      const org = makeLayer({
        tier: "org",
        security: { dangerousOpsBlocked: true },
      });
      const team = makeLayer({
        tier: "team",
        security: { dangerousOpsBlocked: false, newTeamSecurityKey: "sneaky" },
      });

      const result = mergeConfigLayers([org, team]);

      // Org wins on its key
      expect(result.security.dangerousOpsBlocked).toBe(true);
      // Team's new security key should be IGNORED (only org defines security policy)
      expect(result.security).not.toHaveProperty("newTeamSecurityKey");
    });

    test("multiple features merge across layers", () => {
      const org = makeLayer({ tier: "org", features: { a: "org-a", b: "org-b" } });
      const team = makeLayer({ tier: "team", features: { b: "team-b", c: "team-c" } });
      const user = makeLayer({ tier: "user", features: { c: "user-c" } });

      const result = mergeConfigLayers([org, team, user]);

      expect(result.features.a).toBe("org-a");
      expect(result.features.b).toBe("team-b");
      expect(result.features.c).toBe("user-c");
    });
  });
});
