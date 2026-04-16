import { describe, test, expect } from "vitest";
import { resolveMultiTenantRoute, type MultiTenantRouteInput } from "./multi-tenant-routing.js";

function makeInput(overrides?: Partial<MultiTenantRouteInput>): MultiTenantRouteInput {
  return {
    message: "帮我写一篇周报",
    resolvedAgentId: "agent-default",
    channelId: "feishu",
    chatType: "p2p",
    peerId: "user-001",
    prefixMappings: [
      { prefix: "写作", agentId: "agent-writing" },
      { prefix: "数据", agentId: "agent-data" },
    ],
    ...overrides,
  };
}

describe("multi-tenant-routing", () => {
  test("command prefix overrides binding-resolved agent", () => {
    const result = resolveMultiTenantRoute(makeInput({ message: "/写作 帮我写周报" }));
    expect(result.agentId).toBe("agent-writing");
    expect(result.matchedBy).toBe("command-prefix");
  });

  test("no prefix falls through to binding-resolved agent", () => {
    const result = resolveMultiTenantRoute(makeInput({ message: "普通消息" }));
    expect(result.agentId).toBe("agent-default");
    expect(result.matchedBy).toBe("binding");
  });

  test("unknown prefix falls through to binding", () => {
    const result = resolveMultiTenantRoute(makeInput({ message: "/未知 做点什么" }));
    expect(result.agentId).toBe("agent-default");
    expect(result.matchedBy).toBe("binding");
  });

  test("with callLLM, low-confidence intent triggers needsConfirmation", async () => {
    const result = resolveMultiTenantRoute(
      makeInput({
        message: "帮我做个分析",
        callLLM: async () => ({ agentId: "agent-data", confidence: 0.5 }),
      }),
    );
    // Sync result: binding (LLM is async, not awaited in sync path)
    expect(result.agentId).toBe("agent-default");
    expect(result.matchedBy).toBe("binding");
  });

  test("async resolve with LLM returns intent-matched agent when confidence high", async () => {
    const result = await resolveMultiTenantRoute(
      makeInput({
        message: "帮我做个数据分析",
        callLLM: async () => ({ agentId: "agent-data", confidence: 0.9 }),
      }),
    ).asyncIntent;

    expect(result).not.toBeNull();
    expect(result!.agentId).toBe("agent-data");
    expect(result!.confidence).toBe(0.9);
    expect(result!.needsConfirmation).toBe(false);
  });

  test("async resolve with low confidence marks needsConfirmation", async () => {
    const result = await resolveMultiTenantRoute(
      makeInput({
        message: "帮我做个分析",
        callLLM: async () => ({ agentId: "agent-data", confidence: 0.5 }),
      }),
    ).asyncIntent;

    expect(result).not.toBeNull();
    expect(result!.needsConfirmation).toBe(true);
  });

  test("no callLLM means asyncIntent resolves to null", async () => {
    const result = await resolveMultiTenantRoute(makeInput()).asyncIntent;
    expect(result).toBeNull();
  });

  test("prefix routing takes priority over everything (even if LLM provided)", async () => {
    const result = resolveMultiTenantRoute(
      makeInput({
        message: "/数据 分析销售额",
        callLLM: async () => ({ agentId: "agent-writing", confidence: 0.99 }),
      }),
    );
    expect(result.agentId).toBe("agent-data");
    expect(result.matchedBy).toBe("command-prefix");
    // asyncIntent should be null since prefix matched
    const intentResult = await result.asyncIntent;
    expect(intentResult).toBeNull();
  });
});
