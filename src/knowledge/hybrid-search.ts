export type ScoreSource = "bm25" | "vector";

export type HybridSearchResult = {
  id: string;
  combinedScore: number;
  bm25Score: number;
  vectorScore: number;
  sources: ScoreSource[];
};

type ScoreInput = {
  id: string;
  bm25: number;
  vector: number;
};

type HybridWeights = {
  bm25Weight: number;
  vectorWeight: number;
};

const DEFAULT_WEIGHTS: HybridWeights = {
  bm25Weight: 0.3,
  vectorWeight: 0.7,
};

export function combineSearchScores(
  scores: ScoreInput[],
  weights?: Partial<HybridWeights>,
): HybridSearchResult[] {
  if (scores.length === 0) {
    return [];
  }

  const w = { ...DEFAULT_WEIGHTS, ...weights };

  return scores
    .map((s) => {
      const raw = w.bm25Weight * s.bm25 + w.vectorWeight * s.vector;
      const combinedScore = Math.min(1, Math.max(0, raw));

      const sources: ScoreSource[] = [];
      if (s.bm25 > 0) {
        sources.push("bm25");
      }
      if (s.vector > 0) {
        sources.push("vector");
      }

      return {
        id: s.id,
        combinedScore,
        bm25Score: s.bm25,
        vectorScore: s.vector,
        sources,
      };
    })
    .toSorted((a, b) => b.combinedScore - a.combinedScore);
}
