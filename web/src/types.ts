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

export type Script = {
  id: string;
  filename: string;
  breakdown: Breakdown;
  issues: Issue[];
  analysis: Analysis | null;
};

export type Status = {
  version: string;
  llm: { available: boolean; model: string; reason: string };
  pdf_export: boolean;
};

export type ChatEvent =
  | { type: "text"; text: string }
  | { type: "tool"; name: string; input: Record<string, unknown> }
  | { type: "error"; message: string }
  | { type: "done" };
