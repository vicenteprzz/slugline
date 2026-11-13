import { useMemo, useState } from "react";

import { exportUrl } from "./api";
import { FoldTitle } from "./fold";
import { titleCase } from "./format";
import { plural, t } from "./i18n";
import type { Script } from "./types";

/** Story days and continuity: which day of the story each scene happens on,
 * each character's costume changes, and what may have been lost between
 * scenes of the same day. */
export default function ContinuityCard(props: { script: Script; onOpenScene: (number: string) => void }) {
  const { script } = props;
  const continuity = script.continuity;
  const [showAll, setShowAll] = useState(false);

  // Scenes grouped by day of the story, in story order.
  const days = useMemo(() => {
    const groups = new Map<number, { label: string; scenes: string[] }[]>();
    for (const s of script.breakdown.scenes) {
      if (!s.story_day) continue;
      const parts = groups.get(s.story_day) ?? [];
      const last = parts[parts.length - 1];
      if (last && last.label === s.story_label) last.scenes.push(s.number);
      else parts.push({ label: s.story_label, scenes: [s.number] });
      groups.set(s.story_day, parts);
    }
    return [...groups.entries()].sort(([a], [b]) => a - b);
  }, [script.breakdown.scenes]);

  if (!continuity || !days.length) return null;
  const byHand = Object.keys(script.corrections?.story_days ?? {}).length;
  const plot = showAll ? continuity.costume_plot : continuity.costume_plot.slice(0, 12);
  const link = (n: string) => (
    <button key={n} className="scene-link" onClick={() => props.onOpenScene(n)} aria-label={t("Open scene {n}", { n })}>
      {n}
    </button>
  );

  return (
    <section className="card continuity">
      <header className="card-head">
        <div>
          <FoldTitle id="continuity">{t("Story days and continuity")}</FoldTitle>
          <p>
            {t(
              "The day of the story each scene happens on, suggested from the headings (NEXT MORNING, TWO DAYS LATER, from night to morning). Correct a scene's day on its breakdown sheet and the scenes after it follow.",
            )}
          </p>
        </div>
        <a className="ghost small button-link" href={exportUrl(script.id, "costume-plot.csv")} download>
          {t("Costume plot (CSV)")}
        </a>
      </header>

      <p className="fine">
        {t("{days} of story", { days: plural(continuity.days, "story day") })}
        {byHand > 0 && ` · ${byHand === 1 ? t("1 set by hand") : t("{n} set by hand", { n: byHand })}`}
      </p>
      <div className="story-days">
        {days.map(([day, parts]) => (
          <div key={day} className="story-day-row">
            <span className="story-day-name">{t("Story day {n}", { n: day })}</span>
            <span className="scene-links">
              {parts.map((part) => (
                <span key={part.label + part.scenes[0]} className="story-part">
                  <span className="story-day-tag">{part.label}</span>
                  {part.scenes.map(link)}
                </span>
              ))}
            </span>
          </div>
        ))}
      </div>

      <h4>{t("Continuity to check")}</h4>
      {continuity.warnings.length === 0 ? (
        <p className="fine">
          {t("Nothing to check: no wound, blood or costume added by hand goes missing within a day of the story.")}
        </p>
      ) : (
        <>
          <p className="fine">
            {t(
              "A makeup element (a wound, blood) or a costume added by hand is in one scene, and a later scene of the same day of the story, with the same people, doesn't have it. Check whether it should.",
            )}
          </p>
          <ul className="continuity-warnings">
            {continuity.warnings.slice(0, 40).map((w) => (
              <li key={`${w.element}|${w.missing}`}>
                <strong>{w.element}</strong> {t("in scene")} {link(w.has)} · {t("missing in")} {link(w.missing)}
                <span className="muted">
                  {" "}
                  · {t("Story day {n}", { n: w.day })} · {w.characters.map(titleCase).join(", ")}
                </span>
              </li>
            ))}
          </ul>
          {continuity.warnings.length > 40 && (
            <p className="fine">{t("{n} more in the breakdown sheets.", { n: continuity.warnings.length - 40 })}</p>
          )}
        </>
      )}

      <h4>{t("Costume plot")}</h4>
      <p className="fine">{t("One change per day of the story for each character, with its scenes: where the wardrobe department starts.")}</p>
      <div className="table-scroll">
        <table className="data costume-plot">
          <thead>
            <tr>
              <th>{t("Character")}</th>
              <th className="num">{t("Changes")}</th>
              <th>{t("Change · day · scenes")}</th>
            </tr>
          </thead>
          <tbody>
            {plot.map((c) => (
              <tr key={c.character}>
                <td className="element-name">{titleCase(c.character)}</td>
                <td className="num">{c.changes.length}</td>
                <td>
                  <span className="changes">
                    {c.changes.map((ch) => (
                      <span key={ch.day} className="change">
                        <span className="story-day-tag">
                          {ch.number} · {t("Story day {n}", { n: ch.day })}
                        </span>
                        {ch.scenes.map(link)}
                      </span>
                    ))}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {continuity.costume_plot.length > 12 && (
        <button className="link" onClick={() => setShowAll(!showAll)}>
          {showAll ? t("Show fewer") : t("Show all {n} characters", { n: continuity.costume_plot.length })}
        </button>
      )}
    </section>
  );
}
