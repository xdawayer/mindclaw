import fs from "node:fs/promises";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { makeTempWorkspace, writeWorkspaceFile } from "../test-helpers/workspace.js";
import { syncOrgFiles } from "./workspace-org-sync.js";

describe("syncOrgFiles", () => {
  const tempDirs: string[] = [];

  async function makeTempDir(prefix = "openclaw-org-sync-"): Promise<string> {
    const dir = await makeTempWorkspace(prefix);
    tempDirs.push(dir);
    return dir;
  }

  afterEach(async () => {
    await Promise.all(tempDirs.map((dir) => fs.rm(dir, { recursive: true, force: true })));
    tempDirs.length = 0;
  });

  it("copies AGENTS.md from org/ to team workspace when file doesn't exist yet", async () => {
    const orgDir = await makeTempDir();
    const teamDir = await makeTempDir();
    await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org agents\n" });

    const result = await syncOrgFiles({ orgDir, teamDirs: [teamDir] });

    expect(result.synced).toEqual(["AGENTS.md"]);
    expect(result.skipped).toEqual([]);
    expect(result.errors).toEqual([]);
    const content = await fs.readFile(path.join(teamDir, "AGENTS.md"), "utf-8");
    expect(content).toBe("# Org agents\n");
  });

  it("updates AGENTS.md in team workspace when org version is newer", async () => {
    const orgDir = await makeTempDir();
    const teamDir = await makeTempDir();
    await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Updated org agents\n" });
    await writeWorkspaceFile({ dir: teamDir, name: "AGENTS.md", content: "# Old agents\n" });

    const result = await syncOrgFiles({ orgDir, teamDirs: [teamDir] });

    expect(result.synced).toEqual(["AGENTS.md"]);
    expect(result.skipped).toEqual([]);
    const content = await fs.readFile(path.join(teamDir, "AGENTS.md"), "utf-8");
    expect(content).toBe("# Updated org agents\n");
  });

  it("skips copy when team file is already identical to org file", async () => {
    const orgDir = await makeTempDir();
    const teamDir = await makeTempDir();
    const sameContent = "# Org agents\nIdentical content.\n";
    await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: sameContent });
    await writeWorkspaceFile({ dir: teamDir, name: "AGENTS.md", content: sameContent });

    const result = await syncOrgFiles({ orgDir, teamDirs: [teamDir] });

    expect(result.synced).toEqual([]);
    expect(result.skipped).toEqual(["AGENTS.md"]);
    expect(result.errors).toEqual([]);
  });

  it("syncs to multiple team workspaces in one call", async () => {
    const orgDir = await makeTempDir();
    const teamA = await makeTempDir();
    const teamB = await makeTempDir();
    const teamC = await makeTempDir();
    await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org\n" });
    // teamA: missing file (should sync)
    // teamB: different content (should sync)
    await writeWorkspaceFile({ dir: teamB, name: "AGENTS.md", content: "# Old\n" });
    // teamC: identical content (should skip)
    await writeWorkspaceFile({ dir: teamC, name: "AGENTS.md", content: "# Org\n" });

    const result = await syncOrgFiles({ orgDir, teamDirs: [teamA, teamB, teamC] });

    expect(result.synced).toContain("AGENTS.md");
    expect(result.skipped).toContain("AGENTS.md");
    // Verify actual file contents
    expect(await fs.readFile(path.join(teamA, "AGENTS.md"), "utf-8")).toBe("# Org\n");
    expect(await fs.readFile(path.join(teamB, "AGENTS.md"), "utf-8")).toBe("# Org\n");
    expect(await fs.readFile(path.join(teamC, "AGENTS.md"), "utf-8")).toBe("# Org\n");
  });

  it("reports error when org source file doesn't exist", async () => {
    const orgDir = await makeTempDir();
    const teamDir = await makeTempDir();
    // Don't create AGENTS.md in orgDir

    const result = await syncOrgFiles({ orgDir, teamDirs: [teamDir] });

    expect(result.synced).toEqual([]);
    expect(result.skipped).toEqual([]);
    expect(result.errors).toEqual(["AGENTS.md"]);
    // Team dir should not have the file either
    await expect(fs.access(path.join(teamDir, "AGENTS.md"))).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("rejects fileName with path traversal even when source file exists at traversal path", async () => {
    const orgDir = await makeTempDir();
    const teamDir = await makeTempDir();
    // Create the file at the *actual* traversal path so it wouldn't fail on read
    const parentDir = path.dirname(orgDir);
    await writeWorkspaceFile({ dir: parentDir, name: "secret.md", content: "# Secret\n" });
    await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org\n" });

    const result = await syncOrgFiles({
      orgDir,
      teamDirs: [teamDir],
      fileNames: ["../secret.md", "AGENTS.md"],
    });

    // Traversal name must be rejected regardless of whether file exists
    expect(result.errors).toContain("../secret.md");
    // Valid file should still sync
    expect(result.synced).toContain("AGENTS.md");
    // Secret file must NOT appear in team dir
    await expect(fs.access(path.join(teamDir, "secret.md"))).rejects.toMatchObject({
      code: "ENOENT",
    });
  });

  it("rejects fileName containing path separator", async () => {
    const orgDir = await makeTempDir();
    const teamDir = await makeTempDir();
    // Create a subdirectory with the file so it exists
    await fs.mkdir(path.join(orgDir, "subdir"), { recursive: true });
    await writeWorkspaceFile({ dir: path.join(orgDir, "subdir"), name: "file.md", content: "x" });

    const result = await syncOrgFiles({
      orgDir,
      teamDirs: [teamDir],
      fileNames: ["subdir/file.md"],
    });

    expect(result.errors).toContain("subdir/file.md");
  });

  it("does not overwrite team-specific files (only syncs files listed in fileNames)", async () => {
    const orgDir = await makeTempDir();
    const teamDir = await makeTempDir();
    await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org agents\n" });
    await writeWorkspaceFile({ dir: orgDir, name: "SOUL.md", content: "# Org soul\n" });
    // Team has its own TOOLS.md that must not be touched
    await writeWorkspaceFile({ dir: teamDir, name: "TOOLS.md", content: "# Team tools\n" });

    const result = await syncOrgFiles({
      orgDir,
      teamDirs: [teamDir],
      fileNames: ["AGENTS.md", "SOUL.md"],
    });

    expect(result.synced).toContain("AGENTS.md");
    expect(result.synced).toContain("SOUL.md");
    // TOOLS.md must remain untouched
    const toolsContent = await fs.readFile(path.join(teamDir, "TOOLS.md"), "utf-8");
    expect(toolsContent).toBe("# Team tools\n");
  });
});
