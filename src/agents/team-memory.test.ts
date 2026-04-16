import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, test, expect } from "vitest";
import { resolveTeamMemoryDir, listTeamMemoryFiles, canAccessTeamMemory } from "./team-memory.js";

let tmpDirs: string[] = [];

async function makeTmpDir(): Promise<string> {
  const dir = path.join(os.tmpdir(), `team-memory-test-${crypto.randomUUID()}`);
  await fs.mkdir(dir, { recursive: true });
  tmpDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(tmpDirs.map((d) => fs.rm(d, { recursive: true, force: true })));
  tmpDirs = [];
});

describe("team-memory", () => {
  describe("resolveTeamMemoryDir", () => {
    test("returns {workspace}/teams/{teamId}/memory/ path", async () => {
      const workspace = await makeTmpDir();
      const result = resolveTeamMemoryDir(workspace, "sales");
      expect(result).toBe(path.join(workspace, "teams", "sales", "memory"));
    });

    test("sanitizes teamId (lowercase, strip special chars)", () => {
      const result = resolveTeamMemoryDir("/workspace", "Sales-Team@1");
      expect(result).not.toContain("@");
      expect(result).toContain("sales-team1");
    });

    test("throws for empty teamId after sanitization", () => {
      expect(() => resolveTeamMemoryDir("/workspace", "!!!")).toThrow("empty");
    });
  });

  describe("listTeamMemoryFiles", () => {
    test("returns sorted .md files from team memory dir", async () => {
      const workspace = await makeTmpDir();
      const memDir = path.join(workspace, "teams", "eng", "memory");
      await fs.mkdir(memDir, { recursive: true });
      await fs.writeFile(path.join(memDir, "zebra.md"), "z content");
      await fs.writeFile(path.join(memDir, "alpha.md"), "a content");
      await fs.writeFile(path.join(memDir, "notes.txt"), "excluded");

      const files = await listTeamMemoryFiles(workspace, "eng");
      expect(files).toEqual(["alpha.md", "zebra.md"]);
    });

    test("returns empty array when team memory dir does not exist", async () => {
      const workspace = await makeTmpDir();
      const files = await listTeamMemoryFiles(workspace, "ghost");
      expect(files).toEqual([]);
    });
  });

  describe("canAccessTeamMemory", () => {
    test("same team user can access team memory", () => {
      expect(canAccessTeamMemory({ userTeamId: "sales", targetTeamId: "sales" })).toBe(true);
    });

    test("different team user cannot access other team memory", () => {
      expect(canAccessTeamMemory({ userTeamId: "eng", targetTeamId: "sales" })).toBe(false);
    });

    test("admin role can access any team memory", () => {
      expect(canAccessTeamMemory({ userTeamId: "eng", targetTeamId: "sales", isAdmin: true })).toBe(
        true,
      );
    });

    test("org-level memory is accessible to all", () => {
      expect(canAccessTeamMemory({ userTeamId: "eng", targetTeamId: "org" })).toBe(true);
    });
  });
});
