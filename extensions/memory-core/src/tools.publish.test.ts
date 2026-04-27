import fs from "node:fs/promises";
import path from "node:path";
import { readCollaborationAuditEvents } from "openclaw/plugin-sdk/collaboration-runtime";
import { readMemoryHostEvents } from "openclaw/plugin-sdk/memory-core-host-events";
import { beforeEach, describe, expect, it } from "vitest";
import { clearMemoryPluginState } from "../../../src/plugins/memory-state.js";
import { createMemoryCoreTestHarness } from "./test-helpers.js";
import { createMemoryPublishToolOrThrow } from "./tools.test-helpers.js";

const { createTempWorkspace } = createMemoryCoreTestHarness();

const SESSION_KEY = "agent:main:slack:channel:c111proj01:thread:1713891000.123456";

async function writeSessionStoreEntry(params: {
  storePath: string;
  readableScopes?: string[];
  publishableScopes?: string[];
  effectiveRole?: string;
  spaceId?: string;
  mode?: "shadow" | "enforced";
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
            readableScopes: params.readableScopes ?? ["private"],
            publishableScopes: params.publishableScopes ?? [],
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
  return {
    session: {
      store: params.storePath,
    },
    agents: {
      list: [{ id: "main", default: true, workspace: params.workspaceDir }],
    },
  };
}

beforeEach(() => {
  clearMemoryPluginState();
});

describe("memory_publish collaboration gating", () => {
  it("appends to the active collaboration space_shared scope", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-publish-space-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["private", "space_shared"],
      publishableScopes: ["space_shared"],
      effectiveRole: "product",
      spaceId: "project_main",
    });

    const tool = createMemoryPublishToolOrThrow({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });

    const result = await tool.execute("publish-space", {
      scope: "space_shared",
      path: "summaries/daily.md",
      content: "Shared project note",
    });

    const publishedPath = path.join(
      workspaceDir,
      "collaboration",
      "space_shared",
      "project_main",
      "summaries",
      "daily.md",
    );
    const published = await fs.readFile(publishedPath, "utf-8");
    const events = await readMemoryHostEvents({ workspaceDir });
    const auditEvents = await readCollaborationAuditEvents({ workspaceDir });

    expect(result.details).toMatchObject({
      scope: "space_shared",
      path: "collaboration/space_shared/project_main/summaries/daily.md",
      appendOnly: true,
      published: true,
    });
    expect(published).toContain("openclaw-collaboration-publish:");
    expect(published).toContain("scope=space_shared");
    expect(published).toContain("space=project_main");
    expect(published).toContain("Shared project note");
    expect(events.at(-1)).toMatchObject({
      type: "memory.collaboration.published",
      scope: "space_shared",
      path: "collaboration/space_shared/project_main/summaries/daily.md",
      effectiveRole: "product",
      spaceId: "project_main",
    });
    expect(auditEvents.at(-1)).toMatchObject({
      type: "collaboration.memory.published",
      source: "memory_publish",
      scope: "space_shared",
      path: "collaboration/space_shared/project_main/summaries/daily.md",
      effectiveRole: "product",
      spaceId: "project_main",
    });
  });

  it("appends to the active collaboration role_shared scope", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-publish-role-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["private", "role_shared"],
      publishableScopes: ["role_shared"],
      effectiveRole: "product",
    });

    const tool = createMemoryPublishToolOrThrow({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });

    await tool.execute("publish-role", {
      scope: "role_shared",
      path: "runbooks/oncall.md",
      content: "Shared role note",
    });

    const publishedPath = path.join(
      workspaceDir,
      "collaboration",
      "role_shared",
      "product",
      "runbooks",
      "oncall.md",
    );
    await expect(fs.readFile(publishedPath, "utf-8")).resolves.toContain("Shared role note");
  });

  it("denies publish when the session gate does not allow the requested scope", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-publish-denied-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["private", "space_shared"],
      publishableScopes: [],
      effectiveRole: "product",
      spaceId: "project_main",
    });

    const tool = createMemoryPublishToolOrThrow({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });

    const result = await tool.execute("publish-denied", {
      scope: "space_shared",
      path: "summaries/daily.md",
      content: "Denied note",
    });

    expect(result.details).toMatchObject({
      scope: "space_shared",
      path: "summaries/daily.md",
      disabled: true,
      denied: true,
      error: "memory publish blocked by collaboration scope gate",
      debug: {
        collaboration: {
          applied: true,
          effectiveRole: "product",
          publishableScopes: [],
          readableScopes: ["private", "space_shared"],
          spaceId: "project_main",
          blockedScope: "space_shared",
        },
      },
    });
  });

  it("denies publish when the active role is not in the space's writableByRoles list", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-publish-writable-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["private", "space_shared"],
      publishableScopes: ["space_shared"],
      effectiveRole: "ops",
      spaceId: "project_main",
    });

    const config = {
      ...createConfig({ workspaceDir, storePath }),
      collaboration: {
        version: 1 as const,
        identities: { users: {} },
        bots: {},
        roles: {},
        spaces: {
          project_main: {
            kind: "project" as const,
            ownerRole: "product",
            memberRoles: ["product", "ops"],
            memory: {
              writableByRoles: ["product"], // ops is publishable but not writable here
            },
          },
        },
      },
    };

    const tool = createMemoryPublishToolOrThrow({
      config,
      agentSessionKey: SESSION_KEY,
    });

    const result = await tool.execute("publish-writable-denied", {
      scope: "space_shared",
      path: "summaries/daily.md",
      content: "Denied via writableByRoles",
    });

    expect(result.details).toMatchObject({
      scope: "space_shared",
      disabled: true,
      denied: true,
      error: "memory publish blocked by collaboration scope gate",
    });

    // No file should have been written.
    const targetPath = path.join(
      workspaceDir,
      "collaboration",
      "space_shared",
      "project_main",
      "summaries",
      "daily.md",
    );
    await expect(fs.readFile(targetPath)).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("rejects publish paths that escape the collaboration scope", async () => {
    const workspaceDir = await createTempWorkspace("memory-tools-publish-path-");
    const storePath = path.join(workspaceDir, "sessions.json");
    await writeSessionStoreEntry({
      storePath,
      readableScopes: ["private", "space_shared"],
      publishableScopes: ["space_shared"],
      effectiveRole: "product",
      spaceId: "project_main",
    });

    const tool = createMemoryPublishToolOrThrow({
      config: createConfig({ workspaceDir, storePath }),
      agentSessionKey: SESSION_KEY,
    });

    const result = await tool.execute("publish-bad-path", {
      scope: "space_shared",
      path: "../escape.md",
      content: "Denied note",
    });

    expect(result.details).toMatchObject({
      scope: "space_shared",
      path: "../escape.md",
      disabled: true,
      error: "memory_publish path must stay inside the collaboration scope",
      debug: {
        collaboration: {
          applied: true,
          effectiveRole: "product",
          publishableScopes: ["space_shared"],
          readableScopes: ["private", "space_shared"],
          spaceId: "project_main",
        },
      },
    });
  });
});
