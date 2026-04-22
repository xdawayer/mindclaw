import type { CronFailureDestinationConfig } from "../config/types.cron.js";
import type { OpenClawConfig } from "../config/types.openclaw.js";
import {
  normalizeLowercaseStringOrEmpty,
  normalizeOptionalLowercaseString,
  normalizeOptionalString,
  normalizeOptionalThreadValue,
} from "../shared/string-coerce.js";
import {
  resolveCronCollaborationDeliveryTarget,
  resolveCronCollaborationFailureTarget,
} from "./collaboration-delivery.js";
import type {
  CronCollaborationTarget,
  CronDelivery,
  CronDeliveryMode,
  CronJob,
  CronMessageChannel,
} from "./types.js";

export type CronDeliveryPlan = {
  mode: CronDeliveryMode;
  channel?: CronMessageChannel;
  to?: string;
  threadId?: string | number;
  /** Explicit channel account id from the delivery config, if set. */
  accountId?: string;
  source: "delivery";
  requested: boolean;
};

export type CronDeliveryResolutionOptions = {
  cfg?: OpenClawConfig;
  collaborationTarget?: CronCollaborationTarget;
};

function normalizeChannel(value: unknown): CronMessageChannel | undefined {
  const trimmed = normalizeOptionalLowercaseString(value);
  if (!trimmed) {
    return undefined;
  }
  return trimmed as CronMessageChannel;
}

export function resolveCronDeliveryPlan(
  job: CronJob,
  options?: CronDeliveryResolutionOptions,
): CronDeliveryPlan {
  const delivery = job.delivery;
  const hasDelivery = delivery && typeof delivery === "object";
  const rawMode = hasDelivery ? (delivery as { mode?: unknown }).mode : undefined;
  const normalizedMode =
    typeof rawMode === "string" ? normalizeLowercaseStringOrEmpty(rawMode) : rawMode;
  const mode =
    normalizedMode === "announce"
      ? "announce"
      : normalizedMode === "webhook"
        ? "webhook"
        : normalizedMode === "none"
          ? "none"
          : normalizedMode === "deliver"
            ? "announce"
            : undefined;

  const deliveryChannel = normalizeChannel(
    (delivery as { channel?: unknown } | undefined)?.channel,
  );
  const deliveryTo = normalizeOptionalString((delivery as { to?: unknown } | undefined)?.to);
  const deliveryThreadId = normalizeOptionalThreadValue(
    (delivery as { threadId?: unknown } | undefined)?.threadId,
  );
  const channel = deliveryChannel ?? "last";
  const to = deliveryTo;
  const deliveryAccountId = normalizeOptionalString(
    (delivery as { accountId?: unknown } | undefined)?.accountId,
  );
  if (hasDelivery) {
    const resolvedMode = mode ?? "announce";
    return {
      mode: resolvedMode,
      channel: resolvedMode === "announce" ? channel : undefined,
      to,
      threadId: resolvedMode === "announce" ? deliveryThreadId : undefined,
      accountId: deliveryAccountId,
      source: "delivery",
      requested: resolvedMode === "announce",
    };
  }

  const collaborationDelivery = resolveCronCollaborationDeliveryTarget({
    cfg: options?.cfg,
    collaborationTarget: options?.collaborationTarget,
  });
  if (collaborationDelivery) {
    return {
      mode: "announce",
      channel: collaborationDelivery.channel,
      to: collaborationDelivery.to,
      threadId: undefined,
      accountId: undefined,
      source: "delivery",
      requested: true,
    };
  }

  const isIsolatedAgentTurn =
    job.payload.kind === "agentTurn" &&
    (job.sessionTarget === "isolated" ||
      job.sessionTarget === "current" ||
      job.sessionTarget.startsWith("session:"));
  const resolvedMode = isIsolatedAgentTurn ? "announce" : "none";

  return {
    mode: resolvedMode,
    channel: resolvedMode === "announce" ? "last" : undefined,
    to: undefined,
    threadId: undefined,
    source: "delivery",
    requested: resolvedMode === "announce",
  };
}

export type CronFailureDeliveryPlan = {
  mode: "announce" | "webhook";
  channel?: CronMessageChannel;
  to?: string;
  accountId?: string;
};

