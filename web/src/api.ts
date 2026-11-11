import type { Analysis, ChatEvent, Elements, Schedule, Script, ShootDay, Status } from "./types";

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

export const getStatus = () => json<Status>(fetch("/api/status"));

export const listScripts = () => json<{ id: string; filename: string; title: string | null }[]>(fetch("/api/scripts"));

export const getScript = (id: string) => json<Script>(fetch(`/api/scripts/${id}`));

export const uploadScript = (file: File) =>
  json<Script>(
    fetch(`/api/scripts?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    }),
  );

export const analyzeScript = (id: string, refresh = false) =>
  json<Analysis>(fetch(`/api/scripts/${id}/analysis${refresh ? "?refresh=true" : ""}`, { method: "POST" }));

export const extractElements = (id: string) => json<Elements>(fetch(`/api/scripts/${id}/elements`, { method: "POST" }));

export const clearElements = (id: string) => json<Elements>(fetch(`/api/scripts/${id}/elements`, { method: "DELETE" }));

export const saveSceneElements = (id: string, scene: string, elements: { category: string; name: string; notes: string }[]) =>
  json<Elements>(
    fetch(`/api/scripts/${id}/elements/${encodeURIComponent(scene)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ elements }),
    }),
  );

export const suggestSchedule = (id: string, pagesPerDay: number) =>
  json<Schedule>(
    fetch(`/api/scripts/${id}/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pages_per_day: pagesPerDay }),
    }),
  );

export const saveSchedule = (id: string, days: ShootDay[], pagesPerDay?: number) =>
  json<Schedule>(
    fetch(`/api/scripts/${id}/schedule`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days, pages_per_day: pagesPerDay ?? null }),
    }),
  );

export const clearSchedule = (id: string) => json<{ ok: boolean }>(fetch(`/api/scripts/${id}/schedule`, { method: "DELETE" }));

export const exportUrl = (id: string, name: string) => `/api/scripts/${id}/export/${name}`;

export const resetChat = (id: string, session: string) =>
  fetch(`/api/scripts/${id}/chat/${session}`, { method: "DELETE" });

/** Ask the script assistant; `onEvent` receives the answer piece by piece. */
export async function chat(
  id: string,
  session: string,
  message: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await check(
    await fetch(`/api/scripts/${id}/chat`, {
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
