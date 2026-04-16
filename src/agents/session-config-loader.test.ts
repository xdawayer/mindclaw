import { describe, test, expect } from "vitest";
import { resolveConfigLayers, type SessionContext } from "./session-config-loader.js";

function makeCtx(overrides?: Partial<SessionContext>): SessionContext {
  return {
    chatType: "p2p",
    userId: "user-001",
    teamId: "engineering",
    roleId: "engineer",
    ...overrides,
  };
}

describe("session-config-loader", () => {
  describe("resolveConfigLayers", () => {
    test("p2p session loads all 4 layers: org + team + role + user", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "p2p" }));
      expect(layers.tiers).toEqual(["org", "team", "role", "user"]);
    });

    test("group session loads only org + team (no role, no user)", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "group" }));
      expect(layers.tiers).toEqual(["org", "team"]);
    });

    test("p2p session includes user memory", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "p2p" }));
      expect(layers.loadUserMemory).toBe(true);
    });

    test("group session does NOT include user memory", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "group" }));
      expect(layers.loadUserMemory).toBe(false);
    });

    test("group session includes team shared memory", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "group" }));
      expect(layers.loadTeamMemory).toBe(true);
    });

    test("p2p session includes team memory as read-only", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "p2p" }));
      expect(layers.loadTeamMemory).toBe(true);
      expect(layers.teamMemoryReadOnly).toBe(true);
    });

    test("group session team memory is read-write (shared)", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "group" }));
      expect(layers.loadTeamMemory).toBe(true);
      expect(layers.teamMemoryReadOnly).toBe(false);
    });

    test("returns session key in group:{chatId} format for group", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "group", chatId: "chat-abc" }));
      expect(layers.sessionKey).toBe("group:chat-abc");
    });

    test("returns session key in user:{userId} format for p2p", () => {
      const layers = resolveConfigLayers(makeCtx({ chatType: "p2p", userId: "user-001" }));
      expect(layers.sessionKey).toBe("user:user-001");
    });
  });
});
