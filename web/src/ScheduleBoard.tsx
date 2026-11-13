import ConstraintsPanel, { problemText } from "./Constraints";
import { FoldTitle } from "./fold";
import { useState } from "react";

import { clearSchedule, exportUrl, saveSchedule, suggestSchedule } from "./api";
import { eighths, plural, stripColor, titleCase } from "./format";
import { light, t } from "./i18n";
import type { CrewMember, Schedule, Script, ShootDay } from "./types";

/** The editable fields of each day, without what the server computes. */
export const plainDays = (days: Schedule["days"]): ShootDay[] =>
  days.map(({ id, scenes, date, notes, call_time, address, hospital, cast_calls }) => ({
    id,
    scenes: [...scenes],
    date,
    notes,
    call_time,
    address,
    hospital,
    cast_calls: { ...cast_calls },
  }));

const UNSCHEDULED = -1;

/** The shooting schedule: days of stripboard strips, reordered by dragging or with the "Move to" menu. */
export default function ScheduleBoard(props: {
  script: Script;
  pdfExport: boolean;
  onChange: (schedule: Schedule | null) => void;
  onError: (message: string) => void;
  onOpenScene: (number: string) => void;
}) {
  const { script } = props;
  const plan = script.schedule && script.schedule.days.length ? script.schedule : null;
  const pdf = props.pdfExport;
  const rows = new Map(script.breakdown.scenes.map((s) => [s.number, s]));
  const total = script.breakdown.scenes.reduce((sum, s) => sum + s.eighths, 0);
  const [pages, setPages] = useState(plan?.pages_per_day ?? 5);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<number | null>(null);

  async function run<T>(task: () => Promise<T>, apply: (value: T) => void) {
    setBusy(true);
    try {
      apply(await task());
    } catch (e) {
      props.onError(e instanceof Error ? e.message : t("The schedule could not be saved."));
    } finally {
      setBusy(false);
    }
  }

  const suggest = () => run(() => suggestSchedule(script.id, pages), props.onChange);

  function commit(days: ShootDay[]) {
    if (!plan) return;
    const previous = plan;
    // Show the change at once; the server's answer replaces it, or the old plan comes back on error.
    props.onChange({ ...plan, days: days.map((d) => ({ ...d, stats: localStats(d) })), unscheduled: unscheduledOf(days) });
    setBusy(true);
    saveSchedule(script.id, days)
      .then(props.onChange)
      .catch((e) => {
        props.onChange(previous);
        props.onError(e instanceof Error ? e.message : t("The schedule could not be saved."));
      })
      .finally(() => setBusy(false));
  }

  // Everyone on set that day: who speaks and who the action names.
  function castOf(day: ShootDay): string[] {
    const names = day.scenes.flatMap((n) => {
      const s = rows.get(n);
      return s ? [...s.characters, ...s.silent] : [];
    });
    return [...new Set(names)];
  }

  function unscheduledOf(days: ShootDay[]): string[] {
    const placed = new Set(days.flatMap((d) => d.scenes));
    return script.breakdown.scenes.map((s) => s.number).filter((n) => !placed.has(n));
  }

  function localStats(day: ShootDay) {
    const scenes = day.scenes.map((n) => rows.get(n)!).filter(Boolean);
    const length = scenes.reduce((sum, s) => sum + s.eighths, 0);
    const unique = (values: (string | null)[]) => [...new Set(values.filter((v): v is string => !!v))];
    return {
      eighths: length,
      locations: unique(scenes.map((s) => s.location)),
      cast: unique(scenes.flatMap((s) => s.characters)),
      light: unique(scenes.map((s) => s.day_night)),
      over: length > Math.round((plan?.pages_per_day ?? 5) * 8),
    };
  }

  /** Move a scene to a day (or out of the schedule), before the scene at `position`. */
  function move(number: string, toDay: number, position?: number) {
    if (!plan) return;
    const next = days().map((d) => ({ ...d, scenes: d.scenes.filter((n) => n !== number) }));
    if (toDay !== UNSCHEDULED) {
      const target = next[toDay].scenes;
      target.splice(position ?? target.length, 0, number);
    }
    commit(next);
  }

  const days = (): ShootDay[] => plainDays(plan!.days);
  const emptyDay = (): ShootDay => ({ id: "", scenes: [], date: "", notes: "", call_time: "", address: "", hospital: "", cast_calls: {} });
  const editDay = (i: number, change: Partial<ShootDay>) => commit(days().map((d, k) => (k === i ? { ...d, ...change } : d)));

  if (!plan) {
    return (
      <section className="card">
        <header className="card-head">
          <div>
            <FoldTitle id="schedule">{t("Shooting schedule")}</FoldTitle>
            <p>
              {t(
                "Put the scenes in shooting order, day by day. Slugline can suggest a first plan: day work first and nights in one block, each location kept together, and each day filled up to the pages you expect to shoot.",
              )}
            </p>
          </div>
        </header>
        <div className="schedule-start">
          <label>
            {t("Pages a day")}
            <input type="number" min={0.5} max={30} step={0.5} value={pages} onChange={(e) => setPages(Number(e.target.value) || 5)} />
          </label>
          <button className="primary" disabled={busy} onClick={suggest}>
            {busy ? t("Planning…") : t("Suggest a schedule")}
          </button>
          <button
            className="ghost"
            disabled={busy}
            onClick={() => run(() => saveSchedule(script.id, [emptyDay()], { pagesPerDay: pages }), props.onChange)}
          >
            {t("Start with an empty day")}
          </button>
        </div>
      </section>
    );
  }

  const newScenes = plan.revision?.new.filter((n) => plan.unscheduled.includes(n)) ?? [];

  const strip = (number: string, dayIndex: number, position: number) => {
    const s = rows.get(number);
    if (!s) return null;
    return (
      <li
        key={number}
        className={`strip${dragging === number ? " dragging" : ""}`}
        draggable
        onDragStart={(e) => {
          e.dataTransfer.setData("text/plain", number);
          e.dataTransfer.effectAllowed = "move";
          setDragging(number);
        }}
        onDragEnd={() => (setDragging(null), setOver(null))}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOver(dayIndex);
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          const moved = e.dataTransfer.getData("text/plain");
          setOver(null);
          if (moved && moved !== number) move(moved, dayIndex === UNSCHEDULED ? UNSCHEDULED : dayIndex, position);
        }}
      >
        <span className="strip-tab" style={{ background: stripColor(s.int_ext, s.day_night) }} aria-hidden="true" />
        <span className="strip-grip" aria-hidden="true">
          ⋮⋮
        </span>
        <span className="strip-number">{s.number}</span>
        <button className="slug slug-button strip-heading" onClick={() => props.onOpenScene(s.number)}>
          {s.heading}
        </button>
        <span className="strip-day" title={t("Day of the story: D3 is day 3, N3 the night of day 3")}>
          {s.story_label}
        </span>
        <span className="strip-pages">{eighths(s.eighths)}</span>
        <span className="strip-cast">{s.characters.map(titleCase).join(", ") || "–"}</span>
        <select
          className="strip-move"
          aria-label={t("Move scene {n}", { n: s.number })}
          value={dayIndex}
          disabled={busy}
          onChange={(e) => move(number, Number(e.target.value))}
        >
          {plan.days.map((_, i) => (
            <option key={i} value={i}>
              {t("Day {n}", { n: i + 1 })}
            </option>
          ))}
          <option value={UNSCHEDULED}>{t("Not scheduled")}</option>
        </select>
      </li>
    );
  };

  const dropZone = (index: number) => ({
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setOver(index);
    },
    onDragLeave: (e: React.DragEvent) => e.currentTarget === e.target && setOver(null),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const moved = e.dataTransfer.getData("text/plain");
      setOver(null);
      if (moved) move(moved, index);
    },
  });

  return (
    <section className={`card${busy ? " saving" : ""}`}>
      <header className="card-head">
        <div>
          <FoldTitle id="schedule">{t("Shooting schedule")}</FoldTitle>
          <p>
            {t("{days} · {pages} pages · planned at {perDay} pages a day. Drag the strips to reorder them, or use the menu on each strip.", {
              days: plural(plan.days.length, "shooting day"),
              pages: eighths(total),
              perDay: plan.pages_per_day,
            })}
          </p>
        </div>
        <div className="schedule-actions">
          <button className="ghost small" disabled={busy} onClick={() => commit([...days(), emptyDay()])}>
            {t("Add day")}
          </button>
          <label className="replan">
            <input
              type="number"
              min={0.5}
              max={30}
              step={0.5}
              value={pages}
              aria-label={t("Pages a day")}
              onChange={(e) => setPages(Number(e.target.value) || 5)}
            />
            {t("pages a day")}
          </label>
          <button
            className="ghost small"
            disabled={busy}
            onClick={() => window.confirm(t("Replace this schedule with a new suggestion? Your changes to it will be lost.")) && void suggest()}
          >
            {t("Suggest again")}
          </button>
          <button
            className="ghost small"
            disabled={busy}
            onClick={() =>
              window.confirm(t("Delete this shooting schedule?")) &&
              void run(
                () => clearSchedule(script.id),
                () => props.onChange(null),
              )
            }
          >
            {t("Delete")}
          </button>
        </div>
      </header>

      <ConstraintsPanel script={script} plan={plan} busy={busy} onChange={props.onChange} onError={props.onError} />
      {plan.problems.length > 0 && (
        <div className="schedule-problems" role="status">
          <strong>{t("{n} conflicts with the calendar and constraints", { n: plan.problems.length })}</strong>
          <ul>
            {plan.problems.slice(0, 8).map((p, k) => (
              <li key={k}>
                <span className="problem-day">{t("Day {n}", { n: p.day })}</span> {problemText(p)}
              </li>
            ))}
          </ul>
          {plan.problems.length > 8 && <p className="fine">{t("{n} more, marked on each day.", { n: plan.problems.length - 8 })}</p>}
        </div>
      )}

      {newScenes.length > 0 && (
        <p className="revision-note schedule-note">
          <span>
            <strong>{t("New draft.")}</strong>{" "}
            {t("The schedule was carried over from the previous draft. New scenes without a day: {list}.", { list: newScenes.join(", ") })}
          </span>
        </p>
      )}

      <ol className="days">
        {plan.days.map((day, i) => {
          const stats = localStats(day);
          return (
            <li key={day.id || i} className={`day${over === i ? " drop" : ""}`} {...dropZone(i)}>
              <div className="day-head">
                <strong>{t("Day {n}", { n: i + 1 })}</strong>
                <input type="date" value={day.date} aria-label={t("Date of day {n}", { n: i + 1 })} onChange={(e) => editDay(i, { date: e.target.value })} />
                <label className="call">
                  {t("Call")}
                  <input
                    type="time"
                    value={day.call_time}
                    aria-label={t("Crew call, day {n}", { n: i + 1 })}
                    onChange={(e) => editDay(i, { call_time: e.target.value })}
                  />
                </label>
                <span className={stats.over ? "day-pages over" : "day-pages"}>
                  {stats.over && <span aria-hidden="true">▲ </span>}
                  {t("{n} of {max} pages", { n: eighths(stats.eighths), max: plan.pages_per_day })}
                </span>
                <span className="day-meta">
                  {stats.locations.map(titleCase).join(" · ") || t("No scenes yet")}
                  {stats.light.length > 0 && ` · ${stats.light.map(light).join(", ")}`}
                </span>
                {plan.daylight?.[i] && (
                  <span className="day-sun" title={t("Sunrise and sunset on this date, {hours} h of daylight", { hours: plan.daylight[i]!.hours })}>
                    ☀ {plan.daylight[i]!.sunrise}–{plan.daylight[i]!.sunset}
                  </span>
                )}
                {plan.problems.some((p) => p.day === i + 1) && (
                  <span
                    className="day-problem"
                    title={plan.problems
                      .filter((p) => p.day === i + 1)
                      .map(problemText)
                      .join("\n")}
                  >
                    ▲ {plan.problems.filter((p) => p.day === i + 1).length}
                  </span>
                )}
                {pdf && day.scenes.length > 0 && (
                  <a className="small-link" href={exportUrl(script.id, "call-sheets.pdf", `?day=${i + 1}`)} download>
                    {t("Call sheet")}
                  </a>
                )}
                <button
                  className="link small-link"
                  disabled={busy}
                  onClick={() => commit(days().filter((_, k) => k !== i))}
                  title={t("Its scenes go back to Not scheduled")}
                >
                  {t("Remove day")}
                </button>
              </div>
              {day.scenes.length ? (
                <ol className="strips">{day.scenes.map((n, k) => strip(n, i, k))}</ol>
              ) : (
                <p className="day-empty">{t("Drag scenes here.")}</p>
              )}
              <div className="day-fields">
                <input
                  className="day-notes"
                  placeholder={t("Meeting point or address")}
                  aria-label={t("Meeting point, day {n}", { n: i + 1 })}
                  defaultValue={day.address}
                  maxLength={300}
                  onBlur={(e) => e.target.value !== day.address && editDay(i, { address: e.target.value })}
                />
                <input
                  className="day-notes"
                  placeholder={t("Nearest hospital")}
                  aria-label={t("Nearest hospital, day {n}", { n: i + 1 })}
                  defaultValue={day.hospital}
                  maxLength={300}
                  onBlur={(e) => e.target.value !== day.hospital && editDay(i, { hospital: e.target.value })}
                />
                <input
                  className="day-notes"
                  placeholder={t("Notes for the call sheet (company move, weather cover…)")}
                  aria-label={t("Notes, day {n}", { n: i + 1 })}
                  defaultValue={day.notes}
                  maxLength={500}
                  onBlur={(e) => e.target.value !== day.notes && editDay(i, { notes: e.target.value })}
                />
              </div>
              {stats.cast.length > 0 && (
                <CastCalls day={day} dayNumber={i + 1} cast={castOf(day)} actors={plan.actors} onChange={(cast_calls) => editDay(i, { cast_calls })} />
              )}
            </li>
          );
        })}
      </ol>

      <div className={`day unscheduled${over === UNSCHEDULED ? " drop" : ""}`} {...dropZone(UNSCHEDULED)}>
        <div className="day-head">
          <strong>{t("Not scheduled")}</strong>
          <span className="day-meta">{plan.unscheduled.length ? plural(plan.unscheduled.length, "scene") : t("Every scene has a day.")}</span>
        </div>
        {plan.unscheduled.length > 0 && <ol className="strips">{plan.unscheduled.map((n, k) => strip(n, UNSCHEDULED, k))}</ol>}
      </div>
    </section>
  );
}

