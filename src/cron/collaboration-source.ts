import { parseDurationMs } from "../cli/parse-duration.js";
import type { CollaborationConfig } from "../config/types.collaboration.js";
import type { CronDelivery, CronJob, CronJobCollaborationMeta, CronSchedule } from "./types.js";

export const COLLABORATION_CRON_JOB_ID_PREFIX = "collab:";

function sortedEntries<T>(record: Record<string, T>) {
  return Object.entries(record).toSorted(([a], [b]) => a.localeCompare(b));
}

function resolveRoleDefaultAccountId(
  collaboration: CollaborationConfig,
  roleId: string | undefined,
): string | undefined {
  if (!roleId) {
    return undefined;
  }
  const role = collaboration.roles[roleId];
  const bot = role ? collaboration.bots[role.defaultBotId] : undefined;
  return bot?.slackAccountId?.trim() || undefined;
}

function resolveSlackUserIdByIdentityId(
  collaboration: CollaborationConfig,
  identityId: string | undefined,
): string | undefined {
  if (!identityId) {
    return undefined;
  }
  for (const [slackUserId, binding] of sortedEntries(collaboration.identities.users)) {
    if (binding.identityId === identityId) {
      return slackUserId;
    }
  }
  return undefined;
}

function resolveAudienceRole(
  collaboration: CollaborationConfig,
  audience: CronJobCollaborationMeta["audience"],
): string | undefined {
  if (audience.kind === "role") {
    return audience.id;
  }
  if (audience.kind === "space") {
    return collaboration.spaces[audience.id]?.ownerRole;
  }
  for (const binding of Object.values(collaboration.identities.users)) {
    if (binding.identityId === audience.id) {
      return binding.defaultRole ?? binding.roles[0];
    }
  }
  return undefined;
}

function compileSchedule(params: {
  job: NonNullable<CollaborationConfig["schedules"]>["jobs"][number];
  nowMs: number;
}): CronSchedule | null {
  const { job, nowMs } = params;
  if (job.at?.trim()) {
    return { kind: "at", at: job.at.trim() };
  }
  if (job.every?.trim()) {
    const everyMs = parseDurationMs(job.every.trim());
    return { kind: "every", everyMs, anchorMs: nowMs };
  }
  if (job.cron?.trim()) {
    return {
      kind: "cron",
      expr: job.cron.trim(),
      ...(job.tz?.trim() ? { tz: job.tz.trim() } : {}),
    };
  }
  return null;
}

function resolveIdentityBindingByIdentityId(
  collaboration: CollaborationConfig,
  identityId: string | undefined,
) {
  if (!identityId) {
    return undefined;
  }
  for (const binding of Object.values(collaboration.identities.users)) {
    if (binding.identityId === identityId) {
      return binding;
    }
  }
  return undefined;
}

function resolveDeliveryTarget(params: {
  collaboration: CollaborationConfig;
  ownerRole: string;
  audience: CronJobCollaborationMeta["audience"];
  target: NonNullable<CollaborationConfig["schedules"]>["jobs"][number]["delivery"][number];
  depth?: number;
}): CronDelivery | null {
  const depth = params.depth ?? 0;
  if (depth > 4) {
    return null;
  }
  if (params.target.kind === "slack_channel") {
    return {
      mode: "announce",
      channel: "slack",
      to: `channel:${params.target.channelId}`,
      accountId: resolveRoleDefaultAccountId(params.collaboration, params.ownerRole),
    };
  }
  if (params.target.kind === "space_default") {
    const defaults =
      params.collaboration.spaces[params.target.spaceId]?.schedules?.defaultDestinations ?? [];
    const next = defaults[0];
    if (!next) {
      return null;
    }
    return resolveDeliveryTarget({
      ...params,
      target: next,
      depth: depth + 1,
    });
  }

  const identityId =
    params.target.identityId ??
    (params.audience.kind === "identity" ? params.audience.id : undefined);
  const slackUserId = resolveSlackUserIdByIdentityId(params.collaboration, identityId);
  if (!slackUserId) {
    return null;
  }

  const identityBinding = resolveIdentityBindingByIdentityId(params.collaboration, identityId);
  const fallbackBotId = identityBinding?.scheduleDelivery?.fallbackBotId;
  const fallbackAccountId = fallbackBotId
    ? params.collaboration.bots[fallbackBotId]?.slackAccountId
    : undefined;
  const accountId =
    fallbackAccountId ||
    resolveRoleDefaultAccountId(params.collaboration, params.target.roleId ?? params.ownerRole);
  return {
    mode: "announce",
    channel: "slack",
    to: `user:${slackUserId}`,
    ...(accountId ? { accountId } : {}),
  };
}

