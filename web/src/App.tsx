import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { analyzeScript, exportUrl, extractElements, getScript, getStatus, listScripts, saveSceneElements, uploadScript } from "./api";
import Chat from "./Chat";
import { ChartCard, Heatmap, RankedBars, SegmentedBar, StackedColumns, ToneChart, useDismiss } from "./charts";
import { count, eighths, percent, plural, stripColor, titleCase } from "./format";
import SceneSheet from "./SceneSheet";
import type { Analysis, Breakdown, Category, Element, Elements, Issue, Script, Status } from "./types";

type Panel = { kind: "chat" } | { kind: "scene"; number: string } | null;

const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--series-5)", "var(--series-6)"];
const OTHER = "var(--series-other)";

// Chronological order, each with a fixed colour that follows the category.
const DAY_NIGHT = [
  { key: "DAWN", name: "Dawn", color: "var(--series-3)", ink: "#ffffff" },
  { key: "DAY", name: "Day", color: "var(--series-4)", ink: "#0b0b0b" },
  { key: "DUSK", name: "Dusk", color: "var(--series-5)", ink: "#ffffff" },
  { key: "NIGHT", name: "Night", color: "var(--series-1)", ink: "#ffffff" },
];
const INT_EXT = [
  { key: "INT", name: "Interior", color: "var(--series-1)", ink: "#ffffff" },
  { key: "EXT", name: "Exterior", color: "var(--series-2)", ink: "#ffffff" },
  { key: "INT/EXT", name: "Int./Ext.", color: "var(--series-3)", ink: "#ffffff" },
];

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [script, setScript] = useState<Script | null>(null);
  const [loading, setLoading] = useState<string | null>("Loading…");
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [panel, setPanel] = useState<Panel>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const [s, scripts] = await Promise.all([getStatus(), listScripts()]);
        setStatus(s);
        // `slugline serve script.fountain` starts with a script already loaded.
        if (scripts.length) setScript(await getScript(scripts[scripts.length - 1].id));
      } catch {
        setError("Could not reach the Slugline server. Is `slugline serve` running?");
      } finally {
        setLoading(null);
      }
    })();
  }, []);

  const open = useCallback(async (file: File) => {
    setError(null);
    setLoading(`Reading ${file.name}…`);
    try {
      setScript(await uploadScript(file));
      setPanel(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read that file.");
    } finally {
      setLoading(null);
    }
  }, []);

  const analyze = useCallback(
    async (refresh = false) => {
      if (!script) return;
      setError(null);
      setAnalyzing(true);
      try {
        const analysis = await analyzeScript(script.id, refresh);
        setScript((current) => (current && current.id === script.id ? { ...current, analysis } : current));
      } catch (e) {
        setError(e instanceof Error ? e.message : "The analysis failed.");
      } finally {
        setAnalyzing(false);
      }
    },
    [script],
  );

  const extract = useCallback(async () => {
    if (!script) return;
    setError(null);
    setExtracting(true);
    try {
      const elements = await extractElements(script.id);
      setScript((current) => (current && current.id === script.id ? { ...current, elements } : current));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The element breakdown failed.");
    } finally {
      setExtracting(false);
    }
  }, [script]);

  const saveScene = useCallback(
    async (number: string, items: Element[]) => {
      if (!script) return;
      const elements = await saveSceneElements(script.id, number, items);
      setScript((current) => (current && current.id === script.id ? { ...current, elements } : current));
    },
    [script],
  );

  const categories = status?.categories ?? [];

  return (
    <div
      className={`app${panel && script ? " with-panel" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) void open(file);
      }}
    >
      <input
        ref={fileInput}
        type="file"
        accept=".fountain,.spmd,.txt,.pdf"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void open(file);
          e.target.value = "";
        }}
      />
      <header className="topbar">
        <div className="brand">
          <span className="wordmark">Slugline</span>
          {script && (
            <span className="doc">
              <strong>{script.breakdown.title ?? script.filename}</strong>
              {script.breakdown.title && <span>{script.filename}</span>}
            </span>
          )}
        </div>
        <nav className="actions">
          <button className="ghost" onClick={() => fileInput.current?.click()}>
            Open script
          </button>
          {script && <ExportMenu script={script} status={status} />}
          {script && (
            <button className="primary" aria-pressed={panel?.kind === "chat"} onClick={() => setPanel(panel?.kind === "chat" ? null : { kind: "chat" })}>
              Ask the script
            </button>
          )}
        </nav>
      </header>

      <main className={loading && script ? "stale" : undefined}>
        {error && (
          <div className="banner" role="alert">
            <span>{error}</span>
            <button className="ghost small" onClick={() => setError(null)}>
              Dismiss
            </button>
          </div>
        )}
        {script ? (
          <Dashboard
            script={script}
            status={status}
            analyzing={analyzing}
            onAnalyze={analyze}
            extracting={extracting}
            onExtract={extract}
            onOpenScene={(number) => setPanel({ kind: "scene", number })}
          />
        ) : (
          <div className="empty">
            {loading ? (
              <p>{loading}</p>
            ) : (
              <>
                <h1>Break down a screenplay</h1>
                <p>Drop a Fountain or PDF script anywhere on this page. It stays on this computer.</p>
                <button className="primary" onClick={() => fileInput.current?.click()}>
                  Choose a file
                </button>
              </>
            )}
          </div>
        )}
      </main>

      {script && panel?.kind === "chat" && (
        <Chat scriptId={script.id} title={script.breakdown.title ?? script.filename} status={status} onClose={() => setPanel(null)} />
      )}
      {script && panel?.kind === "scene" && (
        <SceneSheet
          script={script}
          number={panel.number}
          categories={categories}
          onNavigate={(number) => setPanel({ kind: "scene", number })}
          onClose={() => setPanel(null)}
          onSave={saveScene}
        />
      )}
      {dragging && <div className="drop-veil">Drop the script to open it</div>}
    </div>
  );
}

function ExportMenu({ script, status }: { script: Script; status: Status | null }) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(
    open,
    useCallback(() => setOpen(false), []),
  );
  const hasElements = (script.elements?.totals.length ?? 0) > 0;
  const items = [
    ["scenes.csv", "Scenes (CSV)"],
    ...(hasElements ? [["elements.csv", "Elements by scene (CSV)"]] : []),
    ["characters.csv", "Characters (CSV)"],
    ["locations.csv", "Locations (CSV)"],
    ["script.fountain", "Script (Fountain)"],
  ];
  return (
    <div className="menu" ref={ref}>
      <button className="ghost" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        Export
      </button>
      {open && (
        <div className="menu-list" role="menu">
          {status?.pdf_export ? (
            <>
              <a role="menuitem" href={exportUrl(script.id, "report.pdf")} download onClick={() => setOpen(false)}>
                Production report (PDF)
              </a>
              <a role="menuitem" href={exportUrl(script.id, "breakdown-sheets.pdf")} download onClick={() => setOpen(false)}>
                Breakdown sheets, one per scene (PDF)
              </a>
            </>
          ) : (
            <span className="menu-off" title="Install it with: pip install 'slugline[export]'">
              Production report (PDF) needs reportlab
            </span>
          )}
          {items.map(([name, label]) => (
            <a key={name} role="menuitem" href={exportUrl(script.id, name)} download onClick={() => setOpen(false)}>
              {label}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function Dashboard(props: {
  script: Script;
  status: Status | null;
  analyzing: boolean;
  onAnalyze: (refresh?: boolean) => void;
  extracting: boolean;
  onExtract: () => void;
  onOpenScene: (number: string) => void;
}) {
  const { script, status, analyzing } = props;
  const b = script.breakdown;
  const analysis = script.analysis;
  const notes = useMemo(() => new Map((analysis?.scenes ?? []).map((n) => [n.number, n])), [analysis]);
  const issues = useMemo(() => [...script.issues, ...(analysis?.issues ?? [])], [script.issues, analysis]);
  const totalEighths = b.scenes.reduce((sum, s) => sum + s.eighths, 0);
  const totalWords = b.characters.reduce((sum, c) => sum + c.words, 0);

  return (
    <>
      <section className="tiles">
        <Tile label="Scenes" value={count(b.scene_count)} />
        <Tile label="Pages, estimated" value={b.page_count.toFixed(1)} />
        <Tile label="Speaking characters" value={count(b.characters.length)} />
        <Tile label="Locations" value={count(b.locations.length)} />
      </section>

      <Story analysis={analysis} status={status} analyzing={analyzing} onAnalyze={props.onAnalyze} />

      <div className="grid">
        <ChartCard
          title="Day and night"
          subtitle={`Share of the ${eighths(totalEighths)} pages. Scenes marked LATER or CONTINUOUS count with the scene before.`}
          table={splitTable(b, "day_night", DAY_NIGHT)}
        >
          <SegmentedBar parts={split(b, "day_night", DAY_NIGHT)} total={`${eighths(totalEighths)} pages`} />
        </ChartCard>
        <ChartCard title="Interior and exterior" subtitle={`Share of the ${eighths(totalEighths)} pages.`} table={splitTable(b, "int_ext", INT_EXT)}>
          <SegmentedBar parts={split(b, "int_ext", INT_EXT)} total={`${eighths(totalEighths)} pages`} />
        </ChartCard>
      </div>

      <Stripboard breakdown={b} notes={notes} elements={script.elements} onOpenScene={props.onOpenScene} />

      <ElementsCard
        breakdown={b}
        elements={script.elements}
        categories={status?.categories ?? []}
        available={status?.llm.available ?? false}
        reason={status?.llm.reason ?? ""}
        extracting={props.extracting}
        onExtract={props.onExtract}
        onOpenScene={props.onOpenScene}
      />

      <div className="grid">
        <WhoSpeaks breakdown={b} />
        <ChartCard
          title="Dialogue share"
          subtitle={`Words spoken by each character, out of ${count(totalWords)}.`}
          table={{
            columns: ["Character", "Words", "Share", "Cues", "Scenes"],
            rows: b.characters.map((c) => [c.name, c.words, percent(c.words, totalWords), c.dialogue_blocks, c.scenes.length]),
          }}
        >
          <RankedBars
            color={SERIES[0]}
            rows={b.characters.slice(0, 14).map((c) => ({
              name: titleCase(c.name),
              value: c.words,
              label: `${count(c.words)} · ${percent(c.words, totalWords)}`,
              detail: `words in ${plural(c.dialogue_blocks, "cue")}, ${plural(c.scenes.length, "scene")}`,
            }))}
          />
          {b.characters.length > 14 && <p className="more">{b.characters.length - 14} more in the table view.</p>}
        </ChartCard>
        <Presence breakdown={b} />
        <Tone breakdown={b} analysis={analysis} />
      </div>

      <div className="grid">
        <ChartCard
          title="Locations"
          subtitle="Pages to shoot at each one."
          table={{
            columns: ["Location", "Scenes", "Length (pages)", "Scene numbers"],
            rows: b.locations.map((l) => [l.location, l.scenes.length, eighths(l.eighths), l.scenes.join(", ")]),
          }}
        >
          <RankedBars
            color={SERIES[0]}
            rows={b.locations.slice(0, 14).map((l) => ({
              name: titleCase(l.location),
              value: l.eighths,
              label: `${eighths(l.eighths)} · ${plural(l.scenes.length, "scene")}`,
              detail: `pages, in scene${l.scenes.length > 1 ? "s" : ""} ${l.scenes.join(", ")}`,
            }))}
          />
          {b.locations.length > 14 && <p className="more">{b.locations.length - 14} more in the table view.</p>}
        </ChartCard>
        <Issues issues={issues} analyzed={analysis !== null} />
      </div>
    </>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
    </div>
  );
}

type Part = { key: string; name: string; color: string; ink: string };

function eighthsBy(b: Breakdown, field: "day_night" | "int_ext"): Map<string, { eighths: number; scenes: number }> {
  const totals = new Map<string, { eighths: number; scenes: number }>();
  for (const s of b.scenes) {
    const key = s[field] ?? "?";
    const entry = totals.get(key) ?? { eighths: 0, scenes: 0 };
    entry.eighths += s.eighths;
    entry.scenes += 1;
    totals.set(key, entry);
  }
  return totals;
}

function split(b: Breakdown, field: "day_night" | "int_ext", parts: Part[]) {
  const totals = eighthsBy(b, field);
  const known = parts.map((p) => ({ ...p, value: totals.get(p.key)?.eighths ?? 0 }));
  const rest = [...totals].filter(([key]) => !parts.some((p) => p.key === key)).reduce((sum, [, v]) => sum + v.eighths, 0);
  return [...known, { key: "?", name: "Not stated", color: OTHER, ink: "#0b0b0b", value: rest }].map((p) => ({
    ...p,
    label: `${eighths(p.value)} pages`,
  }));
}

function splitTable(b: Breakdown, field: "day_night" | "int_ext", parts: Part[]) {
  const totals = eighthsBy(b, field);
  const names = new Map(parts.map((p) => [p.key, p.name]));
  return {
    columns: ["", "Scenes", "Length (pages)"],
    rows: [...totals].map(([key, v]) => [names.get(key) ?? "Not stated", v.scenes, eighths(v.eighths)]),
  };
}

function Story(props: { analysis: Analysis | null; status: Status | null; analyzing: boolean; onAnalyze: (refresh?: boolean) => void }) {
  const { analysis, status, analyzing } = props;
  const available = status?.llm.available ?? false;
  if (!analysis) {
    return (
      <section className="card story">
        <div>
          <h3>Story notes</h3>
          <p>
            Claude can read the script and add a logline, a synopsis, a summary and emotional tone for every scene, and a
            proofread of the formatting.
          </p>
          {!available && <p className="notice">{status?.llm.reason || "The AI features are not available."}</p>}
        </div>
        <button className="primary" disabled={!available || analyzing} onClick={() => props.onAnalyze()}>
          {analyzing ? "Reading the script… about a minute" : "Analyze the script"}
        </button>
      </section>
    );
  }
  return (
    <section className={`card story done${analyzing ? " stale" : ""}`}>
      <div>
        <h3>Story notes</h3>
        <p className="logline">{analysis.logline}</p>
        <p>{analysis.synopsis}</p>
        {analysis.themes.length > 0 && (
          <ul className="themes">
            {analysis.themes.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        )}
        <p className="fine">
          Written by {analysis.model}. Check it against the script before it goes on a call sheet.{" "}
          <button className="link" disabled={!available || analyzing} onClick={() => props.onAnalyze(true)}>
            {analyzing ? "Analyzing again…" : "Analyze again"}
          </button>
        </p>
      </div>
    </section>
  );
}

function Stripboard(props: {
  breakdown: Breakdown;
  notes: Map<string, { summary: string; tone: string }>;
  elements: Elements | null;
  onOpenScene: (number: string) => void;
}) {
  const { breakdown: b, notes, elements } = props;
  return (
    <section className="card">
      <header className="card-head">
        <div>
          <h3>Stripboard</h3>
          <p>Every scene in script order, lengths in pages and eighths. Open a scene for its breakdown sheet.</p>
        </div>
        <ul className="legend strips">
          {[
            ["INT", "DAY", "Int. day"],
            ["EXT", "DAY", "Ext. day"],
            ["INT", "NIGHT", "Int. night"],
            ["EXT", "NIGHT", "Ext. night"],
            ["INT", "DAWN", "Dawn"],
            ["INT", "DUSK", "Dusk"],
          ].map(([ie, dn, label]) => (
            <li key={label}>
              <span className="swatch strip" style={{ background: stripColor(ie, dn) }} />
              {label}
            </li>
          ))}
        </ul>
      </header>
      <div className="table-scroll">
        <table className="data board">
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Scene</th>
              <th className="num">Length</th>
              <th className="num">Starts p.</th>
              <th>Cast</th>
              <th className="num">Elements</th>
              {notes.size > 0 && <th>Tone</th>}
            </tr>
          </thead>
          <tbody>
            {b.scenes.map((s) => {
              const note = notes.get(s.number);
              return (
                <tr key={s.number}>
                  <td className="num strip-cell">
                    <span className="strip-tab" style={{ background: stripColor(s.int_ext, s.day_night) }} />
                    {s.number}
                  </td>
                  <td>
                    <button className="slug slug-button" onClick={() => props.onOpenScene(s.number)}>
                      {s.heading}
                    </button>
                    {note && <span className="summary">{note.summary}</span>}
                  </td>
                  <td className="num">{eighths(s.eighths)}</td>
                  <td className="num">{Math.floor(s.start_page)}</td>
                  <td className="cast">
                    {s.characters.map(titleCase).join(", ") || "–"}
                    {s.silent.length > 0 && <span className="silent"> · no lines: {s.silent.map(titleCase).join(", ")}</span>}
                  </td>
                  <td className="num">{elements?.scenes[s.number]?.length || "–"}</td>
                  {notes.size > 0 && <td className="tone">{note?.tone ?? "–"}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function WhoSpeaks({ breakdown: b }: { breakdown: Breakdown }) {
  // The six characters with most words keep a colour each; the rest fold into "Other".
  const lead = b.characters.slice(0, SERIES.length).map((c) => c.name);
  const hasOther = b.characters.length > lead.length;
  const series = [...lead.map((name, i) => ({ name: titleCase(name), color: SERIES[i] })), ...(hasOther ? [{ name: "Other", color: OTHER }] : [])];
  const columns = b.scenes.map((s) => {
    const values = lead.map((name) => s.words[name] ?? 0);
    if (hasOther) {
      values.push(Object.entries(s.words).reduce((sum, [name, w]) => (lead.includes(name) ? sum : sum + w), 0));
    }
    return { label: s.number, title: `${s.number}. ${s.heading}`, values };
  });
  return (
    <ChartCard
      title="Who speaks in each scene"
      subtitle="Words of dialogue per scene, by character."
      table={{
        columns: ["Scene", ...series.map((s) => s.name)],
        rows: columns.map((c) => [c.title, ...c.values]),
      }}
    >
      <StackedColumns columns={columns} series={series} unit="words" xTitle="Scene" />
    </ChartCard>
  );
}

function Presence({ breakdown: b }: { breakdown: Breakdown }) {
  const cast = b.characters.slice(0, 16);
  const rows = cast.map((c) => ({
    name: titleCase(c.name),
    cells: b.scenes.map((s) => ({ value: s.words[c.name] ?? 0, marked: s.silent.includes(c.name) })),
  }));
  return (
    <ChartCard
      title="Character presence"
      subtitle="Who is in which scene, and how much they say there."
      table={{
        columns: ["Character", "Speaks in scenes", "Named without lines in"],
        rows: b.characters.map((c) => [c.name, c.scenes.join(", ") || "–", c.silent_scenes.join(", ") || "–"]),
      }}
    >
      <Heatmap
        rows={rows}
        columns={b.scenes.map((s) => ({ label: s.number, title: `${s.number}. ${s.heading}` }))}
        unit="words"
        markedLabel="named in the action, no lines"
      />
      {b.characters.length > cast.length && <p className="more">{b.characters.length - cast.length} more in the table view.</p>}
    </ChartCard>
  );
}

function Tone({ breakdown: b, analysis }: { breakdown: Breakdown; analysis: Analysis | null }) {
  if (!analysis || analysis.scenes.length === 0) {
    return (
      <section className="card placeholder">
        <h3>Tone across the story</h3>
        <p>Tension and mood, scene by scene. It appears here once the script has been analyzed.</p>
      </section>
    );
  }
  const notes = new Map(analysis.scenes.map((n) => [n.number, n]));
  const points = b.scenes.map((s) => {
    const n = notes.get(s.number);
    return n ? { label: s.number, title: `${s.number}. ${s.heading}`, tone: n.tone, tension: n.tension, valence: n.valence, summary: n.summary } : null;
  });
  return (
    <ChartCard
      title="Tone across the story"
      subtitle="Claude's reading of each scene, scored against the rest of this script."
      table={{
        columns: ["Scene", "Tone", "Tension (1–5)", "Mood (−2 to +2)"],
        rows: b.scenes.map((s) => {
          const n = notes.get(s.number);
          return [`${s.number}. ${s.heading}`, n?.tone ?? "–", n?.tension ?? "–", n?.valence ?? "–"];
        }),
      }}
    >
      <ToneChart points={points} />
    </ChartCard>
  );
}

function Issues({ issues, analyzed }: { issues: Issue[]; analyzed: boolean }) {
  return (
    <section className="card">
      <header className="card-head">
        <div>
          <h3>Formatting notes</h3>
          <p>{analyzed ? "From the rule-based checks and Claude's proofread." : "From the rule-based checks. Analyzing the script adds a proofread."}</p>
        </div>
      </header>
      {issues.length === 0 ? (
        <p className="clean">Nothing to fix: headings, cues and numbering all look consistent.</p>
      ) : (
        <ul className="issues">
          {issues.map((issue, i) => (
            <li key={i}>
              <span className={`badge ${issue.severity}`}>
                <span aria-hidden="true">{issue.severity === "warning" ? "▲" : "●"}</span>
                {issue.severity === "warning" ? "Fix" : "Note"}
              </span>
              <span className="issue-text">
                {issue.scene && <strong>Scene {issue.scene}. </strong>}
                {issue.message}
                {issue.source === "ai" && <span className="source"> Found by Claude.</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ElementsCard(props: {
  breakdown: Breakdown;
  elements: Elements | null;
  categories: Category[];
  available: boolean;
  reason: string;
  extracting: boolean;
  onExtract: () => void;
  onOpenScene: (number: string) => void;
}) {
  const { elements, categories } = props;
  const [filter, setFilter] = useState<string | null>(null);
  const totals = elements?.totals ?? [];
  const byKey = new Map(categories.map((c) => [c.key, c]));
  const counts = new Map<string, number>();
  for (const t of totals) counts.set(t.category, (counts.get(t.category) ?? 0) + 1);
  const shown = filter ? totals.filter((t) => t.category === filter) : totals;
  const suggested = Object.values(elements?.scenes ?? {}).flat().filter((e) => e.source === "ai").length;
  const first = props.breakdown.scenes[0]?.number;

  const action = (
    <button className={totals.length ? "ghost" : "primary"} disabled={!props.available || props.extracting} onClick={props.onExtract}>
      {props.extracting ? "Breaking down the script… about a minute" : totals.length ? "Suggest again with AI" : "Suggest elements with AI"}
    </button>
  );

  return (
    <section className={`card${props.extracting ? " busy" : ""}`}>
      <header className="card-head">
        <div>
          <h3>Elements</h3>
          <p>
            What each department needs, scene by scene: extras, stunts, props, wardrobe, makeup, vehicles, effects and more.
            {totals.length > 0 && " Suggesting again keeps everything you added or edited by hand."}
          </p>
        </div>
        {action}
      </header>

      {totals.length === 0 ? (
        <div className="elements-empty">
          <p>
            No elements yet. Claude can read the script and suggest them for every scene, or you can open a scene and add them by
            hand.
          </p>
          {!props.available && <p className="notice">{props.reason || "The AI features are not available."} Adding by hand still works.</p>}
          {first && (
            <button className="ghost" onClick={() => props.onOpenScene(first)}>
              Open scene {first}
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="filters" role="group" aria-label="Filter by department">
            <button className="chip" aria-pressed={filter === null} onClick={() => setFilter(null)}>
              All <span>{totals.length}</span>
            </button>
            {categories
              .filter((c) => counts.has(c.key))
              .map((c) => (
                <button key={c.key} className="chip" aria-pressed={filter === c.key} onClick={() => setFilter(filter === c.key ? null : c.key)}>
                  <span className="swatch" style={{ background: c.color }} />
                  {c.label} <span>{counts.get(c.key)}</span>
                </button>
              ))}
          </div>
          <div className="table-scroll">
            <table className="data elements">
              <thead>
                <tr>
                  <th>Element</th>
                  <th>Department</th>
                  <th>Scenes</th>
                  <th className="num">Pages</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((t) => {
                  const category = byKey.get(t.category);
                  return (
                    <tr key={`${t.category}|${t.name}`}>
                      <td className="element-name">{t.name}</td>
                      <td className="dept-cell">
                        <span className="swatch" style={{ background: category?.color }} />
                        {category?.label ?? t.category}
                      </td>
                      <td>
                        <span className="scene-links">
                          {t.scenes.map((n) => (
                            <button key={n} className="scene-link" onClick={() => props.onOpenScene(n)} aria-label={`Open scene ${n}`}>
                              {n}
                            </button>
                          ))}
                        </span>
                      </td>
                      <td className="num">{eighths(t.eighths)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {suggested > 0 && (
            <p className="fine">
              {plural(suggested, "element")} still as Claude suggested them. Open a scene to check, edit or remove them before you print the
              breakdown sheets.
            </p>
          )}
        </>
      )}
    </section>
  );
}
