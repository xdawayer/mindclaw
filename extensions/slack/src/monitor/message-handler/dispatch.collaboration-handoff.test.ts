import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { readCollaborationAuditEvents } from "openclaw/plugin-sdk/collaboration-runtime";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import {
  emitAgentEvent,
  resetAgentRunContextForTest,
} from "../../../../../src/infra/agent-events.js";
import {
  listTaskRecords,
  resetTaskRegistryControlRuntimeForTests,
  resetTaskRegistryDeliveryRuntimeForTests,
  resetTaskRegistryForTests,
} from "../../../../../src/tasks/task-registry.js";

const THREAD_TS = "thread-1";
const HANDOFF_RUN_ID = "run-handoff-1";
const OWNER_SESSION_KEY = "agent:product:slack:channel:c123";
const CHILD_SESSION_KEY = "agent:ops:slack:channel:c123";

const deliverRepliesMock = vi.fn(async () => {});
let dispatchBlocked = false;
let releaseDispatchBlock: (() => void) | null = null;
let dispatchRetryableErrorMessage: string | null = null;
let dispatchInboundWrap: ((inner: Error) => Error) | null = null;

const noop = () => {};
const noopAsync = async () => {};

function createPreparedSlackMessage(workspaceDir: string) {
  const opsWorkspace = path.join(workspaceDir, "workspace-ops");
  const productWorkspace = path.join(workspaceDir, "workspace-product");

  return {
    ctx: {
      cfg: {
        agents: {
          list: [
            { id: "product", workspace: productWorkspace },
            { id: "ops", workspace: opsWorkspace },
          ],
        },
      },
      runtime: {},
      botToken: "xoxb-test",
      app: { client: {} },
      teamId: "T1",
      textLimit: 4000,
      typingReaction: "",
      removeAckAfterReply: false,
      historyLimit: 0,
      channelHistories: new Map(),
      allowFrom: [],
      setSlackThreadStatus: async () => undefined,
    },
    account: {
      accountId: "default",
      config: {},
    },
    message: {
      channel: "C123",
      ts: "171234.111",
      thread_ts: THREAD_TS,
      user: "U123",
      text: "<@ops> please take this",
    },
    route: {
      agentId: "ops",
      accountId: "default",
      channel: "slack",
      sessionKey: CHILD_SESSION_KEY,
      mainSessionKey: "agent:ops:main",
      matchedBy: "collaboration.handoff",
    },
    collaboration: {
      mode: "enforced",
      explain: {
        ok: true,
        mode: "enforced",
        warnings: [],
        identity: {
          identityId: "alice",
          resolvedBy: "collaboration.identities.users",
          roles: ["product"],
          defaultRole: "product",
          effectiveRole: "product",
        },
        space: {
          spaceId: "project_main",
          kind: "project",
          resolvedBy: "slack.channel",
        },
        route: {
          ownerRole: "product",
          ownerAgentId: "product",
          ownerBotId: "product_bot",
          reason: "space_owner_role",
        },
        permissions: {
          granted: ["agent.handoff", "memory.read.private"],
          denied: [],
        },
        memory: {
          readableScopes: ["private"],
          writeDefaultScope: "private",
          publishableScopes: [],
        },
        handoff: {
          allowedTargets: ["ops"],
          maxDepth: 4,
          allowBotAuthoredReentry: false,
        },
        delivery: {
          replyThreadMode: "owner",
          managedSurface: true,
        },
        trace: {
          auditEvent: "slack-collaboration-enforced",
          auditJournalPath: "collaboration/.audit/events.jsonl",
          auditEventTypes: ["collaboration.route.resolved", "collaboration.memory.published"],
          handoffCorrelationField: "collaboration.handoff.correlationId",
          handoffArtifactField: "collaboration.handoff.artifactPath",
          handoffArtifactRoot: "collaboration/handoffs",
          memoryEventTypes: ["memory.collaboration.handoff", "memory.collaboration.published"],
        },
      },
      audit: {
        event: "slack-collaboration-enforced",
        accountId: "default",
        channelId: "C123",
        threadTs: THREAD_TS,
        senderUserId: "U123",
        spaceId: "project_main",
        legacyAgentId: "product",
        collaborationAgentId: "product",
        effectiveAgentId: "ops",
        handoffStatus: "accepted",
        handoffTargetRole: "ops",
        handoffCorrelationId: "handoff-1",
        handoffDepth: 1,
        handoffArtifactPath: "collaboration/handoffs/2026-04-23/handoff-1.json",
        memoryReadableScopes: ["private"],
        routeChanged: true,
        warningCodes: [],
      },
      memory: {
        effectiveReadableScopes: ["private"],
        effectivePublishableScopes: [],
      },
      handoff: {
        correlationId: "handoff-1",
        depth: 1,
        status: "accepted",
        trigger: "explicit_mention",
        sourceRole: "product",
        targetRole: "ops",
        targetAgentId: "ops",
        targetBotId: "ops_bot",
        artifactPath: "collaboration/handoffs/2026-04-23/handoff-1.json",
      },
      ownerRoute: {
        agentId: "product",
        accountId: "default",
        channel: "slack",
        sessionKey: OWNER_SESSION_KEY,
        mainSessionKey: "agent:product:main",
        matchedBy: "collaboration.space",
      },
      effectiveRoute: {
        agentId: "ops",
        accountId: "default",
        channel: "slack",
        sessionKey: CHILD_SESSION_KEY,
        mainSessionKey: "agent:ops:main",
        matchedBy: "collaboration.handoff",
      },
      systemPrompt: "Structured collaboration handoff.",
    },
    channelConfig: null,
    replyTarget: "channel:C123",
    ctxPayload: {
      MessageThreadId: THREAD_TS,
      SessionKey: CHILD_SESSION_KEY,
    },
    replyToMode: "all",
    isDirectMessage: false,
    isRoomish: false,
    historyKey: "history-key",
    preview: "",
    ackReactionValue: "eyes",
    ackReactionPromise: null,
  } as never;
}

