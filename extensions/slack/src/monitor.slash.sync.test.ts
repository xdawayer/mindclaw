import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createApprovedSharedSyncPayload,
  createDmToProjectSyncRequest,
} from "../../../src/collaboration/sync-requests.js";
import type {
  CollaborationPrivateSpace,
  CollaborationProjectSpace,
} from "../../../src/collaboration/types.js";
import { getSlackSlashMocks, resetSlackSlashMocks } from "./monitor/slash.test-harness.js";

type RegisterFn = (params: { ctx: unknown; account: unknown }) => Promise<void>;
const { registerSlackMonitorSlashCommands } = (await import("./monitor/slash.js")) as {
  registerSlackMonitorSlashCommands: RegisterFn;
};

const { dispatchMock } = getSlackSlashMocks();

const privateSpace: CollaborationPrivateSpace = {
  kind: "private",
  userId: "UREQUESTER",
  scope: "private:UREQUESTER",
};

const projectSpace: CollaborationProjectSpace = {
  kind: "project",
  id: "proj-a",
  channelId: "CPROJ1234",
  defaultAgent: "product",
  defaultDmRecipient: "UREQUESTER",
  roleDmRecipients: {},
  scope: "project:proj-a",
};

function encodeReviewToken(request: ReturnType<typeof createDmToProjectSyncRequest>) {
  return Buffer.from(JSON.stringify(request), "utf8").toString("base64url");
}

function createSyncReviewHarness(overrides?: {
  approver?: string;
  resolveChannelName?: () => Promise<{ name?: string; type?: string }>;
}) {
  const commands = new Map<string, (args: unknown) => Promise<void>>();
  const actions = new Map<string, (args: unknown) => Promise<void>>();
  const postEphemeral = vi.fn().mockResolvedValue({ ok: true });
  const app = {
    client: { chat: { postEphemeral } },
    command: (name: string, handler: (args: unknown) => Promise<void>) => {
      commands.set(name, handler);
    },
    action: (id: string, handler: (args: unknown) => Promise<void>) => {
      actions.set(id, handler);
    },
  };

  const ctx = {
    cfg: {
      commands: { native: false, nativeSkills: false },
      collaboration: overrides?.approver
        ? {
            sync: {
              dmToShared: {
                approver: overrides.approver,
              },
            },
          }
        : undefined,
    },
    runtime: {},
    botToken: "bot-token",
    botUserId: "bot",
    teamId: "T1",
    allowFrom: ["*"],
    dmEnabled: true,
    dmPolicy: "open",
    groupDmEnabled: false,
    groupDmChannels: [],
    defaultRequireMention: true,
    groupPolicy: "open",
    useAccessGroups: false,
    channelsConfig: undefined,
    slashCommand: {
      enabled: true,
      name: "openclaw",
      ephemeral: true,
      sessionPrefix: "slack:slash",
    },
    textLimit: 4000,
    app,
    isChannelAllowed: () => true,
    resolveChannelName: overrides?.resolveChannelName ?? (async () => ({ name: "dm", type: "im" })),
    resolveUserName: async () => ({ name: "Ada" }),
  } as const;

  const account = {
    accountId: "acct",
    config: { commands: { native: false, nativeSkills: false } },
  };

  return { commands, actions, ctx, account, postEphemeral };
}

function requireHandler(
  handlers: Map<string | RegExp, (args: unknown) => Promise<void>>,
  matcher: string | RegExp,
  label: string,
) {
  const direct = handlers.get(matcher);
  if (direct) {
    return direct;
  }
  for (const [key, handler] of handlers.entries()) {
    if (matcher instanceof RegExp) {
      if (key instanceof RegExp && key.source === matcher.source) {
        return handler;
      }
      continue;
    }
    if (typeof key === "string" && key === matcher) {
      return handler;
    }
  }
  throw new Error(`Missing ${label} handler`);
}

function requireFirstHandler(
  handlers: Map<string | RegExp, (args: unknown) => Promise<void>>,
  label: string,
) {
  const handler = handlers.values().next().value as ((args: unknown) => Promise<void>) | undefined;
  if (!handler) {
    throw new Error(`Missing ${label} handler`);
  }
  return handler;
}

async function runReviewSlash(params: {
  handler: (args: unknown) => Promise<void>;
  token: string;
  userId?: string;
  channelId?: string;
  channelName?: string;
}) {
  const respond = vi.fn().mockResolvedValue(undefined);
  const ack = vi.fn().mockResolvedValue(undefined);
  await params.handler({
    command: {
      user_id: params.userId ?? "UREQUESTER",
      user_name: "Ada",
      channel_id: params.channelId ?? "DREQUESTER",
      channel_name: params.channelName ?? "directmessage",
      text: `sync-review ${params.token}`,
      trigger_id: "trigger-1",
    },
    ack,
    respond,
  });
  return { ack, respond };
}

