import {
  parseCommandPrefix,
  resolveAgentByPrefix,
  type PrefixMapping,
} from "./command-prefix-routing.js";
import { shouldAskForConfirmation } from "./confidence-gate.js";

export type LLMIntentResult = {
  agentId: string;
  confidence: number;
};

export type MultiTenantRouteInput = {
  message: string;
  resolvedAgentId: string;
  channelId: string;
  chatType: "p2p" | "group";
  peerId: string;
  prefixMappings: PrefixMapping[];
  callLLM?: (message: string) => Promise<LLMIntentResult>;
  confidenceThreshold?: number;
};

export type AsyncIntentResult = {
  agentId: string;
  confidence: number;
  needsConfirmation: boolean;
};

export type MultiTenantRouteResult = {
  agentId: string;
  matchedBy: "command-prefix" | "binding" | "intent";
  asyncIntent: Promise<AsyncIntentResult | null>;
};

export function resolveMultiTenantRoute(input: MultiTenantRouteInput): MultiTenantRouteResult {
  // Stage 1: Command prefix routing (zero LLM cost)
  const parsed = parseCommandPrefix(input.message);
  if (parsed) {
    const prefixAgent = resolveAgentByPrefix(parsed.prefix, input.prefixMappings);
    if (prefixAgent) {
      return {
        agentId: prefixAgent,
        matchedBy: "command-prefix",
        asyncIntent: Promise.resolve(null),
      };
    }
  }

  // Stage 2: Async LLM intent (if provided, runs in background)
  const asyncIntent = input.callLLM
    ? input
        .callLLM(input.message)
        .then((result) => {
          const threshold = input.confidenceThreshold ?? 0.7;
          return {
            agentId: result.agentId,
            confidence: result.confidence,
            needsConfirmation: shouldAskForConfirmation(result.confidence, threshold),
          };
        })
        .catch(() => null)
    : Promise.resolve(null);

  // Sync return: use binding-resolved agent (LLM result available via asyncIntent)
  return {
    agentId: input.resolvedAgentId,
    matchedBy: "binding",
    asyncIntent,
  };
}