vi.mock("openclaw/plugin-sdk/agent-runtime", () => ({
  resolveHumanDelayConfig: () => undefined,
}));

vi.mock("openclaw/plugin-sdk/channel-feedback", () => ({
  DEFAULT_TIMING: {
    doneHoldMs: 0,
    errorHoldMs: 0,
  },
  createStatusReactionController: () => ({
    setQueued: async () => {},
    setThinking: async () => {},
    setTool: async () => {},
    setError: async () => {},
    setDone: async () => {},
    clear: async () => {},
    restoreInitial: async () => {},
  }),
  logAckFailure: () => {},
  logTypingFailure: () => {},
  removeAckReactionAfterReply: () => {},
}));

vi.mock("openclaw/plugin-sdk/channel-lifecycle", () => ({
  deliverFinalizableDraftPreview: async (params: { deliverNormally: () => Promise<void> }) => {
    await params.deliverNormally();
    return "delivered";
  },
}));

vi.mock("openclaw/plugin-sdk/channel-reply-pipeline", () => ({
  createChannelReplyPipeline: () => ({
    typingCallbacks: {
      onIdle: vi.fn(),
    },
    onModelSelected: undefined,
  }),
}));

vi.mock("openclaw/plugin-sdk/channel-streaming", () => ({
  resolveChannelStreamingBlockEnabled: () => false,
  resolveChannelStreamingNativeTransport: () => false,
  resolveChannelStreamingPreviewToolProgress: () => false,
}));

vi.mock("openclaw/plugin-sdk/error-runtime", () => ({
  formatErrorMessage: (error: unknown) => String(error),
}));

vi.mock("openclaw/plugin-sdk/outbound-runtime", () => ({
  resolveAgentOutboundIdentity: () => undefined,
}));

vi.mock("openclaw/plugin-sdk/reply-history", () => ({
  clearHistoryEntriesIfEnabled: () => {},
}));

