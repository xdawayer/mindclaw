import type { UserPreferences } from "./user-preferences.js";

export type FeishuCardElement = Record<string, unknown>;

export type FeishuCard = {
  schema: string;
  config: Record<string, unknown>;
  header: { title: { tag: string; content: string }; template: string };
  body: { elements: FeishuCardElement[] };
};

export type PreferenceCardAction = {
  k: "meta";
  a: string;
  m: { field: string; value: string };
};

const ACTION_NAME = "preferences.update";

type Labels = {
  title: string;
  languageLabel: string;
  styleLabel: string;
  currentLabel: string;
  languages: Record<string, string>;
  styles: Record<string, string>;
};

const LABELS_ZH: Labels = {
  title: "个人偏好设置",
  languageLabel: "语言",
  styleLabel: "回复风格",
  currentLabel: "当前",
  languages: { "zh-CN": "中文", "en-US": "English", "ja-JP": "日本語" },
  styles: { concise: "简洁", detailed: "详细", auto: "自动" },
};

const LABELS_EN: Labels = {
  title: "Preferences",
  languageLabel: "Language",
  styleLabel: "Response Style",
  currentLabel: "Current",
  languages: { "zh-CN": "中文", "en-US": "English", "ja-JP": "日本語" },
  styles: { concise: "Concise", detailed: "Detailed", auto: "Auto" },
};

function getLabels(locale?: string): Labels {
  return locale?.startsWith("en") ? LABELS_EN : LABELS_ZH;
}

function makeButton(
  label: string,
  field: string,
  value: string,
  isSelected: boolean,
): Record<string, unknown> {
  return {
    tag: "button",
    text: { tag: "plain_text", content: label },
    type: isSelected ? "primary" : "default",
    value: { k: "meta", a: ACTION_NAME, m: { field, value } } satisfies PreferenceCardAction,
  };
}

export function buildLanguageSection(current: string, locale?: string): FeishuCardElement[] {
  const labels = getLabels(locale);
  const buttons = Object.entries(labels.languages).map(([code, name]) =>
    makeButton(name, "language", code, code === current),
  );
  return [
    {
      tag: "markdown",
      content: `**${labels.languageLabel}** (${labels.currentLabel}: ${labels.languages[current] ?? current})`,
    },
    { tag: "action", actions: buttons },
  ];
}

export function buildStyleSection(current: string, locale?: string): FeishuCardElement[] {
  const labels = getLabels(locale);
  const buttons = Object.entries(labels.styles).map(([value, name]) =>
    makeButton(name, "responseStyle", value, value === current),
  );
  const displayName = labels.styles[current] ?? current;
  const raw = displayName !== current ? `${displayName} / ${current}` : current;
  return [
    { tag: "markdown", content: `**${labels.styleLabel}** (${labels.currentLabel}: ${raw})` },
    { tag: "action", actions: buttons },
  ];
}

export function buildPreferencesCard(prefs: UserPreferences, locale?: string): FeishuCard {
  const labels = getLabels(locale);
  return {
    schema: "2.0",
    config: { width_mode: "fill" },
    header: {
      title: { tag: "plain_text", content: labels.title },
      template: "blue",
    },
    body: {
      elements: [
        ...buildLanguageSection(prefs.language, locale),
        { tag: "hr" },
        ...buildStyleSection(prefs.responseStyle, locale),
      ],
    },
  };
}

const ALLOWED_PREFERENCE_FIELDS = new Set<string>([
  "language",
  "responseStyle",
  "preferredAgentId",
  "notificationsEnabled",
  "customInstructions",
]);

export function parsePreferenceAction(
  value: Record<string, unknown>,
): { field: keyof UserPreferences; value: string } | null {
  if (value.k !== "meta" || value.a !== ACTION_NAME) {
    return null;
  }
  const m = value.m as { field?: string; value?: string } | undefined;
  if (!m || typeof m.field !== "string" || typeof m.value !== "string") {
    return null;
  }
  if (!ALLOWED_PREFERENCE_FIELDS.has(m.field)) {
    return null;
  }
  return { field: m.field as keyof UserPreferences, value: m.value };
}
