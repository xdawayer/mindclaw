import fs from "node:fs/promises";
import path from "node:path";
import { sanitizeUserId } from "./sanitize-user-id.js";

export type UserMemoryParams = {
  workspaceDir: string;
  userId: string;
  agentId: string;
};

export function resolveUserMemoryDir(params: UserMemoryParams): string {
  const safe = sanitizeUserId(params.userId);
  return path.join(params.workspaceDir, "memory", "users", safe);
}

export function resolveSharedMemoryDir(workspaceDir: string): string {
  return path.join(workspaceDir, "memory");
}

export async function listUserMemoryFiles(params: UserMemoryParams): Promise<string[]> {
  const dir = resolveUserMemoryDir(params);
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return [];
  }
  return entries.filter((f) => f.endsWith(".md")).toSorted();
}

export async function hasUserMemory(params: UserMemoryParams): Promise<boolean> {
  const files = await listUserMemoryFiles(params);
  return files.length > 0;
}
