import type { MetricsStoreRegistry } from "./metrics-store-registry.js";
import { classifySessionOutcome } from "./outcome-classifier.js";

export type AgentEndEvent = {
  messages: unknown[];
  success: boolean;
  error?: string;
  durationMs?: number;
};

export type AgentEndContext = {
  agentId?: string;
  sessionId?: string;
};

export function recordMetricsFromAgentEnd(
  registry: MetricsStoreRegistry,
  event: AgentEndEvent,
  ctx: AgentEndContext,
): void {
  const agentId = ctx.agentId ?? "unknown";
  const sessionId = ctx.sessionId ?? `anon-${Date.now()}`;

  const outcome = classifySessionOutcome({
    messageCount: event.messages.length,
    aborted: false,
    errorOccurred: !event.success || Boolean(event.error),
    durationMs: event.durationMs,
  });

  const store = registry.getStore(agentId);
  store.recordSession({
    sessionId,
    agentId,
    outcome,
    messageCount: event.messages.length,
    durationMs: event.durationMs,
    turnCount: Math.ceil(event.messages.length / 2),
    timestamp: Date.now(),
  });
}
