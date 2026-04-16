import { describe, expect, it, vi } from "vitest";
import type { IntentRoutingDeps } from "./intent-routing.js";
import { routeWithIntentFallback, type RouteResolution } from "./route-with-intent-fallback.js";

function makeIntentDeps(overrides: Partial<IntentRoutingDeps> = {}): IntentRoutingDeps {
  return {
    callLLM: vi.fn().mockResolvedValue({ agentId: "agent-llm", confidence: 0.9 }),
    availableAgents: [
      { id: "agent-a", description: "Agent A" },
      { id: "agent-llm", description: "LLM agent" },
    ],
    defaultAgentId: "agent-a",
    confidenceThreshold: 0.7,
    timeoutMs: 5000,
    ...overrides,
  };
}

describe("routeWithIntentFallback", () => {
  it("returns immediately with no intent routing when deterministic matched a binding", () => {
    const deterministicResult: RouteResolution = { agentId: "agent-a", source: "binding" };

    const result = routeWithIntentFallback({
      message: "hello",
      deterministicResult,
      intentDeps: makeIntentDeps(),
    });

    expect(result.immediate).toEqual(deterministicResult);
    expect(result.intentRouting).toBeUndefined();
  });

  it("returns immediate default + intent routing promise when deterministic fell back and intentDeps provided", () => {
    const deterministicResult: RouteResolution = { agentId: "agent-a", source: "default" };

    const result = routeWithIntentFallback({
      message: "hello",
      deterministicResult,
      intentDeps: makeIntentDeps(),
    });

    expect(result.immediate).toEqual(deterministicResult);
    expect(result.intentRouting).toBeInstanceOf(Promise);
  });

  it("returns just the default with no promise when deterministic fell back but no intentDeps", () => {
    const deterministicResult: RouteResolution = { agentId: "agent-a", source: "default" };

    const result = routeWithIntentFallback({
      message: "hello",
      deterministicResult,
    });

    expect(result.immediate).toEqual(deterministicResult);
    expect(result.intentRouting).toBeUndefined();
  });

  it("intent routing promise resolves to matched agent when LLM picks a different agent", async () => {
    const deterministicResult: RouteResolution = { agentId: "agent-a", source: "default" };
    const deps = makeIntentDeps({
      callLLM: vi.fn().mockResolvedValue({ agentId: "agent-llm", confidence: 0.95 }),
    });

    const result = routeWithIntentFallback({
      message: "do something specific",
      deterministicResult,
      intentDeps: deps,
    });

    const intentResult = await result.intentRouting!;
    expect(intentResult.status).toBe("matched");
    expect(intentResult.agentId).toBe("agent-llm");
    expect(intentResult.confidence).toBe(0.95);
  });

  it("intent routing promise rejection does not cause unhandled rejection", async () => {
    const deterministicResult: RouteResolution = { agentId: "agent-a", source: "default" };
    const deps = makeIntentDeps({
      callLLM: vi.fn().mockRejectedValue(new Error("LLM exploded")),
    });

    const result = routeWithIntentFallback({
      message: "hello",
      deterministicResult,
      intentDeps: deps,
    });

    // The promise should resolve to error status, not reject
    const intentResult = await result.intentRouting!;
    expect(intentResult.status).toBe("error");
    expect(intentResult.agentId).toBe("agent-a");
  });

  it("intent routing promise resolves to default when LLM agrees with default", async () => {
    const deterministicResult: RouteResolution = { agentId: "agent-a", source: "default" };
    const deps = makeIntentDeps({
      callLLM: vi.fn().mockResolvedValue({ agentId: "agent-a", confidence: 0.8 }),
    });

    const result = routeWithIntentFallback({
      message: "hello",
      deterministicResult,
      intentDeps: deps,
    });

    const intentResult = await result.intentRouting!;
    expect(intentResult.status).toBe("matched");
    expect(intentResult.agentId).toBe("agent-a");
  });
});
