export type MemorySafetyViolationType =
  | "prompt-injection"
  | "data-exfiltration"
  | "invisible-unicode"
  | "size-exceeded";

export type MemorySafetyViolation = {
  type: MemorySafetyViolationType;
  detail: string;
};

export type MemorySafetyResult = {
  safe: boolean;
  violations: MemorySafetyViolation[];
};

const MAX_CONTENT_LENGTH = 10_000;

const INJECTION_PATTERNS: Array<{ pattern: RegExp; detail: string }> = [
  { pattern: /ignore\s+(all\s+)?(previous|prior)\s+instructions/i, detail: "ignore instructions" },
  { pattern: /^system:\s/im, detail: "system: prefix" },
  { pattern: /^admin:\s/im, detail: "ADMIN: prefix" },
  { pattern: /you\s+are\s+now\s+/i, detail: "role hijacking" },
];

const EXFILTRATION_PATTERNS: Array<{ pattern: RegExp; detail: string }> = [
  { pattern: /\bcurl\s+https?:\/\//i, detail: "curl command" },
  { pattern: /\bwget\s+https?:\/\//i, detail: "wget command" },
  { pattern: /fetch\s*\(\s*["']https?:\/\//i, detail: "fetch() call" },
];

// Zero-width and bidirectional override characters (individual codepoints, not joined sequences)
const INVISIBLE_UNICODE =
  /\u200B|\u200C|\u200D|\u200E|\u200F|[\u202A-\u202E]|\u2060|[\u2061-\u2064]|\uFEFF/;

export function scanMemoryContent(content: string): MemorySafetyResult {
  const violations: MemorySafetyViolation[] = [];

  if (content.length > MAX_CONTENT_LENGTH) {
    violations.push({
      type: "size-exceeded",
      detail: `Content is ${content.length} chars, max ${MAX_CONTENT_LENGTH}`,
    });
  }

  for (const { pattern, detail } of INJECTION_PATTERNS) {
    if (pattern.test(content)) {
      violations.push({ type: "prompt-injection", detail });
    }
  }

  for (const { pattern, detail } of EXFILTRATION_PATTERNS) {
    if (pattern.test(content)) {
      violations.push({ type: "data-exfiltration", detail });
    }
  }

  if (INVISIBLE_UNICODE.test(content)) {
    violations.push({
      type: "invisible-unicode",
      detail: "Content contains invisible Unicode characters",
    });
  }

  return { safe: violations.length === 0, violations };
}
