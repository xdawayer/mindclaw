import fs from "node:fs/promises";
import { afterEach, describe, expect, it } from "vitest";
import { makeTempWorkspace, writeWorkspaceFile } from "../test-helpers/workspace.js";
import { checkOrgSync, fixOrgSync } from "./workspace-org-sync-doctor.js";

describe("workspace-org-sync-doctor", () => {
  const tempDirs: string[] = [];

  async function makeTempDir(): Promise<string> {
    const dir = await makeTempWorkspace("openclaw-org-sync-doctor-");
    tempDirs.push(dir);
    return dir;
  }

  afterEach(async () => {
    await Promise.all(tempDirs.map((d) => fs.rm(d, { recursive: true, force: true })));
    tempDirs.length = 0;
  });

  describe("checkOrgSync", () => {
    it("reports healthy when all team files match org", async () => {
      const orgDir = await makeTempDir();
      const teamDir = await makeTempDir();
      await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org\n" });
      await writeWorkspaceFile({ dir: teamDir, name: "AGENTS.md", content: "# Org\n" });

      const result = await checkOrgSync({ orgDir, teamDirs: [teamDir], fileNames: ["AGENTS.md"] });

      expect(result.healthy).toBe(true);
      expect(result.issues).toEqual([]);
    });

    it("reports missing issue when team file does not exist", async () => {
      const orgDir = await makeTempDir();
      const teamDir = await makeTempDir();
      await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org\n" });

      const result = await checkOrgSync({ orgDir, teamDirs: [teamDir], fileNames: ["AGENTS.md"] });

      expect(result.healthy).toBe(false);
      expect(result.issues).toEqual([{ teamDir, fileName: "AGENTS.md", type: "missing" }]);
    });

    it("reports outdated issue when team file differs from org", async () => {
      const orgDir = await makeTempDir();
      const teamDir = await makeTempDir();
      await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# New\n" });
      await writeWorkspaceFile({ dir: teamDir, name: "AGENTS.md", content: "# Old\n" });

      const result = await checkOrgSync({ orgDir, teamDirs: [teamDir], fileNames: ["AGENTS.md"] });

      expect(result.healthy).toBe(false);
      expect(result.issues).toEqual([{ teamDir, fileName: "AGENTS.md", type: "outdated" }]);
    });

    it("reports org_missing when org source file does not exist", async () => {
      const orgDir = await makeTempDir();
      const teamDir = await makeTempDir();

      const result = await checkOrgSync({ orgDir, teamDirs: [teamDir], fileNames: ["AGENTS.md"] });

      expect(result.healthy).toBe(false);
      expect(result.issues).toEqual([{ teamDir, fileName: "AGENTS.md", type: "org_missing" }]);
    });
  });

  describe("fixOrgSync", () => {
    it("fixes missing and outdated files via syncOrgFiles", async () => {
      const orgDir = await makeTempDir();
      const teamDir = await makeTempDir();
      await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org\n" });

      const result = await fixOrgSync({ orgDir, teamDirs: [teamDir], fileNames: ["AGENTS.md"] });

      expect(result.synced).toEqual(["AGENTS.md"]);
      expect(result.errors).toEqual([]);
    });

    it("returns the OrgSyncResult from syncOrgFiles", async () => {
      const orgDir = await makeTempDir();
      const teamDir = await makeTempDir();
      await writeWorkspaceFile({ dir: orgDir, name: "AGENTS.md", content: "# Org\n" });
      await writeWorkspaceFile({ dir: teamDir, name: "AGENTS.md", content: "# Org\n" });

      const result = await fixOrgSync({ orgDir, teamDirs: [teamDir], fileNames: ["AGENTS.md"] });

      expect(result.synced).toEqual([]);
      expect(result.skipped).toEqual(["AGENTS.md"]);
      expect(result.errors).toEqual([]);
    });
  });
});
