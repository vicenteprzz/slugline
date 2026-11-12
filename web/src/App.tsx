import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  analyzeScript,
  clearElements,
  exportUrl,
  extractElements,
  getScript,
  getSettings,
  getStatus,
  listScripts,
  openExample,
  removeScript,
  saveSceneElements,
  saveSettings,
  uploadScript,
} from "./api";
import Chat from "./Chat";
import { ChartCard, Heatmap, RankedBars, SegmentedBar, StackedColumns, ToneChart, useDismiss } from "./charts";
import { count, eighths, percent, plural, stripColor, titleCase } from "./format";
import { type Language, initialLanguage, language, setLanguage, t } from "./i18n";
import SceneSheet from "./SceneSheet";
import ScheduleBoard, { CastCard, CrewCard } from "./ScheduleBoard";
import SettingsPanel from "./SettingsPanel";
import type { Analysis, Breakdown, Category, Element, Elements, Issue, LibraryEntry, LicenseStatus, Schedule, Script, Settings, Status } from "./types";

type Panel = { kind: "chat" } | { kind: "scene"; number: string } | { kind: "settings" } | null;

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

/** The script id in the address (#/scripts/<id>), so a reload or the back button keeps your place. */
const routeId = () => location.hash.match(/^#\/scripts\/(\w+)/)?.[1] ?? null;
const goTo = (id: string | null) => {
  location.hash = id ? `#/scripts/${id}` : "#/";
};

export default function App() {
  const [lang, setLang] = useState<Language>(() => {
    const initial = initialLanguage(null);
    setLanguage(initial);
    return initial;
  });
  const [status, setStatus] = useState<Status | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [library, setLibrary] = useState<LibraryEntry[] | null>(null);
  const [route, setRoute] = useState(routeId);
  const [script, setScript] = useState<Script | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [panel, setPanel] = useState<Panel>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const changeLanguage = useCallback((next: Language, save = true) => {
    setLanguage(next);
    setLang(next);
    if (save) void saveSettings({ language: next }).then(setSettings).catch(() => {});
  }, []);

  const refreshStatus = useCallback(async () => {
    const [s, conf] = await Promise.all([getStatus(), getSettings()]);
    setStatus(s);
    setSettings(conf);
    return conf;
  }, []);

  useEffect(() => {
    refreshStatus()
      .then((conf) => conf.language && changeLanguage(initialLanguage(conf.language), false))
      .catch(() => setError(t("Could not reach the Slugline server. Is it running?")));
    const onHash = () => setRoute(routeId());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [refreshStatus, changeLanguage]);

  // Follow the address: a script id opens that script, no id shows the library.
  useEffect(() => {
    if (!route) {
      setScript(null);
      setPanel(null);
      listScripts()
        .then(setLibrary)
        .catch(() => setLibrary([]));
      return;
    }
    if (script?.id === route) return;
    setLoading(t("Opening the script…"));
    getScript(route)
      .then((s) => {
        setScript(s);
        setPanel(null);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : t("Could not open that script."));
        goTo(null);
      })
      .finally(() => setLoading(null));
  }, [route]); // eslint-disable-line react-hooks/exhaustive-deps

  const show = useCallback((opened: Script) => {
    setScript(opened);
    setPanel(null);
    goTo(opened.id);
  }, []);

  const open = useCallback(
    async (file: File) => {
      setError(null);
      setLoading(t("Reading {name}…", { name: file.name }));
      try {
        show(await uploadScript(file));
        void refreshStatus();
      } catch (e) {
        setError(e instanceof Error ? e.message : t("Could not read that file."));
      } finally {
        setLoading(null);
      }
    },
    [show, refreshStatus],
  );

  const tryExample = useCallback(async () => {
    setError(null);
    setLoading(t("Opening the example…"));
    try {
      show(await openExample("johns-boys"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("Could not open the example."));
    } finally {
      setLoading(null);
    }
  }, [show]);

  const update = useCallback(
    (id: string, change: Partial<Script>) => setScript((current) => (current && current.id === id ? { ...current, ...change } : current)),
    [],
  );

  const analyze = useCallback(
    async (refresh = false) => {
      if (!script) return;
      setError(null);
      setAnalyzing(true);
      try {
        update(script.id, { analysis: await analyzeScript(script.id, refresh) });
      } catch (e) {
        setError(e instanceof Error ? e.message : t("The analysis failed."));
      } finally {
        setAnalyzing(false);
      }
    },
    [script, update],
  );

  const extract = useCallback(async () => {
    if (!script) return;
    setError(null);
    setExtracting(true);
    try {
      update(script.id, { elements: await extractElements(script.id) });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("The element breakdown failed."));
    } finally {
      setExtracting(false);
    }
  }, [script, update]);

  const saveScene = useCallback(
    async (number: string, items: Element[]) => {
      if (!script) return;
      update(script.id, { elements: await saveSceneElements(script.id, number, items) });
    },
    [script, update],
  );

  const clear = useCallback(async () => {
    if (!script) return;
    setError(null);
    try {
      update(script.id, { elements: await clearElements(script.id) });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("The breakdown could not be cleared."));
    }
  }, [script, update]);

  const categories = status?.categories ?? [];

  return (
    <div
      className={`app${panel ? " with-panel" : ""}`}
      data-lang={lang}
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
        accept=".fountain,.spmd,.txt,.fdx,.pdf"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void open(file);
          e.target.value = "";
        }}
      />
      <header className="topbar">
        <div className="brand">
          <a className="wordmark" href="#/" title={t("Your scripts")}>
            Slugline
          </a>
          {script && (
            <span className="doc">
              <strong>{script.breakdown.title ?? script.filename}</strong>
              {script.breakdown.title && <span>{script.filename}</span>}
            </span>
          )}
        </div>
        <nav className="actions">
          {script && (
            <a className="ghost button-link nav-link" href="#/">
              {t("Scripts")}
            </a>
          )}
          <button className="ghost" onClick={() => fileInput.current?.click()}>
            {t("Open script")}
          </button>
          {script && <ExportMenu script={script} status={status} />}
          <button
            className="ghost"
            aria-pressed={panel?.kind === "settings"}
            onClick={() => setPanel(panel?.kind === "settings" ? null : { kind: "settings" })}
          >
            {t("Settings")}
          </button>
          <button className="ghost lang" onClick={() => changeLanguage(lang === "es" ? "en" : "es")} title={t("Change language")}>
            {lang === "es" ? "EN" : "ES"}
          </button>
          {script && (
            <button className="primary" aria-pressed={panel?.kind === "chat"} onClick={() => setPanel(panel?.kind === "chat" ? null : { kind: "chat" })}>
              {t("Ask the script")}
            </button>
          )}
        </nav>
      </header>

      <main className={loading && script ? "stale" : undefined}>
        {error && (
          <div className="banner" role="alert">
            <span>{error}</span>
            <button className="ghost small" onClick={() => setError(null)}>
              {t("Dismiss")}
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
            onClearElements={clear}
            onScheduleChange={(schedule) => update(script.id, { schedule })}
            onError={setError}
            onOpenScene={(number) => setPanel({ kind: "scene", number })}
            onOpenSettings={() => setPanel({ kind: "settings" })}
          />
        ) : route || loading ? (
          <div className="empty">
            <p>{loading ?? t("Opening the script…")}</p>
          </div>
        ) : (
          <Home
            library={library}
            license={status?.license ?? null}
            onOpenSettings={() => setPanel({ kind: "settings" })}
            onPick={() => fileInput.current?.click()}
            onExample={tryExample}
            onRemove={async (entry) => {
              if (!window.confirm(t("Remove “{name}” from your scripts? The file on your computer is not touched.", { name: entry.title ?? entry.filename })))
                return;
              try {
                await removeScript(entry.id);
                setLibrary((list) => (list ?? []).filter((e) => e.id !== entry.id));
                void refreshStatus();
              } catch (e) {
                setError(e instanceof Error ? e.message : t("Could not remove it."));
              }
            }}
          />
        )}
      </main>

      {panel?.kind === "settings" && (
        <SettingsPanel
          settings={settings}
          license={status?.license ?? null}
          language={lang}
          onLanguage={(next) => changeLanguage(next)}
          onSaved={async () => {
            await refreshStatus();
          }}
          onClose={() => setPanel(null)}
        />
      )}
      {script && panel?.kind === "chat" && (
        <Chat
          scriptId={script.id}
          title={script.breakdown.title ?? script.filename}
          status={status}
          onClose={() => setPanel(null)}
          onOpenSettings={() => setPanel({ kind: "settings" })}
        />
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
      {dragging && <div className="drop-veil">{t("Drop the script to open it")}</div>}
    </div>
  );
}

