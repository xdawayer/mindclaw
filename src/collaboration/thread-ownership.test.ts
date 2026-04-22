import { describe, expect, it, beforeEach } from "vitest";
import type { ResolvedAgentRoute } from "../routing/resolve-route.js";
import { resolveSlackThreadOwnedRoute } from "./thread-ownership.js";
import {
  clearSlackThreadOwnershipStoreForTest,
  readSlackThreadOwnership,
} from "./thread-ownership.store.js";

function makeRoute(
  agentId: string,
  matchedBy: ResolvedAgentRoute["matchedBy"],
): ResolvedAgentRoute {
  return {
    agentId,
    channel: "slack",
    accountId: "default",
    sessionKey: `agent:${agentId}:slack:channel:C123`,
    mainSessionKey: `agent:${agentId}:main`,
    lastRoutePolicy: "session",
    matchedBy,
  };
}

describe("slack thread ownership", () => {
  beforeEach(() => {
    clearSlackThreadOwnershipStoreForTest();
  });

  it("claims the first collaboration thread reply owner", () => {
    const result = resolveSlackThreadOwnedRoute({
      route: makeRoute("product", "collaboration.project.default"),
      isThreadReply: true,
      accountId: "default",
      channelId: "CPROJ1234",
      threadTs: "1710000000.000100",
      buildRouteForAgent: (agentId, matchedBy) => makeRoute(agentId, matchedBy),
    });

    expect(result.route.agentId).toBe("product");
    expect(
      readSlackThreadOwnership({
        accountId: "default",
        channelId: "CPROJ1234",
        threadTs: "1710000000.000100",
      })?.ownerAgentId,
    ).toBe("product");
  });

  it("keeps subsequent thread replies on the claimed owner", () => {
    resolveSlackThreadOwnedRoute({
      route: makeRoute("product", "collaboration.project.default"),
      isThreadReply: true,
      accountId: "default",
      channelId: "CPROJ1234",
      threadTs: "1710000000.000100",
      buildRouteForAgent: (agentId, matchedBy) => makeRoute(agentId, matchedBy),
    });

    const result = resolveSlackThreadOwnedRoute({
      route: makeRoute("ops", "collaboration.project.default"),
      isThreadReply: true,
      accountId: "default",
      channelId: "CPROJ1234",
      threadTs: "1710000000.000100",
      buildRouteForAgent: (agentId, matchedBy) => makeRoute(agentId, matchedBy),
    });

    expect(result.route.agentId).toBe("product");
    expect(result.route.matchedBy).toBe("collaboration.thread.owner");
  });

  it("switches owner when the thread contains an explicit role mention route", () => {
    resolveSlackThreadOwnedRoute({
      route: makeRoute("product", "collaboration.project.default"),
      isThreadReply: true,
      accountId: "default",
      channelId: "CPROJ1234",
      threadTs: "1710000000.000100",
      buildRouteForAgent: (agentId, matchedBy) => makeRoute(agentId, matchedBy),
    });

    const result = resolveSlackThreadOwnedRoute({
      route: makeRoute("ops", "collaboration.project.mention"),
      isThreadReply: true,
      accountId: "default",
      channelId: "CPROJ1234",
      threadTs: "1710000000.000100",
      buildRouteForAgent: (agentId, matchedBy) => makeRoute(agentId, matchedBy),
    });

    expect(result.route.agentId).toBe("ops");
    expect(
      readSlackThreadOwnership({
        accountId: "default",
        channelId: "CPROJ1234",
        threadTs: "1710000000.000100",
      })?.ownerAgentId,
    ).toBe("ops");
  });

  it("does not mutate ownership for top-level channel messages", () => {
    const result = resolveSlackThreadOwnedRoute({
      route: makeRoute("product", "collaboration.project.default"),
      isThreadReply: false,
      accountId: "default",
      channelId: "CPROJ1234",
      threadTs: undefined,
      buildRouteForAgent: (agentId, matchedBy) => makeRoute(agentId, matchedBy),
    });

    expect(result.ownership).toBeNull();
    expect(
      readSlackThreadOwnership({
        accountId: "default",
        channelId: "CPROJ1234",
        threadTs: "1710000000.000100",
      }),
    ).toBeNull();
  });
});
