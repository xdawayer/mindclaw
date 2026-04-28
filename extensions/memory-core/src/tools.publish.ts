import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Type } from "@sinclair/typebox";
import { stringEnum } from "openclaw/plugin-sdk/channel-actions";
import { appendCollaborationAuditEventForAgent } from "openclaw/plugin-sdk/collaboration-runtime";
import { appendMemoryHostEvent } from "openclaw/plugin-sdk/memory-core-host-events";
import {
  jsonResult,
  readStringParam,
  resolveDefaultAgentId,
  resolveStateDir,
  type OpenClawConfig,
} from "openclaw/plugin-sdk/memory-core-host-runtime-core";
import {
  buildCollaborationPublishDebug,
  isMemoryPublishAllowedByCollaboration,
  resolveCollaborationScopeGate,
} from "./tools.collaboration.js";
import { createMemoryTool } from "./tools.shared.js";

const MEMORY_PUBLISH_SCOPES = ["role_shared", "space_shared"] as const;
type MemoryPublishScope = (typeof MEMORY_PUBLISH_SCOPES)[number];

export const MemoryPublishSchema = Type.Object({
  scope: stringEnum(MEMORY_PUBLISH_SCOPES),
  path: Type.String(),
  content: Type.String(),
});

function normalizeAgentId(value: string | undefined): string {
  return value?.trim().toLowerCase() || "main";
}

function resolveUserPathLocal(input: string): string {
  const trimmed = input.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed === "~") {
    return os.homedir();
  }
  if (trimmed.startsWith("~/") || trimmed.startsWith("~\\")) {
    return path.join(os.homedir(), trimmed.slice(2));
  }
  return path.resolve(trimmed);
}

function resolveDefaultWorkspaceDir(env: NodeJS.ProcessEnv = process.env): string {
  const home = env.HOME?.trim() || os.homedir();
  const profile = env.OPENCLAW_PROFILE?.trim();
  if (profile && profile.toLowerCase() !== "default") {
    return path.join(home, ".openclaw", `workspace-${profile}`);
  }
  return path.join(home, ".openclaw", "workspace");
}

function resolveWorkspaceDirForAgent(cfg: OpenClawConfig, agentId: string): string {
  const normalizedAgentId = normalizeAgentId(agentId);
  const agentEntry = (cfg.agents?.list ?? []).find(
    (entry) => normalizeAgentId(entry?.id) === normalizedAgentId,
  );
  const configuredWorkspace =
    typeof agentEntry?.workspace === "string" ? agentEntry.workspace.trim() : "";
  if (configuredWorkspace) {
    return resolveUserPathLocal(configuredWorkspace);
  }

  const normalizedDefaultAgentId = normalizeAgentId(resolveDefaultAgentId(cfg));
  const defaultWorkspace =
    typeof cfg.agents?.defaults?.workspace === "string" ? cfg.agents.defaults.workspace.trim() : "";
  if (defaultWorkspace) {
    const resolvedDefaultWorkspace = resolveUserPathLocal(defaultWorkspace);
    return normalizedAgentId === normalizedDefaultAgentId
      ? resolvedDefaultWorkspace
      : path.join(resolvedDefaultWorkspace, normalizedAgentId);
  }

  if (normalizedAgentId === normalizedDefaultAgentId) {
    return resolveDefaultWorkspaceDir();
  }
  return path.join(resolveStateDir(), `workspace-${normalizedAgentId}`);
}

function normalizePublishPath(rawPath: string): string {
  const normalized = path.posix.normalize(rawPath.trim().replace(/\\/g, "/"));
  if (!normalized || normalized === ".") {
    throw new Error("memory_publish path is required");
  }
  if (normalized.includes("\0")) {
    throw new Error("memory_publish path cannot contain null bytes");
  }
  if (path.posix.isAbsolute(normalized) || normalized.startsWith("../") || normalized === "..") {
    throw new Error("memory_publish path must stay inside the collaboration scope");
  }
  if (!normalized.toLowerCase().endsWith(".md")) {
    throw new Error("memory_publish path must end with .md");
  }
  return normalized;
}

function buildPublishEntry(params: {
  scope: MemoryPublishScope;
  content: string;
  effectiveRole?: string;
  spaceId?: string;
}): string {
  const body = params.content.trimEnd();
  const timestamp = new Date().toISOString();
  const metadata = [
    `timestamp=${timestamp}`,
    `scope=${params.scope}`,
    ...(params.effectiveRole ? [`role=${params.effectiveRole}`] : []),
    ...(params.spaceId ? [`space=${params.spaceId}`] : []),
  ].join("; ");
  return `<!-- openclaw-collaboration-publish: ${metadata} -->\n${body}\n`;
}

