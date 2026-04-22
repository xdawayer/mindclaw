import type { OpenClawConfig } from "openclaw/plugin-sdk/memory-core-host-engine-foundation";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { resetMemoryToolMockState, setMemorySearchImpl } from "../memory-tool-manager-mock.js";
import { createMemorySearchToolOrThrow } from "../tools.test-helpers.js";
import { resolveScopedMemoryRuntimeContext } from "./manager-provider-state.js";

const runtimeManager = vi.hoisted(() => ({
  search: vi.fn(async () => []),
  readFile: vi.fn(async (params: { relPath: string; from?: number; lines?: number }) => ({
    text: "",
    path: params.relPath,
  })),
  status: vi.fn(() => ({
    backend: "builtin" as const,
    provider: "builtin",
  })),
  sync: vi.fn(async () => {}),
  probeEmbeddingAvailability: vi.fn(async () => ({ ok: true })),
  probeVectorAvailability: vi.fn(async () => true),
  close: vi.fn(async () => {}),
}));

const getRuntimeSearchManagerMock = vi.hoisted(() =>
  vi.fn(async () => ({
    manager: runtimeManager,
    error: undefined,
  })),
);

vi.mock("../memory/index.js", () => ({
  closeAllMemorySearchManagers: vi.fn(async () => {}),
  getMemorySearchManager: getRuntimeSearchManagerMock,
}));

import { memoryRuntime } from "../runtime-provider.js";

const cfg: OpenClawConfig = {
  agents: {
    list: [
      { id: "product", default: true },
      { id: "ops" },
      { id: "main" },
    ],
  },
  collaboration: {
    spaces: {
      projects: {
        "proj-a": {
          channelId: "CPROJ1234",
          defaultAgent: "product",
          defaultDmRecipient: "UPM12345",
          roleDmRecipients: {
            ops: "UOPS1234",
          },
        },
      },
      roles: {
        ops: {
          channelId: "COPS12345",
          agentId: "ops",
        },
      },
    },
  },
};

describe("memory collaboration scope runtime plumbing", () => {
  beforeEach(() => {
    resetMemoryToolMockState();
    getRuntimeSearchManagerMock.mockClear();
    runtimeManager.search.mockClear();
    runtimeManager.readFile.mockClear();
    runtimeManager.status.mockClear();
    runtimeManager.sync.mockClear();
    runtimeManager.probeEmbeddingAvailability.mockClear();
    runtimeManager.probeVectorAvailability.mockClear();
    runtimeManager.close.mockClear();
  });

  it("resolves a private collaboration scope without changing the backend agent id", () => {
    expect(
      resolveScopedMemoryRuntimeContext({
        cfg,
        agentId: "main",
        agentSessionKey: "agent:main:slack:dm:UPM12345",
      }),
    ).toEqual({
      agentId: "main",
      collaborationScope: {
        kind: "private",
        scope: "private:UPM12345",
      },
      agentSessionKey: "agent:main:slack:dm:UPM12345:memory-scope:private:UPM12345",
    });
  });

  it("threads project scope through the memory search tool session key", async () => {
    let seenSessionKey: string | undefined;
    setMemorySearchImpl(async (opts) => {
      seenSessionKey = opts?.sessionKey;
      return [];
    });
    const tool = createMemorySearchToolOrThrow({
      config: cfg,
      agentSessionKey: "agent:main:slack:channel:CPROJ1234",
    });

    await tool.execute("project-scope", { query: "roadmap" });

    expect(seenSessionKey).toBe("agent:main:slack:channel:CPROJ1234:memory-scope:project:proj-a");
  });

  it("threads role scope through the memory runtime manager wrapper", async () => {
    const { manager } = await memoryRuntime.getMemorySearchManager({
      cfg,
      agentId: "main",
      agentSessionKey: "agent:main:slack:channel:COPS12345",
    } as never);

    await manager?.search("handoff", { sessionKey: "agent:main:slack:channel:COPS12345" });

    expect(runtimeManager.search).toHaveBeenLastCalledWith("handoff", {
      sessionKey: "agent:main:slack:channel:COPS12345:memory-scope:role:ops",
    });
  });

  it("keeps direct-message traffic isolated from project and role memory scopes", async () => {
    const { manager } = await memoryRuntime.getMemorySearchManager({
      cfg,
      agentId: "main",
      agentSessionKey: "agent:main:slack:dm:UOPS1234",
    } as never);

    await manager?.search("private note", { sessionKey: "agent:main:slack:dm:UOPS1234" });

    expect(runtimeManager.search).toHaveBeenLastCalledWith("private note", {
      sessionKey: "agent:main:slack:dm:UOPS1234:memory-scope:private:UOPS1234",
    });
  });

  it("anchors project-scoped memory managers to the project's default agent across handoffs", async () => {
    await memoryRuntime.getMemorySearchManager({
      cfg,
      agentId: "ops",
      agentSessionKey: "agent:ops:slack:channel:CPROJ1234:thread:1710000000.000100",
    } as never);

    expect(getRuntimeSearchManagerMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        agentId: "product",
        collaborationScope: {
          kind: "project",
          scope: "project:proj-a",
        },
      }),
    );
  });
});
