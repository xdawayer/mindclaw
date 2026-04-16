export type RoutingCandidate = {
  agentId: string;
  confidence: number;
  label: string;
};

const DEFAULT_THRESHOLD = 0.7;

export function shouldAskForConfirmation(
  confidence: number,
  threshold: number = DEFAULT_THRESHOLD,
): boolean {
  return confidence < threshold;
}

export function selectTopCandidates(
  candidates: RoutingCandidate[],
  n: number = 3,
): RoutingCandidate[] {
  return [...candidates].toSorted((a, b) => b.confidence - a.confidence).slice(0, n);
}
