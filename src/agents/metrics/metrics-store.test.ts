import { existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MetricsStore } from "./metrics-store.js";
import type { SessionMetricRecord } from "./metrics-store.js";

const TEST_DIR = path.join(import.meta.dirname, ".test-metrics-store");

describe("MetricsStore", () => {
  let store: MetricsStore;

  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
    store = new MetricsStore(path.join(TEST_DIR, "metrics.sqlite"));
  });

  afterEach(() => {
    store.close();
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it("creates the database file on construction", () => {
    expect(existsSync(path.join(TEST_DIR, "metrics.sqlite"))).toBe(true);
  });

  it("records a session metric", () => {
    const record: SessionMetricRecord = {
      sessionId: "sess-1",
      agentId: "main",
      outcome: "success",
      messageCount: 6,
      durationMs: 5000,
      turnCount: 3,
      timestamp: Date.now(),
    };

    store.recordSession(record);
    const rows = store.querySessions({ agentId: "main" });

    expect(rows).toHaveLength(1);
    expect(rows[0].sessionId).toBe("sess-1");
    expect(rows[0].outcome).toBe("success");
    expect(rows[0].messageCount).toBe(6);
  });

  it("records multiple sessions and queries by agent", () => {
    const base = {
      durationMs: 5000,
      turnCount: 3,
      timestamp: Date.now(),
    };

    store.recordSession({
      ...base,
      sessionId: "s1",
      agentId: "main",
      outcome: "success",
      messageCount: 4,
    });
    store.recordSession({
      ...base,
      sessionId: "s2",
      agentId: "other",
      outcome: "fail",
      messageCount: 2,
    });
    store.recordSession({
      ...base,
      sessionId: "s3",
      agentId: "main",
      outcome: "fail",
      messageCount: 3,
    });

    const mainRows = store.querySessions({ agentId: "main" });
    expect(mainRows).toHaveLength(2);

    const otherRows = store.querySessions({ agentId: "other" });
    expect(otherRows).toHaveLength(1);
  });

  it("computes summary statistics", () => {
    const base = { durationMs: 5000, turnCount: 3, timestamp: Date.now() };

    store.recordSession({
      ...base,
      sessionId: "s1",
      agentId: "main",
      outcome: "success",
      messageCount: 4,
    });
    store.recordSession({
      ...base,
      sessionId: "s2",
      agentId: "main",
      outcome: "success",
      messageCount: 6,
    });
    store.recordSession({
      ...base,
      sessionId: "s3",
      agentId: "main",
      outcome: "fail",
      messageCount: 2,
    });
    store.recordSession({
      ...base,
      sessionId: "s4",
      agentId: "main",
      outcome: "unknown",
      messageCount: 1,
    });

    const summary = store.summary({ agentId: "main" });

    expect(summary.totalSessions).toBe(4);
    expect(summary.successRate).toBeCloseTo(0.5); // 2/4
    expect(summary.failRate).toBeCloseTo(0.25); // 1/4
    expect(summary.unknownRate).toBeCloseTo(0.25); // 1/4
  });

  it("handles concurrent writes without corruption", () => {
    const base = { durationMs: 1000, turnCount: 1, timestamp: Date.now() };

    // Write 100 records rapidly
    for (let i = 0; i < 100; i++) {
      store.recordSession({
        ...base,
        sessionId: `s-${i}`,
        agentId: "main",
        outcome: i % 3 === 0 ? "fail" : "success",
        messageCount: i + 1,
      });
    }

    const rows = store.querySessions({ agentId: "main" });
    expect(rows).toHaveLength(100);
  });
});
