export type ConfigTier = "org" | "team" | "role" | "user";

export type ConfigLayer = {
  tier: ConfigTier;
  security: Record<string, unknown>;
  features: Record<string, unknown>;
};

export type MergedConfig = {
  security: Record<string, unknown>;
  features: Record<string, unknown>;
};

const TIER_ORDER: ConfigTier[] = ["org", "team", "role", "user"];

export function mergeConfigLayers(layers: ConfigLayer[]): MergedConfig {
  if (layers.length === 0) {
    return { security: {}, features: {} };
  }

  // Sort by tier priority (org first, user last)
  const sorted = [...layers].toSorted(
    (a, b) => TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier),
  );

  // Security: only org-defined keys are accepted. Lower tiers cannot add new security keys.
  const orgLayer = sorted.find((l) => l.tier === "org");
  const security: Record<string, unknown> = orgLayer ? { ...orgLayer.security } : {};

  // Features: most specific tier wins (later in order = higher priority)
  const features: Record<string, unknown> = {};
  for (const layer of sorted) {
    for (const [key, value] of Object.entries(layer.features)) {
      features[key] = value;
    }
  }

  return { security, features };
}
