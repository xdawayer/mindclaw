import { mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MetricsStore } from "./metrics-store.js";
import { recordSessionMetrics } from "./record-session-metrics.js";
import type { AgentRunResult } from "./record-session-metrics.js";

const TEST_DIR = path.join(import.meta.dirname, ".test-record-session");

describe("recordSessionMetrics", () => {
  let store: MetricsStore;

  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
    store = new MetricsStore(path.join(TEST_DIR, "metrics.sqlite"));
  });

  afterEach(() => {
    store.close();
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  function makeRunResult(overrides: Partial<AgentRunResult> = {}): AgentRunResult {
    return {
      sessionId: "sess-1",
      agentId: "main",
      startedAt: Date.now() - 5000,
      endedAt: Date.now(),
      messageCount: 6,
      stopReason: "end_turn",
      aborted: false,
      errorOccurred: false,
      ...overrides,
    };
  }

  it("records a successful session and can query it back", () => {
    recordSessionMetrics(store, makeRunResult());

    const rows = store.querySessions({ agentId: "main" });
    expect(rows).toHaveLength(1);
    expect(rows[0].outcome).toBe("success");
    expect(rows[0].sessionId).toBe("sess-1");
    expect(rows[0].agentId).toBe("main");
  });

  it("classifies a failed session correctly", () => {
    recordSessionMetrics(store, makeRunResult({ errorOccurred: true }));

    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].outcome).toBe("fail");
  });

  it("classifies an aborted session correctly", () => {
    recordSessionMetrics(store, makeRunResult({ aborted: true }));

    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].outcome).toBe("fail");
  });

  it("classifies a session with few messages as unknown", () => {
    recordSessionMetrics(store, makeRunResult({ messageCount: 1 }));

    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].outcome).toBe("unknown");
  });

  it("computes duration from startedAt and endedAt", () => {
    const now = Date.now();
    recordSessionMetrics(store, makeRunResult({ startedAt: now - 10_000, endedAt: now }));

    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].durationMs).toBe(10_000);
  });

  it("computes turn count as half of message count (rounded up)", () => {
    recordSessionMetrics(store, makeRunResult({ messageCount: 7 }));

    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].turnCount).toBe(4); // ceil(7/2)
  });

  it("records multiple sessions for summary", () => {
    recordSessionMetrics(store, makeRunResult({ sessionId: "s1" }));
    recordSessionMetrics(store, makeRunResult({ sessionId: "s2", errorOccurred: true }));
    recordSessionMetrics(store, makeRunResult({ sessionId: "s3" }));

    const summary = store.summary({ agentId: "main" });
    expect(summary.totalSessions).toBe(3);
    expect(summary.successRate).toBeCloseTo(2 / 3);
    expect(summary.failRate).toBeCloseTo(1 / 3);
  });
});
