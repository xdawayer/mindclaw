export type SearchDocument = { id: string; content: string; metadata?: Record<string, string> };
export type SearchResult = {
  id: string;
  score: number;
  snippet: string;
  metadata?: Record<string, string>;
};
export type SearchIndex = {
  add(docs: SearchDocument[]): void;
  search(query: string, limit?: number): SearchResult[];
  size(): number;
};

type IndexedDoc = SearchDocument & { tokens: string[]; termFreq: Map<string, number> };

// CJK Unicode range check for character-level tokenization
const CJK_RE = /[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]/;

function tokenize(text: string): string[] {
  const lower = text.toLowerCase();
  const tokens: string[] = [];
  let buf = "";
  for (const ch of lower) {
    if (CJK_RE.test(ch)) {
      if (buf) {
        tokens.push(buf);
        buf = "";
      }
      tokens.push(ch);
    } else if (/\w/.test(ch)) {
      buf += ch;
    } else if (buf) {
      tokens.push(buf);
      buf = "";
    }
  }
  if (buf) {
    tokens.push(buf);
  }
  return tokens;
}

function buildSnippet(content: string, queryTokens: string[]): string {
  const maxLen = 200;
  if (content.length <= maxLen) {
    return content;
  }
  const lower = content.toLowerCase();
  let best = 0;
  for (const t of queryTokens) {
    const idx = lower.indexOf(t);
    if (idx !== -1) {
      best = idx;
      break;
    }
  }
  const start = Math.max(0, best - 40);
  const end = Math.min(content.length, start + maxLen);
  let snippet = content.slice(start, end);
  if (start > 0) {
    snippet = "..." + snippet;
  }
  if (end < content.length) {
    snippet = snippet + "...";
  }
  return snippet;
}

export function createSearchIndex(): SearchIndex {
  const docs: IndexedDoc[] = [];
  // Document frequency: how many docs contain each term
  const docFreq = new Map<string, number>();

  return {
    add(newDocs: SearchDocument[]): void {
      for (const doc of newDocs) {
        const tokens = tokenize(doc.content);
        const termFreq = new Map<string, number>();
        for (const t of tokens) {
          termFreq.set(t, (termFreq.get(t) ?? 0) + 1);
        }
        // Update document frequency
        for (const term of termFreq.keys()) {
          docFreq.set(term, (docFreq.get(term) ?? 0) + 1);
        }
        docs.push({ ...doc, tokens, termFreq });
      }
    },

    search(query: string, limit = 10): SearchResult[] {
      if (docs.length === 0) {
        return [];
      }
      const queryTokens = tokenize(query);
      if (queryTokens.length === 0) {
        return [];
      }
      const n = docs.length;

      const avgDl = docs.reduce((s, d) => s + d.tokens.length, 0) / n;
      const scored: SearchResult[] = [];
      for (const doc of docs) {
        let score = 0;
        const docLen = doc.tokens.length;
        for (const qt of queryTokens) {
          const tf = doc.termFreq.get(qt) ?? 0;
          if (tf === 0) {
            continue;
          }
          const df = docFreq.get(qt) ?? 0;
          // BM25: IDF * TF-saturation (k1=1.5, b=0.75)
          const idf = Math.log((n - df + 0.5) / (df + 0.5) + 1);
          const tfNorm = (tf * 2.5) / (tf + 1.5 * (0.25 + 0.75 * (docLen / avgDl)));
          score += idf * tfNorm;
        }
        if (score > 0) {
          scored.push({
            id: doc.id,
            score,
            snippet: buildSnippet(doc.content, queryTokens),
            metadata: doc.metadata,
          });
        }
      }

      scored.sort((a, b) => b.score - a.score);
      return scored.slice(0, limit);
    },

    size(): number {
      return docs.length;
    },
  };
}
