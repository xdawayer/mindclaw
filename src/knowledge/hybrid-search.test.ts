import { describe, test, expect } from "vitest";
import { combineSearchScores } from "./hybrid-search.js";

function makeScore(
  id: string,
  bm25: number,
  vector: number,
): { id: string; bm25: number; vector: number } {
  return { id, bm25, vector };
}

describe("hybrid-search", () => {
  describe("combineSearchScores", () => {
    test("combines BM25 and vector scores with default weights (0.3 bm25 + 0.7 vector)", () => {
      const results = combineSearchScores([makeScore("a", 1.0, 0.8)]);
      // 0.3 * 1.0 + 0.7 * 0.8 = 0.86
      expect(results[0].combinedScore).toBeCloseTo(0.86);
    });

    test("sorts results by combined score descending", () => {
      const results = combineSearchScores([
        makeScore("low", 0.1, 0.2),
        makeScore("high", 0.9, 0.9),
        makeScore("mid", 0.5, 0.5),
      ]);
      expect(results[0].id).toBe("high");
      expect(results[1].id).toBe("mid");
      expect(results[2].id).toBe("low");
    });

    test("allows custom weights", () => {
      const results = combineSearchScores([makeScore("a", 1.0, 0.0)], {
        bm25Weight: 1.0,
        vectorWeight: 0.0,
      });
      expect(results[0].combinedScore).toBeCloseTo(1.0);
    });

    test("handles bm25-only results (vector = 0)", () => {
      const results = combineSearchScores([makeScore("a", 0.8, 0)]);
      // 0.3 * 0.8 + 0.7 * 0 = 0.24
      expect(results[0].combinedScore).toBeCloseTo(0.24);
      expect(results[0].sources).toContain("bm25");
    });

    test("handles vector-only results (bm25 = 0)", () => {
      const results = combineSearchScores([makeScore("a", 0, 0.9)]);
      // 0.3 * 0 + 0.7 * 0.9 = 0.63
      expect(results[0].combinedScore).toBeCloseTo(0.63);
      expect(results[0].sources).toContain("vector");
    });

    test("tracks which sources contributed", () => {
      const results = combineSearchScores([
        makeScore("both", 0.5, 0.5),
        makeScore("bm25-only", 0.5, 0),
        makeScore("vector-only", 0, 0.5),
      ]);

      const both = results.find((r) => r.id === "both")!;
      expect(both.sources).toContain("bm25");
      expect(both.sources).toContain("vector");

      const bm25Only = results.find((r) => r.id === "bm25-only")!;
      expect(bm25Only.sources).toEqual(["bm25"]);

      const vectorOnly = results.find((r) => r.id === "vector-only")!;
      expect(vectorOnly.sources).toEqual(["vector"]);
    });

    test("returns empty array for empty input", () => {
      expect(combineSearchScores([])).toEqual([]);
    });

    test("clamps combined score to [0, 1]", () => {
      const results = combineSearchScores([makeScore("a", 1.5, 1.5)], {
        bm25Weight: 0.5,
        vectorWeight: 0.5,
      });
      expect(results[0].combinedScore).toBeLessThanOrEqual(1.0);
    });
  });
});
