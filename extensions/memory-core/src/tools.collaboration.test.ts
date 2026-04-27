import fs from "node:fs/promises";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { clearMemoryPluginState } from "../../../src/plugins/memory-state.js";
import {
  getReadAgentMemoryFileMockCalls,
  resetMemoryToolMockState,
  setMemoryBackend,
  setMemoryReadFileImpl,
  setMemorySearchImpl,
  type MemoryReadParams,
} from "./memory-tool-manager-mock.js";
import { createMemoryCoreTestHarness } from "./test-helpers.js";
import { createMemoryGetTool, createMemorySearchTool } from "./tools.js";
import { asOpenClawConfig } from "./tools.test-helpers.js";

const { createTempWorkspace } = createMemoryCoreTestHarness();

const SESSION_KEY = "agent:main:slack:channel:c111proj01:thread:1713891000.123456";

async function writeSessionStoreEntry(params: {
  storePath: string;
  readableScopes: string[];
  mode?: "shadow" | "enforced";
  effectiveRole?: string;
  spaceId?: string;
}) {
  await fs.writeFile(
    params.storePath,
    JSON.stringify(
      {
        [SESSION_KEY]: {
          sessionId: "collab-session",
          updatedAt: 1,
          collaboration: {
            mode: params.mode ?? "enforced",
            managedSurface: true,
            effectiveRole: params.effectiveRole ?? "product",
            ...(params.spaceId ? { spaceId: params.spaceId } : {}),
            readableScopes: params.readableScopes,
          },
        },
      },
      null,
      2,
    ),
    "utf-8",
  );
}

function createConfig(params: { workspaceDir: string; storePath: string }) {
  return asOpenClawConfig({
    session: {
      store: params.storePath,
    },
    agents: {
      list: [{ id: "main", default: true, workspace: params.workspaceDir }],
    },
  });
}

beforeEach(() => {
  clearMemoryPluginState();
  resetMemoryToolMockState({
    backend: "builtin",
    searchImpl: async () => [
      {
        path: "MEMORY.md",
        startLine: 1,
        endLine: 2,
        score: 0.9,
        snippet: "private note",
        source: "memory" as const,
      },
    ],
    readFileImpl: async (params: MemoryReadParams) => ({
      text: "",
      path: params.relPath,
      from: params.from ?? 1,
      lines: params.lines ?? 120,
    }),
  });
});

describe("memory tools collaboration gating", () => {
  it("filters private memory_search results when collaboration scopes exclude private", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-collab-search-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["role_shared"],
    });

    let searchCalls = 0;
    setMemorySearchImpl(async () => {
      searchCalls += 1;
      return [
        {
          path: "MEMORY.md",
          startLine: 1,
          endLine: 2,
          score: 0.9,
          snippet: "private note",
          source: "memory" as const,
        },
      ];
    });

    const tool = createMemorySearchTool({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });
    if (!tool) {
      throw new Error("tool missing");
    }

    const result = await tool.execute("collab-search-blocked", { query: "private note" });

    expect(searchCalls).toBe(1);
    expect(result.details).toMatchObject({
      results: [],
      debug: {
        collaboration: {
          applied: true,
          readableScopes: ["role_shared"],
        },
      },
    });
    expect(result.details).not.toHaveProperty("debug.collaboration.filteredResults");
  });

  it("allows shared collaboration search results for matching scopes", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-collab-shared-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["space_shared"],
      spaceId: "project_main",
    });

    setMemorySearchImpl(async () => [
      {
        path: "collaboration/space_shared/project_main/summary.md",
        startLine: 4,
        endLine: 6,
        score: 0.8,
        snippet: "shared summary",
        source: "memory" as const,
      },
    ]);

    const tool = createMemorySearchTool({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });
    if (!tool) {
      throw new Error("tool missing");
    }

    const result = await tool.execute("collab-search-shared", { query: "summary" });

    expect(result.details).toMatchObject({
      results: [
        expect.objectContaining({
          path: "collaboration/space_shared/project_main/summary.md",
        }),
      ],
      debug: {
        collaboration: {
          applied: true,
          readableScopes: ["space_shared"],
          spaceId: "project_main",
        },
      },
    });
    expect(result.details).not.toHaveProperty("debug.collaboration.filteredResults");
  });

  it("filters shared results when the collaboration space does not match", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-collab-space-mismatch-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["space_shared"],
      spaceId: "project_main",
    });

    setMemorySearchImpl(async () => [
      {
        path: "collaboration/space_shared/other_project/summary.md",
        startLine: 2,
        endLine: 3,
        score: 0.7,
        snippet: "other shared summary",
        source: "memory" as const,
      },
    ]);

    const tool = createMemorySearchTool({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });
    if (!tool) {
      throw new Error("tool missing");
    }

    const result = await tool.execute("collab-search-space-mismatch", { query: "summary" });

    expect(result.details).toMatchObject({
      results: [],
      debug: {
        collaboration: {
          applied: true,
          readableScopes: ["space_shared"],
          spaceId: "project_main",
        },
      },
    });
    expect(result.details).not.toHaveProperty("debug.collaboration.filteredResults");
  });

  it("filters shared results when the collaboration role does not match", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-collab-role-mismatch-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["role_shared"],
      effectiveRole: "product",
    });

    setMemorySearchImpl(async () => [
      {
        path: "collaboration/role_shared/ops/runbook.md",
        startLine: 3,
        endLine: 5,
        score: 0.82,
        snippet: "ops only",
        source: "memory" as const,
      },
    ]);

    const tool = createMemorySearchTool({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });
    if (!tool) {
      throw new Error("tool missing");
    }

    const result = await tool.execute("collab-search-role-mismatch", { query: "runbook" });

    expect(result.details).toMatchObject({
      results: [],
      debug: {
        collaboration: {
          applied: true,
          effectiveRole: "product",
          readableScopes: ["role_shared"],
        },
      },
    });
    expect(result.details).not.toHaveProperty("debug.collaboration.filteredResults");
  });

  it("blocks memory_get for private paths when collaboration scopes exclude private", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-collab-read-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["role_shared"],
      effectiveRole: "product",
    });

    setMemoryBackend("builtin");
    setMemoryReadFileImpl(async (_params: MemoryReadParams) => ({
      text: "should not read",
      path: "MEMORY.md",
      from: 1,
      lines: 1,
    }));

    const tool = createMemoryGetTool({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });
    if (!tool) {
      throw new Error("tool missing");
    }

    const result = await tool.execute("collab-get-blocked", { path: "MEMORY.md" });

    expect(getReadAgentMemoryFileMockCalls()).toBe(0);
    expect(result.details).toMatchObject({
      path: "MEMORY.md",
      text: "",
      disabled: true,
      denied: true,
      error: "memory read blocked by collaboration scope gate",
      debug: {
        collaboration: {
          applied: true,
          effectiveRole: "product",
          readableScopes: ["role_shared"],
          blockedPath: "MEMORY.md",
        },
      },
    });
  });
});
