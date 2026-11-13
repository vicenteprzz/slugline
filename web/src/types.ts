export type SceneRow = {
  number: string;
  heading: string;
  int_ext: string | null;
  location: string;
  time_of_day: string | null;
  eighths: number;
  characters: string[];
  day_night: string | null;
  silent: string[];
  words: Record<string, number>;
  start_page: number;
  story_day: number | null;
  story_label: string;
};

export type CharacterStats = {
  name: string;
  scenes: string[];
  dialogue_blocks: number;
  words: number;
  silent_scenes: string[];
};

export type LocationStats = { location: string; scenes: string[]; eighths: number };

export type Breakdown = {
  title: string | null;
  scene_count: number;
  page_count: number;
  int_ext: Record<string, number>;
  time_of_day: Record<string, number>;
  day_night: Record<string, number>;
  scenes: SceneRow[];
  characters: CharacterStats[];
  locations: LocationStats[];
};

export type Issue = {
  severity: "warning" | "info";
  code: string;
  message: string;
  scene: string | null;
  source: "rule" | "ai";
  names?: string[] | null; // two spellings of one name, most used first
  template?: string | null; // the message before its values were filled in, for translation
  params?: Record<string, string | number> | null;
};

export type Corrections = {
  characters: Record<string, string>;
  locations: Record<string, string>;
  day_night: Record<string, string>;
  story_days: Record<string, number>;
};

export type Continuity = {
  days: number;
  costume_plot: { character: string; changes: { day: number; number: number; scenes: string[] }[] }[];
  warnings: { element: string; category: string; day: number; has: string; missing: string; characters: string[] }[];
};

export type SceneNote = { number: string; summary: string; tone: string; valence: number; tension: number };

export type Analysis = {
  model: string;
  logline: string;
  synopsis: string;
  themes: string[];
  scenes: SceneNote[];
  issues: Issue[];
};

export type Element = { category: string; name: string; notes: string; source: "ai" | "auto" | "manual" };

export type ElementTotal = { category: string; name: string; scenes: string[]; eighths: number };

export type Revision = {
  from: { title: string | null; saved_at: string | null };
  scenes: Record<string, { old: string; status: "unchanged" | "changed" | "reviewed" }>;
  new: string[];
  omitted: { number: string; heading: string; elements?: number }[];
};

export type Elements = {
  model: string | null;
  scenes: Record<string, Element[]>;
  totals: ElementTotal[];
  revision: Revision | null;
};

export type Category = { key: string; label: string; color: string };

export type ShootDay = {
  id: string;
  scenes: string[];
  date: string;
  notes: string;
  call_time: string;
  address: string;
  hospital: string;
  cast_calls: Record<string, string>;
};

export type CrewMember = { role: string; name: string; phone: string };

export type CastDays = { character: string; actor: string; codes: string[]; work: number; hold: number };

export type Schedule = {
  pages_per_day: number;
  days: (ShootDay & { stats: { eighths: number; locations: string[]; cast: string[]; light: string[]; over: boolean } })[];
  unscheduled: string[];
  revision: Revision | null;
  actors: Record<string, string>;
  crew: CrewMember[];
  day_out_of_days: CastDays[];
  constraints: ScheduleConstraints;
  cities: { key: string; name: string }[];
  problems: Problem[];
  daylight: ({ sunrise: string; sunset: string; hours: number } | null)[];
};

export type Period = [string, string];

export type ScheduleConstraints = {
  start: string;
  weekdays: number[];
  city: string;
  day_hours: number;
  rest_hours: number;
  cast_off: Record<string, Period[]>;
  location_off: Record<string, Period[]>;
};

export type Problem = {
  kind: "cast" | "location" | "dawn" | "rest";
  day: number;
  date: string;
  name: string;
  detail: { call?: string; sunrise?: string; scenes?: string[]; rest?: number; minimum?: number; assumed?: boolean };
};

export type Script = {
  id: string;
  filename: string;
  breakdown: Breakdown;
  issues: Issue[];
  analysis: Analysis | null;
  elements: Elements | null;
  schedule: Schedule | null;
  corrections: Corrections;
  continuity: Continuity;
};

export type LibraryEntry = { id: string; filename: string; title: string | null; scenes: number; added_at: string; opened_at: string };

export type Settings = {
  has_api_key: boolean;
  api_key_hint: string | null;
  api_key_source: "environment" | "app" | null;
  model: string;
  models: string[];
  language: string | null;
};

export type LicenseStatus = {
  licensed: boolean;
  license: { name: string; kind: string; issued: string; expires: string | null } | null;
  free_scripts: number;
  scripts: number;
  purchase_url: string | null;
};

export type Status = {
  version: string;
  license: LicenseStatus;
  llm: { available: boolean; model: string; reason: string };
  pdf_export: boolean;
  categories: Category[];
};

export type ChatEvent =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; input: Record<string, unknown> }
  | { type: "error"; message: string }
  | { type: "done" };

export type BudgetLine = {
  key: string;
  chapter: string;
  concept: string;
  units: number;
  unit: string;
  rate: number;
  total: number;
  to_quote: boolean;
  quoted: boolean;
  edited: boolean;
  detail: string;
  scenes: string[];
};

export type BudgetExtra = { chapter: string; concept: string; units: number; rate: number };

export type BudgetSettings = {
  level: string;
  country: string;
  rates: Record<string, number>;
  units: Record<string, number>;
  quotes: Record<string, number>;
  extra: BudgetExtra[];
  percentages: Record<string, number>;
};

export type Budget = {
  currency: string;
  level: string;
  levels: { key: string; label: string }[];
  country: string;
  countries: { key: string; label: string; social: number }[];
  subtotal: number;
  contingency: { pct: number; amount: number };
  total: number;
  percentages: Record<string, number>;
  days: number;
  scheduled_days: number;
  estimated_days: number;
  chapters: { code: string; label: string; total: number; lines: BudgetLine[] }[];
  to_quote: { count: number; amount: number };
  scenes: { number: string; heading: string; eighths: number; cost: number }[];
  per_day: number | null;
  previous: { total: number; days: number; saved_at?: string } | null;
  settings: BudgetSettings;
};

export type Reorder = {
  saving: number;
  holds_before: number;
  holds_after: number;
  conflicts_before: number;
  conflicts_after: number;
  changed: boolean;
  schedule: Schedule | null;
};
