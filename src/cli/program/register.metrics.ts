import type { Command } from "commander";
import { metricsSummaryCommand } from "../../commands/metrics-summary.js";
import { defaultRuntime } from "../../runtime.js";
import { runCommandWithRuntime } from "../cli-utils.js";

export function registerMetricsCommand(program: Command) {
  const metrics = program.command("metrics").description("View agent session metrics");

  metrics
    .command("summary")
    .description("Show metrics summary for an agent")
    .option("--agent <id>", "Agent ID (default: main)")
    .option("--json", "Output as JSON", false)
    .action(async (opts: { agent?: string; json?: boolean }) => {
      await runCommandWithRuntime(defaultRuntime, () => metricsSummaryCommand(opts));
    });
}
