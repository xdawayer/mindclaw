import { resolveAgentDir } from "../agents/agent-scope.js";
import { formatMetricsSummary } from "../agents/metrics/format-summary.js";
import { MetricsStore } from "../agents/metrics/metrics-store.js";
import { loadConfig } from "../config/io.js";

export async function metricsSummaryCommand(opts: {
  agent?: string;
  json?: boolean;
}): Promise<void> {
  const cfg = loadConfig();
  const agentId = opts.agent ?? "main";
  const agentDir = resolveAgentDir(cfg, agentId);
  const dbPath = `${agentDir}/metrics.sqlite`;

  let store: MetricsStore;
  try {
    store = new MetricsStore(dbPath);
  } catch {
    if (opts.json) {
      console.log(JSON.stringify({ error: "No metrics data found", agentId }));
    } else {
      console.log(`No metrics data found for agent "${agentId}".`);
    }
    return;
  }

  try {
    const summary = store.summary({ agentId });
    console.log(formatMetricsSummary(summary, agentId, { json: opts.json }));
  } finally {
    store.close();
  }
}
