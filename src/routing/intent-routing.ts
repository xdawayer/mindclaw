/** LLM-based intent routing for when deterministic bindings don't match. */

export type AgentInfo = { id: string; description: string };

export type IntentRoutingResult = {
  status: "matched" | "ask_user" | "timeout" | "invalid_agent" | "error" | "skipped";
  agentId: string;
  confidence?: number;
};

export type IntentRoutingDeps = {
  callLLM: (
    message: string,
    agents: AgentInfo[],
  ) => Promise<{ agentId: string; confidence: number }>;
  availableAgents: AgentInfo[];
  defaultAgentId: string;
  confidenceThreshold: number;
  timeoutMs: number;
};

export async function resolveIntentRoute(
  message: string,
  deps: IntentRoutingDeps,
): Promise<IntentRoutingResult> {
  if (!message) {
    return { status: "skipped", agentId: deps.defaultAgentId };
  }

  let llmResult: { agentId: string; confidence: number };
  try {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeoutPromise = new Promise<never>((_resolve, reject) => {
      timer = setTimeout(() => reject(new Error("timeout")), deps.timeoutMs);
    });
    try {
      llmResult = await Promise.race([deps.callLLM(message, deps.availableAgents), timeoutPromise]);
    } finally {
      clearTimeout(timer);
    }
  } catch (err) {
    const isTimeout = err instanceof Error && err.message === "timeout";
    return { status: isTimeout ? "timeout" : "error", agentId: deps.defaultAgentId };
  }

  const agentExists = deps.availableAgents.some((a) => a.id === llmResult.agentId);
  if (!agentExists) {
    return { status: "invalid_agent", agentId: deps.defaultAgentId };
  }

  if (llmResult.confidence < deps.confidenceThreshold) {
    return { status: "ask_user", agentId: deps.defaultAgentId, confidence: llmResult.confidence };
  }

  return { status: "matched", agentId: llmResult.agentId, confidence: llmResult.confidence };
}
