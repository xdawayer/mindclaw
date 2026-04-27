import type { MemoryPromptSectionBuilder } from "openclaw/plugin-sdk/memory-core-host-runtime-core";

export const buildPromptSection: MemoryPromptSectionBuilder = ({
  availableTools,
  citationsMode,
}) => {
  const hasMemorySearch = availableTools.has("memory_search");
  const hasMemoryGet = availableTools.has("memory_get");
  const hasMemoryPublish = availableTools.has("memory_publish");

  if (!hasMemorySearch && !hasMemoryGet && !hasMemoryPublish) {
    return [];
  }

  const guidance: string[] = [];
  if (hasMemorySearch && hasMemoryGet) {
    guidance.push(
      "Before answering anything about prior work, decisions, dates, people, preferences, or todos: run memory_search on MEMORY.md + memory/*.md + indexed session transcripts; then use memory_get to pull only the needed lines. If low confidence after search, say you checked.",
    );
  } else if (hasMemorySearch) {
    guidance.push(
      "Before answering anything about prior work, decisions, dates, people, preferences, or todos: run memory_search on MEMORY.md + memory/*.md + indexed session transcripts and answer from the matching results. If low confidence after search, say you checked.",
    );
  } else if (hasMemoryGet) {
    guidance.push(
      "Before answering anything about prior work, decisions, dates, people, preferences, or todos that already point to a specific memory file or note: run memory_get to pull only the needed lines. If low confidence after reading them, say you checked.",
    );
  }

  if (hasMemoryPublish) {
    guidance.push(
      "When a vetted conclusion should become shared collaboration memory, use memory_publish to append it into the current role_shared or space_shared scope. Do not use memory_publish for private scratch notes or speculative content.",
    );
  }

  const lines = ["## Memory Recall", ...guidance];
  if (citationsMode === "off") {
    lines.push(
      "Citations are disabled: do not mention file paths or line numbers in replies unless the user explicitly asks.",
    );
  } else {
    lines.push(
      "Citations: include Source: <path#line> when it helps the user verify memory snippets.",
    );
  }
  lines.push("");
  return lines;
};
