import { describe, expect, it } from "vitest";
import {
  buildCitationMarkers,
  checkCitationUsage,
  type CitationMarker,
} from "./citation-tracker.js";

describe("buildCitationMarkers", () => {
  it("generates markers from search results", () => {
    const results = [
      { path: "memory/user.md", startLine: 5, snippet: "prefers TypeScript" },
      { path: "memory/project.md", startLine: 12, snippet: "deadline is Friday" },
    ];

    const markers = buildCitationMarkers(results);
    expect(markers).toHaveLength(2);
    expect(markers[0].marker).toBe("[mem:memory/user.md:5]");
    expect(markers[0].path).toBe("memory/user.md");
    expect(markers[1].marker).toBe("[mem:memory/project.md:12]");
  });

  it("returns empty array for empty results", () => {
    const markers = buildCitationMarkers([]);
    expect(markers).toEqual([]);
  });
});

describe("checkCitationUsage", () => {
  const markers: CitationMarker[] = [
    { marker: "[mem:memory/user.md:5]", path: "memory/user.md", line: 5 },
    { marker: "[mem:memory/project.md:12]", path: "memory/project.md", line: 12 },
    { marker: "[mem:memory/prefs.md:1]", path: "memory/prefs.md", line: 1 },
  ];

  it("detects markers referenced in response text", () => {
    const response = "Based on your preferences [mem:memory/user.md:5], I suggest TypeScript.";
    const usage = checkCitationUsage(markers, response);

    expect(usage.totalInjected).toBe(3);
    expect(usage.totalReferenced).toBe(1);
    expect(usage.hitRate).toBeCloseTo(1 / 3);
    expect(usage.referencedPaths).toEqual(["memory/user.md"]);
  });

  it("detects multiple referenced markers", () => {
    const response =
      "Per [mem:memory/user.md:5] and [mem:memory/project.md:12], we should use TS by Friday.";
    const usage = checkCitationUsage(markers, response);

    expect(usage.totalReferenced).toBe(2);
    expect(usage.hitRate).toBeCloseTo(2 / 3);
  });

  it("returns zero hit rate when no markers referenced", () => {
    const response = "I have no memory context to reference here.";
    const usage = checkCitationUsage(markers, response);

    expect(usage.totalReferenced).toBe(0);
    expect(usage.hitRate).toBe(0);
  });

  it("returns zero hit rate when no markers injected", () => {
    const usage = checkCitationUsage([], "Any response text");

    expect(usage.totalInjected).toBe(0);
    expect(usage.totalReferenced).toBe(0);
    expect(usage.hitRate).toBe(0);
  });

  it("also detects path-only references without line numbers", () => {
    const response = "As noted in memory/user.md, the user prefers TypeScript.";
    const usage = checkCitationUsage(markers, response);

    expect(usage.totalReferenced).toBe(1);
    expect(usage.referencedPaths).toEqual(["memory/user.md"]);
  });
});
