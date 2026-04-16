import { describe, expect, it } from "vitest";
import { resolveIntentRoute, type IntentRoutingDeps } from "./intent-routing.js";

/**
 * LLM intent routing tests.
 *
 * The intent router is a fallback for when deterministic routing (bindings)
 * doesn't match. It calls a cheap LLM to classify user intent and pick
 * the best agent. Runs asynchronously so users don't wait.
 *
 * Architecture: async mode — default agent handles immediately,
 * intent router runs in background, transfers if different agent matched.
 */

function makeMockDeps(overrides?: Partial<IntentRoutingDeps>): IntentRoutingDeps {
  return {
    callLLM: async () => ({ agentId: "sales", confidence: 0.9 }),
    availableAgents: [
      { id: "main", description: "通用助手" },
      { id: "sales", description: "销售助手，处理客户、CRM、话术相关" },
      { id: "engineering", description: "工程助手，处理代码、部署、技术问题" },
    ],
    defaultAgentId: "main",
    confidenceThreshold: 0.7,
    timeoutMs: 5000,
    ...overrides,
  };
}

describe("resolveIntentRoute", () => {
  it("returns matched agent when LLM confidence is above threshold", async () => {
    const deps = makeMockDeps({
      callLLM: async () => ({ agentId: "sales", confidence: 0.9 }),
    });

    const result = await resolveIntentRoute("帮我查一下客户A的最新跟进情况", deps);

    expect(result.status).toBe("matched");
    expect(result.agentId).toBe("sales");
    expect(result.confidence).toBe(0.9);
  });

  it("returns ask_user when LLM confidence is below threshold", async () => {
    const deps = makeMockDeps({
      callLLM: async () => ({ agentId: "sales", confidence: 0.5 }),
    });

    const result = await resolveIntentRoute("帮我处理一下这个", deps);

    expect(result.status).toBe("ask_user");
    expect(result.confidence).toBe(0.5);
  });

  it("returns default agent on LLM timeout", async () => {
    const deps = makeMockDeps({
      callLLM: async () => {
        await new Promise((resolve) => setTimeout(resolve, 10_000));
        return { agentId: "sales", confidence: 0.9 };
      },
      timeoutMs: 50, // Very short timeout for test
    });

    const result = await resolveIntentRoute("任何消息", deps);

    expect(result.status).toBe("timeout");
    expect(result.agentId).toBe("main");
  });

  it("returns default agent when LLM returns invalid agent ID", async () => {
    const deps = makeMockDeps({
      callLLM: async () => ({ agentId: "nonexistent", confidence: 0.95 }),
    });

    const result = await resolveIntentRoute("查个数据", deps);

    expect(result.status).toBe("invalid_agent");
    expect(result.agentId).toBe("main");
  });

  it("returns default agent when LLM throws error", async () => {
    const deps = makeMockDeps({
      callLLM: async () => {
        throw new Error("LLM service unavailable");
      },
    });

    const result = await resolveIntentRoute("测试消息", deps);

    expect(result.status).toBe("error");
    expect(result.agentId).toBe("main");
  });

  it("returns default agent for empty message", async () => {
    const deps = makeMockDeps();

    const result = await resolveIntentRoute("", deps);

    expect(result.status).toBe("skipped");
    expect(result.agentId).toBe("main");
  });
});
