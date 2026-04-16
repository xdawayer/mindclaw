import type { IntentRoutingDeps, IntentRoutingResult } from "./intent-routing.js";
import { resolveIntentRoute } from "./intent-routing.js";

export type RouteResolution = {
  agentId: string;
  source: "binding" | "default";
};

export type RouteWithIntentResult = {
  /** Immediate routing result (always returned without delay). */
  immediate: RouteResolution;
  /**
   * Promise that resolves when async intent routing completes.
   * Only present when immediate.source === "default" and intent routing is enabled.
   * If intent routing picks a different agent, the caller can transfer.
   */
  intentRouting?: Promise<IntentRoutingResult>;
};

export function routeWithIntentFallback(params: {
  message: string;
  /** Result from deterministic routing (binding match or default fallback). */
  deterministicResult: RouteResolution;
  /** If provided, triggers async intent routing when deterministic falls back to default. */
  intentDeps?: IntentRoutingDeps;
}): RouteWithIntentResult {
  const { message, deterministicResult, intentDeps } = params;

  if (deterministicResult.source === "binding" || !intentDeps) {
    return { immediate: deterministicResult };
  }

  return {
    immediate: deterministicResult,
    intentRouting: resolveIntentRoute(message, intentDeps),
  };
}
