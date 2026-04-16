import { describe, expect, test } from "vitest";
import { evaluateSearchQuality, normalizeScores } from "./search-quality.js";
import type { SearchResult } from "./text-search.js";

function makeResult(id: string, score: number, snippet = ""): SearchResult {
  return { id, score, snippet };
}

describe("normalizeScores", () => {
  test("maps scores to 0-1 range with max score becoming 1.0", () => {
    const results = [makeResult("a", 10), makeResult("b", 5), makeResult("c", 2)];
    const normalized = normalizeScores(results);

    expect(normalized[0].score).toBeCloseTo(1.0);
    expect(normalized[1].score).toBeCloseTo(0.5);
    expect(normalized[2].score).toBeCloseTo(0.2);
  });

  test("handles empty results", () => {
    const normalized = normalizeScores([]);
    expect(normalized).toEqual([]);
  });

  test("handles single result (score becomes 1.0)", () => {
    const results = [makeResult("a", 7)];
    const normalized = normalizeScores(results);

    expect(normalized).toHaveLength(1);
    expect(normalized[0].score).toBeCloseTo(1.0);
  });

  test("clamps negative scores to 0 before normalizing", () => {
    const results = [makeResult("a", 10), makeResult("b", -5), makeResult("c", -2)];
    const normalized = normalizeScores(results);

    expect(normalized[0].score).toBeCloseTo(1.0);
    expect(normalized[1].score).toBe(0);
    expect(normalized[2].score).toBe(0);
  });

  test("handles all-negative scores (all become 0)", () => {
    const results = [makeResult("a", -3), makeResult("b", -1)];
    const normalized = normalizeScores(results);

    expect(normalized[0].score).toBe(0);
    expect(normalized[1].score).toBe(0);
  });

  test("handles all-zero scores without dividing by zero", () => {
    const results = [makeResult("a", 0), makeResult("b", 0)];
    const normalized = normalizeScores(results);

    expect(normalized).toHaveLength(2);
    expect(normalized[0].score).toBe(0);
    expect(normalized[1].score).toBe(0);
  });
});

describe("evaluateSearchQuality", () => {
  test('returns "excellent" for high-quality results where all scores are above threshold', () => {
    const results = [
      makeResult("a", 0.9),
      makeResult("b", 0.85),
      makeResult("c", 0.8),
      makeResult("d", 0.75),
      makeResult("e", 0.7),
    ];
    const metrics = evaluateSearchQuality(results);

    expect(metrics.grade).toBe("excellent");
    expect(metrics.meetsQualityBar).toBe(true);
  });

  test('returns "poor" for low-quality results where all scores are near 0', () => {
    const results = [
      makeResult("a", 0.01),
      makeResult("b", 0.02),
      makeResult("c", 0.03),
      makeResult("d", 0.01),
      makeResult("e", 0.02),
    ];
    const metrics = evaluateSearchQuality(results);

    expect(metrics.grade).toBe("poor");
    expect(metrics.meetsQualityBar).toBe(false);
  });

  test('returns "fair" for mixed results', () => {
    const results = [
      makeResult("a", 0.8),
      makeResult("b", 0.6),
      makeResult("c", 0.1),
      makeResult("d", 0.05),
      makeResult("e", 0.02),
    ];
    const metrics = evaluateSearchQuality(results);

    expect(metrics.grade).toBe("fair");
  });

  test("calculates correct precisionAtK", () => {
    // With default relevanceThreshold=0.5 and topK=5, 3 out of 5 are relevant
    const results = [
      makeResult("a", 0.9),
      makeResult("b", 0.7),
      makeResult("c", 0.6),
      makeResult("d", 0.3),
      makeResult("e", 0.1),
    ];
    const metrics = evaluateSearchQuality(results);

    expect(metrics.precisionAtK).toBeCloseTo(3 / 5);
  });

  test("calculates correct signalToNoise ratio", () => {
    // With default relevanceThreshold=0.5, 2 out of 4 results are relevant
    const results = [
      makeResult("a", 0.9),
      makeResult("b", 0.7),
      makeResult("c", 0.3),
      makeResult("d", 0.1),
    ];
    const metrics = evaluateSearchQuality(results);

    expect(metrics.signalToNoise).toBeCloseTo(2 / 4);
  });

  test("respects custom config thresholds", () => {
    const results = [makeResult("a", 0.4), makeResult("b", 0.35), makeResult("c", 0.3)];

    // With default threshold (0.5), none are relevant
    const defaultMetrics = evaluateSearchQuality(results);
    expect(defaultMetrics.precisionAtK).toBe(0);

    // With lowered threshold (0.3), all are relevant
    const customMetrics = evaluateSearchQuality(results, {
      relevanceThreshold: 0.3,
      topK: 3,
      qualityBarThreshold: 0.2,
    });
    expect(customMetrics.precisionAtK).toBeCloseTo(3 / 3);
    expect(customMetrics.meetsQualityBar).toBe(true);
  });

  test("handles empty results with grade poor and meetsQualityBar false", () => {
    const metrics = evaluateSearchQuality([]);

    expect(metrics.grade).toBe("poor");
    expect(metrics.meetsQualityBar).toBe(false);
    expect(metrics.avgRelevance).toBe(0);
    expect(metrics.precisionAtK).toBe(0);
    expect(metrics.signalToNoise).toBe(0);
  });

  test("meetsQualityBar is true only when avgRelevance >= qualityBarThreshold", () => {
    // avgRelevance will be 0.6 (mean of 0.8 and 0.4), above default 0.3
    const aboveBar = [makeResult("a", 0.8), makeResult("b", 0.4)];
    expect(evaluateSearchQuality(aboveBar).meetsQualityBar).toBe(true);

    // avgRelevance will be 0.15 (mean of 0.2 and 0.1), below default 0.3
    const belowBar = [makeResult("a", 0.2), makeResult("b", 0.1)];
    expect(evaluateSearchQuality(belowBar).meetsQualityBar).toBe(false);

    // Exactly at the threshold with custom config
    const atThreshold = [makeResult("a", 0.5)];
    expect(evaluateSearchQuality(atThreshold, { qualityBarThreshold: 0.5 }).meetsQualityBar).toBe(
      true,
    );
  });
});
