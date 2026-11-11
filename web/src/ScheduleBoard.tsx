import { useState } from "react";

import { clearSchedule, saveSchedule, suggestSchedule } from "./api";
import { eighths, plural, stripColor, titleCase } from "./format";
import type { Schedule, Script, ShootDay } from "./types";

const UNSCHEDULED = -1;

/** The shooting schedule: days of stripboard strips, reordered by dragging or with the "Move to" menu. */
export default function ScheduleBoard(props: {
  script: Script;
  onChange: (schedule: Schedule | null) => void;
  onError: (message: string) => void;
  onOpenScene: (number: string) => void;
}) {
  const { script } = props;
  const plan = script.schedule && script.schedule.days.length ? script.schedule : null;
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
      props.onError(e instanceof Error ? e.message : "The schedule could not be saved.");
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
    saveSchedule(script.id, days.map(({ id, scenes, date, notes }) => ({ id, scenes, date, notes })))
      .then(props.onChange)
      .catch((e) => {
        props.onChange(previous);
        props.onError(e instanceof Error ? e.message : "The schedule could not be saved.");
      })
      .finally(() => setBusy(false));
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
    const days = plan.days.map((d) => ({ id: d.id, scenes: d.scenes.filter((n) => n !== number), date: d.date, notes: d.notes }));
    if (toDay !== UNSCHEDULED) {
      const target = days[toDay].scenes;
      target.splice(position ?? target.length, 0, number);
    }
    commit(days);
  }

  const plainDays = () => plan!.days.map(({ id, scenes, date, notes }) => ({ id, scenes: [...scenes], date, notes }));

  if (!plan) {
    return (
      <section className="card">
        <header className="card-head">
          <div>
            <h3>Shooting schedule</h3>
            <p>
              Put the scenes in shooting order, day by day. Slugline can suggest a first plan: day work first and nights in one block, each
              location kept together, and each day filled up to the pages you expect to shoot.
            </p>
          </div>
        </header>
        <div className="schedule-start">
          <label>
            Pages a day
            <input type="number" min={0.5} max={30} step={0.5} value={pages} onChange={(e) => setPages(Number(e.target.value) || 5)} />
          </label>
          <button className="primary" disabled={busy} onClick={suggest}>
            {busy ? "Planning…" : "Suggest a schedule"}
          </button>
          <button
            className="ghost"
            disabled={busy}
            onClick={() => run(() => saveSchedule(script.id, [{ id: "", scenes: [], date: "", notes: "" }], pages), props.onChange)}
          >
            Start with an empty day
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
        <span className="strip-pages">{eighths(s.eighths)}</span>
        <span className="strip-cast">{s.characters.map(titleCase).join(", ") || "–"}</span>
        <select
          className="strip-move"
          aria-label={`Move scene ${s.number}`}
          value={dayIndex}
          disabled={busy}
          onChange={(e) => move(number, Number(e.target.value))}
        >
          {plan.days.map((_, i) => (
            <option key={i} value={i}>
              Day {i + 1}
            </option>
          ))}
          <option value={UNSCHEDULED}>Not scheduled</option>
        </select>
      </li>
    );
  };

  const dropZone = (index: number) => ({
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
      setOver(index);
    },
    onDragLeave: (e: React.DragEvent) => e.currentTarget === e.target && setOver(null),
    onDrop: (e: React.DragEvent) => {
      e.preventDefault();
      const moved = e.dataTransfer.getData("text/plain");
      setOver(null);
      if (moved) move(moved, index);
    },
  });

  return (
    <section className={`card${busy ? " saving" : ""}`}>
      <header className="card-head">
        <div>
          <h3>Shooting schedule</h3>
          <p>
            {plural(plan.days.length, "shooting day")} · {eighths(total)} pages · planned at {plan.pages_per_day} pages a day. Drag the
            strips to reorder them, or use the menu on each strip.
          </p>
        </div>
        <div className="schedule-actions">
          <button className="ghost small" disabled={busy} onClick={() => commit([...plainDays(), { id: "", scenes: [], date: "", notes: "" }])}>
            Add day
          </button>
          <label className="replan">
            <input
              type="number"
              min={0.5}
              max={30}
              step={0.5}
              value={pages}
              aria-label="Pages a day"
              onChange={(e) => setPages(Number(e.target.value) || 5)}
            />
            pages a day
          </label>
          <button
            className="ghost small"
            disabled={busy}
            onClick={() => window.confirm("Replace this schedule with a new suggestion? Your changes to it will be lost.") && void suggest()}
          >
            Suggest again
          </button>
          <button
            className="ghost small"
            disabled={busy}
            onClick={() =>
              window.confirm("Delete this shooting schedule?") &&
              void run(
                () => clearSchedule(script.id),
                () => props.onChange(null),
              )
            }
          >
            Delete
          </button>
        </div>
      </header>

      {newScenes.length > 0 && (
        <p className="revision-note schedule-note">
          <span>
            <strong>New draft.</strong> The schedule was carried over from the previous draft. {plural(newScenes.length, "new scene")} still{" "}
            {newScenes.length === 1 ? "needs" : "need"} a day: {newScenes.join(", ")}.
          </span>
        </p>
      )}

      <ol className="days">
        {plan.days.map((day, i) => {
          const stats = localStats(day);
          return (
            <li key={day.id || i} className={`day${over === i ? " drop" : ""}`} {...dropZone(i)}>
              <div className="day-head">
                <strong>Day {i + 1}</strong>
                <input
                  type="date"
                  value={day.date}
                  aria-label={`Date of day ${i + 1}`}
                  onChange={(e) => commit(plainDays().map((d, k) => (k === i ? { ...d, date: e.target.value } : d)))}
                />
                <span className={stats.over ? "day-pages over" : "day-pages"}>
                  {stats.over && <span aria-hidden="true">▲ </span>}
                  {eighths(stats.eighths)} of {plan.pages_per_day} pages
                </span>
                <span className="day-meta">
                  {stats.locations.map(titleCase).join(" · ") || "No scenes yet"}
                  {stats.light.length > 0 && ` · ${stats.light.map(titleCase).join(", ")}`}
                </span>
                <button
                  className="link small-link"
                  disabled={busy}
                  onClick={() => commit(plainDays().filter((_, k) => k !== i))}
                  title="Its scenes go back to Not scheduled"
                >
                  Remove day
                </button>
              </div>
              {day.scenes.length ? (
                <ol className="strips">{day.scenes.map((n, k) => strip(n, i, k))}</ol>
              ) : (
                <p className="day-empty">Drag scenes here.</p>
              )}
              <input
                className="day-notes"
                placeholder="Notes for this day (call time, company move, weather cover…)"
                defaultValue={day.notes}
                maxLength={500}
                onBlur={(e) => e.target.value !== day.notes && commit(plainDays().map((d, k) => (k === i ? { ...d, notes: e.target.value } : d)))}
              />
            </li>
          );
        })}
      </ol>

      <div className={`day unscheduled${over === UNSCHEDULED ? " drop" : ""}`} {...dropZone(UNSCHEDULED)}>
        <div className="day-head">
          <strong>Not scheduled</strong>
          <span className="day-meta">{plan.unscheduled.length ? plural(plan.unscheduled.length, "scene") : "Every scene has a day."}</span>
        </div>
        {plan.unscheduled.length > 0 && <ol className="strips">{plan.unscheduled.map((n, k) => strip(n, UNSCHEDULED, k))}</ol>}
      </div>
    </section>
  );
}
