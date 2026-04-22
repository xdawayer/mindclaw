import type { MemoryPluginRuntime } from "openclaw/plugin-sdk/memory-core-host-runtime-core";
import { resolveMemoryBackendConfig } from "openclaw/plugin-sdk/memory-core-host-runtime-files";
import { closeAllMemorySearchManagers, getMemorySearchManager } from "./memory/index.js";
import {
  resolveScopedMemoryRuntimeContext,
  wrapMemorySearchManager,
} from "./memory/manager-provider-state.js";

export const memoryRuntime: MemoryPluginRuntime = {
  async getMemorySearchManager(params) {
    const resolved = resolveScopedMemoryRuntimeContext({
      cfg: params.cfg,
      agentId: params.agentId,
      agentSessionKey: params.agentSessionKey,
    });
    const { manager, error } = await getMemorySearchManager({
      cfg: params.cfg,
      agentId: resolved.agentId,
      purpose: params.purpose,
      collaborationScope: resolved.collaborationScope,
    });
    return {
      manager: manager
        ? wrapMemorySearchManager({
            manager,
            fallbackSessionKey: resolved.agentSessionKey,
            collaborationScope: resolved.collaborationScope,
          })
        : null,
      error,
    };
  },
  resolveMemoryBackendConfig(params) {
    const resolved = resolveScopedMemoryRuntimeContext({
      cfg: params.cfg,
      agentId: params.agentId,
      agentSessionKey: params.agentSessionKey,
    });
    return resolveMemoryBackendConfig({
      cfg: params.cfg,
      agentId: resolved.agentId,
    });
  },
  async closeAllMemorySearchManagers() {
    await closeAllMemorySearchManagers();
  },
};
