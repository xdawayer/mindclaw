import { describe, test, expect } from "vitest";
import {
  buildPreferencesCard,
  parsePreferenceAction,
  buildLanguageSection,
  buildStyleSection,
} from "./user-preference-card.js";
import type { PreferenceCardAction } from "./user-preference-card.js";
import type { UserPreferences } from "./user-preferences.js";

function makePrefs(overrides?: Partial<UserPreferences>): UserPreferences {
  return {
    language: "zh-CN",
    responseStyle: "auto",
    notificationsEnabled: true,
    preferredAgentId: undefined,
    customInstructions: undefined,
    ...overrides,
  };
}

describe("user-preference-card", () => {
  describe("buildPreferencesCard", () => {
    test("returns valid schema 2.0 structure", () => {
      const card = buildPreferencesCard(makePrefs());

      expect(card.schema).toBe("2.0");
      expect(card.config).toBeDefined();
      expect(card.config).toHaveProperty("width_mode", "fill");
      expect(card.header).toBeDefined();
      expect(card.body).toBeDefined();
      expect(Array.isArray(card.body.elements)).toBe(true);
      expect(card.body.elements.length).toBeGreaterThan(0);
    });

    test("includes header with title", () => {
      const card = buildPreferencesCard(makePrefs());

      expect(card.header.title).toBeDefined();
      expect(card.header.title.tag).toBe("plain_text");
      expect(card.header.title.content).toBeTruthy();
      expect(typeof card.header.template).toBe("string");
    });

    test("body contains markdown elements showing current values", () => {
      const prefs = makePrefs({ language: "en-US", responseStyle: "concise" });
      const card = buildPreferencesCard(prefs);

      const markdownElements = card.body.elements.filter(
        (el: Record<string, unknown>) => el.tag === "markdown",
      );
      expect(markdownElements.length).toBeGreaterThan(0);

      const markdownContent = markdownElements
        .map((el: Record<string, unknown>) => el.content as string)
        .join("\n");

      // Should display current language and style values somewhere in markdown
      expect(markdownContent).toMatch(/en-US|English/i);
      expect(markdownContent).toMatch(/concise/i);
    });

    test("body contains action buttons for each configurable preference", () => {
      const card = buildPreferencesCard(makePrefs());

      const actionElements = card.body.elements.filter(
        (el: Record<string, unknown>) => el.tag === "action",
      );
      expect(actionElements.length).toBeGreaterThanOrEqual(2); // at least language + style

      for (const actionEl of actionElements) {
        const actions = (actionEl as Record<string, unknown>).actions as Record<string, unknown>[];
        expect(Array.isArray(actions)).toBe(true);
        expect(actions.length).toBeGreaterThan(0);

        for (const btn of actions) {
          const button = btn;
          expect(button.tag).toBe("button");
          expect(button.text).toBeDefined();
        }
      }
    });

    test("buttons encode correct action envelope format", () => {
      const card = buildPreferencesCard(makePrefs());

      const actionElements = card.body.elements.filter(
        (el: Record<string, unknown>) => el.tag === "action",
      );

      let foundEnvelope = false;
      for (const actionEl of actionElements) {
        const actions = (actionEl as Record<string, unknown>).actions as Record<string, unknown>[];
        for (const btn of actions) {
          const button = btn;
          const value = button.value as PreferenceCardAction | undefined;
          if (value) {
            expect(value.k).toBe("meta");
            expect(value.a).toBe("preferences.update");
            expect(value.m).toBeDefined();
            expect(typeof value.m.field).toBe("string");
            expect(typeof value.m.value).toBe("string");
            foundEnvelope = true;
          }
        }
      }
      expect(foundEnvelope).toBe(true);
    });

    test("highlights the currently selected language option", () => {
      const card = buildPreferencesCard(makePrefs({ language: "en-US" }));

      const actionElements = card.body.elements.filter(
        (el: Record<string, unknown>) => el.tag === "action",
      );

      let foundHighlighted = false;
      let foundNonHighlighted = false;

      for (const actionEl of actionElements) {
        const actions = (actionEl as Record<string, unknown>).actions as Record<string, unknown>[];
        for (const btn of actions) {
          const button = btn;
          const value = button.value as PreferenceCardAction | undefined;
          if (value?.m?.field === "language") {
            if (value.m.value === "en-US") {
              // Currently selected should be visually distinct (e.g. type="primary")
              expect(button.type).toBe("primary");
              foundHighlighted = true;
            } else {
              // Non-selected language buttons should not be primary
              expect(button.type).not.toBe("primary");
              foundNonHighlighted = true;
            }
          }
        }
      }

      expect(foundHighlighted).toBe(true);
      expect(foundNonHighlighted).toBe(true);
    });

    test("with locale='en' uses English labels", () => {
      const card = buildPreferencesCard(makePrefs(), "en");

      const allText = JSON.stringify(card);
      // Should contain English text for header/labels
      expect(allText).toMatch(/language|Language/i);
      expect(allText).toMatch(/style|Style/i);
      // Should not contain Chinese labels
      expect(allText).not.toMatch(/语言/);
      expect(allText).not.toMatch(/风格/);
    });

    test("with locale='zh' uses Chinese labels", () => {
      const card = buildPreferencesCard(makePrefs(), "zh");

      const allText = JSON.stringify(card);
      // Should contain Chinese text
      expect(allText).toMatch(/语言/);
      expect(allText).toMatch(/风格/);
    });
  });

  describe("parsePreferenceAction", () => {
    test("extracts field and value from valid envelope", () => {
      const result = parsePreferenceAction({
        k: "meta",
        a: "preferences.update",
        m: { field: "language", value: "en-US" },
      });

      expect(result).not.toBeNull();
      expect(result!.field).toBe("language");
      expect(result!.value).toBe("en-US");
    });

    test("extracts responseStyle field", () => {
      const result = parsePreferenceAction({
        k: "meta",
        a: "preferences.update",
        m: { field: "responseStyle", value: "concise" },
      });

      expect(result).not.toBeNull();
      expect(result!.field).toBe("responseStyle");
      expect(result!.value).toBe("concise");
    });

    test("returns null for invalid envelope missing k", () => {
      const result = parsePreferenceAction({
        a: "preferences.update",
        m: { field: "language", value: "en-US" },
      });
      expect(result).toBeNull();
    });

    test("returns null for invalid envelope missing a", () => {
      const result = parsePreferenceAction({
        k: "meta",
        m: { field: "language", value: "en-US" },
      });
      expect(result).toBeNull();
    });

    test("returns null for invalid envelope with wrong k value", () => {
      const result = parsePreferenceAction({
        k: "other",
        a: "preferences.update",
        m: { field: "language", value: "en-US" },
      });
      expect(result).toBeNull();
    });

    test("returns null for non-preference actions", () => {
      const result = parsePreferenceAction({
        k: "meta",
        a: "some.other.action",
        m: { field: "language", value: "en-US" },
      });
      expect(result).toBeNull();
    });

    test("returns null for empty object", () => {
      const result = parsePreferenceAction({});
      expect(result).toBeNull();
    });

    test("returns null when m is missing", () => {
      const result = parsePreferenceAction({
        k: "meta",
        a: "preferences.update",
      });
      expect(result).toBeNull();
    });

    test("returns null for __proto__ field (prototype pollution guard)", () => {
      const result = parsePreferenceAction({
        k: "meta",
        a: "preferences.update",
        m: { field: "__proto__", value: "hacked" },
      });
      expect(result).toBeNull();
    });

    test("returns null for unknown field name", () => {
      const result = parsePreferenceAction({
        k: "meta",
        a: "preferences.update",
        m: { field: "randomUnknown", value: "anything" },
      });
      expect(result).toBeNull();
    });

    test("returns null for constructor field", () => {
      const result = parsePreferenceAction({
        k: "meta",
        a: "preferences.update",
        m: { field: "constructor", value: "Object" },
      });
      expect(result).toBeNull();
    });
  });

  describe("buildLanguageSection", () => {
    test("returns action elements with language buttons", () => {
      const elements = buildLanguageSection("zh-CN");

      expect(Array.isArray(elements)).toBe(true);
      expect(elements.length).toBeGreaterThan(0);

      // Should contain at least one action element
      const actionEl = elements.find((el: Record<string, unknown>) => el.tag === "action") as
        | Record<string, unknown>
        | undefined;
      expect(actionEl).toBeDefined();

      const actions = actionEl!.actions as Record<string, unknown>[];
      expect(Array.isArray(actions)).toBe(true);

      // Should have buttons for different languages
      const buttons = actions.filter((a: Record<string, unknown>) => a.tag === "button");
      expect(buttons.length).toBeGreaterThanOrEqual(2);

      // Each button value should target the language field
      for (const btn of buttons) {
        const button = btn;
        const value = button.value as PreferenceCardAction;
        expect(value.m.field).toBe("language");
      }
    });

    test("highlights the currently selected language", () => {
      const elements = buildLanguageSection("en-US");

      const actionEl = elements.find(
        (el: Record<string, unknown>) => el.tag === "action",
      ) as Record<string, unknown>;
      const actions = actionEl.actions as Record<string, unknown>[];

      const enButton = actions.find((a: Record<string, unknown>) => {
        const value = a.value as PreferenceCardAction | undefined;
        return value?.m?.value === "en-US";
      }) as Record<string, unknown>;

      expect(enButton).toBeDefined();
      expect(enButton.type).toBe("primary");
    });
  });

  describe("buildStyleSection", () => {
    test("returns action elements with style buttons for concise/detailed/auto", () => {
      const elements = buildStyleSection("auto");

      expect(Array.isArray(elements)).toBe(true);
      expect(elements.length).toBeGreaterThan(0);

      const actionEl = elements.find((el: Record<string, unknown>) => el.tag === "action") as
        | Record<string, unknown>
        | undefined;
      expect(actionEl).toBeDefined();

      const actions = actionEl!.actions as Record<string, unknown>[];
      const buttons = actions.filter((a: Record<string, unknown>) => a.tag === "button");

      // Should have buttons for concise, detailed, auto
      expect(buttons.length).toBeGreaterThanOrEqual(3);

      const styleValues = buttons.map((btn: Record<string, unknown>) => {
        const value = btn.value as PreferenceCardAction;
        return value.m.value;
      });

      expect(styleValues).toContain("concise");
      expect(styleValues).toContain("detailed");
      expect(styleValues).toContain("auto");

      // Each button value should target the responseStyle field
      for (const btn of buttons) {
        const button = btn;
        const value = button.value as PreferenceCardAction;
        expect(value.m.field).toBe("responseStyle");
      }
    });

    test("highlights the currently selected style", () => {
      const elements = buildStyleSection("concise");

      const actionEl = elements.find(
        (el: Record<string, unknown>) => el.tag === "action",
      ) as Record<string, unknown>;
      const actions = actionEl.actions as Record<string, unknown>[];

      const conciseButton = actions.find((a: Record<string, unknown>) => {
        const value = a.value as PreferenceCardAction | undefined;
        return value?.m?.value === "concise";
      }) as Record<string, unknown>;

      expect(conciseButton).toBeDefined();
      expect(conciseButton.type).toBe("primary");

      // Other style buttons should not be primary
      const autoButton = actions.find((a: Record<string, unknown>) => {
        const value = a.value as PreferenceCardAction | undefined;
        return value?.m?.value === "auto";
      }) as Record<string, unknown>;

      expect(autoButton).toBeDefined();
      expect(autoButton.type).not.toBe("primary");
    });
  });
});