const CODE_HELP: Record<string, string> = {
  SW: "starts work",
  W: "works",
  WF: "finishes",
  SWF: "works this day only",
  H: "on hold",
};

/** Who works which day, as production tracks it for contracts, with the actor's name for each character. */
export function CastCard(props: {
  script: Script;
  onChange: (schedule: Schedule) => void;
  onError: (message: string) => void;
}) {
  const plan = props.script.schedule;
  if (!plan || !plan.days.length) return null;
  const cast = plan.day_out_of_days;

  async function setActor(character: string, actor: string) {
    if (!plan || (plan.actors[character] ?? "") === actor.trim()) return;
    const actors = { ...plan.actors, [character]: actor.trim() };
    try {
      props.onChange(await saveSchedule(props.script.id, plainDays(plan.days), { actors }));
    } catch (e) {
      props.onError(e instanceof Error ? e.message : t("The cast list could not be saved."));
    }
  }

  return (
    <section className="card">
      <header className="card-head">
        <div>
          <FoldTitle id="cast">{t("Cast and day out of days")}</FoldTitle>
          <p>
            {t(
              "Which shooting days each character works, from the schedule above. Holds are days between work days when the actor is paid but not shooting: moving scenes to cut them saves money. Add the actors' names for the call sheets.",
            )}
          </p>
        </div>
        <a className="ghost small button-link" href={exportUrl(props.script.id, "day-out-of-days.csv")} download>
          {t("Download CSV")}
        </a>
      </header>
      <div className="table-scroll">
        <table className="data dood">
          <thead>
            <tr>
              <th>{t("Character")}</th>
              <th>{t("Actor")}</th>
              {plan.days.map((d, i) => (
                <th key={d.id || i} className="num" title={d.date || undefined}>
                  {i + 1}
                </th>
              ))}
              <th className="num">{t("Work")}</th>
              <th className="num">{t("Hold")}</th>
            </tr>
          </thead>
          <tbody>
            {cast.map((c) => (
              <tr key={c.character}>
                <td className="element-name">{titleCase(c.character)}</td>
                <td>
                  <input
                    className="actor"
                    placeholder={t("Actor's name")}
                    aria-label={t("Actor playing {name}", { name: titleCase(c.character) })}
                    defaultValue={c.actor}
                    maxLength={80}
                    onBlur={(e) => void setActor(c.character, e.target.value)}
                  />
                </td>
                {c.codes.map((code, i) => (
                  <td key={i} className={`code${code ? ` code-${code === "H" ? "hold" : "work"}` : ""}`} title={code ? `${t("Day {n}", { n: i + 1 })}: ${t(CODE_HELP[code])}` : undefined}>
                    {code}
                  </td>
                ))}
                <td className="num">{c.work}</td>
                <td className={`num${c.hold ? " hold-count" : ""}`}>{c.hold}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="fine">{t("SW starts work · W works · WF finishes · SWF one day only · H on hold.")}</p>
    </section>
  );
}

/** Call times for the actors working a day, when they differ from the crew call. */
function CastCalls(props: {
  day: ShootDay;
  dayNumber: number;
  cast: string[];
  actors: Record<string, string>;
  onChange: (calls: Record<string, string>) => void;
}) {
  const { day } = props;
  const set = Object.keys(day.cast_calls).filter((name) => props.cast.includes(name)).length;
  return (
    <details className="cast-calls">
      <summary>
        {t("Cast call times")}
        <span className="muted">
          {" "}
          · {set ? t("{n} set, the rest at the crew call", { n: set }) : t("everyone at the crew call")}
        </span>
      </summary>
      <ul>
        {props.cast.map((name) => (
          <li key={name}>
            <span>
              {titleCase(name)}
              {props.actors[name] && <span className="muted"> · {props.actors[name]}</span>}
            </span>
            <input
              type="time"
              value={day.cast_calls[name] ?? ""}
              placeholder={day.call_time}
              aria-label={t("Call time for {name}, day {n}", { name: titleCase(name), n: props.dayNumber })}
              onChange={(e) => {
                const next = { ...day.cast_calls };
                if (e.target.value) next[name] = e.target.value;
                else delete next[name];
                props.onChange(next);
              }}
            />
          </li>
        ))}
      </ul>
    </details>
  );
}

/** The crew list printed on every call sheet. */
export function CrewCard(props: { script: Script; onChange: (schedule: Schedule) => void; onError: (message: string) => void }) {
  const plan = props.script.schedule;
  const [rows, setRows] = useState<CrewMember[] | null>(null);
  if (!plan || !plan.days.length) return null;
  const crew = rows ?? (plan.crew.length ? plan.crew : [{ role: "", name: "", phone: "" }]);

  async function save(next: CrewMember[]) {
    if (!plan) return;
    try {
      const saved = await saveSchedule(props.script.id, plainDays(plan.days), { crew: next });
      setRows(null);
      props.onChange(saved);
    } catch (e) {
      props.onError(e instanceof Error ? e.message : t("The crew list could not be saved."));
    }
  }

  const edit = (i: number, field: keyof CrewMember, value: string) => setRows(crew.map((m, k) => (k === i ? { ...m, [field]: value } : m)));

  return (
    <section className="card">
      <header className="card-head">
        <div>
          <FoldTitle id="crew">{t("Crew")}</FoldTitle>
          <p>{t("Printed on every call sheet, called at the crew call of each day.")}</p>
        </div>
      </header>
      <div className="table-scroll">
        <table className="data crew">
          <thead>
            <tr>
              <th>{t("Role")}</th>
              <th>{t("Name")}</th>
              <th>{t("Phone")}</th>
              <th aria-label={t("Remove")} />
            </tr>
          </thead>
          <tbody>
            {crew.map((m, i) => (
              <tr key={i}>
                {(["role", "name", "phone"] as const).map((field) => (
                  <td key={field}>
                    <input
                      className="actor"
                      value={m[field]}
                      maxLength={80}
                      placeholder={field === "role" ? t("e.g. First AD") : field === "name" ? t("Name") : t("Phone")}
                      aria-label={`${t(field === "role" ? "Role" : field === "name" ? "Name" : "Phone")} ${i + 1}`}
                      onChange={(e) => edit(i, field, e.target.value)}
                      onBlur={() => rows && void save(rows)}
                    />
                  </td>
                ))}
                <td className="num">
                  <button className="item-remove" aria-label={t("Remove")} onClick={() => void save(crew.filter((_, k) => k !== i))}>
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="ghost small add-row" onClick={() => setRows([...crew, { role: "", name: "", phone: "" }])}>
        + {t("Add a person")}
      </button>
    </section>
  );
}
