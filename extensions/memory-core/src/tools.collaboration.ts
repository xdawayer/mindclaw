import path from "node:path";
import type { OpenClawConfig } from "openclaw/plugin-sdk/memory-core-host-runtime-core";
import type { MemorySearchResult } from "openclaw/plugin-sdk/memory-core-host-runtime-files";
import {
  loadSessionStore,
  resolveSessionStoreEntry,
  resolveStorePath,
} from "openclaw/plugin-sdk/session-store-runtime";

type CollaborationMemoryScope = "private" | "role_shared" | "space_shared";
type CollaborationPublishScope = "role_shared" | "space_shared";

type CollaborationScopeGate = {
  applied: boolean;
  readableScopes: CollaborationMemoryScope[];
  publishableScopes: CollaborationPublishScope[];
  effectiveRole?: string;
  spaceId?: string;
};

type CollaborationResolvedPathScope =
  | { scope: "private" }
  | { scope: "role_shared"; roleId?: string }
  | { scope: "space_shared"; spaceId?: string };

function normalizeId(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  return normalized || undefined;
}

function normalizeReadableScopes(value: unknown): CollaborationMemoryScope[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const allowed = new Set<CollaborationMemoryScope>();
  for (const entry of value) {
    if (entry === "private" || entry === "role_shared" || entry === "space_shared") {
      allowed.add(entry);
    }
  }
  return [...allowed];
}

function normalizePublishableScopes(value: unknown): CollaborationPublishScope[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const allowed = new Set<CollaborationPublishScope>();
  for (const entry of value) {
    if (entry === "role_shared" || entry === "space_shared") {
      allowed.add(entry);
    }
  }
  return [...allowed];
}

function resolvePathScope(
  relPath: string,
  source?: MemorySearchResult["source"],
): CollaborationResolvedPathScope {
  if (source === "sessions") {
    return { scope: "private" };
  }
  const normalized = relPath.replace(/\\/g, "/").toLowerCase();
  const segments = normalized
    .split("/")
    .map((segment) => segment.trim())
    .filter(Boolean);
  const collaborationIndex = segments.lastIndexOf("collaboration");
  if (collaborationIndex >= 0) {
    const scope = segments[collaborationIndex + 1];
    if (scope === "role_shared") {
      return {
        scope: "role_shared",
        roleId: normalizeId(segments[collaborationIndex + 2]),
      };
    }
    if (scope === "space_shared") {
      return {
        scope: "space_shared",
        spaceId: normalizeId(segments[collaborationIndex + 2]),
      };
    }
  }
  if (
    normalized === "memory.md" ||
    normalized === "dreams.md" ||
    normalized.startsWith("memory/")
  ) {
    return { scope: "private" };
  }
  return { scope: "private" };
}

function isPathScopeAllowed(params: {
  gate: CollaborationScopeGate | null;
  relPath: string;
  source?: MemorySearchResult["source"];
}): boolean {
  if (!params.gate) {
    return true;
  }
  const resolvedScope = resolvePathScope(params.relPath, params.source);
  if (!params.gate.readableScopes.includes(resolvedScope.scope)) {
    return false;
  }
  if (resolvedScope.scope === "private") {
    return true;
  }
  if (resolvedScope.scope === "role_shared") {
    return Boolean(
      resolvedScope.roleId &&
      params.gate.effectiveRole &&
      resolvedScope.roleId === params.gate.effectiveRole,
    );
  }
  return Boolean(
    resolvedScope.spaceId && params.gate.spaceId && resolvedScope.spaceId === params.gate.spaceId,
  );
}

export function resolveCollaborationScopeGate(params: {
  cfg: OpenClawConfig;
  agentId: string;
  agentSessionKey?: string;
}): CollaborationScopeGate | null {
  const sessionKey = params.agentSessionKey?.trim();
  if (!sessionKey) {
    return null;
  }
  const storePath = resolveStorePath(params.cfg.session?.store, { agentId: params.agentId });
  const store = loadSessionStore(storePath);
  const entry = resolveSessionStoreEntry({ store, sessionKey }).existing as
    | {
        collaboration?: {
          mode?: unknown;
          managedSurface?: unknown;
          spaceId?: unknown;
          effectiveRole?: unknown;
          readableScopes?: unknown;
          publishableScopes?: unknown;
        };
      }
    | undefined;
  const collaboration = entry?.collaboration;
  if (
    !collaboration ||
    collaboration.mode !== "enforced" ||
    collaboration.managedSurface !== true
  ) {
    return null;
  }
  return {
    applied: true,
    effectiveRole: normalizeId(collaboration.effectiveRole),
    publishableScopes: normalizePublishableScopes(collaboration.publishableScopes),
    readableScopes: normalizeReadableScopes(collaboration.readableScopes),
    spaceId: normalizeId(collaboration.spaceId),
  };
}

