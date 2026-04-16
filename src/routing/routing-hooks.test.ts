import { describe, expect, test } from "vitest";
import {
  createRoutingHookRegistry,
  type RoutingContext,
  type RoutingHook,
  type RoutingHookRegistry,
} from "./routing-hooks.js";

function makeContext(overrides?: Partial<RoutingContext>): RoutingContext {
  return {
    message: "hello",
    channelId: "ch-1",
    peerId: "peer-1",
    resolvedAgentId: "agent-default",
    source: "binding",
    ...overrides,
  };
}

describe("RoutingHookRegistry", () => {
  let registry: RoutingHookRegistry;

  test("register adds a hook and list returns it", () => {
    registry = createRoutingHookRegistry();
    const hook: RoutingHook = {
      id: "hook-a",
      priority: 10,
      handler: () => ({}),
    };

    registry.register(hook);

    const hooks = registry.list();
    expect(hooks).toHaveLength(1);
    expect(hooks[0].id).toBe("hook-a");
  });

  test("unregister removes a hook by id", () => {
    registry = createRoutingHookRegistry();
    registry.register({ id: "hook-a", priority: 10, handler: () => ({}) });
    registry.register({ id: "hook-b", priority: 20, handler: () => ({}) });

    registry.unregister("hook-a");

    const ids = registry.list().map((h) => h.id);
    expect(ids).toEqual(["hook-b"]);
  });

  test("unregister is a no-op for unknown id", () => {
    registry = createRoutingHookRegistry();
    registry.register({ id: "hook-a", priority: 10, handler: () => ({}) });

    registry.unregister("nonexistent");

    expect(registry.list()).toHaveLength(1);
  });

  test("execute runs hooks in priority order (lower number first)", async () => {
    registry = createRoutingHookRegistry();
    const callOrder: string[] = [];

    registry.register({
      id: "high-priority",
      priority: 100,
      handler: () => {
        callOrder.push("high-priority");
        return {};
      },
    });
    registry.register({
      id: "low-priority",
      priority: 1,
      handler: () => {
        callOrder.push("low-priority");
        return {};
      },
    });
    registry.register({
      id: "mid-priority",
      priority: 50,
      handler: () => {
        callOrder.push("mid-priority");
        return {};
      },
    });

    await registry.execute(makeContext());

    expect(callOrder).toEqual(["low-priority", "mid-priority", "high-priority"]);
  });

  test("execute returns original agentId when no hooks registered", async () => {
    registry = createRoutingHookRegistry();

    const result = await registry.execute(makeContext({ resolvedAgentId: "agent-original" }));

    expect(result).toBe("agent-original");
  });

  test("execute returns original agentId when hooks don't override", async () => {
    registry = createRoutingHookRegistry();
    registry.register({ id: "noop", priority: 10, handler: () => ({}) });

    const result = await registry.execute(makeContext({ resolvedAgentId: "agent-original" }));

    expect(result).toBe("agent-original");
  });

  test("execute applies agentId override from hook", async () => {
    registry = createRoutingHookRegistry();
    registry.register({
      id: "override",
      priority: 10,
      handler: () => ({ agentId: "agent-custom" }),
    });

    const result = await registry.execute(makeContext({ resolvedAgentId: "agent-original" }));

    expect(result).toBe("agent-custom");
  });

  test("execute chains hooks: first hook overrides, second sees updated agentId", async () => {
    registry = createRoutingHookRegistry();
    const seenAgentIds: string[] = [];

    registry.register({
      id: "first",
      priority: 1,
      handler: (ctx) => {
        seenAgentIds.push(ctx.resolvedAgentId);
        return { agentId: "agent-from-first" };
      },
    });
    registry.register({
      id: "second",
      priority: 2,
      handler: (ctx) => {
        seenAgentIds.push(ctx.resolvedAgentId);
        return { agentId: "agent-from-second" };
      },
    });

    const result = await registry.execute(makeContext({ resolvedAgentId: "agent-original" }));

    expect(seenAgentIds).toEqual(["agent-original", "agent-from-first"]);
    expect(result).toBe("agent-from-second");
  });

  test("execute stops early when a hook returns stop: true", async () => {
    registry = createRoutingHookRegistry();
    const called: string[] = [];

    registry.register({
      id: "stopper",
      priority: 1,
      handler: () => {
        called.push("stopper");
        return { agentId: "agent-stopped", stop: true };
      },
    });
    registry.register({
      id: "after-stop",
      priority: 2,
      handler: () => {
        called.push("after-stop");
        return { agentId: "agent-should-not-apply" };
      },
    });

    const result = await registry.execute(makeContext());

    expect(called).toEqual(["stopper"]);
    expect(result).toBe("agent-stopped");
  });

  test("execute handles async hooks", async () => {
    registry = createRoutingHookRegistry();

    registry.register({
      id: "async-hook",
      priority: 10,
      handler: async (_ctx) => {
        await new Promise((resolve) => setTimeout(resolve, 5));
        return { agentId: "agent-async" };
      },
    });

    const result = await registry.execute(makeContext());

    expect(result).toBe("agent-async");
  });

  test("execute handles hook errors gracefully (skips errored hook, continues)", async () => {
    registry = createRoutingHookRegistry();
    const called: string[] = [];

    registry.register({
      id: "before-error",
      priority: 1,
      handler: () => {
        called.push("before-error");
        return { agentId: "agent-before" };
      },
    });
    registry.register({
      id: "erroring",
      priority: 2,
      handler: () => {
        called.push("erroring");
        throw new Error("hook exploded");
      },
    });
    registry.register({
      id: "after-error",
      priority: 3,
      handler: () => {
        called.push("after-error");
        return { agentId: "agent-after" };
      },
    });

    const result = await registry.execute(makeContext());

    expect(called).toEqual(["before-error", "erroring", "after-error"]);
    expect(result).toBe("agent-after");
  });

  test("multiple hooks with same priority maintain insertion order", async () => {
    registry = createRoutingHookRegistry();
    const callOrder: string[] = [];

    registry.register({
      id: "same-pri-first",
      priority: 10,
      handler: () => {
        callOrder.push("same-pri-first");
        return {};
      },
    });
    registry.register({
      id: "same-pri-second",
      priority: 10,
      handler: () => {
        callOrder.push("same-pri-second");
        return {};
      },
    });
    registry.register({
      id: "same-pri-third",
      priority: 10,
      handler: () => {
        callOrder.push("same-pri-third");
        return {};
      },
    });

    await registry.execute(makeContext());

    expect(callOrder).toEqual(["same-pri-first", "same-pri-second", "same-pri-third"]);
  });
});
