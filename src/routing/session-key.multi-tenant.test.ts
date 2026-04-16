import { describe, expect, it } from "vitest";
import { buildAgentPeerSessionKey } from "./session-key.js";

/**
 * Multi-tenant session isolation tests.
 *
 * Validates that dmScope + multi-agent composition provides
 * correct session key isolation for the multi-tenant architecture:
 *   - Different Feishu users get different session keys (per-channel-peer)
 *   - Group chats route to team agent with group-scoped session keys
 *   - DMs route to personal agent with user-scoped session keys
 */
describe("multi-tenant session isolation", () => {
  it("per-channel-peer DM scope isolates Feishu users into separate sessions", () => {
    const userA = buildAgentPeerSessionKey({
      agentId: "main",
      channel: "feishu",
      peerKind: "direct",
      peerId: "ou_user_001",
      dmScope: "per-channel-peer",
    });
    const userB = buildAgentPeerSessionKey({
      agentId: "main",
      channel: "feishu",
      peerKind: "direct",
      peerId: "ou_user_002",
      dmScope: "per-channel-peer",
    });

    expect(userA).not.toBe(userB);
    expect(userA).toBe("agent:main:feishu:direct:ou_user_001");
    expect(userB).toBe("agent:main:feishu:direct:ou_user_002");
  });

  it("group chats route to team agent with group-scoped session key", () => {
    const salesGroupSession = buildAgentPeerSessionKey({
      agentId: "sales",
      channel: "feishu",
      peerKind: "group",
      peerId: "oc_group_sales_001",
    });

    expect(salesGroupSession).toBe("agent:sales:feishu:group:oc_group_sales_001");
  });

  it("same user in different contexts gets different session keys", () => {
    // User in DM (personal agent)
    const userDM = buildAgentPeerSessionKey({
      agentId: "main",
      channel: "feishu",
      peerKind: "direct",
      peerId: "ou_user_001",
      dmScope: "per-channel-peer",
    });
    // Same user's group chat (team agent)
    const userGroup = buildAgentPeerSessionKey({
      agentId: "sales",
      channel: "feishu",
      peerKind: "group",
      peerId: "oc_group_sales_001",
    });

    // Different agent, different peer kind, different session
    expect(userDM).not.toBe(userGroup);
    expect(userDM).toContain("agent:main:");
    expect(userGroup).toContain("agent:sales:");
  });

  it("group sessions never leak into DM sessions across agents", () => {
    const salesGroup = buildAgentPeerSessionKey({
      agentId: "sales",
      channel: "feishu",
      peerKind: "group",
      peerId: "oc_group_sales",
    });
    const personalDM = buildAgentPeerSessionKey({
      agentId: "main",
      channel: "feishu",
      peerKind: "direct",
      peerId: "ou_user_001",
      dmScope: "per-channel-peer",
    });

    // No shared prefix beyond "agent:"
    expect(salesGroup.startsWith("agent:sales:")).toBe(true);
    expect(personalDM.startsWith("agent:main:")).toBe(true);
    // Group key does not contain "direct", DM key does not contain "group"
    expect(salesGroup).toContain(":group:");
    expect(personalDM).toContain(":direct:");
    expect(salesGroup).not.toContain(":direct:");
    expect(personalDM).not.toContain(":group:");
  });
});
