import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, test } from "vitest";
import {
  hasUserMemory,
  listUserMemoryFiles,
  resolveSharedMemoryDir,
  resolveUserMemoryDir,
} from "./user-memory.js";

let tmpDirs: string[] = [];

async function makeTmpDir(): Promise<string> {
  const dir = path.join(os.tmpdir(), `user-memory-test-${crypto.randomUUID()}`);
  await fs.mkdir(dir, { recursive: true });
  tmpDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(tmpDirs.map((d) => fs.rm(d, { recursive: true, force: true })));
  tmpDirs = [];
});

const baseParams = (workspaceDir: string, userId = "user-abc-123", agentId = "default") => ({
  workspaceDir,
  userId,
  agentId,
});

describe("resolveUserMemoryDir", () => {
  test("returns {workspace}/memory/users/{userId}/ path", async () => {
    const workspace = await makeTmpDir();
    const result = resolveUserMemoryDir(baseParams(workspace));
    expect(result).toBe(path.join(workspace, "memory", "users", "user-abc-123"));
  });

  test("normalizes userId to lowercase", async () => {
    const workspace = await makeTmpDir();
    const result = resolveUserMemoryDir(baseParams(workspace, "User-ABC-123"));
    expect(result).toBe(path.join(workspace, "memory", "users", "user-abc-123"));
  });

  test("strips special characters from userId", async () => {
    const workspace = await makeTmpDir();
    const result = resolveUserMemoryDir(baseParams(workspace, "user@foo.com/bar"));
    // Only alphanumeric, hyphens, and underscores should remain
    expect(result).not.toContain("@");
    expect(result).not.toContain("/bar");
  });

  test("throws when userId sanitizes to empty string", async () => {
    const workspace = await makeTmpDir();
    expect(() => resolveUserMemoryDir(baseParams(workspace, "!!!"))).toThrow("empty string");
    expect(() => resolveUserMemoryDir(baseParams(workspace, ""))).toThrow("empty string");
  });

  test("rejects path traversal attempts", async () => {
    const workspace = await makeTmpDir();
    const result = resolveUserMemoryDir(baseParams(workspace, "../../../etc/passwd"));
    expect(result).not.toContain("..");
    expect(result).toContain("etcpasswd");
  });

  test("different agentIds with same userId resolve to the same user memory dir", async () => {
    const workspace = await makeTmpDir();
    const a = resolveUserMemoryDir(baseParams(workspace, "alice", "agent-1"));
    const b = resolveUserMemoryDir(baseParams(workspace, "alice", "agent-2"));
    expect(a).toBe(b);
  });
});

describe("resolveSharedMemoryDir", () => {
  test("returns {workspace}/memory/ path", async () => {
    const workspace = await makeTmpDir();
    const result = resolveSharedMemoryDir(workspace);
    expect(result).toBe(path.join(workspace, "memory"));
  });
});

describe("listUserMemoryFiles", () => {
  test("returns sorted .md files from user memory dir", async () => {
    const workspace = await makeTmpDir();
    const params = baseParams(workspace, "alice");
    const memDir = resolveUserMemoryDir(params);
    await fs.mkdir(memDir, { recursive: true });

    await fs.writeFile(path.join(memDir, "zebra.md"), "z content");
    await fs.writeFile(path.join(memDir, "alpha.md"), "a content");
    await fs.writeFile(path.join(memDir, "middle.md"), "m content");
    // Non-md file should be excluded
    await fs.writeFile(path.join(memDir, "notes.txt"), "not included");

    const files = await listUserMemoryFiles(params);
    expect(files).toEqual(["alpha.md", "middle.md", "zebra.md"]);
  });

  test("returns empty array when directory does not exist", async () => {
    const workspace = await makeTmpDir();
    const params = baseParams(workspace, "nonexistent-user");

    const files = await listUserMemoryFiles(params);
    expect(files).toEqual([]);
  });
});

describe("hasUserMemory", () => {
  test("returns true when user has memory files", async () => {
    const workspace = await makeTmpDir();
    const params = baseParams(workspace, "bob");
    const memDir = resolveUserMemoryDir(params);
    await fs.mkdir(memDir, { recursive: true });
    await fs.writeFile(path.join(memDir, "MEMORY.md"), "some memory");

    expect(await hasUserMemory(params)).toBe(true);
  });

  test("returns false when user memory directory does not exist", async () => {
    const workspace = await makeTmpDir();
    const params = baseParams(workspace, "ghost");

    expect(await hasUserMemory(params)).toBe(false);
  });

  test("returns false when user memory directory exists but has no .md files", async () => {
    const workspace = await makeTmpDir();
    const params = baseParams(workspace, "empty-user");
    const memDir = resolveUserMemoryDir(params);
    await fs.mkdir(memDir, { recursive: true });
    await fs.writeFile(path.join(memDir, "notes.txt"), "not a md file");

    expect(await hasUserMemory(params)).toBe(false);
  });
});

describe("user memory isolation", () => {
  test("user A memory is isolated from user B", async () => {
    const workspace = await makeTmpDir();
    const paramsA = baseParams(workspace, "alice");
    const paramsB = baseParams(workspace, "bob");

    const dirA = resolveUserMemoryDir(paramsA);
    const dirB = resolveUserMemoryDir(paramsB);

    // Directories must differ
    expect(dirA).not.toBe(dirB);

    // Create files for each user
    await fs.mkdir(dirA, { recursive: true });
    await fs.mkdir(dirB, { recursive: true });
    await fs.writeFile(path.join(dirA, "alice-private.md"), "alice secret");
    await fs.writeFile(path.join(dirB, "bob-private.md"), "bob secret");

    const filesA = await listUserMemoryFiles(paramsA);
    const filesB = await listUserMemoryFiles(paramsB);

    expect(filesA).toEqual(["alice-private.md"]);
    expect(filesB).toEqual(["bob-private.md"]);

    // Alice should not see Bob's files and vice versa
    expect(filesA).not.toContain("bob-private.md");
    expect(filesB).not.toContain("alice-private.md");
  });
});
