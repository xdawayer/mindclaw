import { resolveApprovalApprovers } from "openclaw/plugin-sdk/approval-auth-runtime";
import {
  createChannelExecApprovalProfile,
  isChannelExecApprovalClientEnabledFromConfig,
  isChannelExecApprovalTargetRecipient,
  matchesApprovalRequestFilters,
} from "openclaw/plugin-sdk/approval-client-runtime";
import { doesApprovalRequestMatchChannelAccount } from "openclaw/plugin-sdk/approval-native-runtime";
import {
  hasManagedCollaborationApprovalContext,
  resolveCollaborationApprovalApproverUserIds,
  resolveCollaborationExecApprovalPolicy,
} from "openclaw/plugin-sdk/collaboration-runtime";
import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import type { ExecApprovalRequest } from "openclaw/plugin-sdk/infra-runtime";
import { normalizeStringifiedOptionalString } from "openclaw/plugin-sdk/text-runtime";
import { resolveSlackAccount } from "./accounts.js";

export function normalizeSlackApproverId(value: string | number): string | undefined {
  const trimmed = normalizeStringifiedOptionalString(value);
  if (!trimmed) {
    return undefined;
  }
  const prefixed = trimmed.match(/^(?:slack|user):([A-Z0-9]+)$/i);
  if (prefixed?.[1]) {
    return prefixed[1];
  }
  const mention = trimmed.match(/^<@([A-Z0-9]+)>$/i);
  if (mention?.[1]) {
    return mention[1];
  }
  return /^[UW][A-Z0-9]+$/i.test(trimmed) ? trimmed : undefined;
}

function resolveSlackOwnerApprovers(cfg: OpenClawConfig): string[] {
  const ownerAllowFrom = cfg.commands?.ownerAllowFrom;
  if (!Array.isArray(ownerAllowFrom) || ownerAllowFrom.length === 0) {
    return [];
  }
  return resolveApprovalApprovers({
    explicit: ownerAllowFrom,
    normalizeApprover: normalizeSlackApproverId,
  });
}

function resolveStaticSlackExecApprovalApprovers(params: {
  cfg: OpenClawConfig;
  accountId?: string | null;
}): string[] {
  const account = resolveSlackAccount(params).config;
  return resolveApprovalApprovers({
    explicit: account.execApprovals?.approvers ?? resolveSlackOwnerApprovers(params.cfg),
    normalizeApprover: normalizeSlackApproverId,
  });
}

export function getSlackExecApprovalApprovers(params: {
  cfg: OpenClawConfig;
  accountId?: string | null;
  request?: ExecApprovalRequest;
}): string[] {
  const requestApprovers = params.request
    ? resolveCollaborationExecApprovalPolicy({
        cfg: params.cfg,
        request: params.request,
      })?.approverSlackUserIds
    : undefined;
  if (requestApprovers?.length) {
    return [...requestApprovers];
  }
  const staticApprovers = resolveStaticSlackExecApprovalApprovers(params);
  if (staticApprovers.length > 0) {
    return staticApprovers;
  }
  // Without a request we cannot scope to a specific collaboration policy.
  // Returning the union of all policies' approvers would let anyone listed in
  // any policy authorize unrelated managed exec requests, which is a bypass.
  // Use hasSlackExecApprovalApprovers for "are there any approvers anywhere"
  // probes (e.g. auto-enable client) and pass `request` to scope per policy.
  return [];
}

export function hasSlackExecApprovalApprovers(params: {
  cfg: OpenClawConfig;
  accountId?: string | null;
}): boolean {
  if (resolveStaticSlackExecApprovalApprovers(params).length > 0) {
    return true;
  }
  return (
    resolveCollaborationApprovalApproverUserIds({
      cfg: params.cfg,
    }).length > 0
  );
}

function resolveSlackExecApprovalRequestTarget(params: {
  cfg: OpenClawConfig;
  accountId?: string | null;
  request: ExecApprovalRequest;
}): "dm" | "channel" | "both" {
  const delivery = resolveCollaborationExecApprovalPolicy({
    cfg: params.cfg,
    request: params.request,
  })?.delivery;
  if (delivery?.length) {
    const includesDm = delivery.includes("dm");
    const includesOrigin = delivery.includes("origin_thread");
    if (includesDm && includesOrigin) {
      return "both";
    }
    if (includesOrigin) {
      return "channel";
    }
    return "dm";
  }
  return resolveSlackExecApprovalTarget(params);
}

export function isSlackExecApprovalTargetRecipient(params: {
  cfg: OpenClawConfig;
  senderId?: string | null;
  accountId?: string | null;
}): boolean {
  return isChannelExecApprovalTargetRecipient({
    ...params,
    channel: "slack",
    normalizeSenderId: normalizeSlackApproverId,
    matchTarget: ({ target, normalizedSenderId }) =>
      normalizeSlackApproverId(target.to) === normalizedSenderId,
  });
}

const slackExecApprovalProfile = createChannelExecApprovalProfile({
  resolveConfig: (params) => resolveSlackAccount(params).config.execApprovals,
  resolveApprovers: getSlackExecApprovalApprovers,
  normalizeSenderId: normalizeSlackApproverId,
  isTargetRecipient: isSlackExecApprovalTargetRecipient,
  matchesRequestAccount: (params) =>
    doesApprovalRequestMatchChannelAccount({
      cfg: params.cfg,
      request: params.request,
      channel: "slack",
      accountId: params.accountId,
    }),
});

export function isSlackExecApprovalClientEnabled(params: {
  cfg: OpenClawConfig;
  accountId?: string | null;
}): boolean {
  const config = resolveSlackAccount(params).config.execApprovals;
  return isChannelExecApprovalClientEnabledFromConfig({
    enabled: config?.enabled,
    approverCount: hasSlackExecApprovalApprovers(params) ? 1 : 0,
  });
}
export const isSlackExecApprovalApprover = slackExecApprovalProfile.isApprover;
export const isSlackExecApprovalAuthorizedSender = slackExecApprovalProfile.isAuthorizedSender;
export const resolveSlackExecApprovalTarget = slackExecApprovalProfile.resolveTarget;
export const shouldSuppressLocalSlackExecApprovalPrompt =
  slackExecApprovalProfile.shouldSuppressLocalPrompt;

export function shouldHandleSlackExecApprovalRequest(params: {
  cfg: OpenClawConfig;
  accountId?: string | null;
  request: ExecApprovalRequest;
}): boolean {
  if (
    !doesApprovalRequestMatchChannelAccount({
      cfg: params.cfg,
      request: params.request,
      channel: "slack",
      accountId: params.accountId,
    })
  ) {
    return false;
  }
  const config = resolveSlackAccount(params).config.execApprovals;
  if (
    !isChannelExecApprovalClientEnabledFromConfig({
      enabled: config?.enabled,
      approverCount: hasSlackExecApprovalApprovers(params) ? 1 : 0,
    })
  ) {
    return false;
  }
  const collaborationPolicy = resolveCollaborationExecApprovalPolicy({
    cfg: params.cfg,
    request: params.request,
  });
  if (collaborationPolicy) {
    return true;
  }
  if (
    hasManagedCollaborationApprovalContext({
      cfg: params.cfg,
      request: params.request,
    })
  ) {
    return false;
  }
  return matchesApprovalRequestFilters({
    request: params.request.request,
    agentFilter: config?.agentFilter,
    sessionFilter: config?.sessionFilter,
    fallbackAgentIdFromSessionKey: true,
  });
}

export { resolveSlackExecApprovalRequestTarget };
