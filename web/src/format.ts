/** A length in eighths of a page, written as on a production board: 1 3/8, 4/8, 2. */
export function eighths(value: number): string {
  const pages = Math.floor(value / 8);
  const rest = value % 8;
  if (pages && rest) return `${pages} ${rest}/8`;
  if (pages) return String(pages);
  return `${rest}/8`;
}

import { language } from "./i18n";

export { plural } from "./i18n";

export const count = (n: number) => n.toLocaleString(language() === "es" ? "es-ES" : "en-US");

export const percent = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 100)}%` : "0%");

/** "MR. B" -> "Mr. B": names are stored in caps, which shout in running text. */
export function titleCase(name: string): string {
  return name
    .toLowerCase()
    .replace(/(^|[\s.'#-])([a-z])/g, (_, sep: string, c: string) => sep + c.toUpperCase())
    .replace(/'S\b/g, "'s"); // possessives: Billy's, not Billy'S
}

// Traditional stripboard colours: the strip tells the crew at a glance whether
// a scene is inside or outside, day or night.
const STRIPS: Record<string, string> = {
  "INT DAY": "#ffffff",
  "EXT DAY": "#fff3b0",
  "INT NIGHT": "#cfe2f7",
  "EXT NIGHT": "#cfe8cf",
  "INT DAWN": "#fbd9e3",
  "EXT DAWN": "#fbd9e3",
  "INT DUSK": "#fde0c8",
  "EXT DUSK": "#fde0c8",
};

export function stripColor(intExt: string | null, dayNight: string | null): string {
  const side = intExt && intExt !== "INT" ? "EXT" : "INT";
  return STRIPS[`${side} ${dayNight ?? ""}`] ?? "#eeeeee";
}

/** Round axis values: 0, 50, 100... */
export function niceTicks(max: number, target = 4): number[] {
  if (max <= 0) return [0, 1];
  const rough = max / target;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= rough) ?? 10 * power;
  const ticks = [];
  for (let v = 0; v < max + step - 1e-9; v += step) ticks.push(Math.round(v * 1000) / 1000);
  return ticks;
}