async function appendPublishedContent(params: {
  absolutePath: string;
  entry: string;
}): Promise<void> {
  let existing = "";
  try {
    existing = await fs.readFile(params.absolutePath, "utf-8");
  } catch (error) {
    const code = (error as NodeJS.ErrnoException)?.code;
    if (code !== "ENOENT") {
      throw error;
    }
  }

  const separator =
    existing.length > 0 && !existing.endsWith("\n") && !params.entry.startsWith("\n") ? "\n" : "";
  await fs.mkdir(path.dirname(params.absolutePath), { recursive: true });
  await fs.writeFile(params.absolutePath, `${existing}${separator}${params.entry}`, "utf-8");
}

function resolvePublishRoot(params: {
  gate: NonNullable<ReturnType<typeof resolveCollaborationScopeGate>>;
  scope: MemoryPublishScope;
}): string | null {
  if (params.scope === "role_shared") {
    return params.gate.effectiveRole
      ? `collaboration/role_shared/${params.gate.effectiveRole}`
      : null;
  }
  return params.gate.spaceId ? `collaboration/space_shared/${params.gate.spaceId}` : null;
}

export function createMemoryPublishTool(options: {
  config?: OpenClawConfig;
  agentSessionKey?: string;
}) {
  return createMemoryTool({
    options,
    label: "Memory Publish",
    name: "memory_publish",
    description:
      "Append a vetted collaboration note into the current role_shared or space_shared memory scope. Use this only to publish durable shared context, not for private scratch notes.",
    parameters: MemoryPublishSchema,
    execute:
      ({ cfg, agentId }) =>
      async (_toolCallId, params) => {
        const scope = readStringParam(params, "scope", { required: true }) as MemoryPublishScope;
        const requestedPath = readStringParam(params, "path", { required: true });
        const content = readStringParam(params, "content", { required: true });
        const gate = resolveCollaborationScopeGate({
          cfg,
          agentId,
          agentSessionKey: options.agentSessionKey,
        });

        if (!isMemoryPublishAllowedByCollaboration({ cfg, scope, gate }) || !gate) {
          return jsonResult({
            scope,
            path: requestedPath,
            disabled: true,
            denied: true,
            error: "memory publish blocked by collaboration scope gate",
            debug: {
              collaboration: buildCollaborationPublishDebug({
                gate,
                blockedScope: scope,
              }),
            },
          });
        }

        try {
          const relativeTarget = normalizePublishPath(requestedPath);
          const publishRoot = resolvePublishRoot({ gate, scope });
          if (!publishRoot) {
            throw new Error("memory_publish target scope is unresolved for the current session");
          }
          const fullRelativePath = path.posix.join(publishRoot, relativeTarget);
          const workspaceDir = resolveWorkspaceDirForAgent(cfg, agentId);
          const absolutePath = path.join(workspaceDir, fullRelativePath);
          const entry = buildPublishEntry({
            scope,
            content,
            effectiveRole: gate.effectiveRole,
            spaceId: gate.spaceId,
          });
          await appendPublishedContent({
            absolutePath,
            entry,
          });
          await appendMemoryHostEvent(workspaceDir, {
            type: "memory.collaboration.published",
            timestamp: new Date().toISOString(),
            scope,
            path: fullRelativePath,
            ...(gate.effectiveRole ? { effectiveRole: gate.effectiveRole } : {}),
            ...(gate.spaceId ? { spaceId: gate.spaceId } : {}),
          });
          await appendCollaborationAuditEventForAgent({
            cfg,
            agentId,
            event: {
              type: "collaboration.memory.published",
              timestamp: new Date().toISOString(),
              source: "memory_publish",
              scope,
              path: fullRelativePath,
              ...(gate.effectiveRole ? { effectiveRole: gate.effectiveRole } : {}),
              ...(gate.spaceId ? { spaceId: gate.spaceId } : {}),
            },
          });
          return jsonResult({
            scope,
            path: fullRelativePath,
            appendOnly: true,
            published: true,
          });
        } catch (error) {
          return jsonResult({
            scope,
            path: requestedPath,
            disabled: true,
            error: error instanceof Error ? error.message : "memory publish failed",
            debug: {
              collaboration: buildCollaborationPublishDebug({
                gate,
              }),
            },
          });
        }
      },
  });
}
