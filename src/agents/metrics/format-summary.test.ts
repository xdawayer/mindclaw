import { describe, expect, it } from "vitest";
import { formatMetricsSummary } from "./format-summary.js";
import type { MetricsSummary } from "./metrics-store.js";

describe("formatMetricsSummary", () => {
  it("formats summary with all metrics as text", () => {
    const summary: MetricsSummary = {
      totalSessions: 100,
      successRate: 0.75,
      failRate: 0.15,
      partialRate: 0.05,
      unknownRate: 0.05,
    };

    const output = formatMetricsSummary(summary, "main");
    expect(output).toContain("main");
    expect(output).toContain("100");
    expect(output).toContain("75.0%");
    expect(output).toContain("15.0%");
    expect(output).toContain("5.0%");
  });

  it("formats zero-session summary gracefully", () => {
    const summary: MetricsSummary = {
      totalSessions: 0,
      successRate: 0,
      failRate: 0,
      partialRate: 0,
      unknownRate: 0,
    };

    const output = formatMetricsSummary(summary, "bot");
    expect(output).toContain("0");
    expect(output).toContain("bot");
  });

  it("formats as JSON when json flag is true", () => {
    const summary: MetricsSummary = {
      totalSessions: 10,
      successRate: 0.8,
      failRate: 0.1,
      partialRate: 0.1,
      unknownRate: 0,
    };

    const output = formatMetricsSummary(summary, "main", { json: true });
    const parsed = JSON.parse(output);
    expect(parsed.agentId).toBe("main");
    expect(parsed.totalSessions).toBe(10);
    expect(parsed.successRate).toBe(0.8);
  });

  it("flags unknown rate above 40% threshold", () => {
    const summary: MetricsSummary = {
      totalSessions: 10,
      successRate: 0.3,
      failRate: 0.1,
      partialRate: 0.1,
      unknownRate: 0.5,
    };

    const output = formatMetricsSummary(summary, "main");
    expect(output).toContain("unknown");
    // Should contain a warning about classifier refinement
    expect(output.toLowerCase()).toContain("warning");
  });
});