vi.mock("openclaw/plugin-sdk/reply-payload", () => ({
  resolveSendableOutboundReplyParts: (payload: { text?: string }) => {
    const text = (payload.text ?? "").trim();
    return {
      text,
      trimmedText: text,
      hasText: text.length > 0,
      hasMedia: false,
      mediaUrls: [],
      hasContent: text.length > 0,
    };
  },
}));

vi.mock("openclaw/plugin-sdk/reply-runtime", () => ({
  createReplyDispatcherWithTyping: (params: {
    deliver: (payload: unknown, info: { kind: "tool" | "block" | "final" }) => Promise<void>;
  }) => ({
    dispatcher: {
      deliver: params.deliver,
    },
    replyOptions: {},
    markDispatchIdle: () => {},
    markRunComplete: () => {},
  }),
  dispatchInboundMessage: async (params: {
    dispatcher: {
      deliver: (
        payload: { text: string },
        info: { kind: "tool" | "block" | "final" },
      ) => Promise<void>;
    };
    replyOptions?: {
      onAgentRunStart?: (runId: string) => void;
    };
  }) => {
    params.replyOptions?.onAgentRunStart?.(HANDOFF_RUN_ID);
    if (dispatchBlocked) {
      await new Promise<void>((resolve) => {
        releaseDispatchBlock = resolve;
      });
    }
    if (dispatchRetryableErrorMessage) {
      const message = dispatchRetryableErrorMessage;
      const { SlackRetryableInboundError } = await import("../message-handler.js");
      const inner = new SlackRetryableInboundError(message);
      throw dispatchInboundWrap ? dispatchInboundWrap(inner) : inner;
    }
    await params.dispatcher.deliver({ text: "ops reply" }, { kind: "final" });
    return {
      queuedFinal: false,
      counts: { final: 1 },
    };
  },
}));

vi.mock("openclaw/plugin-sdk/runtime-env", () => ({
  danger: (message: string) => message,
  logVerbose: () => {},
  shouldLogVerbose: () => false,
}));

vi.mock("openclaw/plugin-sdk/security-runtime", () => ({
  resolvePinnedMainDmOwnerFromAllowlist: () => undefined,
}));

vi.mock("openclaw/plugin-sdk/text-runtime", () => ({
  normalizeOptionalLowercaseString: (value?: string) => value?.toLowerCase(),
}));

vi.mock("../../actions.js", () => ({
  reactSlackMessage: async () => {},
  removeSlackReaction: async () => {},
}));

vi.mock("../../draft-stream.js", () => ({
  createSlackDraftStream: () => ({
    update: noop,
    flush: noopAsync,
    clear: noopAsync,
    discardPending: noopAsync,
    seal: noopAsync,
    stop: noop,
    forceNewMessage: noop,
    messageId: () => "171234.567",
    channelId: () => "C123",
  }),
}));

vi.mock("../../format.js", () => ({
  normalizeSlackOutboundText: (value: string) => value.trim(),
}));

vi.mock("../../interactive-replies.js", () => ({
  compileSlackInteractiveReplies: (payload: unknown) => payload,
  isSlackInteractiveRepliesEnabled: () => false,
}));

vi.mock("../../limits.js", () => ({
  SLACK_TEXT_LIMIT: 4000,
}));

vi.mock("../../sent-thread-cache.js", () => ({
  recordSlackThreadParticipation: () => {},
}));

vi.mock("../../stream-mode.js", () => ({
  applyAppendOnlyStreamUpdate: ({ incoming }: { incoming: string }) => ({
    changed: true,
    rendered: incoming,
    source: incoming,
  }),
  buildStatusFinalPreviewText: () => "status",
  resolveSlackStreamingConfig: () => ({
    mode: "partial",
    nativeStreaming: false,
    draftMode: "append",
  }),
}));

vi.mock("../../streaming.js", () => ({
  appendSlackStream: async () => {},
  startSlackStream: async () => ({
    threadTs: THREAD_TS,
    stopped: false,
  }),
  stopSlackStream: async () => {},
}));

