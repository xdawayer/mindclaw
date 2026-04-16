import { existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MetricsStore } from "./metrics-store.js";
import { tryRecordAgentMetrics } from "./try-record-metrics.js";

const TEST_DIR = path.join(import.meta.dirname, ".test-try-record-metrics");

describe("tryRecordAgentMetrics", () => {
  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it("writes a metrics record with correct message count", () => {
    tryRecordAgentMetrics({
      agentDir: TEST_DIR,
      sessionId: "sess-1",
      agentId: "main",
      durationMs: 5000,
      messageCount: 8,
      success: true,
      aborted: false,
    });

    const dbPath = path.join(TEST_DIR, "metrics.sqlite");
    expect(existsSync(dbPath)).toBe(true);

    const store = new MetricsStore(dbPath);
    const rows = store.querySessions({ agentId: "main" });
    expect(rows).toHaveLength(1);
    expect(rows[0].outcome).toBe("success");
    expect(rows[0].durationMs).toBe(5000);
    expect(rows[0].messageCount).toBe(8);
    store.close();
  });

  it("records a failed session when success is false", () => {
    tryRecordAgentMetrics({
      agentDir: TEST_DIR,
      sessionId: "sess-2",
      agentId: "bot",
      durationMs: 1000,
      messageCount: 4,
      success: false,
      aborted: false,
      error: "timeout",
    });

    const store = new MetricsStore(path.join(TEST_DIR, "metrics.sqlite"));
    const rows = store.querySessions({ agentId: "bot" });
    expect(rows[0].outcome).toBe("fail");
    store.close();
  });

  it("does not throw when agentDir is invalid", () => {
    expect(() => {
      tryRecordAgentMetrics({
        agentDir: "/nonexistent/path/that/cannot/be/created",
        sessionId: "x",
        agentId: "x",
        durationMs: 0,
        messageCount: 0,
        success: true,
        aborted: false,
      });
    }).not.toThrow();
  });

  it("records aborted session as fail", () => {
    tryRecordAgentMetrics({
      agentDir: TEST_DIR,
      sessionId: "sess-3",
      agentId: "main",
      durationMs: 2000,
      messageCount: 5,
      success: false,
      aborted: true,
    });

    const store = new MetricsStore(path.join(TEST_DIR, "metrics.sqlite"));
    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].outcome).toBe("fail");
    store.close();
  });

  it("classifies session with 1 message as unknown", () => {
    tryRecordAgentMetrics({
      agentDir: TEST_DIR,
      sessionId: "sess-short",
      agentId: "main",
      durationMs: 500,
      messageCount: 1,
      success: true,
      aborted: false,
    });

    const store = new MetricsStore(path.join(TEST_DIR, "metrics.sqlite"));
    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].outcome).toBe("unknown");
    store.close();
  });
});
