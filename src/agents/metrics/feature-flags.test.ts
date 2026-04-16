import { describe, expect, it } from "vitest";
import { resolveMetricsFlags } from "./feature-flags.js";

describe("resolveMetricsFlags", () => {
  it("returns all flags disabled by default when config is empty", () => {
    const flags = resolveMetricsFlags({});

    expect(flags.contextFencing).toBe(true); // Default ON per plan (DX review #2)
    expect(flags.citationTracking).toBe(false);
    expect(flags.skillProposalTool).toBe(false);
    expect(flags.sessionMetrics).toBe(false);
  });

  it("respects explicit memory experimental overrides", () => {
    const flags = resolveMetricsFlags({
      memory: { experimental: { contextFencing: false, citationTracking: true } },
    });

    expect(flags.contextFencing).toBe(false);
    expect(flags.citationTracking).toBe(true);
  });

  it("respects explicit skills experimental overrides", () => {
    const flags = resolveMetricsFlags({
      skills: { experimental: { proposalTool: true } },
    });

    expect(flags.skillProposalTool).toBe(true);
  });

  it("respects metrics experimental overrides", () => {
    const flags = resolveMetricsFlags({
      metrics: { experimental: { sessionMetrics: true } },
    });

    expect(flags.sessionMetrics).toBe(true);
  });

  it("handles undefined experimental sections gracefully", () => {
    const flags = resolveMetricsFlags({
      memory: {},
      skills: {},
    });

    expect(flags.contextFencing).toBe(true);
    expect(flags.skillProposalTool).toBe(false);
  });
});
