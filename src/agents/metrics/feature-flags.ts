/**
 * Experimental feature flags for the metrics-driven improvements.
 * These use a lightweight config shape to avoid coupling to the full OpenClawConfig type.
 */

export type MetricsFeatureFlags = {
  /** Wrap recalled memories with <memory-context> fencing tags. Default: true (DX review: default ON). */
  contextFencing: boolean;
  /** Track citation markers in model responses for memory hit rate. Default: false. */
  citationTracking: boolean;
  /** Enable the skill proposal tool for agents. Default: false. */
  skillProposalTool: boolean;
  /** Record session metrics to SQLite. Default: false. */
  sessionMetrics: boolean;
};

export type FeatureFlagConfig = {
  memory?: {
    experimental?: {
      contextFencing?: boolean;
      citationTracking?: boolean;
    };
  };
  skills?: {
    experimental?: {
      proposalTool?: boolean;
    };
  };
  metrics?: {
    experimental?: {
      sessionMetrics?: boolean;
    };
  };
};

export function resolveMetricsFlags(config: FeatureFlagConfig): MetricsFeatureFlags {
  return {
    contextFencing: config.memory?.experimental?.contextFencing ?? true,
    citationTracking: config.memory?.experimental?.citationTracking ?? false,
    skillProposalTool: config.skills?.experimental?.proposalTool ?? false,
    sessionMetrics: config.metrics?.experimental?.sessionMetrics ?? false,
  };
}
