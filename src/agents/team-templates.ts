import fs from "node:fs/promises";
import path from "node:path";

const SANITIZE_RE = /[^a-z0-9_-]/g;

function sanitizeTeamId(teamId: string): string {
  return teamId.toLowerCase().replace(SANITIZE_RE, "") || "default";
}

export type TemplateMetadata = {
  name: string;
  description?: string;
  variables: string[];
};

export type TeamTemplate = {
  metadata: TemplateMetadata;
  body: string;
  fileName: string;
};

export function resolveTemplateDir(workspaceDir: string, teamId: string): string {
  return path.join(workspaceDir, "teams", sanitizeTeamId(teamId), "templates");
}

export async function listTemplates(workspaceDir: string, teamId: string): Promise<string[]> {
  const dir = resolveTemplateDir(workspaceDir, teamId);
  let entries: string[];
  try {
    const dirents = await fs.readdir(dir, { withFileTypes: false });
    entries = dirents;
  } catch {
    return [];
  }
  return entries.filter((f) => f.endsWith(".md")).toSorted();
}

function parseFrontmatter(raw: string): { metadata: TemplateMetadata; body: string } | null {
  const match = /^---\n([\s\S]*?)\n---\n([\s\S]*)$/.exec(raw);
  if (!match) {
    return null;
  }

  const yamlBlock = match[1];
  const body = match[2];

  // Simple YAML-like parsing for our known fields
  let name = "";
  let description: string | undefined;
  const variables: string[] = [];

  let inVariables = false;
  for (const line of yamlBlock.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("name:")) {
      name = trimmed.slice(5).trim();
      inVariables = false;
    } else if (trimmed.startsWith("description:")) {
      description = trimmed.slice(12).trim();
      inVariables = false;
    } else if (trimmed === "variables:") {
      inVariables = true;
    } else if (inVariables && trimmed.startsWith("- ")) {
      variables.push(trimmed.slice(2).trim());
    } else {
      inVariables = false;
    }
  }

  return {
    metadata: { name, description, variables },
    body,
  };
}

const PATH_TRAVERSAL_RE = /\.\./;

export async function loadTemplate(
  workspaceDir: string,
  teamId: string,
  fileName: string,
): Promise<TeamTemplate | null> {
  if (PATH_TRAVERSAL_RE.test(fileName)) {
    return null;
  }

  const dir = resolveTemplateDir(workspaceDir, teamId);
  const filePath = path.join(dir, fileName);

  let raw: string;
  try {
    raw = await fs.readFile(filePath, "utf-8");
  } catch {
    return null;
  }

  const parsed = parseFrontmatter(raw);
  if (!parsed) {
    return { metadata: { name: fileName, variables: [] }, body: raw, fileName };
  }

  return { ...parsed, fileName };
}

export function renderTemplate(body: string, variables: Record<string, string>): string {
  let result = body;
  for (const [key, value] of Object.entries(variables)) {
    result = result.replaceAll(`{{${key}}}`, value);
  }
  return result;
}