function Home(props: {
  library: LibraryEntry[] | null;
  license: LicenseStatus | null;
  onOpenSettings: () => void;
  onPick: () => void;
  onExample: () => void;
  onRemove: (entry: LibraryEntry) => void;
}) {
  const { library } = props;
  const date = (iso: string) =>
    new Date(iso).toLocaleDateString(language() === "es" ? "es-ES" : "en-GB", { day: "numeric", month: "short", year: "numeric" });
  return (
    <div className="home">
      <section className="hero">
        <h1>{t("From screenplay to shooting schedule")}</h1>
        <p>
          {t(
            "Open a script and Slugline breaks it down: scenes, cast, locations and every department's elements, a shooting schedule, call sheets and the cast's day out of days. Your scripts stay on this computer.",
          )}
        </p>
        <div className="hero-actions">
          <button className="primary" onClick={props.onPick}>
            {t("Open a script")}
          </button>
          <button className="ghost" onClick={props.onExample}>
            {t("Try it with an example script")}
          </button>
        </div>
        <p className="fine">{t("Fountain, Final Draft (.fdx) and PDF. You can also drop the file anywhere on this page.")}</p>
        {props.license && !props.license.licensed && (
          <p className="trial">
            {t("Trial version · {used} of {n} scripts.", {
              used: Math.min(props.license.scripts, props.license.free_scripts),
              n: props.license.free_scripts,
            })}{" "}
            <button className="link" onClick={props.onOpenSettings}>
              {t("Activate a licence")}
            </button>
          </p>
        )}
      </section>

      {library && library.length > 0 && (
        <section className="card">
          <header className="card-head">
            <div>
              <h3>{t("Your scripts")}</h3>
              <p>{t("Everything you did on each one is saved: breakdown, schedule, cast and notes.")}</p>
            </div>
          </header>
          <ul className="library">
            {library.map((entry) => (
              <li key={entry.id}>
                <a className="library-open" href={`#/scripts/${entry.id}`}>
                  <strong>{entry.title ?? entry.filename}</strong>
                  <span>
                    {entry.title ? `${entry.filename} · ` : ""}
                    {plural(entry.scenes, "scene")} · {t("opened {date}", { date: date(entry.opened_at) })}
                  </span>
                </a>
                <button className="item-remove" aria-label={t("Remove {name}", { name: entry.title ?? entry.filename })} onClick={() => props.onRemove(entry)}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
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
  const hasSchedule = (script.schedule?.days.length ?? 0) > 0;
  const pdfs = [
    ["report.pdf", "Production report (PDF)"],
    ["breakdown-sheets.pdf", "Breakdown sheets, one per scene (PDF)"],
    ...(hasSchedule
      ? [
          ["schedule.pdf", "Shooting schedule (PDF)"],
          ["call-sheets.pdf", "Call sheets, every day (PDF)"],
        ]
      : []),
  ];
  const tables = [
    ...(hasSchedule
      ? [
          ["schedule.csv", "Shooting schedule (CSV)"],
          ["day-out-of-days.csv", "Day out of days (CSV)"],
        ]
      : []),
    ["scenes.csv", "Scenes (CSV)"],
    ...(hasElements ? [["elements.csv", "Elements by scene (CSV)"]] : []),
    ["characters.csv", "Characters (CSV)"],
    ["locations.csv", "Locations (CSV)"],
    ["script.fountain", "Script (Fountain)"],
  ];
  const link = ([name, label]: string[]) => (
    <a key={name} role="menuitem" href={exportUrl(script.id, name)} download onClick={() => setOpen(false)}>
      {t(label)}
    </a>
  );
  return (
    <div className="menu" ref={ref}>
      <button className="ghost" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        {t("Export")}
      </button>
      {open && (
        <div className="menu-list" role="menu">
          {status?.pdf_export ? pdfs.map(link) : <span className="menu-off">{t("PDF exports need reportlab: pip install 'slugline[export]'")}</span>}
          {tables.map(link)}
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
  onClearElements: () => void;
  onScheduleChange: (schedule: Schedule | null) => void;
  onError: (message: string) => void;
  onOpenScene: (number: string) => void;
  onOpenSettings: () => void;
}) {
  const { script, status, analyzing } = props;
  const b = script.breakdown;
  const analysis = script.analysis;
  const notes = useMemo(() => new Map((analysis?.scenes ?? []).map((n) => [n.number, n])), [analysis]);
  const issues = useMemo(() => [...script.issues, ...(analysis?.issues ?? [])], [script.issues, analysis]);
  const totalEighths = b.scenes.reduce((sum, s) => sum + s.eighths, 0);
  const totalWords = b.characters.reduce((sum, c) => sum + c.words, 0);
  const pages = t("{n} pages", { n: eighths(totalEighths) });

  return (
    <>
      <section className="tiles">
        <Tile label={t("Scenes")} value={count(b.scene_count)} />
        <Tile label={t("Pages, estimated")} value={b.page_count.toLocaleString(language() === "es" ? "es-ES" : "en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} />
        <Tile label={t("Speaking characters")} value={count(b.characters.length)} />
        <Tile label={t("Locations")} value={count(b.locations.length)} />
      </section>

      <Story analysis={analysis} status={status} analyzing={analyzing} onAnalyze={props.onAnalyze} onOpenSettings={props.onOpenSettings} />

      <div className="grid">
        <ChartCard
          title={t("Day and night")}
          subtitle={t("Share of the {pages}. Scenes marked LATER or CONTINUOUS count with the scene before.", { pages })}
          table={splitTable(b, "day_night", DAY_NIGHT)}
        >
          <SegmentedBar parts={split(b, "day_night", DAY_NIGHT)} total={pages} />
        </ChartCard>
        <ChartCard title={t("Interior and exterior")} subtitle={t("Share of the {pages}.", { pages })} table={splitTable(b, "int_ext", INT_EXT)}>
          <SegmentedBar parts={split(b, "int_ext", INT_EXT)} total={pages} />
        </ChartCard>
      </div>

      <Stripboard breakdown={b} notes={notes} elements={script.elements} onOpenScene={props.onOpenScene} />

      <ElementsCard
        breakdown={b}
        elements={script.elements}
        categories={status?.categories ?? []}
        available={status?.llm.available ?? false}
        extracting={props.extracting}
        onExtract={props.onExtract}
        onClear={props.onClearElements}
        onOpenScene={props.onOpenScene}
        onOpenSettings={props.onOpenSettings}
      />

      <ScheduleBoard
        script={script}
        pdfExport={status?.pdf_export ?? false}
        onChange={props.onScheduleChange}
        onError={props.onError}
        onOpenScene={props.onOpenScene}
      />
      <CastCard script={script} onChange={props.onScheduleChange} onError={props.onError} />
      <CrewCard script={script} onChange={props.onScheduleChange} onError={props.onError} />

      <div className="grid">
        <WhoSpeaks breakdown={b} />
        <ChartCard
          title={t("Dialogue share")}
          subtitle={t("Words spoken by each character, out of {n}.", { n: count(totalWords) })}
          table={{
            columns: [t("Character"), t("Words"), t("Share"), t("Cues"), t("Scenes")],
            rows: b.characters.map((c) => [c.name, c.words, percent(c.words, totalWords), c.dialogue_blocks, c.scenes.length]),
          }}
        >
          <RankedBars
            color={SERIES[0]}
            rows={b.characters.slice(0, 14).map((c) => ({
              name: titleCase(c.name),
              value: c.words,
              label: `${count(c.words)} · ${percent(c.words, totalWords)}`,
              detail: t("words in {cues}, {scenes}", { cues: plural(c.dialogue_blocks, "cue"), scenes: plural(c.scenes.length, "scene") }),
            }))}
          />
          {b.characters.length > 14 && <p className="more">{t("{n} more in the table view.", { n: b.characters.length - 14 })}</p>}
        </ChartCard>
        <Presence breakdown={b} />
        <Tone breakdown={b} analysis={analysis} />
      </div>

      <div className="grid">
        <ChartCard
          title={t("Locations")}
          subtitle={t("Pages to shoot at each one.")}
          table={{
            columns: [t("Location"), t("Scenes"), t("Length (pages)"), t("Scene numbers")],
            rows: b.locations.map((l) => [l.location, l.scenes.length, eighths(l.eighths), l.scenes.join(", ")]),
          }}
        >
          <RankedBars
            color={SERIES[0]}
            rows={b.locations.slice(0, 14).map((l) => ({
              name: titleCase(l.location),
              value: l.eighths,
              label: `${eighths(l.eighths)} · ${plural(l.scenes.length, "scene")}`,
              detail: t("pages, in scenes {list}", { list: l.scenes.join(", ") }),
            }))}
          />
          {b.locations.length > 14 && <p className="more">{t("{n} more in the table view.", { n: b.locations.length - 14 })}</p>}
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
  const known = parts.map((p) => ({ ...p, name: t(p.name), value: totals.get(p.key)?.eighths ?? 0 }));
  const rest = [...totals].filter(([key]) => !parts.some((p) => p.key === key)).reduce((sum, [, v]) => sum + v.eighths, 0);
  return [...known, { key: "?", name: t("Not stated"), color: OTHER, ink: "#0b0b0b", value: rest }].map((p) => ({
    ...p,
    label: t("{n} pages", { n: eighths(p.value) }),
  }));
}

function splitTable(b: Breakdown, field: "day_night" | "int_ext", parts: Part[]) {
  const totals = eighthsBy(b, field);
  const names = new Map(parts.map((p) => [p.key, t(p.name)]));
  return {
    columns: ["", t("Scenes"), t("Length (pages)")],
    rows: [...totals].map(([key, v]) => [names.get(key) ?? t("Not stated"), v.scenes, eighths(v.eighths)]),
  };
}

function AiOff({ onOpenSettings }: { onOpenSettings: () => void }) {
  return (
    <p className="notice">
      {t("The AI features need your Anthropic API key.")}{" "}
      <button className="link" onClick={onOpenSettings}>
        {t("Add it in Settings")}
      </button>
    </p>
  );
}

function Story(props: {
  analysis: Analysis | null;
  status: Status | null;
  analyzing: boolean;
  onAnalyze: (refresh?: boolean) => void;
  onOpenSettings: () => void;
}) {
  const { analysis, status, analyzing } = props;
  const available = status?.llm.available ?? false;
  if (!analysis) {
    return (
      <section className="card story">
        <div>
          <h3>{t("Story notes")}</h3>
          <p>
            {t(
              "Claude can read the script and add a logline, a synopsis, a summary and emotional tone for every scene, and a proofread of the formatting.",
            )}
          </p>
          {!available && status && <AiOff onOpenSettings={props.onOpenSettings} />}
        </div>
        <button className="primary" disabled={!available || analyzing} onClick={() => props.onAnalyze()}>
          {analyzing ? t("Reading the script… about a minute") : t("Analyze the script")}
        </button>
      </section>
    );
  }
  return (
    <section className={`card story done${analyzing ? " stale" : ""}`}>
      <div>
        <h3>{t("Story notes")}</h3>
        <p className="logline">{analysis.logline}</p>
        <p>{analysis.synopsis}</p>
        {analysis.themes.length > 0 && (
          <ul className="themes">
            {analysis.themes.map((theme) => (
              <li key={theme}>{theme}</li>
            ))}
          </ul>
        )}
        <p className="fine">
          {t("Written by {model}. Check it against the script before it goes on a call sheet.", { model: analysis.model })}{" "}
          <button className="link" disabled={!available || analyzing} onClick={() => props.onAnalyze(true)}>
            {analyzing ? t("Analyzing again…") : t("Analyze again")}
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
          <h3>{t("Stripboard")}</h3>
          <p>{t("Every scene in script order, lengths in pages and eighths. Open a scene for its breakdown sheet.")}</p>
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
              {t(label)}
            </li>
          ))}
        </ul>
      </header>
      <div className="table-scroll">
        <table className="data board">
          <thead>
            <tr>
              <th className="num">#</th>
              <th>{t("Scene")}</th>
              <th className="num">{t("Length")}</th>
              <th className="num">{t("Starts p.")}</th>
              <th>{t("Cast")}</th>
              <th className="num">{t("Elements")}</th>
              {notes.size > 0 && <th>{t("Tone")}</th>}
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
                    {s.silent.length > 0 && (
                      <span className="silent">
                        {" "}
                        · {t("no lines")}: {s.silent.map(titleCase).join(", ")}
                      </span>
                    )}
                  </td>
                  <td className="num">
                    {elements?.revision?.scenes[s.number]?.status === "changed" && <span className="flag">{t("changed")}</span>}
                    {elements?.revision?.new.includes(s.number) && <span className="flag">{t("new")}</span>}
                    {elements?.scenes[s.number]?.length || "–"}
                  </td>
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
  const series = [...lead.map((name, i) => ({ name: titleCase(name), color: SERIES[i] })), ...(hasOther ? [{ name: t("Other"), color: OTHER }] : [])];
  const columns = b.scenes.map((s) => {
    const values = lead.map((name) => s.words[name] ?? 0);
    if (hasOther) {
      values.push(Object.entries(s.words).reduce((sum, [name, w]) => (lead.includes(name) ? sum : sum + w), 0));
    }
    return { label: s.number, title: `${s.number}. ${s.heading}`, values };
  });
  return (
    <ChartCard
      title={t("Who speaks in each scene")}
      subtitle={t("Words of dialogue per scene, by character.")}
      table={{
        columns: [t("Scene"), ...series.map((s) => s.name)],
        rows: columns.map((c) => [c.title, ...c.values]),
      }}
    >
      <StackedColumns columns={columns} series={series} unit={t("words")} xTitle={t("Scene")} />
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
      title={t("Character presence")}
      subtitle={t("Who is in which scene, and how much they say there.")}
      table={{
        columns: [t("Character"), t("Speaks in scenes"), t("Named without lines in")],
        rows: b.characters.map((c) => [c.name, c.scenes.join(", ") || "–", c.silent_scenes.join(", ") || "–"]),
      }}
    >
      <Heatmap
        rows={rows}
        columns={b.scenes.map((s) => ({ label: s.number, title: `${s.number}. ${s.heading}` }))}
        unit={t("words")}
        markedLabel={t("named in the action, no lines")}
      />
      {b.characters.length > cast.length && <p className="more">{t("{n} more in the table view.", { n: b.characters.length - cast.length })}</p>}
    </ChartCard>
  );
}

function Tone({ breakdown: b, analysis }: { breakdown: Breakdown; analysis: Analysis | null }) {
  if (!analysis || analysis.scenes.length === 0) {
    return (
      <section className="card placeholder">
        <h3>{t("Tone across the story")}</h3>
        <p>{t("Tension and mood, scene by scene. It appears here once the script has been analyzed.")}</p>
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
      title={t("Tone across the story")}
      subtitle={t("Claude's reading of each scene, scored against the rest of this script.")}
      table={{
        columns: [t("Scene"), t("Tone"), t("Tension (1–5)"), t("Mood (−2 to +2)")],
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
          <h3>{t("Formatting notes")}</h3>
          <p>{analyzed ? t("From the rule-based checks and Claude's proofread.") : t("From the rule-based checks. Analyzing the script adds a proofread.")}</p>
        </div>
      </header>
      {issues.length === 0 ? (
        <p className="clean">{t("Nothing to fix: headings, cues and numbering all look consistent.")}</p>
      ) : (
        <ul className="issues">
          {issues.map((issue, i) => (
            <li key={i}>
              <span className={`badge ${issue.severity}`}>
                <span aria-hidden="true">{issue.severity === "warning" ? "▲" : "●"}</span>
                {issue.severity === "warning" ? t("Fix") : t("Note")}
              </span>
              <span className="issue-text">
                {issue.scene && <strong>{t("Scene {n}.", { n: issue.scene })} </strong>}
                {issue.message}
                {issue.source === "ai" && <span className="source"> {t("Found by Claude.")}</span>}
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
  extracting: boolean;
  onExtract: () => void;
  onClear: () => void;
  onOpenScene: (number: string) => void;
  onOpenSettings: () => void;
}) {
  const { elements, categories } = props;
  const [filter, setFilter] = useState<string | null>(null);
  const totals = elements?.totals ?? [];
  const byKey = new Map(categories.map((c) => [c.key, c]));
  const counts = new Map<string, number>();
  for (const total of totals) counts.set(total.category, (counts.get(total.category) ?? 0) + 1);
  const shown = filter ? totals.filter((total) => total.category === filter) : totals;
  const all = Object.values(elements?.scenes ?? {}).flat();
  const suggested = all.filter((e) => e.source !== "manual").length;
  const byClaude = all.some((e) => e.source === "ai");
  const first = props.breakdown.scenes[0]?.number;

  return (
    <section className={`card${props.extracting ? " busy" : ""}`}>
      <header className="card-head">
        <div>
          <h3>{t("Elements")}</h3>
          <p>
            {t("What each department needs, scene by scene: extras, stunts, props, wardrobe, makeup, vehicles, effects and more.")}
            {totals.length > 0 && ` ${t("Suggesting again keeps everything you added or edited by hand.")}`}
          </p>
        </div>
        <button className={byClaude ? "ghost" : "primary"} disabled={!props.available || props.extracting} onClick={props.onExtract}>
          {props.extracting
            ? t("Breaking down the script… about a minute")
            : byClaude
              ? t("Suggest again with AI")
              : t("Suggest elements with AI")}
        </button>
      </header>

      {elements?.revision && <RevisionBanner revision={elements.revision} onOpenScene={props.onOpenScene} onClear={props.onClear} />}

      {totals.length === 0 ? (
        <div className="elements-empty">
          <p>{t("No elements yet. Claude can read the script and suggest them for every scene, or you can open a scene and add them by hand.")}</p>
          {!props.available && <AiOff onOpenSettings={props.onOpenSettings} />}
          {first && (
            <button className="ghost" onClick={() => props.onOpenScene(first)}>
              {t("Open scene {n}", { n: first })}
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="filters" role="group" aria-label={t("Filter by department")}>
            <button className="chip" aria-pressed={filter === null} onClick={() => setFilter(null)}>
              {t("All")} <span>{totals.length}</span>
            </button>
            {categories
              .filter((c) => counts.has(c.key))
              .map((c) => (
                <button key={c.key} className="chip" aria-pressed={filter === c.key} onClick={() => setFilter(filter === c.key ? null : c.key)}>
                  <span className="swatch" style={{ background: c.color }} />
                  {t(c.label)} <span>{counts.get(c.key)}</span>
                </button>
              ))}
          </div>
          <div className="table-scroll">
            <table className="data elements">
              <thead>
                <tr>
                  <th>{t("Element")}</th>
                  <th>{t("Department")}</th>
                  <th>{t("Scenes")}</th>
                  <th className="num">{t("Pages")}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((total) => {
                  const category = byKey.get(total.category);
                  return (
                    <tr key={`${total.category}|${total.name}`}>
                      <td className="element-name">{total.name}</td>
                      <td className="dept-cell">
                        <span className="swatch" style={{ background: category?.color }} />
                        {category ? t(category.label) : total.category}
                      </td>
                      <td>
                        <span className="scene-links">
                          {total.scenes.map((n) => (
                            <button key={n} className="scene-link" onClick={() => props.onOpenScene(n)} aria-label={t("Open scene {n}", { n })}>
                              {n}
                            </button>
                          ))}
                        </span>
                      </td>
                      <td className="num">{eighths(total.eighths)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {suggested > 0 && (
            <p className="fine">
              {byClaude
                ? t("{elements} still as Claude suggested them. Open a scene to check, edit or remove them before you print the breakdown sheets.", {
                    elements: plural(suggested, "element"),
                  })
                : t("{elements} suggested from words in the action, without AI: a first pass to check scene by scene. With an API key, Claude reads the whole script and suggests a fuller breakdown.", {
                    elements: plural(suggested, "element"),
                  })}
            </p>
          )}
          {!props.available && suggested > 0 && !byClaude && <AiOff onOpenSettings={props.onOpenSettings} />}
        </>
      )}
    </section>
  );
}

function RevisionBanner(props: { revision: NonNullable<Elements["revision"]>; onOpenScene: (n: string) => void; onClear: () => void }) {
  const { revision } = props;
  const statuses = Object.entries(revision.scenes);
  const changed = statuses.filter(([, m]) => m.status === "changed").map(([n]) => n);
  const unchanged = statuses.filter(([, m]) => m.status === "unchanged").length;
  const reviewed = statuses.filter(([, m]) => m.status === "reviewed").length;
  const when = revision.from.saved_at
    ? new Date(revision.from.saved_at).toLocaleDateString(language() === "es" ? "es-ES" : "en-GB", { day: "numeric", month: "short", year: "numeric" })
    : "";
  const links = (numbers: string[]) => (
    <span className="scene-links inline">
      {numbers.map((n) => (
        <button key={n} className="scene-link" onClick={() => props.onOpenScene(n)} aria-label={t("Open scene {n}", { n })}>
          {n}
        </button>
      ))}
    </span>
  );
  const parts = [
    t("{scenes} unchanged", { scenes: plural(unchanged, "scene") }),
    ...(reviewed ? [t("{n} reviewed", { n: reviewed })] : []),
    t("{scenes} to check", { scenes: plural(changed.length, "rewritten scene") }),
    plural(revision.new.length, "new scene"),
    ...(revision.omitted.length ? [t("{scenes} cut", { scenes: plural(revision.omitted.length, "scene") })] : []),
  ];
  return (
    <div className="revision">
      <p>
        <strong>{t("New draft.")}</strong> {when ? t("This breakdown was carried over from the previous draft (saved {date}):", { date: when }) : t("This breakdown was carried over from the previous draft:")}{" "}
        {parts.join(", ")}.
      </p>
      {changed.length > 0 && (
        <p>
          {t("Check the rewritten scenes:")} {links(changed)}
        </p>
      )}
      {revision.new.length > 0 && (
        <p>
          {t("Break down the new scenes:")} {links(revision.new)}
        </p>
      )}
      {revision.omitted.length > 0 && (
        <p className="muted">
          {t("Cut from this draft:")}{" "}
          {revision.omitted
            .map((o) => `${o.number}. ${o.heading}` + (o.elements ? ` (${t("{elements} dropped", { elements: plural(o.elements, "element") })})` : ""))
            .join("; ")}
        </p>
      )}
      <p>
        <button
          className="link"
          onClick={() => {
            if (window.confirm(t("Start this draft's breakdown empty? The carried-over elements will be removed from this draft."))) props.onClear();
          }}
        >
          {t("Start this draft empty instead")}
        </button>
      </p>
    </div>
  );
}
