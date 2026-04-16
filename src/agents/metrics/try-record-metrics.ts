import path from "node:path";
import { MetricsStore } from "./metrics-store.js";
import { classifySessionOutcome } from "./outcome-classifier.js";

export type TryRecordParams = {
  agentDir: string;
  sessionId: string;
  agentId: string;
  durationMs: number;
  messageCount: number;
  success: boolean;
  aborted: boolean;
  error?: string;
};

/**
 * Best-effort metrics recording. Never throws — metrics failures
 * must not break the agent run flow.
 *
 * Designed to be called from the agent_end hook site in attempt.ts,
 * where real message count and success/error status are available.
 */
export function tryRecordAgentMetrics(params: TryRecordParams): void {
  let store: MetricsStore | undefined;
  try {
    const dbPath = path.join(params.agentDir, "metrics.sqlite");
    store = new MetricsStore(dbPath);

    const outcome = classifySessionOutcome({
      messageCount: params.messageCount,
      aborted: params.aborted,
      errorOccurred: !params.success || Boolean(params.error),
      durationMs: params.durationMs,
    });

    store.recordSession({
      sessionId: params.sessionId,
      agentId: params.agentId,
      outcome,
      messageCount: params.messageCount,
      durationMs: params.durationMs,
      turnCount: Math.ceil(params.messageCount / 2),
      timestamp: Date.now(),
    });
  } catch {
    // Metrics recording is best-effort — never crash the agent
  } finally {
    try {
      store?.close();
    } catch {
      // ignore close errors
    }
  }
}
