export type MetricsExperimentalConfig = {
  /** Record session metrics to SQLite. Default: false. */
  sessionMetrics?: boolean;
};

export type MetricsConfig = {
  experimental?: MetricsExperimentalConfig;
};
