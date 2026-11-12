import { FoldTitle } from "./fold";
import { useEffect, useRef, useState } from "react";

import { exportUrl, getBudget, saveBudget } from "./api";
import { RankedBars } from "./charts";
import { eighths, titleCase } from "./format";
import { language, t } from "./i18n";
import type { Budget, BudgetLine, BudgetSettings, Script } from "./types";

/** Whole euros, as a budget prints them: 12.500 € / €12,500. */
export function money(amount: number): string {
  const es = language() === "es";
  return new Intl.NumberFormat(es ? "es-ES" : "en-US", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(amount);
}

// Lines whose concept comes from the script or the user (a character, a
// place, an element, a line added by hand): shown as written, not translated.
const NAMED = /^(cast|location):/;
const OWN = /^(element|extra):/;

function concept(line: BudgetLine): string {
  if (NAMED.test(line.key)) return titleCase(line.concept);
  return OWN.test(line.key) ? line.concept : t(line.concept);
}

/** Where a line's quantity comes from, in a few words. */
function explain(line: BudgetLine): string | null {
  const parts = line.detail.split("|");
  if (line.key.startsWith("cast:") && parts.length === 3) {
    const [role, work, hold] = parts;
    const kind = t(role === "lead" ? "lead" : role === "supporting" ? "supporting" : "small part");
    return Number(hold) ? t("{role} · works {work} days, {hold} on hold", { role: kind, work, hold }) : t("{role} · works {work} days", { role: kind, work });
  }
  if (line.key.startsWith("crew:") && parts.length === 3) {
    const [, shooting, prep] = parts;
    return Number(prep) ? t("{shooting} shooting days + {prep} preparation", { shooting, prep }) : t("{shooting} shooting days", { shooting });
  }
  if (line.key === "extras" && parts.length === 2) return t("{people} people on {days} days with extras", { people: parts[0], days: parts[1] });
  if (line.key === "vans" && parts.length === 2) return t("{vans} vans for {days} days", { vans: parts[0], days: parts[1] });
  if (line.key === "catering" && parts.length === 3) return t("{crew} crew for {days} days, plus {cast} cast days", { crew: parts[0], days: parts[1], cast: parts[2] });
  if (line.key === "insurance" || line.key === "overheads") return t("{pct} of the rest of the budget", { pct: `${Math.round(Number(parts[0]) * 1000) / 10}%` });
  if (line.scenes.length) return t("scenes {list}", { list: line.scenes.slice(0, 12).join(", ") + (line.scenes.length > 12 ? "…" : "") });
  return null;
}

function NumberInput(props: { value: number; label: string; onCommit: (value: number) => void; step?: number }) {
  const [text, setText] = useState(String(props.value));
  useEffect(() => setText(String(props.value)), [props.value]);
  const commit = () => {
    const value = Number(text.replace(",", "."));
    if (Number.isFinite(value) && value >= 0 && value !== props.value) props.onCommit(value);
    else setText(String(props.value));
  };
  return (
    <input
      className="num-input"
      inputMode="decimal"
      aria-label={props.label}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
    />
  );
}

export default function BudgetCard(props: {
  script: Script;
  pdfExport: boolean;
  onError: (message: string) => void;
  onOpenScene: (number: string) => void;
}) {
  const { script } = props;
  const [budget, setBudget] = useState<Budget | null>(null);
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const settingsRef = useRef<BudgetSettings | null>(null);

  // Worked out again whenever the schedule or the elements change.
  useEffect(() => {
    let live = true;
    getBudget(script.id)
      .then((b) => {
        if (!live) return;
        setBudget(b);
        settingsRef.current = b.settings;
      })
      .catch((e) => live && props.onError(e instanceof Error ? e.message : t("The budget could not be worked out.")));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [script.id, script.schedule, script.elements, script.breakdown]);

  async function change(edit: (s: BudgetSettings) => BudgetSettings) {
    const current = settingsRef.current;
    if (!current) return;
    const next = edit(structuredClone(current));
    settingsRef.current = next;
    setSaving(true);
    try {
      const b = await saveBudget(script.id, next);
      setBudget(b);
      settingsRef.current = b.settings;
    } catch (e) {
      props.onError(e instanceof Error ? e.message : t("The budget could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  if (!budget) return null;
  const previous = budget.previous;
  const difference = previous ? budget.total - previous.total : 0;

  const setRate = (key: string, value: number) => change((s) => ({ ...s, rates: { ...s.rates, [key]: value } }));
  const setUnits = (key: string, value: number) => change((s) => ({ ...s, units: { ...s.units, [key]: value } }));
  const setQuote = (key: string, value: number) => change((s) => ({ ...s, quotes: { ...s.quotes, [key]: value } }));
  const reset = (key: string) =>
    change((s) => {
      const drop = (record: Record<string, number>) => Object.fromEntries(Object.entries(record).filter(([k]) => k !== key));
      return { ...s, rates: drop(s.rates), units: drop(s.units), quotes: drop(s.quotes) };
    });
  const removeExtra = (index: number) => change((s) => ({ ...s, extra: s.extra.filter((_, i) => i !== index) }));

  const top = budget.scenes.slice(0, 8);

  return (
    <section className={`card budget${saving ? " busy" : ""}`}>
      <header className="card-head">
        <div>
          <FoldTitle id="budget">{t("Budget")}</FoldTitle>
          <p>
            {t(
              "Worked out from the breakdown and the schedule: shooting days, the days each actor works, extras, locations, vehicles. Quantities follow the schedule; the rates are a starting point to replace with your own.",
            )}
          </p>
        </div>
        <div className="budget-actions">
          <label className="field-inline">
            <span>{t("Level")}</span>
            <select value={budget.level} onChange={(e) => void change((s) => ({ ...s, level: e.target.value }))}>
              {budget.levels.map((l) => (
                <option key={l.key} value={l.key}>
                  {t(l.label)}
                </option>
              ))}
            </select>
          </label>
          {props.pdfExport && (
            <a className="ghost small button-link" href={exportUrl(script.id, "budget.pdf")} download>
              {t("PDF")}
            </a>
          )}
          <a className="ghost small button-link" href={exportUrl(script.id, "budget.csv")} download>
            {t("Excel (CSV)")}
          </a>
        </div>
      </header>

      <div className="tiles budget-tiles">
        <div className="tile">
          <span className="tile-label">{t("Total")}</span>
          <span className="tile-value">{money(budget.total)}</span>
        </div>
        <div className="tile">
          <span className="tile-label">{t("Shooting days")}</span>
          <span className="tile-value">{budget.days}</span>
        </div>
        <div className="tile">
          <span className="tile-label">{t("Per shooting day")}</span>
          <span className="tile-value">{budget.per_day !== null ? money(budget.per_day) : "–"}</span>
        </div>
        <div className={`tile${budget.to_quote.count ? " tile-warn" : ""}`}>
          <span className="tile-label">{t("To be quoted")}</span>
          <span className="tile-value">{budget.to_quote.count}</span>
        </div>
      </div>

      {budget.estimated_days > 0 && (
        <p className="fine">
          {budget.scheduled_days
            ? t("{n} of the days are estimated for scenes not in the schedule yet.", { n: budget.estimated_days })
            : t("There is no schedule yet: the days are estimated from a suggested plan. Make the schedule above and the budget follows it.")}
        </p>
      )}
      {budget.to_quote.count > 0 && (
        <p className="budget-warning">
          {t("{n} lines need a quote (effects that can't be priced from the script). They carry {amount} as a placeholder until you enter the quote.", {
            n: budget.to_quote.count,
            amount: money(budget.to_quote.amount),
          })}
        </p>
      )}
      {previous && (
        <p className="revision-note">
          {t("The previous draft came to {total} in {days} days. This one: {now} in {now_days} days ({diff}).", {
            total: money(previous.total),
            days: previous.days,
            now: money(budget.total),
            now_days: budget.days,
            diff: `${difference >= 0 ? "+" : "−"}${money(Math.abs(difference))}`,
          })}
        </p>
      )}

      <div className="grid budget-grid">
        <div>
          <h4>{t("By chapter")}</h4>
          <RankedBars
            color="var(--series-1)"
            rows={budget.chapters
              .filter((c) => c.total > 0)
              .map((c) => ({ name: `${c.code} ${t(c.label)}`, value: c.total, label: money(c.total), detail: t("of {total}", { total: money(budget.total) }) }))}
          />
        </div>
        <div>
          <h4>{t("What each scene costs to shoot")}</h4>
          <p className="fine">{t("Its share of the days it is shot on (crew, equipment, location, cast) plus what only it needs. Cutting a scene saves about this much.")}</p>
          <ol className="scene-costs">
            {top.map((s) => (
              <li key={s.number}>
                <button className="scene-link" onClick={() => props.onOpenScene(s.number)} aria-label={t("Open scene {n}", { n: s.number })}>
                  {s.number}
                </button>
                <span className="scene-cost-heading">{s.heading}</span>
                <span className="muted">{eighths(s.eighths)}</span>
                <strong>{money(s.cost)}</strong>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="budget-chapters">
        {budget.chapters.map((chapter) => (
          <details key={chapter.code} open={open === chapter.code} onToggle={(e) => (e.currentTarget.open ? setOpen(chapter.code) : open === chapter.code && setOpen(null))}>
            <summary>
              <span>
                {chapter.code} · {t(chapter.label)}
              </span>
              <span className="muted">{chapter.lines.length}</span>
              <strong>{money(chapter.total)}</strong>
            </summary>
            {chapter.lines.length > 0 && (
              <div className="table-scroll">
                <table className="data budget-lines">
                  <thead>
                    <tr>
                      <th>{t("Concept")}</th>
                      <th className="num">{t("Quantity")}</th>
                      <th>{t("Unit")}</th>
                      <th className="num">{t("Rate")}</th>
                      <th className="num">{t("Total")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {chapter.lines.map((line) => {
                      const why = explain(line);
                      const pending = line.to_quote && !line.quoted;
                      const extraIndex = line.key.startsWith("extra:") ? Number(line.key.slice(6)) : null;
                      return (
                        <tr key={line.key} className={pending ? "to-quote" : undefined}>
                          <td>
                            <span className="element-name">{concept(line)}</span>
                            {pending && <span className="quote-tag">{t("to be quoted")}</span>}
                            {why && <span className="line-why">{why}</span>}
                          </td>
                          {line.to_quote ? (
                            <>
                              <td className="num">{line.quoted ? "1" : line.units}</td>
                              <td>{line.quoted ? t("quote") : t(line.unit)}</td>
                              <td className="num" colSpan={1}>
                                <NumberInput value={line.quoted ? line.rate : 0} label={t("Quote for {name}", { name: concept(line) })} onCommit={(v) => void setQuote(line.key, v)} />
                              </td>
                            </>
                          ) : (
                            <>
                              <td className="num">
                                {line.unit === "lump" ? "1" : <NumberInput value={line.units} label={t("Quantity for {name}", { name: concept(line) })} onCommit={(v) => void setUnits(line.key, v)} />}
                              </td>
                              <td>{t(line.unit)}</td>
                              <td className="num">
                                <NumberInput value={line.rate} label={t("Rate for {name}", { name: concept(line) })} onCommit={(v) => void setRate(line.key, v)} />
                              </td>
                            </>
                          )}
                          <td className="num">{money(line.total)}</td>
                          <td>
                            {extraIndex !== null ? (
                              <button className="link" onClick={() => void removeExtra(extraIndex)}>
                                {t("Remove")}
                              </button>
                            ) : (
                              (line.edited || line.quoted) && (
                                <button className="link" onClick={() => void reset(line.key)} title={t("Back to the worked-out value")}>
                                  {t("Reset")}
                                </button>
                              )
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <AddLine chapter={chapter.code} onAdd={(item) => void change((s) => ({ ...s, extra: [...s.extra, item] }))} />
          </details>
        ))}
      </div>
      <p className="fine">
        {t(
          "Chapters follow the ICAA budget model. This is a first draft from the script: check it with a production manager, and replace the rates with your agreements and quotes before using it for funding.",
        )}
      </p>
    </section>
  );
}

function AddLine(props: { chapter: string; onAdd: (item: { chapter: string; concept: string; units: number; rate: number }) => void }) {
  const [name, setName] = useState("");
  const [units, setUnits] = useState("1");
  const [rate, setRate] = useState("");
  const add = () => {
    const u = Number(units.replace(",", "."));
    const r = Number(rate.replace(",", "."));
    if (!name.trim() || !Number.isFinite(u) || !Number.isFinite(r) || u < 0 || r < 0) return;
    props.onAdd({ chapter: props.chapter, concept: name.trim(), units: u, rate: r });
    setName("");
    setUnits("1");
    setRate("");
  };
  return (
    <form
      className="add-line"
      onSubmit={(e) => {
        e.preventDefault();
        add();
      }}
    >
      <input placeholder={t("Add a line: concept")} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} aria-label={t("Concept")} />
      <input className="num-input" inputMode="decimal" value={units} onChange={(e) => setUnits(e.target.value)} aria-label={t("Quantity")} />
      <input className="num-input" inputMode="decimal" placeholder={t("Rate")} value={rate} onChange={(e) => setRate(e.target.value)} aria-label={t("Rate")} />
      <button className="ghost small" type="submit">
        {t("Add")}
      </button>
    </form>
  );
}
