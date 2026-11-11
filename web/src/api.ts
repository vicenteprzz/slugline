import { language } from "./i18n";
import type { Analysis, ChatEvent, Elements, LibraryEntry, Schedule, Script, Settings, ShootDay, Status } from "./types";

/** Every request carries the app's header; the server refuses changes without it. */
const call = (url: string, init: RequestInit = {}) =>
  fetch(url, { ...init, headers: { ...(init.headers as Record<string, string> | undefined), "X-Slugline": "1" } });

async function check(response: Response): Promise<Response> {
  if (response.ok) return response;
  let message = `The server answered ${response.status}.`;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // not JSON: keep the generic message
  }
  throw new Error(message);
}

const json = async <T,>(response: Promise<Response>): Promise<T> => (await check(await response)).json();

export const getStatus = () => json<Status>(call("/api/status"));

export const listScripts = () => json<LibraryEntry[]>(call("/api/scripts"));

export const removeScript = (id: string) => json<{ ok: boolean }>(call(`/api/scripts/${id}`, { method: "DELETE" }));

export const openExample = (name: string) => json<Script>(call(`/api/examples/${name}`, { method: "POST" }));

export const getSettings = () => json<Settings>(call("/api/settings"));

export const saveSettings = (changes: { anthropic_api_key?: string; model?: string; language?: string }) =>
  json<Settings>(
    call("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) }),
  );

export const getScript = (id: string) => json<Script>(call(`/api/scripts/${id}`));

export const uploadScript = (file: File) =>
  json<Script>(
    call(`/api/scripts?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    }),
  );

export const analyzeScript = (id: string, refresh = false) =>
  json<Analysis>(call(`/api/scripts/${id}/analysis${refresh ? "?refresh=true" : ""}`, { method: "POST" }));

export const extractElements = (id: string) => json<Elements>(call(`/api/scripts/${id}/elements`, { method: "POST" }));

export const clearElements = (id: string) => json<Elements>(call(`/api/scripts/${id}/elements`, { method: "DELETE" }));

export const saveSceneElements = (id: string, scene: string, elements: { category: string; name: string; notes: string }[]) =>
  json<Elements>(
    call(`/api/scripts/${id}/elements/${encodeURIComponent(scene)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ elements }),
    }),
  );

export const suggestSchedule = (id: string, pagesPerDay: number) =>
  json<Schedule>(
    call(`/api/scripts/${id}/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pages_per_day: pagesPerDay }),
    }),
  );

export const saveSchedule = (id: string, days: ShootDay[], options: { pagesPerDay?: number; actors?: Record<string, string> } = {}) =>
  json<Schedule>(
    call(`/api/scripts/${id}/schedule`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days, pages_per_day: options.pagesPerDay ?? null, actors: options.actors ?? null }),
    }),
  );

export const clearSchedule = (id: string) => json<{ ok: boolean }>(call(`/api/scripts/${id}/schedule`, { method: "DELETE" }));

/** A download link; printed documents come out in the interface's language. */
export const exportUrl = (id: string, name: string, query = "") =>
  `/api/scripts/${id}/export/${name}${query ? `${query}&` : "?"}lang=${language()}`;

export const resetChat = (id: string, session: string) =>
  call(`/api/scripts/${id}/chat/${session}`, { method: "DELETE" });

/** Ask the script assistant; `onEvent` receives the answer piece by piece. */
export async function chat(
  id: string,
  session: string,
  message: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await check(
    await call(`/api/scripts/${id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session }),
      signal,
    }),
  );
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line) as ChatEvent);
    if (done) break;
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer) as ChatEvent);
}
