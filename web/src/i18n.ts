import { ES, ES_WORDS } from "./es";

export type Language = "en" | "es";

let current: Language = "en";

export function setLanguage(language: Language) {
  current = language;
  document.documentElement.lang = language;
}

export const language = () => current;

/**
 * The text in the current language. Strings are written in English in the
 * code and looked up in the Spanish dictionary; anything missing stays in
 * English rather than breaking. `{name}` placeholders are filled from `vars`.
 */
export function t(text: string, vars?: Record<string, string | number>): string {
  const translated = current === "es" ? (ES[text] ?? text) : text;
  return vars ? translated.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? "")) : translated;
}

/** "3 scenes" / "3 secuencias", "1 scene" / "1 secuencia". */
export function plural(n: number, word: string): string {
  const count = n.toLocaleString(current === "es" ? "es-ES" : "en-US");
  if (current === "es" && ES_WORDS[word]) return `${count} ${n === 1 ? ES_WORDS[word][0] : ES_WORDS[word][1]}`;
  return `${count} ${word}${n === 1 ? "" : "s"}`;
}

/** Day, night, dawn and dusk as they read in the interface. */
export function light(value: string | null | undefined): string {
  const names: Record<string, string> = { DAY: "Day", NIGHT: "Night", DAWN: "Dawn", DUSK: "Dusk" };
  return value ? t(names[value] ?? value) : "–";
}

export function initialLanguage(saved: string | null | undefined): Language {
  if (saved === "en" || saved === "es") return saved;
  return navigator.language.toLowerCase().startsWith("es") ? "es" : "en";
}
