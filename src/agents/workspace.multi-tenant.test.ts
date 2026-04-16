import fs from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { makeTempWorkspace, writeWorkspaceFile } from "../test-helpers/workspace.js";
import { loadWorkspaceBootstrapFiles } from "./workspace.js";

/**
 * Multi-tenant workspace composition tests.
 *
 * Validates that OpenClaw's existing workspace primitives support
 * multi-tenant architecture through composition:
 *   - Each Team agent has isolated workspace with its own files
 *   - Org-level rules are included directly in each Team workspace
 *   - Team-specific TOOLS.md provides role-based tool isolation
 *
 * Architecture note: symlinks across workspace boundaries are rejected
 * by the boundary security check (by design). Org files must be placed
 * directly in each Team workspace, kept in sync by setup/doctor scripts.
 */
describe("multi-tenant workspace: per-team isolation", () => {
  it("loads Org rules from Team workspace when placed directly", async () => {
    const teamDir = await makeTempWorkspace("mt-team-sales-");

    // Org rules placed directly in team workspace (maintained by setup script)
    await writeWorkspaceFile({
      dir: teamDir,
      name: "AGENTS.md",
      content: "# Org Safety Rules\n\nNever execute destructive operations.",
    });
    // Team-specific soul
    await writeWorkspaceFile({
      dir: teamDir,
      name: "SOUL.md",
      content: "# Sales Team\n\nYou are a sales assistant.",
    });

    const files = await loadWorkspaceBootstrapFiles(teamDir);

    const agentsFile = files.find((f) => f.name === "AGENTS.md");
    expect(agentsFile).toBeDefined();
    expect(agentsFile!.missing).toBe(false);
    expect(agentsFile!.content).toContain("Org Safety Rules");
    expect(agentsFile!.content).toContain("Never execute destructive operations");

    const soulFile = files.find((f) => f.name === "SOUL.md");
    expect(soulFile).toBeDefined();
    expect(soulFile!.missing).toBe(false);
    expect(soulFile!.content).toContain("Sales Team");
  });

  it("team workspaces are fully isolated from each other", async () => {
    const salesDir = await makeTempWorkspace("mt-sales-");
    const engDir = await makeTempWorkspace("mt-eng-");

    // Same Org rules in both (maintained by setup script)
    const orgRules = "# Org Rules\nNo sensitive data. No external API calls.";
    await writeWorkspaceFile({ dir: salesDir, name: "AGENTS.md", content: orgRules });
    await writeWorkspaceFile({ dir: engDir, name: "AGENTS.md", content: orgRules });

    // Different tools per team = role-based access
    await writeWorkspaceFile({
      dir: salesDir,
      name: "TOOLS.md",
      content: "# Sales Tools\n\n- CRM query\n- Email generation",
    });
    await writeWorkspaceFile({
      dir: engDir,
      name: "TOOLS.md",
      content: "# Engineering Tools\n\n- exec\n- bash\n- git",
    });

    const salesFiles = await loadWorkspaceBootstrapFiles(salesDir);
    const engFiles = await loadWorkspaceBootstrapFiles(engDir);

    // Both share Org rules
    const salesAgents = salesFiles.find((f) => f.name === "AGENTS.md");
    const engAgents = engFiles.find((f) => f.name === "AGENTS.md");
    expect(salesAgents!.content).toBe(orgRules);
    expect(engAgents!.content).toBe(orgRules);

    // But have different tools (role isolation)
    const salesTools = salesFiles.find((f) => f.name === "TOOLS.md");
    const engTools = engFiles.find((f) => f.name === "TOOLS.md");
    expect(salesTools!.content).toContain("CRM query");
    expect(salesTools!.content).not.toContain("exec");
    expect(engTools!.content).toContain("exec");
    expect(engTools!.content).not.toContain("CRM query");
  });

  it("symlinks across workspace boundary are correctly rejected (security)", async () => {
    // This test documents the security constraint that informed the architecture:
    // symlinks pointing outside the workspace boundary are rejected.
    const root = await makeTempWorkspace("mt-symlink-reject-");
    const orgDir = path.join(root, "org");
    const teamDir = path.join(root, "teams", "sales");
    await fs.mkdir(orgDir, { recursive: true });
    await fs.mkdir(teamDir, { recursive: true });

    await fs.writeFile(path.join(orgDir, "AGENTS.md"), "# Org Rules");
    await fs.symlink(path.join(orgDir, "AGENTS.md"), path.join(teamDir, "AGENTS.md"));

    const files = await loadWorkspaceBootstrapFiles(teamDir);

    const agentsFile = files.find((f) => f.name === "AGENTS.md");
    // Symlink outside boundary → file treated as missing (security by design)
    expect(agentsFile).toBeDefined();
    expect(agentsFile!.missing).toBe(true);
  });

  it("group chat agent workspace does not contain personal files", async () => {
    const teamDir = await makeTempWorkspace("mt-group-");
    await writeWorkspaceFile({
      dir: teamDir,
      name: "AGENTS.md",
      content: "# Team Rules",
    });
    await writeWorkspaceFile({
      dir: teamDir,
      name: "TOOLS.md",
      content: "# Team Tools\n\n- shared-tool",
    });
    // No USER.md, no MEMORY.md in group workspace (isolation by absence)

    const files = await loadWorkspaceBootstrapFiles(teamDir);

    const userFile = files.find((f) => f.name === "USER.md");
    const memoryFile = files.find((f) => f.name === "MEMORY.md");
    const memoryAltFile = files.find((f) => f.name === "memory.md");
    // Personal files should be missing or absent from team workspace
    expect(userFile?.missing ?? true).toBe(true);
    expect(memoryFile?.missing ?? true).toBe(true);
    expect(memoryAltFile?.missing ?? true).toBe(true);
  });
});
