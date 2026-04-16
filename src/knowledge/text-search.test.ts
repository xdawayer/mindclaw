import { describe, expect, it } from "vitest";
import { createSearchIndex } from "./text-search.js";
import type { SearchDocument } from "./text-search.js";

describe("text-search", () => {
  it("empty index returns empty results", () => {
    const index = createSearchIndex();
    expect(index.search("anything")).toEqual([]);
    expect(index.size()).toBe(0);
  });

  it("single document matches by keyword", () => {
    const index = createSearchIndex();
    index.add([{ id: "doc1", content: "The quick brown fox jumps over the lazy dog" }]);
    const results = index.search("fox");
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("doc1");
    expect(results[0].score).toBeGreaterThan(0);
  });

  it("returns results sorted by relevance score (highest first)", () => {
    const index = createSearchIndex();
    index.add([
      { id: "low", content: "The cat sat on the mat" },
      { id: "high", content: "Deploy deploy deploy the deployment pipeline for deploying" },
      { id: "mid", content: "We need to deploy the service" },
    ]);
    const results = index.search("deploy");
    expect(results.length).toBeGreaterThanOrEqual(2);
    expect(results[0].id).toBe("high");
    // Scores must be descending
    for (let i = 1; i < results.length; i++) {
      expect(results[i - 1].score).toBeGreaterThanOrEqual(results[i].score);
    }
  });

  it("respects limit parameter", () => {
    const index = createSearchIndex();
    const docs: SearchDocument[] = Array.from({ length: 10 }, (_, i) => ({
      id: `doc${i}`,
      content: `Document number ${i} about testing`,
    }));
    index.add(docs);
    const results = index.search("testing", 3);
    expect(results).toHaveLength(3);
  });

  it("returns snippet with matched term context", () => {
    const index = createSearchIndex();
    index.add([
      {
        id: "doc1",
        content:
          "This is a long document with many words. " +
          "The deployment process requires careful planning and execution. " +
          "After deployment, monitor the system closely for any issues.",
      },
    ]);
    const results = index.search("deployment");
    expect(results).toHaveLength(1);
    expect(results[0].snippet).toContain("deployment");
    expect(results[0].snippet.length).toBeLessThanOrEqual(220);
  });

  it("multiple keyword query scores higher for docs matching more terms", () => {
    const index = createSearchIndex();
    index.add([
      { id: "one-term", content: "The server crashed yesterday" },
      { id: "two-terms", content: "The server crashed and the database was corrupted" },
    ]);
    const results = index.search("server database");
    expect(results[0].id).toBe("two-terms");
    expect(results[0].score).toBeGreaterThan(results[1].score);
  });

  it("case-insensitive matching", () => {
    const index = createSearchIndex();
    index.add([{ id: "doc1", content: "OpenClaw is a great tool" }]);
    const results = index.search("openclaw");
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("doc1");
  });

  it("Chinese text search works", () => {
    const index = createSearchIndex();
    index.add([
      { id: "zh1", content: "这是一个关于部署流程的文档" },
      { id: "zh2", content: "今天天气很好适合出门" },
    ]);
    const results = index.search("部署");
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("zh1");
  });

  it("no results for unrelated query", () => {
    const index = createSearchIndex();
    index.add([{ id: "doc1", content: "The quick brown fox jumps over the lazy dog" }]);
    const results = index.search("kubernetes");
    expect(results).toEqual([]);
  });

  it("handles duplicate document IDs (accepts both, no dedup)", () => {
    const index = createSearchIndex();
    index.add([
      { id: "dup", content: "first version of the document about servers" },
      { id: "dup", content: "second version of the document about servers" },
    ]);
    expect(index.size()).toBe(2);
    const results = index.search("servers");
    expect(results.length).toBe(2);
  });

  it("preserves metadata in results", () => {
    const index = createSearchIndex();
    index.add([
      {
        id: "doc1",
        content: "Runbook for database migrations",
        metadata: { team: "platform", category: "sop" },
      },
    ]);
    const results = index.search("database");
    expect(results[0].metadata).toEqual({ team: "platform", category: "sop" });
  });
});
