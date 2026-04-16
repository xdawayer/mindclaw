import { existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MetricsStoreRegistry } from "./metrics-store-registry.js";

const TEST_DIR = path.join(import.meta.dirname, ".test-metrics-registry");

describe("MetricsStoreRegistry", () => {
  let registry: MetricsStoreRegistry;

  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
    registry = new MetricsStoreRegistry(TEST_DIR);
  });

  afterEach(() => {
    registry.closeAll();
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it("creates a store for a given agent ID", () => {
    const store = registry.getStore("main");
    expect(store).toBeDefined();

    const dbPath = path.join(TEST_DIR, "main", "metrics.sqlite");
    expect(existsSync(dbPath)).toBe(true);
  });

  it("returns the same store instance for the same agent ID", () => {
    const store1 = registry.getStore("main");
    const store2 = registry.getStore("main");
    expect(store1).toBe(store2);
  });

  it("returns different stores for different agent IDs", () => {
    const store1 = registry.getStore("main");
    const store2 = registry.getStore("other");
    expect(store1).not.toBe(store2);
  });

  it("stores persist data independently", () => {
    const storeA = registry.getStore("agent-a");
    const storeB = registry.getStore("agent-b");

    storeA.recordSession({
      sessionId: "s1",
      agentId: "agent-a",
      outcome: "success",
      messageCount: 4,
      durationMs: 1000,
      turnCount: 2,
      timestamp: Date.now(),
    });

    expect(storeA.querySessions({ agentId: "agent-a" })).toHaveLength(1);
    expect(storeB.querySessions({ agentId: "agent-b" })).toHaveLength(0);
  });

  it("closeAll closes all open stores", () => {
    registry.getStore("main");
    registry.getStore("other");

    // Should not throw
    registry.closeAll();

    // After close, getting a new store should work (creates fresh)
    const store = registry.getStore("main");
    expect(store).toBeDefined();
  });
});
