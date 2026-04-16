import { describe, expect, it, vi, beforeEach } from "vitest";
import { canAuditUserMemory, auditListUserMemory, buildAuditEntry } from "./user-memory-audit.js";

vi.mock("./user-memory.js", () => ({
  listUserMemoryFiles: vi.fn(),
  resolveUserMemoryDir: vi.fn(() => "/workspace/memory/users/user123"),
}));

import { listUserMemoryFiles } from "./user-memory.js";

beforeEach(() => {
  vi.mocked(listUserMemoryFiles).mockReset();
});

describe("user-memory-audit", () => {
  describe("canAuditUserMemory", () => {
    it("allows admin to audit any user", () => {
      expect(
        canAuditUserMemory({
          requesterId: "admin1",
          targetUserId: "user123",
          requesterRole: "admin",
        }),
      ).toBe(true);
    });

    it("denies non-admin auditing another user", () => {
      expect(
        canAuditUserMemory({
          requesterId: "user456",
          targetUserId: "user123",
          requesterRole: "engineer",
        }),
      ).toBe(false);
    });

    it("denies user auditing their own memory (use normal access instead)", () => {
      expect(
        canAuditUserMemory({
          requesterId: "user123",
          targetUserId: "user123",
          requesterRole: "engineer",
        }),
      ).toBe(false);
    });

    it("allows admin to audit themselves", () => {
      expect(
        canAuditUserMemory({
          requesterId: "admin1",
          targetUserId: "admin1",
          requesterRole: "admin",
          isAdmin: true,
        }),
      ).toBe(true);
    });

    it("allows CEO with isAdmin flag to audit users", () => {
      expect(
        canAuditUserMemory({
          requesterId: "ceo1",
          targetUserId: "user123",
          requesterRole: "ceo",
          isAdmin: true,
        }),
      ).toBe(true);
    });

    it("denies non-admin even with admin-like role name", () => {
      expect(
        canAuditUserMemory({
          requesterId: "user456",
          targetUserId: "user123",
          requesterRole: "admin-assistant",
          isAdmin: false,
        }),
      ).toBe(false);
    });
  });

  describe("auditListUserMemory", () => {
    it("returns file list with audit entry when authorized", async () => {
      vi.mocked(listUserMemoryFiles).mockResolvedValue(["note1.md", "note2.md"]);

      const result = await auditListUserMemory({
        requesterId: "admin1",
        targetUserId: "user123",
        requesterRole: "admin",
        workspaceDir: "/workspace",
        agentId: "default",
      });

      expect(result.authorized).toBe(true);
      expect(result.files).toEqual(["note1.md", "note2.md"]);
      expect(result.auditEntry).toBeDefined();
      expect(result.auditEntry!.action).toBe("list-user-memory");
      expect(result.auditEntry!.requesterId).toBe("admin1");
      expect(result.auditEntry!.targetUserId).toBe("user123");
    });

    it("returns unauthorized with no files when not admin", async () => {
      const result = await auditListUserMemory({
        requesterId: "user456",
        targetUserId: "user123",
        requesterRole: "engineer",
        workspaceDir: "/workspace",
        agentId: "default",
      });

      expect(result.authorized).toBe(false);
      expect(result.files).toEqual([]);
      expect(result.auditEntry).toBeDefined();
      expect(result.auditEntry!.action).toBe("list-user-memory");
      expect(result.auditEntry!.denied).toBe(true);
    });
  });

  describe("buildAuditEntry", () => {
    it("creates a structured audit log entry", () => {
      const entry = buildAuditEntry({
        requesterId: "admin1",
        targetUserId: "user123",
        action: "list-user-memory",
        denied: false,
      });
      expect(entry.requesterId).toBe("admin1");
      expect(entry.targetUserId).toBe("user123");
      expect(entry.action).toBe("list-user-memory");
      expect(entry.denied).toBe(false);
      expect(typeof entry.timestamp).toBe("string");
    });

    it("includes denied flag when access was rejected", () => {
      const entry = buildAuditEntry({
        requesterId: "user456",
        targetUserId: "user123",
        action: "list-user-memory",
        denied: true,
      });
      expect(entry.denied).toBe(true);
    });
  });
});
