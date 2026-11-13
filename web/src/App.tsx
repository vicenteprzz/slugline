import { FoldAllControls, FoldTitle } from "./fold";
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { Clapper, CountUp, Loading, Slate } from "./cinema";

import {
  analyzeScript,
  clearElements,
  mergeNames,
  resuggestElements,
  setDayNight,
  unmergeName,
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
import BudgetCard from "./Budget";
import ContinuityCard from "./Continuity";
import ScheduleBoard, { CastCard, CrewCard } from "./ScheduleBoard";
import SettingsPanel from "./SettingsPanel";
import type { Analysis, Breakdown, Category, Corrections, Element, Elements, Issue, LibraryEntry, LicenseStatus, Schedule, Script, Settings, Status } from "./types";

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

/** The script id in the address (#/scripts/<id>/<reel>), so a reload or the back button keeps your place. */
const routeId = () => location.hash.match(/^#\/scripts\/(\w+)/)?.[1] ?? null;
const goTo = (id: string | null) => {
  location.hash = id ? `#/scripts/${id}` : "#/";
};

/** The dashboard's reels: one screen each instead of one long page. */
const REELS = [
  { key: "overview", label: "Overview" },
  { key: "breakdown", label: "Breakdown" },
  { key: "cast", label: "Cast and locations" },
  { key: "continuity", label: "Continuity" },
  { key: "schedule", label: "Schedule" },
  { key: "budget", label: "Budget" },
] as const;
type Reel = (typeof REELS)[number]["key"];
const routeReel = (): Reel => {
  const key = location.hash.match(/^#\/scripts\/\w+\/(\w+)/)?.[1];
  return REELS.find((r) => r.key === key)?.key ?? "overview";
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
  // The slate claps when a script is opened from the app, not on a reload.
  const [slate, setSlate] = useState<{ title: string; scenes: number } | null>(null);
  const firstLoad = useRef(true);
  const endSlate = useCallback(() => setSlate(null), []);
  const clap = useCallback((s: Script) => setSlate({ title: s.breakdown.title ?? s.filename, scenes: s.breakdown.scene_count }), []);
  // The reel bar sits right under the top bar, whatever its height.
  const topbar = useRef<HTMLElement>(null);
  useLayoutEffect(() => {
    const bar = topbar.current;
    if (!bar || typeof ResizeObserver === "undefined") return;
    const set = () => document.documentElement.style.setProperty("--topbar-h", `${bar.offsetHeight}px`);
    set();
    const observer = new ResizeObserver(set);
    observer.observe(bar);
    return () => observer.disconnect();
  }, []);
  // Whatever happens to a drag (dropped on a strip, outside the window,
  // cancelled with Escape), the "drop the script" veil goes away.
  useEffect(() => {
    const clear = () => setDragging(false);
    window.addEventListener("dragend", clear);
    window.addEventListener("drop", clear, true);
    return () => {
      window.removeEventListener("dragend", clear);
      window.removeEventListener("drop", clear, true);
    };
  }, []);
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
    const initial = firstLoad.current;
    firstLoad.current = false;
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
        if (!initial) clap(s);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : t("Could not open that script."));
        goTo(null);
      })
      .finally(() => setLoading(null));
  }, [route]); // eslint-disable-line react-hooks/exhaustive-deps

  const show = useCallback(
    (opened: Script) => {
      setScript(opened);
      setPanel(null);
      clap(opened);
      goTo(opened.id);
    },
    [clap],
  );

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
      void refreshContinuity(script.id);
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
      void refreshContinuity(script.id);
    },
    [script, update],
  );

  const clear = useCallback(async () => {
    if (!script) return;
    setError(null);
    try {
      update(script.id, { elements: await clearElements(script.id) });
      void refreshContinuity(script.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("The breakdown could not be cleared."));
    }
  }, [script, update]);

  // Continuity follows the elements: after they change, the server works it out again.
  const refreshContinuity = useCallback(
    async (id: string) => {
      try {
        const fresh = await getScript(id);
        update(id, { continuity: fresh.continuity });
      } catch {
        // stays as it was until the next change
      }
    },
    [update],
  );

  const resuggest = useCallback(async () => {
    if (!script) return;
    setError(null);
    try {
      update(script.id, { elements: await resuggestElements(script.id) });
      void refreshContinuity(script.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("The elements could not be suggested."));
    }
  }, [script, update]);

  /** Corrections come back as the whole script, read again with them applied. */
  const correct = useCallback(
    async (change: (id: string) => Promise<Script>) => {
      if (!script) return;
      setError(null);
      try {
        const fixed = await change(script.id);
        update(script.id, { breakdown: fixed.breakdown, issues: fixed.issues, corrections: fixed.corrections });
      } catch (e) {
        setError(e instanceof Error ? e.message : t("The change could not be saved."));
      }
    },
    [script, update],
  );

  const categories = status?.categories ?? [];

  return (
    <div
      className={`app${panel ? " with-panel" : ""}`}
      data-lang={lang}
      onDragOver={(e) => {
        // Only a file from outside opens a script: dragging a strip in the
        // schedule is not a script being dropped.
        if (!isFileDrag(e)) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
      onDrop={(e) => {
        setDragging(false);
        if (!isFileDrag(e)) return;
        e.preventDefault();
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
      <header className="topbar" ref={topbar}>
        <div className="brand">
          <a className="wordmark" href="#/" title={t("Your scripts")}>
            <Clapper size={18} className="wordmark-mark" />
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
            onResuggest={resuggest}
            onCorrect={correct}
            onScheduleChange={(schedule) => update(script.id, { schedule })}
            onError={setError}
            onOpenScene={(number) => setPanel({ kind: "scene", number })}
            onOpenSettings={() => setPanel({ kind: "settings" })}
          />
        ) : route || loading ? (
          <Loading text={loading ?? t("Opening the script…")} />
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
          onCorrect={correct}
        />
      )}
      {dragging && <div className="drop-veil">{t("Drop the script to open it")}</div>}
      {slate && <Slate title={slate.title} scenes={slate.scenes} onDone={endSlate} />}
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
        <div className="filmstrip" aria-hidden="true" />
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
    ["dossier.pdf", "Production dossier (PDF)"],
    ["budget.pdf", "Budget (PDF)"],
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
    ["budget.csv", "Budget (CSV)"],
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
  onResuggest: () => void;
  onCorrect: (change: (id: string) => Promise<Script>) => void;
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

  const [reel, setReel] = useState<Reel>(routeReel);
  const go = useCallback(
    (next: Reel) => {
      setReel(next);
      history.replaceState(null, "", `#/scripts/${script.id}${next === "overview" ? "" : `/${next}`}`);
      window.scrollTo({ top: 0 });
    },
    [script.id],
  );
  // 1 to 6 jump between reels, unless you are typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
      const index = Number(e.key) - 1;
      if (Number.isInteger(index) && index >= 0 && index < REELS.length) go(REELS[index].key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const warnings = issues.filter((i) => i.severity === "warning").length;
  const badges: Record<Reel, string> = {
    overview: warnings ? String(warnings) : "",
    breakdown: String(b.scene_count),
    cast: String(b.characters.length),
    continuity: script.continuity?.days ? String(script.continuity.days) : "",
    schedule: script.schedule?.days.length ? String(script.schedule.days.length) : "",
    budget: "",
  };
  const decimal = (n: number) =>
    n.toLocaleString(language() === "es" ? "es-ES" : "en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const whole = (n: number) => count(Math.round(n));

  return (
    <>
      <ReelBar reel={reel} badges={badges} warn={warnings > 0} onGo={go} />
      <ReadingWarning issues={script.issues} filename={script.filename} />

      <div key={reel} className="reel" role="tabpanel" aria-label={t(REELS.find((r) => r.key === reel)!.label)}>
        {reel === "overview" && (
          <>
            <section className="tiles">
              <Tile label={t("Scenes")} value={<CountUp value={b.scene_count} format={whole} />} onClick={() => go("breakdown")} />
              <Tile label={t("Pages, estimated")} value={<CountUp value={b.page_count} format={decimal} />} onClick={() => go("breakdown")} />
              <Tile label={t("Speaking characters")} value={<CountUp value={b.characters.length} format={whole} />} onClick={() => go("cast")} />
              <Tile label={t("Locations")} value={<CountUp value={b.locations.length} format={whole} />} onClick={() => go("cast")} />
            </section>

            <Story analysis={analysis} status={status} analyzing={analyzing} onAnalyze={props.onAnalyze} onOpenSettings={props.onOpenSettings} />

            <div className="grid">
              <ChartCard
                id="day-night" title={t("Day and night")}
                subtitle={t("Share of the {pages}. Scenes marked LATER or CONTINUOUS count with the scene before.", { pages })}
                table={splitTable(b, "day_night", DAY_NIGHT)}
              >
                <SegmentedBar parts={split(b, "day_night", DAY_NIGHT)} total={pages} />
              </ChartCard>
              <ChartCard id="int-ext" title={t("Interior and exterior")} subtitle={t("Share of the {pages}.", { pages })} table={splitTable(b, "int_ext", INT_EXT)}>
                <SegmentedBar parts={split(b, "int_ext", INT_EXT)} total={pages} />
              </ChartCard>
            </div>

            <Issues issues={issues} analyzed={analysis !== null} corrections={script.corrections} onCorrect={props.onCorrect} />
            <NextReels onGo={go} />
          </>
        )}

        {reel === "breakdown" && (
          <>
            <Stripboard breakdown={b} notes={notes} elements={script.elements} issues={script.issues} onOpenScene={props.onOpenScene} />
            <ElementsCard
              breakdown={b}
              elements={script.elements}
              categories={status?.categories ?? []}
              available={status?.llm.available ?? false}
              extracting={props.extracting}
              onExtract={props.onExtract}
              onClear={props.onClearElements}
              onResuggest={props.onResuggest}
              onOpenScene={props.onOpenScene}
              onOpenSettings={props.onOpenSettings}
            />
          </>
        )}

        {reel === "cast" && (
          <>
            <div className="grid">
              <ChartCard
                id="dialogue" title={t("Dialogue share")}
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
              <ChartCard
                id="locations" title={t("Locations")}
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
            </div>
            <WhoSpeaks breakdown={b} />
            <Presence breakdown={b} />
            <Tone breakdown={b} analysis={analysis} />
          </>
        )}

        {reel === "continuity" &&
          (script.continuity && b.scenes.some((s) => s.story_day) ? (
            <ContinuityCard script={script} onOpenScene={props.onOpenScene} />
          ) : (
            <section className="card placeholder">
              <h3>{t("Story days and continuity")}</h3>
              <p>{t("The days of the story appear here once the scenes have a day or a night.")}</p>
            </section>
          ))}

        {reel === "schedule" && (
          <>
            <ScheduleBoard
              script={script}
              pdfExport={status?.pdf_export ?? false}
              onChange={props.onScheduleChange}
              onError={props.onError}
              onOpenScene={props.onOpenScene}
            />
            <CastCard script={script} onChange={props.onScheduleChange} onError={props.onError} />
            <CrewCard script={script} onChange={props.onScheduleChange} onError={props.onError} />
          </>
        )}

        {reel === "budget" && (
          <BudgetCard
            script={script}
            pdfExport={status?.pdf_export ?? false}
            onError={props.onError}
            onOpenScene={props.onOpenScene}
            onScheduleChange={props.onScheduleChange}
          />
        )}
      </div>
    </>
  );
}

/** The bar of reels: a strip of film, the frame you are on lit. */
function ReelBar(props: { reel: Reel; badges: Record<Reel, string>; warn: boolean; onGo: (reel: Reel) => void }) {
  const refs = useRef(new Map<Reel, HTMLButtonElement>());
  const bar = useRef<HTMLElement>(null);
  // What sticks under the reels (the schedule's days) needs their height.
  useLayoutEffect(() => {
    const el = bar.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const set = () => document.documentElement.style.setProperty("--reels-h", `${el.offsetHeight}px`);
    set();
    const observer = new ResizeObserver(set);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  const [mark, setMark] = useState<{ left: number; width: number } | null>(null);
  useLayoutEffect(() => {
    const place = () => {
      const button = refs.current.get(props.reel);
      if (button) setMark({ left: button.offsetLeft, width: button.offsetWidth });
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [props.reel, props.badges]);
  return (
    <nav className="reels" ref={bar} aria-label={t("Sections")}>
      <div className="reels-strip" role="tablist">
        {REELS.map((r, i) => (
          <button
            key={r.key}
            ref={(el) => {
              if (el) refs.current.set(r.key, el);
            }}
            role="tab"
            aria-selected={props.reel === r.key}
            className="reel-tab"
            title={t("Key {n}", { n: i + 1 })}
            onClick={() => props.onGo(r.key)}
          >
            <span className="reel-number">{String(i + 1).padStart(2, "0")}</span>
            <span className="reel-label">{t(r.label)}</span>
            {props.badges[r.key] && (
              <span className={`reel-badge${r.key === "overview" && props.warn ? " warn" : ""}`}>{props.badges[r.key]}</span>
            )}
          </button>
        ))}
        {mark && <span className="reel-mark" style={{ transform: `translateX(${mark.left}px)`, width: mark.width }} />}
      </div>
      <FoldAllControls />
    </nav>
  );
}

/** At the end of the overview, where to go next. */
function NextReels({ onGo }: { onGo: (reel: Reel) => void }) {
  return (
    <section className="next-reels">
      {REELS.slice(1).map((r, i) => (
        <button key={r.key} className="next-reel" onClick={() => onGo(r.key)}>
          <span className="reel-number">{String(i + 2).padStart(2, "0")}</span>
          {t(r.label)}
          <span aria-hidden="true">→</span>
        </button>
      ))}
    </section>
  );
}

function Tile({ label, value, onClick }: { label: string; value: React.ReactNode; onClick?: () => void }) {
  return (
    <button className="tile" onClick={onClick}>
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
    </button>
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
          <FoldTitle id="story">{t("Story notes")}</FoldTitle>
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
        <FoldTitle id="story">{t("Story notes")}</FoldTitle>
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
  issues: Issue[];
  onOpenScene: (number: string) => void;
}) {
  const { breakdown: b, notes, elements } = props;
  // Where the script's numbering jumps (22, then 25), the board says so.
  const gaps = new Map(
    props.issues.filter((i) => i.code === "missing-scenes" && i.scene).map((i) => [i.scene as string, String(i.params?.missing ?? "")]),
  );
  const [query, setQuery] = useState("");
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const scenes = words.length
    ? b.scenes.filter((s) => {
        const text = [s.number, s.heading, s.story_label, ...s.characters, ...s.silent, notes.get(s.number)?.summary ?? ""].join(" ").toLowerCase();
        return words.every((w) => text.includes(w));
      })
    : b.scenes;
  return (
    <section className="card">
      <header className="card-head">
        <div>
          <FoldTitle id="stripboard">{t("Stripboard")}</FoldTitle>
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
        <label className="search">
          <span aria-hidden="true">⌕</span>
          <input
            type="search"
            value={query}
            placeholder={t("Find a scene, place or character")}
            aria-label={t("Find a scene, place or character")}
            onChange={(e) => setQuery(e.target.value)}
          />
          {words.length > 0 && <span className="search-count">{t("{n} of {total}", { n: scenes.length, total: b.scenes.length })}</span>}
        </label>
      <div className="table-scroll">
        <table className="data board">
          <thead>
            <tr>
              <th className="num">#</th>
              <th>{t("Scene")}</th>
              <th className="num" title={t("Day of the story: D3 is day 3, N3 the night of day 3")}>{t("Story day")}</th>
              <th className="num">{t("Length")}</th>
              <th className="num">{t("Starts p.")}</th>
              <th>{t("Cast")}</th>
              <th className="num">{t("Elements")}</th>
              {notes.size > 0 && <th>{t("Tone")}</th>}
            </tr>
          </thead>
          <tbody>
            {scenes.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  {t("No scene matches “{q}”.", { q: query.trim() })}
                </td>
              </tr>
            )}
            {scenes.map((s) => {
              const note = notes.get(s.number);
              const gap = words.length ? undefined : gaps.get(s.number);
              return (
                <Fragment key={s.number}>
                {gap && (
                  <tr className="gap-row">
                    <td colSpan={8}>
                      <span aria-hidden="true">▲</span> {t("Scene {missing} is not in the file", { missing: gap })} ·{" "}
                      <span className="muted">{t("it may be hard to read; check these pages")}</span>
                    </td>
                  </tr>
                )}
                <tr>
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
                  <td className="num story-day">{s.story_label || "–"}</td>
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
                </Fragment>
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
      id="who-speaks" title={t("Who speaks in each scene")}
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
      id="presence" title={t("Character presence")}
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
        <FoldTitle id="tone">{t("Tone across the story")}</FoldTitle>
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
      id="tone" title={t("Tone across the story")}
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

const MERGE_KINDS: Record<string, string> = { "similar-characters": "characters", "similar-locations": "locations" };

function IssueFix({ issue, onCorrect }: { issue: Issue; onCorrect: (change: (id: string) => Promise<Script>) => void }) {
  const kind = MERGE_KINDS[issue.code];
  if (kind && issue.names?.length === 2) {
    return (
      <span className="issue-fix">
        {issue.names.map((into) => (
          <button key={into} className="chip" onClick={() => onCorrect((id) => mergeNames(id, kind, issue.names!, into))}>
            {t("Merge as {name}", { name: into })}
          </button>
        ))}
      </span>
    );
  }
  if (issue.code === "no-time" && issue.scene) {
    const scene = issue.scene;
    return (
      <span className="issue-fix" role="group" aria-label={t("Set day or night for scene {n}", { n: scene })}>
        {DAY_NIGHT.map((d) => (
          <button key={d.key} className="chip" onClick={() => onCorrect((id) => setDayNight(id, scene, d.key))}>
            <span className="swatch" style={{ background: d.color }} />
            {t(d.name)}
          </button>
        ))}
      </span>
    );
  }
  return null;
}

function CorrectionsList({ corrections, onCorrect }: { corrections: Corrections; onCorrect: (change: (id: string) => Promise<Script>) => void }) {
  const merges = (["characters", "locations"] as const).flatMap((kind) =>
    Object.entries(corrections[kind]).map(([name, into]) => ({ kind, name, into })),
  );
  const days = Object.entries(corrections.day_night).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));
  if (merges.length === 0 && days.length === 0) return null;
  return (
    <div className="corrections">
      <h4>{t("Corrected in Slugline")}</h4>
      <p className="fine">{t("Counted this way in the cast, the locations and the schedule. The script file is not changed.")}</p>
      <ul>
        {merges.map((m) => (
          <li key={`${m.kind}|${m.name}`}>
            <span>{t("{name} counts as {into}", { name: m.name, into: m.into })}</span>
            <button className="link" onClick={() => onCorrect((id) => unmergeName(id, m.kind, m.name))}>
              {t("Undo")}
            </button>
          </li>
        ))}
        {days.map(([scene, value]) => (
          <li key={`dn|${scene}`}>
            <span>
              {t("Scene {n}.", { n: scene })} {t(DAY_NIGHT.find((d) => d.key === value)?.name ?? value)}
            </span>
            <button className="link" onClick={() => onCorrect((id) => setDayNight(id, scene, null))}>
              {t("Undo")}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Issues(props: {
  issues: Issue[];
  analyzed: boolean;
  corrections: Corrections;
  onCorrect: (change: (id: string) => Promise<Script>) => void;
}) {
  const { issues, analyzed } = props;
  const [all, setAll] = useState(false);
  const FIRST = 6;
  // Fixes first, then notes: what needs a hand comes to the top.
  const sorted = [...issues].sort((x, y) => Number(y.severity === "warning") - Number(x.severity === "warning"));
  const shown = all ? sorted : sorted.slice(0, FIRST);
  return (
    <section className="card">
      <header className="card-head">
        <div>
          <FoldTitle id="issues">{t("Formatting notes")}</FoldTitle>
          <p>{analyzed ? t("From the rule-based checks and Claude's proofread.") : t("From the rule-based checks. Analyzing the script adds a proofread.")}</p>
        </div>
      </header>
      {issues.length === 0 ? (
        <p className="clean">{t("Nothing to fix: headings, cues and numbering all look consistent.")}</p>
      ) : (
        <ul className="issues">
          {shown.map((issue, i) => (
            <li key={i}>
              <span className={`badge ${issue.severity}`}>
                <span aria-hidden="true">{issue.severity === "warning" ? "▲" : "●"}</span>
                {issue.severity === "warning" ? t("Fix") : t("Note")}
              </span>
              <span className="issue-text">
                {issue.scene && <strong>{t("Scene {n}.", { n: issue.scene })} </strong>}
                {issue.template ? t(issue.template, issue.params ?? undefined) : issue.message}
                {issue.source === "ai" && <span className="source"> {t("Found by Claude.")}</span>}
                <IssueFix issue={issue} onCorrect={props.onCorrect} />
              </span>
            </li>
          ))}
        </ul>
      )}
      {issues.length > FIRST && (
        <button className="link" onClick={() => setAll(!all)}>
          {all ? t("Show fewer") : t("Show all {n} notes", { n: issues.length })}
        </button>
      )}
      <CorrectionsList corrections={props.corrections} onCorrect={props.onCorrect} />
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
  onResuggest: () => void;
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
          <FoldTitle id="elements">{t("Elements")}</FoldTitle>
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
          <div className="actions-row">
            <button className="ghost" onClick={props.onResuggest}>
              {t("Suggest from words in the script")}
            </button>
            {first && (
              <button className="ghost" onClick={() => props.onOpenScene(first)}>
                {t("Open scene {n}", { n: first })}
              </button>
            )}
          </div>
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
          <p className="fine">
            <button className="link" onClick={props.onResuggest}>
              {t("Suggest again from words in the script")}
            </button>{" "}
            {t("Updates the suggestions made without AI; Claude's and yours stay as they are.")}
          </p>
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

/** True when what is being dragged includes files from outside the page. */
function isFileDrag(e: React.DragEvent): boolean {
  return Array.from(e.dataTransfer?.types ?? []).includes("Files");
}

const READ_CODES = new Set(["read-no-dialogue", "read-few-scenes", "read-no-light"]);

/** When the file looks badly read, say so before anyone plans with it. */
function ReadingWarning({ issues, filename }: { issues: Issue[]; filename: string }) {
  const found = issues.filter((i) => READ_CODES.has(i.code));
  if (found.length === 0) return null;
  return (
    <section className="read-warning" role="alert">
      <strong>{t("This script may not have been read correctly.")}</strong>
      <ul>
        {found.map((i) => (
          <li key={i.code}>{i.template ? t(i.template, i.params ?? undefined) : i.message}</li>
        ))}
      </ul>
      <p>
        {/\.pdf$/i.test(filename)
          ? t(
              "Check the breakdown before using it. If {file} is a normal script, send it to us from the website so we can fix the reading; a Fountain or Final Draft file, if you have one, is read exactly.",
              { file: filename },
            )
          : t("Check the breakdown before using it, and the formatting notes below: the scene headings or the character names may not follow the usual format.")}
      </p>
    </section>
  );
}
