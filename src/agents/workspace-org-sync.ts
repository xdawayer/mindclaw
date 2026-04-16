import fs from "node:fs/promises";
import path from "node:path";

export type OrgSyncResult = {
  synced: string[];
  skipped: string[];
  errors: string[];
};

const DEFAULT_FILE_NAMES = ["AGENTS.md"];

/**
 * Copy org-level workspace files to each team workspace directory.
 * Files already identical in the target are skipped. Missing source files
 * are reported as errors without touching the target.
 */
export async function syncOrgFiles(params: {
  orgDir: string;
  teamDirs: string[];
  fileNames?: string[];
}): Promise<OrgSyncResult> {
  const { orgDir, teamDirs, fileNames = DEFAULT_FILE_NAMES } = params;
  const synced: string[] = [];
  const skipped: string[] = [];
  const errors: string[] = [];

  for (const fileName of fileNames) {
    // Reject path traversal and subdirectory references
    if (fileName.includes("..") || fileName.includes("/") || fileName.includes("\\")) {
      errors.push(fileName);
      continue;
    }

    const srcPath = path.join(orgDir, fileName);

    let srcContent: string;
    try {
      srcContent = await fs.readFile(srcPath, "utf-8");
    } catch {
      errors.push(fileName);
      continue;
    }

    for (const teamDir of teamDirs) {
      const destPath = path.join(teamDir, fileName);

      // Check whether the target already matches the source content.
      try {
        const existing = await fs.readFile(destPath, "utf-8");
        if (existing === srcContent) {
          if (!skipped.includes(fileName)) {
            skipped.push(fileName);
          }
          continue;
        }
      } catch {
        // File doesn't exist yet -- will be created below.
      }

      await fs.mkdir(path.dirname(destPath), { recursive: true });
      await fs.writeFile(destPath, srcContent, "utf-8");
      if (!synced.includes(fileName)) {
        synced.push(fileName);
      }
    }
  }

  return { synced, skipped, errors };
}
