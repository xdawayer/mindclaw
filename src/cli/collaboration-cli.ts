import type { Command } from "commander";
import { collaborationAuditCommand } from "../commands/collaboration-audit.js";
import { collaborationExplainCommand } from "../commands/collaboration-explain.js";
import { collaborationValidateCommand } from "../commands/collaboration-validate.js";
import { defaultRuntime } from "../runtime.js";
import { formatHelpExamples } from "./help-format.js";

const COLLABORATION_EXAMPLES = {
  main: [
    ["openclaw collaboration validate", "Validate the collaboration config surface."],
    [
      "openclaw collaboration explain --user U111PM001 --channel C111PROJ01",
      "Explain routing and policy for a Slack surface.",
    ],
    ["openclaw collaboration explain --user U111PM001 --json", "Emit JSON explain output."],
    [
      "openclaw collaboration audit --agent product --limit 10",
      "Inspect recent collaboration audit events for one agent workspace.",
    ],
  ],
  validate: [
    ["openclaw collaboration validate", "Validate the collaboration config surface."],
    ["openclaw collaboration validate --json", "Emit JSON validation output."],
  ],
  explain: [
    [
      "openclaw collaboration explain --user U111PM001 --channel C111PROJ01",
      "Explain a project channel route.",
    ],
    ["openclaw collaboration explain --user U111PM001", "Explain a DM route for a Slack user."],
    ["openclaw collaboration explain --user U111PM001 --json", "Emit JSON explain output."],
  ],
  audit: [
    [
      "openclaw collaboration audit --agent product --limit 10",
      "Read recent collaboration audit events for one agent workspace.",
    ],
    [
      "openclaw collaboration audit --agent product --type route --correlation handoff-1",
      "Filter route events down to one handoff chain.",
    ],
    [
      "openclaw collaboration audit --agent ops --type handoff-run --correlation handoff-1",
      "Inspect the started child run for one collaboration handoff chain.",
    ],
    [
      "openclaw collaboration audit --user U111PM001 --channel C111PROJ01 --type route",
      "Resolve the owner agent from a Slack surface and filter route events.",
    ],
    ["openclaw collaboration audit --agent product --json", "Emit JSON audit output."],
  ],
} as const;

export function registerCollaborationCli(program: Command) {
  const collaboration = program
    .command("collaboration")
    .description("Validate and explain Slack collaboration routing and policy")
    .addHelpText("after", () => `\nExamples:\n${formatHelpExamples(COLLABORATION_EXAMPLES.main)}\n`)
    .action(() => {
      collaboration.help({ error: true });
    });

  collaboration
    .command("validate")
    .description("Validate the collaboration config surface")
    .option("--json", "Output validation result as JSON", false)
    .addHelpText(
      "after",
      () => `\nExamples:\n${formatHelpExamples(COLLABORATION_EXAMPLES.validate)}\n`,
    )
    .action(async (opts) => {
      await collaborationValidateCommand({ json: Boolean(opts.json) }, defaultRuntime);
    });

  collaboration
    .command("audit")
    .description("Inspect persisted collaboration audit events")
    .option("--agent <agentId>", "Explicit agent id to inspect")
    .option("--user <slackUserId>", "Slack user id used to resolve the owner agent")
    .option("--channel <slackChannelId>", "Slack channel id used to resolve/filter route events")
    .option("--account <slackAccountId>", "Slack account id used to resolve/filter route events")
    .option("--thread <threadTs>", "Slack thread ts used to resolve/filter route events")
    .option("--type <eventType>", "Filter by event type: route | memory-published | handoff-run")
    .option("--correlation <handoffCorrelationId>", "Filter route events by handoff correlation id")
    .option("--limit <count>", "Maximum number of events to read", "20")
    .option("--json", "Output audit result as JSON", false)
    .addHelpText(
      "after",
      () => `\nExamples:\n${formatHelpExamples(COLLABORATION_EXAMPLES.audit)}\n`,
    )
    .action(async (opts) => {
      await collaborationAuditCommand(
        {
          agent: opts.agent as string | undefined,
          account: opts.account as string | undefined,
          user: opts.user as string | undefined,
          channel: opts.channel as string | undefined,
          thread: opts.thread as string | undefined,
          type: opts.type as "route" | "memory-published" | "handoff-run" | undefined,
          correlation: opts.correlation as string | undefined,
          limit: Number(opts.limit),
          json: Boolean(opts.json),
        },
        defaultRuntime,
      );
    });

  collaboration
    .command("explain")
    .description("Explain collaboration routing and policy for a Slack user and surface")
    .requiredOption("--user <slackUserId>", "Slack user id to resolve")
    .option("--channel <slackChannelId>", "Slack channel id to resolve")
    .option("--account <slackAccountId>", "Slack account id")
    .option("--thread <threadTs>", "Slack thread ts")
    .option("--json", "Output explain result as JSON", false)
    .addHelpText(
      "after",
      () => `\nExamples:\n${formatHelpExamples(COLLABORATION_EXAMPLES.explain)}\n`,
    )
    .action(async (opts) => {
      await collaborationExplainCommand(
        {
          account: opts.account as string | undefined,
          user: opts.user as string | undefined,
          channel: opts.channel as string | undefined,
          thread: opts.thread as string | undefined,
          json: Boolean(opts.json),
        },
        defaultRuntime,
      );
    });
}
