import type { MetricsSummary } from "./metrics-store.js";

const UNKNOWN_THRESHOLD = 0.4;

export function formatMetricsSummary(
  summary: MetricsSummary,
  agentId: string,
  opts?: { json?: boolean },
): string {
  if (opts?.json) {
    return JSON.stringify({
      agentId,
      totalSessions: summary.totalSessions,
      successRate: summary.successRate,
      failRate: summary.failRate,
      partialRate: summary.partialRate,
      unknownRate: summary.unknownRate,
    });
  }

  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  const lines = [
    `Metrics Summary: ${agentId}`,
    `──────────────────────────`,
    `Total sessions:  ${summary.totalSessions}`,
    `Success rate:    ${pct(summary.successRate)}`,
    `Fail rate:       ${pct(summary.failRate)}`,
    `Partial rate:    ${pct(summary.partialRate)}`,
    `Unknown rate:    ${pct(summary.unknownRate)}`,
  ];

  if (summary.unknownRate > UNKNOWN_THRESHOLD && summary.totalSessions > 0) {
    lines.push("");
    lines.push(
      `⚠ WARNING: unknown rate is ${pct(summary.unknownRate)} (>${pct(UNKNOWN_THRESHOLD)}). ` +
        `Outcome classifier may need refinement.`,
    );
  }

  return lines.join("\n");
}
