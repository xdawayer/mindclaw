/**
 * User registry for multi-tenant identity resolution.
 *
 * Core principle: userId uniquely determines a user's role, team, permissions,
 * and agent config — regardless of whether the message comes from DM or group chat.
 */

export type UserRegistryEntry = {
  userId: string;
  displayName: string;
  roleId: string;
  teamId: string;
  isAdmin?: boolean;
  /** Override agent ID. Defaults to "default" if not set. */
  agentId?: string;
};

export type UserIdentity = {
  userId: string;
  displayName: string;
  roleId: string;
  teamId: string;
  isAdmin: boolean;
  agentId: string;
};

export type UserRegistry = {
  entries: Map<string, UserRegistryEntry>;
};

const GUEST_DEFAULTS: Omit<UserIdentity, "userId" | "displayName"> = {
  roleId: "default",
  teamId: "general",
  isAdmin: false,
  agentId: "default",
};

export function createUserRegistry(initial?: UserRegistryEntry[]): UserRegistry {
  const registry: UserRegistry = { entries: new Map() };
  if (initial) {
    for (const entry of initial) {
      registerUser(registry, entry);
    }
  }
  return registry;
}

export function registerUser(registry: UserRegistry, entry: UserRegistryEntry): void {
  registry.entries.set(entry.userId, entry);
}

export function listRegisteredUsers(registry: UserRegistry): UserRegistryEntry[] {
  return [...registry.entries.values()];
}

/**
 * Resolve a user's full identity from their userId.
 * Returns guest defaults for unregistered users.
 * This is context-independent — same result for DM and group messages.
 */
export function resolveUserIdentity(registry: UserRegistry, userId: string): UserIdentity {
  const entry = registry.entries.get(userId);
  if (!entry) {
    return {
      userId,
      displayName: userId,
      ...GUEST_DEFAULTS,
    };
  }
  return {
    userId: entry.userId,
    displayName: entry.displayName,
    roleId: entry.roleId,
    teamId: entry.teamId,
    isAdmin: entry.isAdmin ?? false,
    agentId: entry.agentId ?? "default",
  };
}