vi.mock("../../threading.js", () => ({
  resolveSlackThreadTargets: () => ({
    statusThreadTs: THREAD_TS,
    isThreadReply: true,
  }),
}));

vi.mock("../allow-list.js", () => ({
  normalizeSlackAllowOwnerEntry: (value: string) => value,
}));

vi.mock("../config.runtime.js", () => ({
  resolveStorePath: () => "/tmp/openclaw-store.json",
  updateLastRoute: async () => {},
}));

vi.mock("../replies.js", () => ({
  createSlackReplyDeliveryPlan: () => ({
    peekThreadTs: () => THREAD_TS,
    nextThreadTs: () => THREAD_TS,
    markSent: () => {},
  }),
  deliverReplies: deliverRepliesMock,
  readSlackReplyBlocks: () => undefined,
  resolveSlackThreadTs: () => THREAD_TS,
}));

vi.mock("./preview-finalize.js", () => ({
  finalizeSlackPreviewEdit: async () => undefined,
}));

let dispatchPreparedSlackMessage: typeof import("./dispatch.js").dispatchPreparedSlackMessage;

describe("dispatchPreparedSlackMessage collaboration handoff child run lifecycle", () => {
  const tempRoots: string[] = [];

  beforeAll(async () => {
    ({ dispatchPreparedSlackMessage } = await import("./dispatch.js"));
  });

  beforeEach(() => {
    deliverRepliesMock.mockReset();
    dispatchBlocked = false;
    releaseDispatchBlock = null;
    dispatchRetryableErrorMessage = null;
    dispatchInboundWrap = null;
    resetAgentRunContextForTest();
    resetTaskRegistryDeliveryRuntimeForTests();
    resetTaskRegistryControlRuntimeForTests();
    resetTaskRegistryForTests({ persist: false });
  });

  afterEach(async () => {
    resetAgentRunContextForTest();
    resetTaskRegistryDeliveryRuntimeForTests();
    resetTaskRegistryControlRuntimeForTests();
    resetTaskRegistryForTests({ persist: false });
    await Promise.all(
      tempRoots.splice(0).map((dir) => fs.rm(dir, { recursive: true, force: true })),
    );
  });

  it("creates a task-backed child run for accepted collaboration handoffs and records the run audit", async () => {
    const rootDir = await fs.mkdtemp(path.join(os.tmpdir(), "slack-collab-handoff-dispatch-"));
    tempRoots.push(rootDir);
    const prepared = createPreparedSlackMessage(rootDir);

    await dispatchPreparedSlackMessage(prepared);

    await vi.waitFor(() => {
      expect(listTaskRecords().some((entry) => entry.runId === HANDOFF_RUN_ID)).toBe(true);
    });

    let task = listTaskRecords().find((entry) => entry.runId === HANDOFF_RUN_ID);
    expect(task).toMatchObject({
      runtime: "subagent",
      taskKind: "collaboration_handoff",
      sourceId: "handoff-1",
      requesterSessionKey: OWNER_SESSION_KEY,
      ownerKey: OWNER_SESSION_KEY,
      childSessionKey: CHILD_SESSION_KEY,
      agentId: "ops",
      runId: HANDOFF_RUN_ID,
      status: "running",
    });

    emitAgentEvent({
      runId: HANDOFF_RUN_ID,
      sessionKey: CHILD_SESSION_KEY,
      stream: "lifecycle",
      data: {
        phase: "end",
        endedAt: 1234,
      },
    });

    task = listTaskRecords().find((entry) => entry.runId === HANDOFF_RUN_ID);
    expect(task?.status).toBe("succeeded");

    await vi.waitFor(async () => {
      const events = await readCollaborationAuditEvents({
        workspaceDir: path.join(rootDir, "workspace-ops"),
      });
      expect(events).toContainEqual(
        expect.objectContaining({
          type: "collaboration.handoff.run.started",
          correlationId: "handoff-1",
          runId: HANDOFF_RUN_ID,
          taskId: task?.taskId,
          ownerSessionKey: OWNER_SESSION_KEY,
          childSessionKey: CHILD_SESSION_KEY,
          agentId: "ops",
        }),
      );
    });
  });

  it("detaches accepted collaboration handoffs from the inbound dispatch lifecycle", async () => {
    dispatchBlocked = true;
    const rootDir = await fs.mkdtemp(path.join(os.tmpdir(), "slack-collab-handoff-detached-"));
    tempRoots.push(rootDir);
    const prepared = createPreparedSlackMessage(rootDir);

    let resolved = false;
    const dispatchPromise = dispatchPreparedSlackMessage(prepared).then(() => {
      resolved = true;
    });

    await Promise.resolve();
    await Promise.resolve();

    expect(resolved).toBe(true);
    expect(deliverRepliesMock).not.toHaveBeenCalled();

    releaseDispatchBlock?.();
    await vi.waitFor(() => {
      expect(deliverRepliesMock).toHaveBeenCalledTimes(1);
    });

    await dispatchPromise;
  });

  it("releases the seen-message lock when the detached handoff fails with a retryable error", async () => {
    dispatchRetryableErrorMessage = "transient slack outage";
    const rootDir = await fs.mkdtemp(path.join(os.tmpdir(), "slack-collab-handoff-retry-"));
    tempRoots.push(rootDir);
    const prepared = createPreparedSlackMessage(rootDir);
    const releaseSeenMessage = vi.fn();
    (prepared as { ctx: { releaseSeenMessage: typeof releaseSeenMessage } }).ctx.releaseSeenMessage =
      releaseSeenMessage;

    await dispatchPreparedSlackMessage(prepared);

    await vi.waitFor(
      () => {
        expect(releaseSeenMessage).toHaveBeenCalledWith("C123", "171234.111");
      },
      { timeout: 5000 },
    );
  });

  it("releases the seen-message lock when a wrapped error has a retryable cause", async () => {
    dispatchRetryableErrorMessage = "wrapped retryable cause";
    const rootDir = await fs.mkdtemp(path.join(os.tmpdir(), "slack-collab-handoff-wrapped-"));
    tempRoots.push(rootDir);
    const prepared = createPreparedSlackMessage(rootDir);
    const releaseSeenMessage = vi.fn();
    (prepared as { ctx: { releaseSeenMessage: typeof releaseSeenMessage } }).ctx.releaseSeenMessage =
      releaseSeenMessage;

    // Wrap the inner retryable error in a generic Error to simulate a layer
    // that catches and rethrows with `cause` (e.g. an instrumentation wrapper).
    dispatchInboundWrap = (inner: Error) =>
      new Error(`upstream layer failure: ${inner.message}`, { cause: inner });

    try {
      await dispatchPreparedSlackMessage(prepared);
      await vi.waitFor(
        () => {
          expect(releaseSeenMessage).toHaveBeenCalledWith("C123", "171234.111");
        },
        { timeout: 5000 },
      );
    } finally {
      dispatchInboundWrap = null;
    }
  });

  it("does not release the seen-message lock for non-retryable detached handoff failures", async () => {
    dispatchRetryableErrorMessage = null;
    const rootDir = await fs.mkdtemp(path.join(os.tmpdir(), "slack-collab-handoff-fatal-"));
    tempRoots.push(rootDir);
    const prepared = createPreparedSlackMessage(rootDir);
    const releaseSeenMessage = vi.fn();
    (prepared as { ctx: { releaseSeenMessage: typeof releaseSeenMessage } }).ctx.releaseSeenMessage =
      releaseSeenMessage;

    await dispatchPreparedSlackMessage(prepared);

    // Allow the detached microtask to settle.
    await Promise.resolve();
    await Promise.resolve();
    expect(releaseSeenMessage).not.toHaveBeenCalled();
  });
});
