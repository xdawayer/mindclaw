export type RoutingContext = {
  message: string;
  channelId: string;
  peerId: string;
  resolvedAgentId: string;
  source: "binding" | "default" | "intent";
  metadata?: Record<string, string>;
};

export type RoutingHookResult = {
  agentId?: string;
  stop?: boolean;
};

export type RoutingHook = {
  id: string;
  priority: number;
  handler: (ctx: RoutingContext) => RoutingHookResult | Promise<RoutingHookResult>;
};

export type RoutingHookRegistry = {
  register(hook: RoutingHook): void;
  unregister(hookId: string): void;
  list(): RoutingHook[];
  execute(ctx: RoutingContext): Promise<string>;
};

export function createRoutingHookRegistry(): RoutingHookRegistry {
  const hooks: RoutingHook[] = [];

  return {
    register(hook: RoutingHook): void {
      // Replace existing hook with same id to prevent duplicates on hot-reload
      const idx = hooks.findIndex((h) => h.id === hook.id);
      if (idx !== -1) {
        hooks.splice(idx, 1);
      }
      hooks.push(hook);
    },

    unregister(hookId: string): void {
      const idx = hooks.findIndex((h) => h.id === hookId);
      if (idx !== -1) {
        hooks.splice(idx, 1);
      }
    },

    list(): RoutingHook[] {
      return [...hooks];
    },

    async execute(ctx: RoutingContext): Promise<string> {
      let currentAgentId = ctx.resolvedAgentId;

      // Sort by priority (stable sort preserves insertion order for equal priorities)
      const sorted = [...hooks].toSorted((a, b) => a.priority - b.priority);

      for (const hook of sorted) {
        try {
          const result = await hook.handler({ ...ctx, resolvedAgentId: currentAgentId });
          if (result.agentId) {
            currentAgentId = result.agentId;
          }
          if (result.stop) {
            break;
          }
        } catch {
          // Log but continue: a broken hook should not block routing.
          // In production this would go to a subsystem logger.
        }
      }

      return currentAgentId;
    },
  };
}
