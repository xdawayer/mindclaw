import { mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { recordMetricsFromAgentEnd } from "./agent-end-metrics.js";
import type { AgentEndEvent, AgentEndContext } from "./agent-end-metrics.js";
import { MetricsStoreRegistry } from "./metrics-store-registry.js";

const TEST_DIR = path.join(import.meta.dirname, ".test-agent-end-metrics");

describe("recordMetricsFromAgentEnd", () => {
  let registry: MetricsStoreRegistry;

  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
    registry = new MetricsStoreRegistry(TEST_DIR);
  });

  afterEach(() => {
    registry.closeAll();
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  function makeEvent(overrides: Partial<AgentEndEvent> = {}): AgentEndEvent {
    return {
      messages: [{}, {}, {}, {}],
      success: true,
      durationMs: 5000,
      ...overrides,
    };
  }

  function makeCtx(overrides: Partial<AgentEndContext> = {}): AgentEndContext {
    return {
      agentId: "main",
      sessionId: "sess-1",
      ...overrides,
    };
  }

  it("records a successful session from agent_end event", () => {
    recordMetricsFromAgentEnd(registry, makeEvent(), makeCtx());

    const store = registry.getStore("main");
    const rows = store.querySessions({ agentId: "main" });
    expect(rows).toHaveLength(1);
    expect(rows[0].outcome).toBe("success");
    expect(rows[0].messageCount).toBe(4);
    expect(rows[0].durationMs).toBe(5000);
  });

  it("records a failed session", () => {
    recordMetricsFromAgentEnd(registry, makeEvent({ success: false, error: "timeout" }), makeCtx());

    const store = registry.getStore("main");
    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].outcome).toBe("fail");
  });

  it("classifies session with 1 message as unknown", () => {
    recordMetricsFromAgentEnd(registry, makeEvent({ messages: [{}] }), makeCtx());

    const store = registry.getStore("main");
    const rows = store.querySessions({ agentId: "main" });
    expect(rows[0].outcome).toBe("unknown");
  });

  it("uses agentId from context to route to correct store", () => {
    recordMetricsFromAgentEnd(registry, makeEvent(), makeCtx({ agentId: "bot-a" }));
    recordMetricsFromAgentEnd(registry, makeEvent(), makeCtx({ agentId: "bot-b" }));

    expect(registry.getStore("bot-a").querySessions({ agentId: "bot-a" })).toHaveLength(1);
    expect(registry.getStore("bot-b").querySessions({ agentId: "bot-b" })).toHaveLength(1);
  });

  it("does not throw on missing agentId", () => {
    expect(() => {
      recordMetricsFromAgentEnd(registry, makeEvent(), makeCtx({ agentId: undefined }));
    }).not.toThrow();
  });

  it("does not throw on missing sessionId", () => {
    expect(() => {
      recordMetricsFromAgentEnd(registry, makeEvent(), makeCtx({ sessionId: undefined }));
    }).not.toThrow();
  });
});
