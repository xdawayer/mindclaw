/**
 * Multi-tenant workspace setup script.
 *
 * Reads the hardcoded user registry, generates per-user workspaces,
 * updates openclaw.json with agent entries + bindings,
 * and creates TEAM-ROSTER.md in the default workspace.
 *
 * Usage: bun scripts/mt-setup.ts
 *
 * Idempotent: won't overwrite existing USER.md files.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  generateTeamRoster,
  generateUserMd,
  buildPerUserAgentEntries,
} from "../src/agents/mt-workspace-generator.js";
import {
  createUserRegistry,
  registerUser,
  type UserRegistryEntry,
} from "../src/agents/user-registry-mt.js";

// ─── User Registry (hardcoded for now) ───────────────────────────

const USERS: (UserRegistryEntry & { language?: string })[] = [
  {
    userId: "ou_3ce0dce02872c344a4e244a1837ebced",
    displayName: "彪哥",
    roleId: "ceo",
    teamId: "product",
    isAdmin: true,
    language:
      "所有输出必须中文。技术术语（代码、命令、API名称）保留英文，其余全部中文。严禁输出英文句子或段落。",
  },
  {
    userId: "ou_48945201d6ed99e3ab27f983bde7f507",
    displayName: "王玲",
    roleId: "ceo",
    teamId: "product",
    isAdmin: true,
    language: "所有输出必须中文。技术术语保留英文，其余全部中文。",
  },
];

// ─── Paths ───────────────────────────────────────────────────────

const HOME = os.homedir();
const OPENCLAW_DIR = path.join(HOME, ".openclaw");
const CONFIG_PATH = path.join(OPENCLAW_DIR, "openclaw.json");
const DEFAULT_WORKSPACE = path.join(OPENCLAW_DIR, "workspace");

function resolveHome(p: string): string {
  return p.startsWith("~/") ? path.join(HOME, p.slice(2)) : p;
}

// ─── Main ────────────────────────────────────────────────────────

async function main() {
  console.log("=== Multi-tenant workspace setup ===\n");

  // 1. Build registry
  const registry = createUserRegistry();
  for (const u of USERS) {
    registerUser(registry, u);
  }

  // 2. Generate TEAM-ROSTER.md in default workspace (before per-user copy)
  const rosterPath = path.join(DEFAULT_WORKSPACE, "TEAM-ROSTER.md");
  const rosterContent = generateTeamRoster(registry);
  fs.writeFileSync(rosterPath, rosterContent, "utf-8");
  console.log(`  [written] ${rosterPath}`);

  // 3. Generate per-user agent entries
  const { agents, bindings } = buildPerUserAgentEntries(registry);

  // 4. Create per-user workspace directories + files
  // Build userId→agent map for safe lookup (avoids index alignment bugs)
  const agentByUserId = new Map(agents.map((a, i) => [USERS[i].userId, a]));
  for (const user of USERS) {
    const agent = agentByUserId.get(user.userId);
    if (!agent) {
      continue;
    }
    const wsDir = resolveHome(agent.workspace);

    fs.mkdirSync(wsDir, { recursive: true });

    // USER.md (don't overwrite if exists)
    const userMdPath = path.join(wsDir, "USER.md");
    if (!fs.existsSync(userMdPath)) {
      const content = generateUserMd({
        userId: user.userId,
        displayName: user.displayName,
        roleId: user.roleId,
        teamId: user.teamId,
        isAdmin: user.isAdmin ?? false,
        language: user.language,
      });
      fs.writeFileSync(userMdPath, content, "utf-8");
      console.log(`  [created] ${userMdPath}`);
    } else {
      console.log(`  [exists]  ${userMdPath}`);
    }

    // Copy shared files from default workspace if not exists
    for (const file of ["SOUL.md", "AGENTS.md", "TEAM-ROSTER.md"]) {
      const dst = path.join(wsDir, file);
      const src = path.join(DEFAULT_WORKSPACE, file);
      if (!fs.existsSync(dst) && fs.existsSync(src)) {
        fs.copyFileSync(src, dst);
        console.log(`  [copied]  ${dst}`);
      }
    }

    // Copy team-specific files
    const teamDir = path.join(DEFAULT_WORKSPACE, "teams", user.teamId);
    if (fs.existsSync(teamDir)) {
      for (const file of ["AGENTS.md", "SOUL.md"]) {
        const teamFile = path.join(teamDir, file);
        const teamDst = path.join(wsDir, `TEAM-${file}`);
        if (!fs.existsSync(teamDst) && fs.existsSync(teamFile)) {
          fs.copyFileSync(teamFile, teamDst);
          console.log(`  [copied]  ${teamDst}`);
        }
      }
    }
  }

  // 5. Update openclaw.json
  const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));

  // Add per-user agents to agents.list (skip if already exists)
  const existingIds = new Set((cfg.agents?.list ?? []).map((a: { id: string }) => a.id));
  const newAgents = agents.filter((a) => !existingIds.has(a.id));
  if (newAgents.length > 0) {
    cfg.agents = cfg.agents ?? {};
    cfg.agents.list = [
      ...(cfg.agents.list ?? []),
      ...newAgents.map((a) => ({
        id: a.id,
        ...(a.name ? { name: a.name } : {}),
        workspace: resolveHome(a.workspace),
      })),
    ];
    console.log(`  [config]  added ${newAgents.length} agents to agents.list`);
  }

  // Add bindings (skip if already exists for this peer)
  const existingBindings = cfg.bindings ?? [];
  const existingPeerIds = new Set(
    existingBindings.map((b: { match?: { peer?: { id?: string } } }) => b.match?.peer?.id),
  );
  const newBindings = bindings.filter((b) => !existingPeerIds.has(b.match.peer.id));
  if (newBindings.length > 0) {
    cfg.bindings = [...existingBindings, ...newBindings];
    console.log(`  [config]  added ${newBindings.length} bindings`);
  }

  // Enable dynamicAgentCreation for future new users
  cfg.channels = cfg.channels ?? {};
  cfg.channels.feishu = cfg.channels.feishu ?? {};
  cfg.channels.feishu.dynamicAgentCreation = {
    enabled: true,
    maxAgents: 20,
    workspaceTemplate: "~/.openclaw/workspace-{agentId}",
  };
  console.log("  [config]  enabled dynamicAgentCreation for new users");

  // Write config
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2) + "\n", "utf-8");
  console.log(`  [written] ${CONFIG_PATH}`);

  console.log("\n=== Setup complete ===");
  console.log("Restart the gateway for changes to take effect:");
  console.log("  pkill -f openclaw-gateway; openclaw gateway run &");
}

main().catch((err) => {
  console.error("Setup failed:", err);
  process.exit(1);
});
