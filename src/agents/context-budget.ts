export type LayerBudget = {
  org: number;
  team: number;
  role: number;
  user: number;
};

export const DEFAULT_BUDGET: LayerBudget = {
  org: 500,
  team: 500,
  role: 200,
  user: 300,
};

const MAX_TOTAL = 1500;
const CJK_RE = /[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]/;
const CHARS_PER_TOKEN_EN = 4;
const CHARS_PER_TOKEN_CJK = 1.5;

export function estimateTokens(text: string): number {
  if (!text) {
    return 0;
  }
  let cjkChars = 0;
  let otherChars = 0;
  for (const char of text) {
    if (CJK_RE.test(char)) {
      cjkChars++;
    } else {
      otherChars++;
    }
  }
  return Math.ceil(cjkChars / CHARS_PER_TOKEN_CJK + otherChars / CHARS_PER_TOKEN_EN);
}

export function allocateBudget(overrides?: Partial<LayerBudget>): LayerBudget {
  const budget = { ...DEFAULT_BUDGET, ...overrides };
  const total = budget.org + budget.team + budget.role + budget.user;

  if (total > MAX_TOTAL) {
    // Scale down proportionally
    const scale = MAX_TOTAL / total;
    budget.org = Math.floor(budget.org * scale);
    budget.team = Math.floor(budget.team * scale);
    budget.role = Math.floor(budget.role * scale);
    budget.user = Math.floor(budget.user * scale);
  }

  return budget;
}

export function truncateToFit(content: string, budgetTokens: number): string {
  if (budgetTokens <= 0) {
    return "";
  }
  if (estimateTokens(content) <= budgetTokens) {
    return content;
  }

  // Binary search for the right truncation point
  let low = 0;
  let high = content.length;
  while (low < high) {
    const mid = Math.floor((low + high + 1) / 2);
    if (estimateTokens(content.slice(0, mid)) <= budgetTokens) {
      low = mid;
    } else {
      high = mid - 1;
    }
  }
  return content.slice(0, low);
}
