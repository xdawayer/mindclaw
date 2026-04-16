import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  resolveTemplateDir,
  listTemplates,
  loadTemplate,
  renderTemplate,
} from "./team-templates.js";

// Mock fs for file operations
vi.mock("node:fs/promises", () => ({
  default: {
    readdir: vi.fn(),
    readFile: vi.fn(),
  },
}));

import fs from "node:fs/promises";

beforeEach(() => {
  vi.mocked(fs.readdir).mockReset();
  vi.mocked(fs.readFile).mockReset();
});

describe("team-templates", () => {
  describe("resolveTemplateDir", () => {
    it("returns workspace/teams/{teamId}/templates path", () => {
      const dir = resolveTemplateDir("/workspace", "sales");
      expect(dir).toBe("/workspace/teams/sales/templates");
    });

    it("sanitizes teamId", () => {
      const dir = resolveTemplateDir("/workspace", "Sales Team!");
      expect(dir).toBe("/workspace/teams/salesteam/templates");
    });
  });

  describe("listTemplates", () => {
    it("returns .md template files sorted", async () => {
      vi.mocked(fs.readdir).mockResolvedValue([
        "weekly-report.md",
        "email.md",
        "README.txt",
        "standup.md",
      ] as never);
      const result = await listTemplates("/workspace", "sales");
      expect(result).toEqual(["email.md", "standup.md", "weekly-report.md"]);
    });

    it("returns empty array when directory does not exist", async () => {
      vi.mocked(fs.readdir).mockRejectedValue(new Error("ENOENT"));
      const result = await listTemplates("/workspace", "sales");
      expect(result).toEqual([]);
    });
  });

  describe("loadTemplate", () => {
    it("loads and parses template with frontmatter", async () => {
      const raw = `---
name: 周报模板
description: Weekly status report template
variables:
  - name
  - week
  - highlights
---
# {{name}} 的第 {{week}} 周周报

## 本周亮点
{{highlights}}
`;
      vi.mocked(fs.readFile).mockResolvedValue(raw);
      const tmpl = await loadTemplate("/workspace", "sales", "weekly-report.md");
      expect(tmpl).not.toBeNull();
      expect(tmpl!.metadata.name).toBe("周报模板");
      expect(tmpl!.metadata.variables).toEqual(["name", "week", "highlights"]);
      expect(tmpl!.body).toContain("{{name}}");
    });

    it("returns null when file does not exist", async () => {
      vi.mocked(fs.readFile).mockRejectedValue(new Error("ENOENT"));
      const tmpl = await loadTemplate("/workspace", "sales", "nonexistent.md");
      expect(tmpl).toBeNull();
    });

    it("rejects path traversal in filename", async () => {
      const tmpl = await loadTemplate("/workspace", "sales", "../../../etc/passwd");
      expect(tmpl).toBeNull();
      expect(fs.readFile).not.toHaveBeenCalled();
    });
  });

  describe("renderTemplate", () => {
    it("substitutes variables in template body", () => {
      const result = renderTemplate("# {{name}} 的第 {{week}} 周周报\n\n{{highlights}}", {
        name: "张三",
        week: "12",
        highlights: "完成了多租户设计",
      });
      expect(result).toBe("# 张三 的第 12 周周报\n\n完成了多租户设计");
    });

    it("leaves unmatched variables as-is", () => {
      const result = renderTemplate("Hello {{name}}, your role is {{role}}", {
        name: "Alice",
      });
      expect(result).toBe("Hello Alice, your role is {{role}}");
    });

    it("handles empty variables map", () => {
      const body = "No vars here";
      expect(renderTemplate(body, {})).toBe("No vars here");
    });
  });
});
