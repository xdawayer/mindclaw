export type SessionOutcome = "success" | "partial" | "fail" | "unknown";

export type SessionOutcomeInput = {
  messageCount: number;
  stopReason?: string;
  aborted: boolean;
  errorOccurred: boolean;
  durationMs?: number;
};

export function classifySessionOutcome(input: SessionOutcomeInput): SessionOutcome {
  // Fail conditions take precedence
  if (input.errorOccurred || input.aborted) {
    return "fail";
  }

  if (input.stopReason === "max_tokens") {
    return "fail";
  }

  // Too few messages to classify
  if (input.messageCount < 2) {
    return "unknown";
  }

  // Partial: session hit length limit but didn't error
  if (input.stopReason === "length") {
    return "partial";
  }

  // Normal completion
  return "success";
}