function buildScheduleMessage(params: {
  job: NonNullable<CollaborationConfig["schedules"]>["jobs"][number];
  collaboration: CronJobCollaborationMeta;
}): string {
  const lines = [
    "Generate a collaboration schedule digest for Slack delivery.",
    `Collaboration schedule ID: ${params.job.id}.`,
    `Audience: ${params.collaboration.audience.kind}:${params.collaboration.audience.id}.`,
    `Owner role: ${params.collaboration.ownerRole}.`,
    `Effective role: ${params.collaboration.effectiveRole}.`,
    `Source spaces: ${params.collaboration.sourceSpaces.join(", ")}.`,
    `Readable collaboration memory scopes: ${params.collaboration.readableScopes.join(", ")}.`,
    params.collaboration.publishableScopes?.length
      ? `Publishable collaboration scopes: ${params.collaboration.publishableScopes.join(", ")}.`
      : "Do not publish new shared memory during this schedule run.",
    params.job.template?.trim() ? `Template: ${params.job.template.trim()}.` : undefined,
    "Return one final Slack-ready message body. Fallback delivery is handled by cron.",
    params.job.systemPrompt?.trim() ? params.job.systemPrompt.trim() : undefined,
  ];
  return lines.filter((line): line is string => Boolean(line?.trim())).join("\n");
}

export function compileCollaborationCronJobs(params: {
  collaboration: CollaborationConfig | null | undefined;
  nowMs: number;
}): { jobs: CronJob[]; ids: Set<string> } {
  const collaboration = params.collaboration;
  if (!collaboration || collaboration.mode === "disabled" || collaboration.mode === "shadow") {
    return { jobs: [], ids: new Set() };
  }

  const jobs: CronJob[] = [];
  const ids = new Set<string>();

  for (const job of collaboration.schedules?.jobs ?? []) {
    const ownerRole = job.ownerRole ?? resolveAudienceRole(collaboration, job.audience);
    if (!ownerRole) {
      continue;
    }
    const role = collaboration.roles[ownerRole];
    if (!role?.defaultAgentId) {
      continue;
    }
    const schedule = compileSchedule({ job, nowMs: params.nowMs });
    if (!schedule) {
      continue;
    }
    const primaryTarget = job.delivery[0];
    if (!primaryTarget) {
      continue;
    }
    const effectiveRole = ownerRole;
    const readableScopes = [...(job.memoryReadScopes ?? [])];
    const sourceSpaceId =
      readableScopes.includes("space_shared") && job.sourceSpaces.length === 1
        ? job.sourceSpaces[0]
        : undefined;
    const collaborationMeta: CronJobCollaborationMeta = {
      source: "collaboration",
      sourceJobId: job.id,
      audience: job.audience,
      ownerRole,
      effectiveRole,
      readableScopes,
      publishableScopes: [],
      sourceSpaces: [...job.sourceSpaces],
      ...(sourceSpaceId ? { spaceId: sourceSpaceId } : {}),
    };
    const delivery = resolveDeliveryTarget({
      collaboration,
      ownerRole,
      audience: job.audience,
      target: primaryTarget,
    });
    if (!delivery) {
      continue;
    }

    const compiledJobId = `${COLLABORATION_CRON_JOB_ID_PREFIX}${job.id}`;
    jobs.push({
      id: compiledJobId,
      name: job.id,
      description: `Collaboration schedule for ${job.audience.kind}:${job.audience.id}`,
      enabled: job.enabled ?? true,
      deleteAfterRun: false,
      createdAtMs: params.nowMs,
      updatedAtMs: params.nowMs,
      schedule,
      sessionTarget: "isolated",
      wakeMode: "next-heartbeat",
      payload: {
        kind: "agentTurn",
        message: buildScheduleMessage({ job, collaboration: collaborationMeta }),
        ...(job.systemPrompt?.trim() ? { lightContext: true } : {}),
      },
      agentId: role.defaultAgentId,
      delivery,
      state: {},
      collaboration: collaborationMeta,
    });
    ids.add(compiledJobId);
  }

  return { jobs, ids };
}

export function isCollaborationCronJobId(id: string): boolean {
  return id.startsWith(COLLABORATION_CRON_JOB_ID_PREFIX);
}
