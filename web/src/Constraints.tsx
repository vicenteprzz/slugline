import { useState } from "react";

import { fillDates, saveConstraints } from "./api";
import { titleCase } from "./format";
import { t } from "./i18n";
import type { Period, Problem, Schedule, ScheduleConstraints, Script } from "./types";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** One conflict of the schedule, in words. */
export function problemText(p: Problem): string {
  switch (p.kind) {
    case "cast":
      return t("{name} is not available on {date}.", { name: titleCase(p.name), date: p.date });
    case "location":
      return t("{name} can't be used on {date}.", { name: titleCase(p.name), date: p.date });
    case "dawn":
      return t("Exterior at dawn (scenes {scenes}): the sun rises at {sunrise} and the call is at {call}.", {
        scenes: (p.detail.scenes ?? []).join(", "),
        sunrise: p.detail.sunrise ?? "",
        call: p.detail.call ?? "",
      });
    case "rest":
      return (
        t("Only {rest} h of rest before the {call} call (the minimum is {minimum} h).", {
          rest: p.detail.rest ?? 0,
          call: p.detail.call ?? "",
          minimum: p.detail.minimum ?? 0,
        }) + (p.detail.assumed ? ` ${t("Call times assumed where none is set.")}` : "")
      );
  }
}

/** Dates someone or somewhere can't be used: chips, and a from/to to add one. */
function Periods(props: { name: string; periods: Period[]; onChange: (periods: Period[]) => void }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const add = () => {
    if (!from) return;
    const end = to && to >= from ? to : from;
    props.onChange([...props.periods, [from, end]]);
    setFrom("");
    setTo("");
  };
  return (
    <div className="periods">
      <span className="element-name">{titleCase(props.name)}</span>
      <span className="period-chips">
        {props.periods.map(([a, b], i) => (
          <span key={`${a}${b}${i}`} className="chip">
            {a === b ? a : `${a} → ${b}`}
            <button className="link" aria-label={t("Remove")} onClick={() => props.onChange(props.periods.filter((_, k) => k !== i))}>
              ×
            </button>
          </span>
        ))}
      </span>
      <span className="period-add">
        <input type="date" value={from} aria-label={t("From")} onChange={(e) => setFrom(e.target.value)} />
        <input type="date" value={to} aria-label={t("To")} onChange={(e) => setTo(e.target.value)} />
        <button className="ghost small" disabled={!from} onClick={add}>
          {t("Add")}
        </button>
      </span>
    </div>
  );
}

/** Calendar, availability, daylight and rest for the schedule. */
export default function ConstraintsPanel(props: {
  script: Script;
  plan: Schedule;
  busy: boolean;
  onChange: (schedule: Schedule) => void;
  onError: (message: string) => void;
}) {
  const { script, plan } = props;
  const c = plan.constraints;
  const [saving, setSaving] = useState(false);
  const [who, setWho] = useState("");
  const [where, setWhere] = useState("");

  async function save(next: ScheduleConstraints) {
    setSaving(true);
    try {
      props.onChange(await saveConstraints(script.id, next));
    } catch (e) {
      props.onError(e instanceof Error ? e.message : t("The constraints could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  async function dates() {
    setSaving(true);
    try {
      props.onChange(await fillDates(script.id));
    } catch (e) {
      props.onError(e instanceof Error ? e.message : t("The dates could not be set."));
    } finally {
      setSaving(false);
    }
  }

  const cast = plan.day_out_of_days.map((d) => d.character);
  const places = script.breakdown.locations.map((l) => l.location);
  const castNames = [...new Set([...Object.keys(c.cast_off), ...(who ? [who] : [])])];
  const placeNames = [...new Set([...Object.keys(c.location_off), ...(where ? [where] : [])])];
  const setOff = (table: "cast_off" | "location_off", name: string, periods: Period[]) => {
    const next = { ...c[table] };
    if (periods.length) next[name] = periods;
    else delete next[name];
    void save({ ...c, [table]: next });
  };

  return (
    <details className={`constraints${saving ? " busy" : ""}`}>
      <summary>
        {t("Calendar and constraints")}
        <span className="muted">
          {" "}
          ·{" "}
          {plan.problems.length
            ? t("{n} conflicts", { n: plan.problems.length })
            : c.start || c.city || Object.keys(c.cast_off).length
              ? t("no conflicts")
              : t("dates, availability, daylight and rest")}
        </span>
      </summary>

      <div className="constraints-grid">
        <label className="field-inline">
          <span>{t("First shooting day")}</span>
          <input type="date" value={c.start} onChange={(e) => void save({ ...c, start: e.target.value })} />
        </label>
        <span className="field-inline weekdays" role="group" aria-label={t("Shooting weekdays")}>
          {WEEKDAYS.map((d, i) => (
            <button
              key={d}
              className="chip"
              aria-pressed={c.weekdays.includes(i)}
              onClick={() =>
                void save({ ...c, weekdays: c.weekdays.includes(i) ? c.weekdays.filter((x) => x !== i) : [...c.weekdays, i].sort() })
              }
            >
              {t(d)}
            </button>
          ))}
        </span>
        <button className="ghost small" disabled={!c.start || props.busy || saving} onClick={() => void dates()}>
          {t("Date every day")}
        </button>
        <label className="field-inline">
          <span>{t("City (for daylight)")}</span>
          <select value={c.city} onChange={(e) => void save({ ...c, city: e.target.value })}>
            <option value="">{t("None")}</option>
            {plan.cities.map((city) => (
              <option key={city.key} value={city.key}>
                {city.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field-inline">
          <span>{t("Hours from call to wrap")}</span>
          <input
            className="num-input"
            type="number"
            min={4}
            max={18}
            step={0.5}
            value={c.day_hours}
            onChange={(e) => void save({ ...c, day_hours: Number(e.target.value) })}
          />
        </label>
        <label className="field-inline">
          <span>{t("Minimum rest (h)")}</span>
          <input
            className="num-input"
            type="number"
            min={0}
            max={24}
            step={0.5}
            value={c.rest_hours}
            onChange={(e) => void save({ ...c, rest_hours: Number(e.target.value) })}
          />
        </label>
      </div>

      <h4>{t("When the cast is not available")}</h4>
      {castNames.map((name) => (
        <Periods key={name} name={name} periods={c.cast_off[name] ?? []} onChange={(p) => setOff("cast_off", name, p)} />
      ))}
      <select value="" onChange={(e) => setWho(e.target.value)} aria-label={t("Add a character")}>
        <option value="">{t("+ Add a character")}</option>
        {cast
          .filter((n) => !castNames.includes(n))
          .map((n) => (
            <option key={n} value={n}>
              {titleCase(n)}
            </option>
          ))}
      </select>

      <h4>{t("When a location can't be used")}</h4>
      {placeNames.map((name) => (
        <Periods key={name} name={name} periods={c.location_off[name] ?? []} onChange={(p) => setOff("location_off", name, p)} />
      ))}
      <select value="" onChange={(e) => setWhere(e.target.value)} aria-label={t("Add a location")}>
        <option value="">{t("+ Add a location")}</option>
        {places
          .filter((n) => !placeNames.includes(n))
          .map((n) => (
            <option key={n} value={n}>
              {titleCase(n)}
            </option>
          ))}
      </select>
      <p className="fine">
        {t("Reordering the days in the budget also moves them to dates that work, when it can. Daylight is worked out on this computer, for the city chosen.")}
      </p>
    </details>
  );
}