async function runSyncAction(params: {
  handler: (args: unknown) => Promise<void>;
  actionId: string;
  value: string;
  userId?: string;
  channelId?: string;
  channelName?: string;
}) {
  const respond = vi.fn().mockResolvedValue(undefined);
  const ack = vi.fn().mockResolvedValue(undefined);
  await params.handler({
    ack,
    action: {
      action_id: params.actionId,
      value: params.value,
    },
    body: {
      user: { id: params.userId ?? "UREQUESTER", name: "Ada" },
      channel: {
        id: params.channelId ?? "DREQUESTER",
        name: params.channelName ?? "directmessage",
      },
      trigger_id: "trigger-1",
    },
    respond,
  });
  return { ack, respond };
}

beforeEach(() => {
  resetSlackSlashMocks();
});

describe("Slack sync review slash flow", () => {
  it("renders approve and reject buttons for a pending sync request", async () => {
    const harness = createSyncReviewHarness();
    await registerSlackMonitorSlashCommands({
      ctx: harness.ctx as never,
      account: harness.account as never,
    });

    const slashHandler = requireFirstHandler(harness.commands, "/openclaw");
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UREQUESTER",
      content: "Ship only this excerpt",
    });

    const { ack, respond } = await runReviewSlash({
      handler: slashHandler,
      token: encodeReviewToken(request),
    });

    expect(ack).toHaveBeenCalledTimes(1);
    expect(dispatchMock).not.toHaveBeenCalled();
    expect(respond).toHaveBeenCalledTimes(1);
    expect(respond).toHaveBeenCalledWith(
      expect.objectContaining({
        response_type: "ephemeral",
        text: expect.stringContaining("Pending DM-to-shared sync request"),
        blocks: expect.arrayContaining([
          expect.objectContaining({ type: "header" }),
          expect.objectContaining({ type: "section" }),
          expect.objectContaining({
            type: "actions",
            elements: expect.arrayContaining([
              expect.objectContaining({
                action_id: "openclaw_sync_review_approve",
                text: expect.objectContaining({ text: "Approve sync" }),
              }),
              expect.objectContaining({
                action_id: "openclaw_sync_review_reject",
                text: expect.objectContaining({ text: "Reject sync" }),
                style: "danger",
              }),
            ]),
          }),
        ]),
      }),
    );
  });

  it("approves a sync request and replies with the shared payload summary", async () => {
    const harness = createSyncReviewHarness();
    await registerSlackMonitorSlashCommands({
      ctx: harness.ctx as never,
      account: harness.account as never,
    });

    const slashHandler = requireFirstHandler(harness.commands, "/openclaw");
    const approveHandler = requireHandler(
      harness.actions,
      "openclaw_sync_review_approve",
      "sync approve action",
    );
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UREQUESTER",
      content: "Ship only this excerpt",
    });

    const { respond: reviewRespond } = await runReviewSlash({
      handler: slashHandler,
      token: encodeReviewToken(request),
    });
    const actionsBlock = (
      reviewRespond.mock.calls[0]?.[0] as {
        blocks?: Array<{
          type: string;
          elements?: Array<{ action_id?: string; value?: string }>;
        }>;
      }
    ).blocks?.find((block) => block.type === "actions");
    const approveButton = actionsBlock?.elements?.find(
      (element) => element.action_id === "openclaw_sync_review_approve",
    );

    const { ack, respond } = await runSyncAction({
      handler: approveHandler,
      actionId: "openclaw_sync_review_approve",
      value: approveButton?.value ?? "",
    });

    expect(ack).toHaveBeenCalledTimes(1);
    expect(respond).toHaveBeenCalledWith({
      text: `Approved sync request ${request.id}.\nScope: project:proj-a\nContent: Ship only this excerpt`,
      response_type: "ephemeral",
      replace_original: true,
    });
    expect(createApprovedSharedSyncPayload({ request })).toEqual({
      scope: "project:proj-a",
      content: "Ship only this excerpt",
      sourceSlackUserId: "UREQUESTER",
      sourceScope: "private:UREQUESTER",
      targetKind: "project",
      targetId: "proj-a",
    });
  });

  it("rejects review attempts from a different explicit approver", async () => {
    const harness = createSyncReviewHarness({ approver: "UAPPROVER1" });
    await registerSlackMonitorSlashCommands({
      ctx: harness.ctx as never,
      account: harness.account as never,
    });

    const slashHandler = requireFirstHandler(harness.commands, "/openclaw");
    const request = createDmToProjectSyncRequest({
      source: privateSpace,
      project: projectSpace,
      requesterSlackUserId: "UREQUESTER",
      content: "Ship only this excerpt",
    });

    const { ack, respond } = await runReviewSlash({
      handler: slashHandler,
      token: encodeReviewToken(request),
      userId: "UNAUTHORIZED",
    });

    expect(ack).toHaveBeenCalledTimes(1);
    expect(dispatchMock).not.toHaveBeenCalled();
    expect(respond).toHaveBeenCalledWith({
      text: "You are not authorized to review this sync request.",
      response_type: "ephemeral",
    });
  });
});
