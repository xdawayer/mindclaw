import { describe, test, expect } from "vitest";
import {
  parseCommandPrefix,
  resolveAgentByPrefix,
  type PrefixMapping,
} from "./command-prefix-routing.js";

describe("command-prefix-routing", () => {
  describe("parseCommandPrefix", () => {
    test("extracts /写作 prefix from message", () => {
      const result = parseCommandPrefix("/写作 帮我写一篇周报");
      expect(result).toEqual({ prefix: "写作", rest: "帮我写一篇周报" });
    });

    test("extracts /数据 prefix", () => {
      const result = parseCommandPrefix("/数据 本月销售额多少");
      expect(result).toEqual({ prefix: "数据", rest: "本月销售额多少" });
    });

    test("extracts English prefix", () => {
      const result = parseCommandPrefix("/schedule plan sprint 5");
      expect(result).toEqual({ prefix: "schedule", rest: "plan sprint 5" });
    });

    test("returns null when no prefix found", () => {
      const result = parseCommandPrefix("帮我写一篇周报");
      expect(result).toBeNull();
    });

    test("returns null for empty message", () => {
      const result = parseCommandPrefix("");
      expect(result).toBeNull();
    });

    test("returns null for / alone", () => {
      const result = parseCommandPrefix("/");
      expect(result).toBeNull();
    });

    test("handles prefix with no rest content", () => {
      const result = parseCommandPrefix("/写作");
      expect(result).toEqual({ prefix: "写作", rest: "" });
    });

    test("trims whitespace from rest", () => {
      const result = parseCommandPrefix("/写作   帮我写一篇周报  ");
      expect(result).toEqual({ prefix: "写作", rest: "帮我写一篇周报" });
    });
  });

  describe("resolveAgentByPrefix", () => {
    const mappings: PrefixMapping[] = [
      { prefix: "写作", agentId: "agent-writing" },
      { prefix: "数据", agentId: "agent-data" },
      { prefix: "排期", agentId: "agent-schedule" },
      { prefix: "schedule", agentId: "agent-schedule" },
    ];

    test("resolves known prefix to agent", () => {
      const result = resolveAgentByPrefix("写作", mappings);
      expect(result).toBe("agent-writing");
    });

    test("resolves English prefix", () => {
      const result = resolveAgentByPrefix("schedule", mappings);
      expect(result).toBe("agent-schedule");
    });

    test("returns undefined for unknown prefix", () => {
      const result = resolveAgentByPrefix("unknown", mappings);
      expect(result).toBeUndefined();
    });

    test("matching is case-insensitive for English prefixes", () => {
      const result = resolveAgentByPrefix("Schedule", mappings);
      expect(result).toBe("agent-schedule");
    });
  });
});
