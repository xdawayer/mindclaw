import { describe, expect, it } from "vitest";
import {
  getDefaultAgents,
  getAgentById,
  getAgentPrefixMappings,
  getAgentsByTeam,
  type SpecializedAgent,
} from "./agent-registry-mt.js";

describe("agent-registry-mt", () => {
  describe("getDefaultAgents", () => {
    it("returns at least 4 specialized agents", () => {
      const agents = getDefaultAgents();
      expect(agents.length).toBeGreaterThanOrEqual(4);
    });

    it("includes writing, data-analysis, scheduling, and knowledge agents", () => {
      const agents = getDefaultAgents();
      const ids = agents.map((a) => a.id);
      expect(ids).toContain("writing");
      expect(ids).toContain("data-analysis");
      expect(ids).toContain("scheduling");
      expect(ids).toContain("knowledge");
    });

    it("each agent has required fields", () => {
      const agents = getDefaultAgents();
      for (const agent of agents) {
        expect(agent.id).toBeTruthy();
        expect(agent.name).toBeTruthy();
        expect(agent.description).toBeTruthy();
        expect(agent.commandPrefixes.length).toBeGreaterThan(0);
        expect(agent.toolIds.length).toBeGreaterThan(0);
      }
    });

    it("returns copies (not shared references)", () => {
      const a = getDefaultAgents();
      const b = getDefaultAgents();
      expect(a).not.toBe(b);
      expect(a[0]).not.toBe(b[0]);
    });
  });

  describe("getAgentById", () => {
    it("returns agent for known id", () => {
      const agents = getDefaultAgents();
      const agent = getAgentById("writing", agents);
      expect(agent).toBeDefined();
      expect(agent!.id).toBe("writing");
    });

    it("returns undefined for unknown id", () => {
      const agents = getDefaultAgents();
      expect(getAgentById("nonexistent", agents)).toBeUndefined();
    });
  });

  describe("getAgentPrefixMappings", () => {
    it("generates prefix mappings from all agents", () => {
      const agents = getDefaultAgents();
      const mappings = getAgentPrefixMappings(agents);
      expect(mappings.length).toBeGreaterThan(0);
      for (const m of mappings) {
        expect(m.prefix).toBeTruthy();
        expect(m.agentId).toBeTruthy();
      }
    });

    it("includes Chinese prefixes for writing agent", () => {
      const agents = getDefaultAgents();
      const mappings = getAgentPrefixMappings(agents);
      const writingPrefixes = mappings.filter((m) => m.agentId === "writing");
      const prefixValues = writingPrefixes.map((m) => m.prefix);
      expect(prefixValues).toContain("写作");
    });

    it("includes Chinese prefixes for data-analysis agent", () => {
      const agents = getDefaultAgents();
      const mappings = getAgentPrefixMappings(agents);
      const dataPrefixes = mappings.filter((m) => m.agentId === "data-analysis");
      const prefixValues = dataPrefixes.map((m) => m.prefix);
      expect(prefixValues).toContain("数据");
    });
  });

  describe("getAgentsByTeam", () => {
    it("returns agents bound to a specific team", () => {
      const agents = getDefaultAgents();
      const salesAgents = getAgentsByTeam("sales", agents);
      expect(salesAgents.length).toBeGreaterThan(0);
    });

    it("returns all agents for 'all' team binding", () => {
      const agents = getDefaultAgents();
      const allAgents = getAgentsByTeam("engineering", agents);
      // engineering team should have at least the knowledge agent (shared)
      expect(allAgents.length).toBeGreaterThan(0);
    });

    it("returns empty for unknown team with no shared agents", () => {
      const agents: SpecializedAgent[] = [
        {
          id: "test",
          name: "Test",
          description: "Test",
          commandPrefixes: ["test"],
          toolIds: ["search"],
          teamBindings: ["sales-only"],
        },
      ];
      expect(getAgentsByTeam("engineering", agents)).toEqual([]);
    });
  });
});
