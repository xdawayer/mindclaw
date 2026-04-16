import type { MetricsStore } from "./metrics-store.js";
import { classifySessionOutcome } from "./outcome-classifier.js";

export type AgentRunResult = {
  sessionId: string;
  agentId: string;
  startedAt: number;
  endedAt: number;
  messageCount: number;
  stopReason?: string;
  aborted: boolean;
  errorOccurred: boolean;
};

export function recordSessionMetrics(store: MetricsStore, run: AgentRunResult): void {
  const outcome = classifySessionOutcome({
    messageCount: run.messageCount,
    stopReason: run.stopReason,
    aborted: run.aborted,
    errorOccurred: run.errorOccurred,
    durationMs: run.endedAt - run.startedAt,
  });

  store.recordSession({
    sessionId: run.sessionId,
    agentId: run.agentId,
    outcome,
    messageCount: run.messageCount,
    durationMs: run.endedAt - run.startedAt,
    turnCount: Math.ceil(run.messageCount / 2),
    timestamp: run.endedAt,
  });
}
