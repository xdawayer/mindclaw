import fs from "node:fs/promises";
import path from "node:path";

const SANITIZE_RE = /[^a-z0-9_-]/g;

function sanitizeTeamId(teamId: string): string {
  const safe = teamId.toLowerCase().replace(SANITIZE_RE, "");
  if (!safe) {
    throw new Error("teamId resolves to empty string after sanitization");
  }
  return safe;
}

export function resolveTeamMemoryDir(workspaceDir: string, teamId: string): string {
  const safe = sanitizeTeamId(teamId);
  return path.join(workspaceDir, "teams", safe, "memory");
}

export async function listTeamMemoryFiles(workspaceDir: string, teamId: string): Promise<string[]> {
  const dir = resolveTeamMemoryDir(workspaceDir, teamId);
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return [];
  }
  return entries.filter((f) => f.endsWith(".md")).toSorted();
}

export function canAccessTeamMemory(params: {
  userTeamId: string;
  targetTeamId: string;
  isAdmin?: boolean;
}): boolean {
  // Org-level memory is accessible to all
  if (params.targetTeamId === "org") {
    return true;
  }
  // Admin can access any team
  if (params.isAdmin) {
    return true;
  }
  // Same team
  return params.userTeamId === params.targetTeamId;
}
