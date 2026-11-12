import { FoldTitle } from "./fold";
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";

import { count, niceTicks } from "./format";
import { t } from "./i18n";

// ---------------------------------------------------------------------------
// Shared pieces

/** The width of an element, kept up to date, so charts can draw in real pixels. */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    setWidth(node.clientWidth);
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

type Tip = { x: number; y: number; node: ReactNode };
type TipEvent = React.PointerEvent<Element> | React.FocusEvent<Element>;

/** One tooltip per chart, shown on hover and on keyboard focus alike. */
function useTip() {
  const [tip, setTip] = useState<Tip | null>(null);
  // The tooltip is pinned to the screen, so it must not outlive a scroll.
  useEffect(() => {
    if (!tip) return;
    const hide = () => setTip(null);
    window.addEventListener("scroll", hide, { passive: true, once: true });
    return () => window.removeEventListener("scroll", hide);
  }, [tip]);
  const show = (event: TipEvent, node: ReactNode) => {
    if ("clientX" in event && event.type !== "focus") {
      setTip({ x: event.clientX, y: event.clientY, node });
    } else {
      const box = event.currentTarget.getBoundingClientRect();
      setTip({ x: box.left + box.width / 2, y: box.top + box.height / 2, node });
    }
  };
  return { tip, show, hide: () => setTip(null) };
}

