export type SlackThreadOwnershipRecord = {
  ownerAgentId: string;
  boundAt: number;
  lastActivityAt: number;
  lastExplicitSwitchAt?: number;
};

const threadOwnershipStore = new Map<string, SlackThreadOwnershipRecord>();

function buildSlackThreadOwnershipKey(params: {
  accountId?: string | null;
  channelId: string;
  threadTs: string;
}): string {
  return `${params.accountId?.trim() || "default"}:${params.channelId}:${params.threadTs}`;
}

export function readSlackThreadOwnership(params: {
  accountId?: string | null;
  channelId: string;
  threadTs: string;
}): SlackThreadOwnershipRecord | null {
  return (
    threadOwnershipStore.get(
      buildSlackThreadOwnershipKey({
        accountId: params.accountId,
        channelId: params.channelId,
        threadTs: params.threadTs,
      }),
    ) ?? null
  );
}

export function writeSlackThreadOwnership(params: {
  accountId?: string | null;
  channelId: string;
  threadTs: string;
  ownerAgentId: string;
  explicitSwitch?: boolean;
  nowMs?: number;
}): SlackThreadOwnershipRecord {
  const nowMs = params.nowMs ?? Date.now();
  const existing = readSlackThreadOwnership(params);
  const next: SlackThreadOwnershipRecord = {
    ownerAgentId: params.ownerAgentId,
    boundAt: existing?.boundAt ?? nowMs,
    lastActivityAt: nowMs,
    ...(params.explicitSwitch
      ? { lastExplicitSwitchAt: nowMs }
      : existing?.lastExplicitSwitchAt
        ? { lastExplicitSwitchAt: existing.lastExplicitSwitchAt }
        : {}),
  };
  threadOwnershipStore.set(
    buildSlackThreadOwnershipKey({
      accountId: params.accountId,
      channelId: params.channelId,
      threadTs: params.threadTs,
    }),
    next,
  );
  return next;
}

export function touchSlackThreadOwnership(params: {
  accountId?: string | null;
  channelId: string;
  threadTs: string;
  nowMs?: number;
}): SlackThreadOwnershipRecord | null {
  const existing = readSlackThreadOwnership(params);
  if (!existing) {
    return null;
  }
  const next = {
    ...existing,
    lastActivityAt: params.nowMs ?? Date.now(),
  };
  threadOwnershipStore.set(
    buildSlackThreadOwnershipKey({
      accountId: params.accountId,
      channelId: params.channelId,
      threadTs: params.threadTs,
    }),
    next,
  );
  return next;
}

export function clearSlackThreadOwnershipStoreForTest(): void {
  threadOwnershipStore.clear();
}
