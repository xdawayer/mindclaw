import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  appendCollaborationAuditEvent,
  COLLABORATION_AUDIT_LOG_RELATIVE_PATH,
  readCollaborationAuditEvents,
  resolveCollaborationAuditLogPath,
} from "./audit.js";

describe("collaboration audit journal", () => {
  it("appends and reads collaboration audit events from the workspace journal", async () => {
    const workspaceDir = await fs.mkdtemp(path.join(os.tmpdir(), "collaboration-audit-test-"));

    try {
      await appendCollaborationAuditEvent(workspaceDir, {
        type: "collaboration.route.resolved",
        timestamp: "2026-04-23T00:00:00.000Z",
        surface: "slack",
        mode: "enforced",
        accountId: "default",
        senderUserId: "U1",
        channelId: "C1",
        spaceId: "project_main",
        legacyAgentId: "main",
        collaborationAgentId: "product",
        effectiveAgentId: "ops",
        handoffStatus: "accepted",
        handoffTargetRole: "ops",
        handoffCorrelationId: "handoff-1",
        handoffArtifactPath: "collaboration/handoffs/2026-04-23/handoff-1.json",
        memoryReadableScopes: ["private", "role_shared"],
        routeChanged: true,
        warningCodes: [],
      });

      const logPath = resolveCollaborationAuditLogPath(workspaceDir);
      const raw = await fs.readFile(logPath, "utf8");
      const events = await readCollaborationAuditEvents({ workspaceDir });

      expect(logPath).toBe(path.join(workspaceDir, COLLABORATION_AUDIT_LOG_RELATIVE_PATH));
      expect(raw).toContain("collaboration.route.resolved");
      expect(events).toEqual([
        {
          type: "collaboration.route.resolved",
          timestamp: "2026-04-23T00:00:00.000Z",
          surface: "slack",
          mode: "enforced",
          accountId: "default",
          senderUserId: "U1",
          channelId: "C1",
          spaceId: "project_main",
          legacyAgentId: "main",
          collaborationAgentId: "product",
          effectiveAgentId: "ops",
          handoffStatus: "accepted",
          handoffTargetRole: "ops",
          handoffCorrelationId: "handoff-1",
          handoffArtifactPath: "collaboration/handoffs/2026-04-23/handoff-1.json",
          memoryReadableScopes: ["private", "role_shared"],
          routeChanged: true,
          warningCodes: [],
        },
      ]);
    } finally {
      await fs.rm(workspaceDir, { recursive: true, force: true });
    }
  });
});