function TipBox({ tip }: { tip: Tip | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  useLayoutEffect(() => {
    if (!tip || !ref.current) return;
    const { offsetWidth: w, offsetHeight: h } = ref.current;
    // Keep the box on screen: flip to the other side of the pointer near an edge.
    const left = tip.x + 14 + w > window.innerWidth - 8 ? tip.x - 14 - w : tip.x + 14;
    const top = tip.y + 14 + h > window.innerHeight - 8 ? tip.y - 14 - h : tip.y + 14;
    setPosition({ left: Math.max(8, left), top: Math.max(8, top) });
  }, [tip]);
  if (!tip) return null;
  return (
    <div ref={ref} className="tip" role="status" style={position}>
      {tip.node}
    </div>
  );
}

function TipRows({ title, note, rows }: { title: string; note?: string; rows: { key?: string; label: string; value: string }[] }) {
  return (
    <>
      <div className="tip-title">{title}</div>
      {note && <div className="tip-note">{note}</div>}
      {rows.map((row) => (
        <div className="tip-row" key={row.label}>
          {row.key && <span className="tip-key" style={{ background: row.key }} />}
          <strong>{row.value}</strong>
          <span>{row.label}</span>
        </div>
      ))}
    </>
  );
}

export type TableData = { columns: string[]; rows: (string | number)[][] };

/** A card holding one chart, with the same data available as a table. */
export function ChartCard(props: {
  id?: string; // remembers the card as folded; the title is used if missing
  title: string;
  subtitle?: string;
  table?: TableData;
  wide?: boolean;
  children: ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section className={`card${props.wide ? " wide" : ""}`}>
      <header className="card-head">
        <div>
          <FoldTitle id={props.id ?? props.title}>{props.title}</FoldTitle>
          {props.subtitle && <p>{props.subtitle}</p>}
        </div>
        {props.table && (
          <button className="ghost small" aria-pressed={asTable} onClick={() => setAsTable(!asTable)}>
            {asTable ? t("Chart") : t("Table")}
          </button>
        )}
      </header>
      {asTable && props.table ? <DataTable {...props.table} /> : props.children}
    </section>
  );
}

function DataTable({ columns, rows }: TableData) {
  return (
    <div className="table-scroll">
      <table className="data">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className={typeof cell === "number" ? "num" : undefined}>
                  {typeof cell === "number" ? count(cell) : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Legend({ items }: { items: { name: string; color: string }[] }) {
  return (
    <ul className="legend">
      {items.map((item) => (
        <li key={item.name}>
          <span className="swatch" style={{ background: item.color }} />
          {item.name}
        </li>
      ))}
    </ul>
  );
}

/** A bar with a rounded data end and a square end on the baseline. */
function barPath(x: number, y: number, w: number, h: number, down = false): string {
  const r = Math.min(4, w / 2, h);
  if (down) {
    return `M${x},${y}H${x + w}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x + r}Q${x},${y + h} ${x},${y + h - r}Z`;
  }
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

const GAP = 2; // surface gap between touching fills

// ---------------------------------------------------------------------------
// Stacked columns: who speaks in each scene

export type Column = { label: string; title: string; values: number[] };

export function StackedColumns(props: {
  columns: Column[];
  series: { name: string; color: string }[];
  unit: string;
  xTitle: string;
}) {
  const { columns, series, unit } = props;
  const [ref, width] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const [active, setActive] = useState<number | null>(null);

  const height = 260;
  const m = { top: 10, right: 4, bottom: 40, left: 40 };
  const innerW = Math.max(0, width - m.left - m.right);
  const innerH = height - m.top - m.bottom;
  const totals = columns.map((c) => c.values.reduce((a, b) => a + b, 0));
  const ticks = niceTicks(Math.max(...totals, 1));
  const top = ticks[ticks.length - 1];
  const y = (v: number) => m.top + innerH - (v / top) * innerH;
  const band = columns.length ? innerW / columns.length : 0;
  const barW = Math.min(24, band * 0.7);
  // With many scenes, number only every nth so the labels never collide.
  const every = Math.ceil(22 / Math.max(band, 1));

  const describe = (i: number) => (
    <TipRows
      title={columns[i].title}
      rows={[
        ...series
          .map((s, k) => ({ key: s.color, label: s.name, value: count(columns[i].values[k]) }))
          .filter((_, k) => columns[i].values[k] > 0),
        { label: t("{unit} in total", { unit }), value: count(totals[i]) },
      ]}
    />
  );

  return (
    <div ref={ref} className="chart">
      <Legend items={series} />
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={`${unit} per character in each scene`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} className={t === 0 ? "axis" : "grid"} />
              <text x={m.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="tick">
                {count(t)}
              </text>
            </g>
          ))}
          {columns.map((column, i) => {
            const x = m.left + band * i + (band - barW) / 2;
            let base = 0;
            const last = column.values.reduce((acc, v, k) => (v > 0 ? k : acc), -1);
            return (
              <g
                key={column.label}
                tabIndex={0}
                className="hit"
                aria-label={`${column.title}: ${count(totals[i])} ${unit}`}
                onPointerMove={(e) => (setActive(i), show(e, describe(i)))}
                onPointerLeave={() => (setActive(null), hide())}
                onFocus={(e) => (setActive(i), show(e, describe(i)))}
                onBlur={() => (setActive(null), hide())}
              >
                <rect x={m.left + band * i} y={m.top} width={band} height={innerH + 22} className={active === i ? "wash on" : "wash"} />
                {column.values.map((v, k) => {
                  if (v <= 0) return null;
                  const y0 = y(base + v);
                  const h = Math.max(1, y(base) - y0 - (base > 0 ? GAP : 0));
                  base += v;
                  return k === last ? (
                    <path key={k} d={barPath(x, y0, barW, h)} fill={series[k].color} />
                  ) : (
                    <rect key={k} x={x} y={y0} width={barW} height={h} fill={series[k].color} />
                  );
                })}
                {i % every === 0 && (
                  <text x={m.left + band * (i + 0.5)} y={height - m.bottom + 16} textAnchor="middle" className="tick">
                    {column.label}
                  </text>
                )}
              </g>
            );
          })}
          <text x={m.left + innerW / 2} y={height - 4} textAnchor="middle" className="axis-title">
            {props.xTitle}
          </text>
        </svg>
      )}
      <TipBox tip={tip} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ranked bars: one value per named row, largest first

export function RankedBars(props: { rows: { name: string; value: number; label: string; detail: string }[]; color: string }) {
  const { tip, show, hide } = useTip();
  const max = Math.max(...props.rows.map((r) => r.value), 1);
  return (
    <div className="chart ranked">
      {props.rows.map((row) => {
        const describe = <TipRows title={row.name} rows={[{ label: row.detail, value: row.label }]} />;
        return (
          <div
            className="ranked-row"
            key={row.name}
            tabIndex={0}
            onPointerMove={(e) => show(e, describe)}
            onPointerLeave={hide}
            onFocus={(e) => show(e, describe)}
            onBlur={hide}
          >
            <span className="ranked-name">{row.name}</span>
            <span className="ranked-track">
              <span className="ranked-bar" style={{ width: `${(row.value / max) * 100}%`, background: props.color }} />
              <span className="ranked-value">{row.label}</span>
            </span>
          </div>
        );
      })}
      <TipBox tip={tip} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Heatmap: characters by scene

export type HeatCell = { value: number; marked: boolean };

export function Heatmap(props: {
  rows: { name: string; cells: HeatCell[] }[];
  columns: { label: string; title: string }[];
  unit: string;
  markedLabel: string;
}) {
  const { rows, columns } = props;
  const [ref, width] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const labelW = Math.min(150, Math.max(90, width * 0.26));
  // Cells shrink to fit every scene in the card; on a feature with 200+ scenes
  // they get thin, and the table view carries the exact numbers.
  const cell = Math.max(1, Math.min(34, (width - labelW) / Math.max(columns.length, 1)));
  const gap = cell >= 8 ? GAP : cell >= 4 ? 1 : 0;
  const rowH = 22;
  const max = Math.max(...rows.flatMap((r) => r.cells.map((c) => c.value)), 1);
  // Five steps of one hue: more words, darker (lighter in dark mode).
  const step = (v: number) => Math.min(5, Math.max(1, Math.ceil((v / max) * 5)));
  const every = Math.ceil(22 / cell);
  const height = rows.length * rowH + 22;

  return (
    <div ref={ref} className="chart">
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={`${props.unit} per character and scene`}>
          {rows.map((row, r) => (
            <g key={row.name}>
              <text x={labelW - 8} y={r * rowH + rowH / 2} dy="0.32em" textAnchor="end" className="row-label">
                {row.name.length > 18 ? `${row.name.slice(0, 17)}…` : row.name}
              </text>
              {row.cells.map((c, i) => {
                const x = labelW + i * cell;
                const describe = (
                  <TipRows
                    title={row.name}
                    note={columns[i].title}
                    rows={[{ label: c.value ? props.unit : props.markedLabel, value: c.value ? count(c.value) : c.marked ? "0" : "–" }]}
                  />
                );
                return (
                  <g key={i} onPointerMove={(e) => show(e, describe)} onPointerLeave={hide}>
                    <rect
                      x={x}
                      y={r * rowH}
                      width={Math.max(cell - gap, 0.5)}
                      height={rowH - GAP}
                      rx={cell >= 8 ? 2 : 0}
                      className={c.value ? `heat heat-${step(c.value)}` : "heat heat-0"}
                    />
                    {!c.value && c.marked && cell >= 8 && (
                      <circle cx={x + (cell - gap) / 2} cy={r * rowH + (rowH - GAP) / 2} r={3.5} className="heat-mark" />
                    )}
                  </g>
                );
              })}
            </g>
          ))}
          {columns.map(
            (c, i) =>
              i % every === 0 && (
                <text key={c.label} x={labelW + i * cell + (cell - gap) / 2} y={rows.length * rowH + 14} textAnchor="middle" className="tick">
                  {c.label}
                </text>
              ),
          )}
        </svg>
      )}
      <div className="heat-legend">
        <span>{t("Fewer {unit}", { unit: props.unit })}</span>
        {[1, 2, 3, 4, 5].map((s) => (
          <span key={s} className={`heat-chip heat-${s}`} />
        ))}
        <span>{t("More")}</span>
        <span className="heat-legend-mark">
          <svg width="12" height="12" aria-hidden="true">
            <circle cx="6" cy="6" r="3.5" className="heat-mark" />
          </svg>
          {props.markedLabel}
        </span>
      </div>
      <TipBox tip={tip} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tall segmented bar: one whole split into a few parts

export function SegmentedBar(props: { parts: { name: string; value: number; label: string; color: string; ink: string }[]; total: string }) {
  const { tip, show, hide } = useTip();
  const [ref, width] = useWidth<HTMLDivElement>();
  const parts = props.parts.filter((p) => p.value > 0);
  const sum = parts.reduce((a, p) => a + p.value, 0) || 1;
  return (
    <div className="chart">
      <div ref={ref} className="segments" role="img" aria-label={parts.map((p) => `${p.name} ${p.label}`).join(", ")}>
        {parts.map((p) => {
          const share = Math.round((p.value / sum) * 100);
          const text = `${share}%`;
          // Print the share only where it fits with padding; the legend and tooltip carry the rest.
          const fits = (p.value / sum) * width > text.length * 8 + 16;
          const describe = <TipRows title={p.name} rows={[{ label: t("of {total}", { total: props.total }), value: `${p.label} · ${share}%` }]} />;
          return (
            <span
              key={p.name}
              className="segment"
              tabIndex={0}
              style={{ flexGrow: p.value, background: p.color, color: p.ink }}
              onPointerMove={(e) => show(e, describe)}
              onPointerLeave={hide}
              onFocus={(e) => show(e, describe)}
              onBlur={hide}
            >
              {fits ? text : ""}
            </span>
          );
        })}
      </div>
      <Legend items={parts.map((p) => ({ name: p.name, color: p.color }))} />
      <TipBox tip={tip} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tone: tension and mood, scene by scene, as two small charts on one x axis

export type TonePoint = { label: string; title: string; tone: string; tension: number; valence: number; summary: string } | null;

export function ToneChart({ points }: { points: TonePoint[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const [active, setActive] = useState<number | null>(null);

  const m = { left: 40, right: 4 };
  const tensionH = 84;
  const moodH = 96;
  const gap = 34;
  const tensionTop = 24;
  const moodTop = tensionTop + tensionH + gap;
  const height = moodTop + moodH + 40;
  const innerW = Math.max(0, width - m.left - m.right);
  const band = points.length ? innerW / points.length : 0;
  const barW = Math.min(24, band * 0.7);
  const every = Math.ceil(22 / Math.max(band, 1));
  const tensionY = (v: number) => tensionTop + tensionH - (v / 5) * tensionH;
  const moodZero = moodTop + moodH / 2;
  const moodUnit = moodH / 4;

  return (
    <div ref={ref} className="chart">
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={t("Tension and mood in each scene")}>
          <text x={m.left} y={tensionTop - 10} className="panel-title">
            {t("Tension, 1 to 5")}
          </text>
          {[0, 1, 3, 5].map((t) => (
            <g key={t}>
              <line x1={m.left} x2={width - m.right} y1={tensionY(t)} y2={tensionY(t)} className={t === 0 ? "axis" : "grid"} />
              {t > 0 && (
                <text x={m.left - 8} y={tensionY(t)} dy="0.32em" textAnchor="end" className="tick">
                  {t}
                </text>
              )}
            </g>
          ))}
          <text x={m.left} y={moodTop - 10} className="panel-title">
            {t("Mood, −2 to +2")}
          </text>
          {[2, 0, -2].map((t) => (
            <g key={t}>
              <line x1={m.left} x2={width - m.right} y1={moodZero - t * moodUnit} y2={moodZero - t * moodUnit} className={t === 0 ? "axis" : "grid"} />
              <text x={m.left - 8} y={moodZero - t * moodUnit} dy="0.32em" textAnchor="end" className="tick">
                {t > 0 ? `+${t}` : t === 0 ? "0" : `−${-t}`}
              </text>
            </g>
          ))}
          {points.map((p, i) => {
            if (!p) return null;
            const x = m.left + band * i + (band - barW) / 2;
            const describe = (
              <>
                <TipRows
                  title={p.title}
                  rows={[
                    { label: t("tone"), value: p.tone },
                    { label: t("tension, out of 5"), value: String(p.tension) },
                    { label: t("mood, from −2 to +2"), value: p.valence > 0 ? `+${p.valence}` : String(p.valence).replace("-", "−") },
                  ]}
                />
                <div className="tip-text">{p.summary}</div>
              </>
            );
            const moodHgt = Math.abs(p.valence) * moodUnit;
            return (
              <g
                key={p.label}
                tabIndex={0}
                className="hit"
                aria-label={`${p.title}: ${p.tone}, tension ${p.tension} of 5, mood ${p.valence}`}
                onPointerMove={(e) => (setActive(i), show(e, describe))}
                onPointerLeave={() => (setActive(null), hide())}
                onFocus={(e) => (setActive(i), show(e, describe))}
                onBlur={() => (setActive(null), hide())}
              >
                <rect x={m.left + band * i} y={tensionTop} width={band} height={moodTop + moodH - tensionTop + 22} className={active === i ? "wash on" : "wash"} />
                <path d={barPath(x, tensionY(p.tension), barW, tensionY(0) - tensionY(p.tension))} className="tone-tension" />
                {p.valence > 0 && <path d={barPath(x, moodZero - moodHgt, barW, moodHgt)} className="tone-up" />}
                {p.valence < 0 && <path d={barPath(x, moodZero, barW, moodHgt, true)} className="tone-down" />}
                {p.valence === 0 && <rect x={x} y={moodZero - 1.5} width={barW} height={3} className="tone-flat" />}
                {i % every === 0 && (
                  <text x={m.left + band * (i + 0.5)} y={moodTop + moodH + 16} textAnchor="middle" className="tick">
                    {p.label}
                  </text>
                )}
              </g>
            );
          })}
          <text x={m.left + innerW / 2} y={height - 4} textAnchor="middle" className="axis-title">
            {t("Scene")}
          </text>
        </svg>
      )}
      <ul className="legend">
        <li>
          <span className="swatch tone-up" />
          {t("Lighter mood")}
        </li>
        <li>
          <span className="swatch tone-down" />
          {t("Darker mood")}
        </li>
      </ul>
      <TipBox tip={tip} />
    </div>
  );
}

/** Close a menu or panel when the user clicks elsewhere or presses Escape. */
export function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}
