import fs from "node:fs/promises";
import path from "node:path";
import {
  resolveSessionTranscriptsDirForAgent,
  type OpenClawConfig,
} from "openclaw/plugin-sdk/memory-core-host-engine-foundation";
import { listSessionFilesForAgent } from "openclaw/plugin-sdk/memory-core-host-engine-qmd";
import type { ResolvedMemoryCollaborationScope } from "./manager-provider-state.js";
import { resolveMemoryCollaborationScope } from "./manager-provider-state.js";

type SessionStoreEntry = {
  sessionFile?: unknown;
  sessionId?: unknown;
};

function normalizeTranscriptBaseName(entry: SessionStoreEntry): string | null {
  const sessionFile =
    typeof entry.sessionFile === "string" && entry.sessionFile.trim() ? entry.sessionFile.trim() : "";
  if (sessionFile) {
    return path.basename(sessionFile);
  }

  const sessionId =
    typeof entry.sessionId === "string" && entry.sessionId.trim() ? entry.sessionId.trim() : "";
  if (!sessionId || sessionId.includes("/") || sessionId.includes("\\")) {
    return null;
  }
  return `${sessionId}.jsonl`;
}

function matchesTranscriptBaseName(filePath: string, expectedBaseName: string): boolean {
  const basename = path.basename(filePath);
  return (
    basename === expectedBaseName ||
    basename.startsWith(`${expectedBaseName}.reset.`) ||
    basename.startsWith(`${expectedBaseName}.deleted.`)
  );
}

async function readSessionStore(agentId: string): Promise<Record<string, SessionStoreEntry>> {
  const sessionsDir = resolveSessionTranscriptsDirForAgent(agentId);
  const storePath = path.join(sessionsDir, "sessions.json");
  try {
    const raw = JSON.parse(await fs.readFile(storePath, "utf8")) as unknown;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      return {};
    }
    return raw as Record<string, SessionStoreEntry>;
  } catch {
    return {};
  }
}

export async function listSessionFilesForCollaborationScope(params: {
  cfg: OpenClawConfig | undefined;
  collaborationScope: ResolvedMemoryCollaborationScope;
  candidateAgentIds: string[];
}): Promise<string[]> {
  const resolvedFiles = new Set<string>();

  for (const agentId of params.candidateAgentIds) {
    const normalizedAgentId = agentId.trim();
    if (!normalizedAgentId) {
      continue;
    }

    const [availableFiles, store] = await Promise.all([
      listSessionFilesForAgent(normalizedAgentId),
      readSessionStore(normalizedAgentId),
    ]);
    if (availableFiles.length === 0) {
      continue;
    }

    const expectedBaseNames = new Set<string>();
    for (const [sessionKey, entry] of Object.entries(store)) {
      if (
        resolveMemoryCollaborationScope({
          cfg: params.cfg,
          agentSessionKey: sessionKey,
        })?.scope !== params.collaborationScope.scope
      ) {
        continue;
      }
      const baseName = normalizeTranscriptBaseName(entry);
      if (baseName) {
        expectedBaseNames.add(baseName);
      }
    }

    for (const filePath of availableFiles) {
      if (![...expectedBaseNames].some((baseName) => matchesTranscriptBaseName(filePath, baseName))) {
        continue;
      }
      resolvedFiles.add(filePath);
    }
  }

  return [...resolvedFiles].toSorted();
}
