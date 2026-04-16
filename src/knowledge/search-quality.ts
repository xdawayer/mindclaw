import type { SearchResult } from "./text-search.js";

export type QualityMetrics = {
  avgRelevance: number;
  precisionAtK: number;
  signalToNoise: number;
  meetsQualityBar: boolean;
  grade: "excellent" | "good" | "fair" | "poor";
};

export type QualityConfig = {
  relevanceThreshold?: number;
  topK?: number;
  qualityBarThreshold?: number;
};

export function normalizeScores(results: SearchResult[]): SearchResult[] {
  if (results.length === 0) {
    return [];
  }
  // Clamp negative scores to 0 before normalizing
  const clamped = results.map((r) => ({ ...r, score: Math.max(0, r.score) }));
  const maxScore = Math.max(...clamped.map((r) => r.score));
  if (maxScore === 0) {
    return clamped;
  }
  return clamped.map((r) => ({ ...r, score: r.score / maxScore }));
}

function resolveGrade(avgRelevance: number, precisionAtK: number): QualityMetrics["grade"] {
  if (avgRelevance >= 0.7 && precisionAtK >= 0.6) {
    return "excellent";
  }
  if (avgRelevance >= 0.4 && precisionAtK >= 0.3) {
    return "good";
  }
  if (avgRelevance >= 0.2 || precisionAtK > 0) {
    return "fair";
  }
  return "poor";
}

export function evaluateSearchQuality(
  results: SearchResult[],
  config?: QualityConfig,
): QualityMetrics {
  const threshold = config?.relevanceThreshold ?? 0.5;
  const topK = config?.topK ?? 5;
  const qualityBar = config?.qualityBarThreshold ?? 0.3;

  if (results.length === 0) {
    return {
      avgRelevance: 0,
      precisionAtK: 0,
      signalToNoise: 0,
      meetsQualityBar: false,
      grade: "poor",
    };
  }

  const avgRelevance = results.reduce((sum, r) => sum + r.score, 0) / results.length;

  const topResults = results.slice(0, topK);
  const relevantInTopK = topResults.filter((r) => r.score >= threshold).length;
  const precisionAtK = relevantInTopK / topResults.length;

  const relevantTotal = results.filter((r) => r.score >= threshold).length;
  const signalToNoise = relevantTotal / results.length;

  return {
    avgRelevance,
    precisionAtK,
    signalToNoise,
    meetsQualityBar: avgRelevance >= qualityBar,
    grade: resolveGrade(avgRelevance, precisionAtK),
  };
}