export function filterMemorySearchResultsByCollaboration(
  results: MemorySearchResult[],
  gate: CollaborationScopeGate | null,
): {
  results: MemorySearchResult[];
  filteredResults: number;
} {
  if (!gate) {
    return { results, filteredResults: 0 };
  }
  const filtered = results.filter((result) =>
    isPathScopeAllowed({
      gate,
      relPath: result.path,
      source: result.source,
    }),
  );
  return {
    results: filtered,
    filteredResults: Math.max(0, results.length - filtered.length),
  };
}

export function isMemoryReadAllowedByCollaboration(params: {
  relPath: string;
  gate: CollaborationScopeGate | null;
}): boolean {
  if (!params.gate) {
    return true;
  }
  const normalized = path.normalize(params.relPath).replace(/\\/g, "/");
  return isPathScopeAllowed({
    gate: params.gate,
    relPath: normalized,
  });
}

export function buildCollaborationSearchDebug(params: { gate: CollaborationScopeGate | null }) {
  if (!params.gate) {
    return undefined;
  }
  // Note: do not surface raw counts of filtered-out results here. The model
  // would otherwise infer existence and approximate volume of memories it is
  // not allowed to see. Operators get the full count via host events / logs
  // instead of through the tool reply.
  return {
    applied: true,
    ...(params.gate.effectiveRole ? { effectiveRole: params.gate.effectiveRole } : {}),
    publishableScopes: [...params.gate.publishableScopes],
    readableScopes: [...params.gate.readableScopes],
    ...(params.gate.spaceId ? { spaceId: params.gate.spaceId } : {}),
  };
}

export function buildCollaborationReadDebug(params: {
  gate: CollaborationScopeGate | null;
  blockedPath: string;
}) {
  if (!params.gate) {
    return undefined;
  }
  return {
    applied: true,
    ...(params.gate.effectiveRole ? { effectiveRole: params.gate.effectiveRole } : {}),
    publishableScopes: [...params.gate.publishableScopes],
    readableScopes: [...params.gate.readableScopes],
    blockedPath: params.blockedPath,
    ...(params.gate.spaceId ? { spaceId: params.gate.spaceId } : {}),
  };
}

export function isMemoryPublishAllowedByCollaboration(params: {
  cfg?: OpenClawConfig;
  scope: CollaborationPublishScope;
  gate: CollaborationScopeGate | null;
}): boolean {
  if (!params.gate) {
    return false;
  }
  if (!params.gate.publishableScopes.includes(params.scope)) {
    return false;
  }
  if (params.scope === "role_shared") {
    return Boolean(params.gate.effectiveRole);
  }
  if (!params.gate.spaceId) {
    return false;
  }
  // space_shared: also require the effective role to be in writableByRoles when
  // the space defines that allowlist. Without the allowlist (undefined/empty),
  // any role with publishableScopes.space_shared may publish.
  const writableByRoles = params.cfg?.collaboration?.spaces?.[params.gate.spaceId]?.memory
    ?.writableByRoles;
  if (writableByRoles?.length) {
    if (!params.gate.effectiveRole || !writableByRoles.includes(params.gate.effectiveRole)) {
      return false;
    }
  }
  return true;
}

export function buildCollaborationPublishDebug(params: {
  gate: CollaborationScopeGate | null;
  blockedScope?: CollaborationPublishScope;
}) {
  if (!params.gate) {
    return undefined;
  }
  return {
    applied: true,
    ...(params.gate.effectiveRole ? { effectiveRole: params.gate.effectiveRole } : {}),
    publishableScopes: [...params.gate.publishableScopes],
    readableScopes: [...params.gate.readableScopes],
    ...(params.gate.spaceId ? { spaceId: params.gate.spaceId } : {}),
    ...(params.blockedScope ? { blockedScope: params.blockedScope } : {}),
  };
}