export type CronFailureDestinationInput = {
  channel?: CronMessageChannel;
  to?: string;
  accountId?: string;
  mode?: "announce" | "webhook";
};

function normalizeFailureMode(value: unknown): "announce" | "webhook" | undefined {
  const trimmed = normalizeOptionalLowercaseString(value);
  if (trimmed === "announce" || trimmed === "webhook") {
    return trimmed;
  }
  return undefined;
}

export function resolveFailureDestination(
  job: CronJob,
  globalConfig?: CronFailureDestinationConfig,
  options?: CronDeliveryResolutionOptions,
): CronFailureDeliveryPlan | null {
  const delivery = job.delivery;
  const jobFailureDest = delivery?.failureDestination as CronFailureDestinationInput | undefined;
  const hasJobFailureDest = jobFailureDest && typeof jobFailureDest === "object";

  const base = {
    channel: undefined as CronMessageChannel | undefined,
    to: undefined as string | undefined,
    accountId: undefined as string | undefined,
    mode: undefined as "announce" | "webhook" | undefined,
  };

  const collaborationFailureTarget = resolveCronCollaborationFailureTarget({
    cfg: options?.cfg,
    collaborationTarget: options?.collaborationTarget,
  });
  if (collaborationFailureTarget) {
    base.channel = collaborationFailureTarget.channel;
    base.to = collaborationFailureTarget.to;
  }

  applyFailureDestinationLayer(base, globalConfig);
  if (hasJobFailureDest) {
    applyFailureDestinationLayer(base, jobFailureDest);
  }

  const { channel, to, accountId, mode } = base;

  if (!channel && !to && !accountId && !mode) {
    return null;
  }

  const resolvedMode = mode ?? "announce";
  if (resolvedMode === "webhook" && !to) {
    return null;
  }

  const result: CronFailureDeliveryPlan = {
    mode: resolvedMode,
    channel: resolvedMode === "announce" ? (channel ?? "last") : undefined,
    to,
    accountId,
  };

  if (delivery && isSameDeliveryTarget(delivery, result)) {
    return null;
  }

  return result;
}

function applyFailureDestinationLayer(
  state: {
    channel?: CronMessageChannel;
    to?: string;
    accountId?: string;
    mode?: "announce" | "webhook";
  },
  layer: CronFailureDestinationInput | CronFailureDestinationConfig | undefined,
): void {
  if (!layer || typeof layer !== "object") {
    return;
  }

  const nextChannel = normalizeChannel(layer.channel);
  const nextTo = normalizeOptionalString(layer.to);
  const nextAccountId = normalizeOptionalString(layer.accountId);
  const nextMode = normalizeFailureMode(layer.mode);
  const hasChannelField = "channel" in layer;
  const hasToField = "to" in layer;
  const hasAccountIdField = "accountId" in layer;
  const hasExplicitTo = hasToField && nextTo !== undefined;

  if (nextMode !== undefined) {
    const previousMode = state.mode ?? "announce";
    if (!hasExplicitTo && previousMode !== nextMode) {
      state.to = undefined;
    }
    state.mode = nextMode;
  }
  if (hasChannelField) {
    state.channel = nextChannel;
  }
  if (hasToField) {
    state.to = nextTo;
  }
  if (hasAccountIdField) {
    state.accountId = nextAccountId;
  }
}

function isSameDeliveryTarget(
  delivery: CronDelivery,
  failurePlan: CronFailureDeliveryPlan,
): boolean {
  const primaryMode = delivery.mode ?? "announce";
  if (primaryMode === "none") {
    return false;
  }

  const primaryChannel = delivery.channel;
  const primaryTo = delivery.to;
  const primaryAccountId = delivery.accountId;

  if (failurePlan.mode === "webhook") {
    return primaryMode === "webhook" && primaryTo === failurePlan.to;
  }

  const primaryChannelNormalized = primaryChannel ?? "last";
  const failureChannelNormalized = failurePlan.channel ?? "last";

  return (
    failureChannelNormalized === primaryChannelNormalized &&
    failurePlan.to === primaryTo &&
    failurePlan.accountId === primaryAccountId
  );
}
