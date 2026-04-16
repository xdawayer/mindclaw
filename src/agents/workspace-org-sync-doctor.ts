import fs from "node:fs/promises";
import path from "node:path";
import { type OrgSyncResult, syncOrgFiles } from "./workspace-org-sync.js";

export type OrgSyncIssue = {
  teamDir: string;
  fileName: string;
  type: "missing" | "outdated" | "org_missing";
};

export type OrgSyncCheckResult = {
  healthy: boolean;
  issues: OrgSyncIssue[];
};

/** Check org file consistency without modifying anything. */
export async function checkOrgSync(params: {
  orgDir: string;
  teamDirs: string[];
  fileNames?: string[];
}): Promise<OrgSyncCheckResult> {
  const { orgDir, teamDirs, fileNames = ["AGENTS.md"] } = params;
  const issues: OrgSyncIssue[] = [];

  for (const fileName of fileNames) {
    let srcContent: string;
    try {
      srcContent = await fs.readFile(path.join(orgDir, fileName), "utf-8");
    } catch {
      for (const teamDir of teamDirs) {
        issues.push({ teamDir, fileName, type: "org_missing" });
      }
      continue;
    }
    for (const teamDir of teamDirs) {
      try {
        const existing = await fs.readFile(path.join(teamDir, fileName), "utf-8");
        if (existing !== srcContent) {
          issues.push({ teamDir, fileName, type: "outdated" });
        }
      } catch {
        issues.push({ teamDir, fileName, type: "missing" });
      }
    }
  }

  return { healthy: issues.length === 0, issues };
}

/** Fix org file consistency by syncing. Returns the sync result. */
export async function fixOrgSync(params: {
  orgDir: string;
  teamDirs: string[];
  fileNames?: string[];
}): Promise<OrgSyncResult> {
  return syncOrgFiles(params);
}
