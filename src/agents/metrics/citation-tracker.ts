export type CitationMarker = {
  marker: string;
  path: string;
  line: number;
};

export type CitationUsage = {
  totalInjected: number;
  totalReferenced: number;
  hitRate: number;
  referencedPaths: string[];
};

export function buildCitationMarkers(
  results: ReadonlyArray<{ path: string; startLine: number; snippet: string }>,
): CitationMarker[] {
  return results.map((r) => ({
    marker: `[mem:${r.path}:${r.startLine}]`,
    path: r.path,
    line: r.startLine,
  }));
}

export function checkCitationUsage(
  markers: ReadonlyArray<CitationMarker>,
  responseText: string,
): CitationUsage {
  if (markers.length === 0) {
    return { totalInjected: 0, totalReferenced: 0, hitRate: 0, referencedPaths: [] };
  }

  const referencedPaths: string[] = [];

  for (const m of markers) {
    // Check for full marker reference or just path reference
    if (responseText.includes(m.marker) || responseText.includes(m.path)) {
      referencedPaths.push(m.path);
    }
  }

  // Deduplicate paths
  const uniquePaths = [...new Set(referencedPaths)];

  return {
    totalInjected: markers.length,
    totalReferenced: uniquePaths.length,
    hitRate: uniquePaths.length / markers.length,
    referencedPaths: uniquePaths,
  };
}
