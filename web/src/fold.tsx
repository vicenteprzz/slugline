import { useLayoutEffect, useRef, useSyncExternalStore, type ReactNode } from "react";

import { t } from "./i18n";

/**
 * Folding the dashboard's cards: a click on a card's title hides everything
 * but the title. Which cards are folded is remembered in this browser, so the
 * dashboard opens the way it was left.
 */

const KEY = "slugline.folded";
const listeners = new Set<() => void>();
const mounted = new Set<string>();

function read(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((v) => typeof v === "string") : [];
  } catch {
    return [];
  }
}

let folded = new Set(read());
let snapshot = "";

// What the components watch: which cards are folded and which are on screen.
function refresh() {
  snapshot = `${[...folded].sort().join("|")}#${[...mounted].sort().join("|")}`;
  listeners.forEach((listener) => listener());
}

function write(next: Set<string>) {
  folded = next;
  try {
    localStorage.setItem(KEY, JSON.stringify([...folded]));
  } catch {
    // storage blocked: folding still works until the page is closed
  }
  refresh();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

function useFolded(): Set<string> {
  useSyncExternalStore(subscribe, () => snapshot);
  return folded;
}

export function toggleFold(id: string) {
  const next = new Set(folded);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  write(next);
}

/** Fold or unfold every card on the dashboard. */
export function foldAll(fold: boolean) {
  write(fold ? new Set([...folded, ...mounted]) : new Set([...folded].filter((id) => !mounted.has(id))));
}

/** A card's title that folds the card when clicked. */
export function FoldTitle(props: { id: string; children: ReactNode }) {
  const isFolded = useFolded().has(props.id);
  const ref = useRef<HTMLHeadingElement>(null);

  useLayoutEffect(() => {
    mounted.add(props.id);
    refresh();
    return () => {
      mounted.delete(props.id);
      refresh();
    };
  }, [props.id]);

  // After every render, since React rewrites the card's class when it changes.
  useLayoutEffect(() => {
    ref.current?.closest(".card")?.classList.toggle("folded", isFolded);
  });

  return (
    <h3 ref={ref} className="fold-title">
      <button
        type="button"
        className="fold-button"
        aria-expanded={!isFolded}
        title={isFolded ? t("Show this section") : t("Hide this section")}
        onClick={() => toggleFold(props.id)}
      >
        <span className="fold-chevron" aria-hidden="true">
          ▾
        </span>
        {props.children}
      </button>
    </h3>
  );
}

/** "Fold all" and "Unfold all", for the top of the dashboard. */
export function FoldAllControls() {
  const current = useFolded();
  const anyOpen = [...mounted].some((id) => !current.has(id));
  return (
    <div className="fold-all">
      <button className="ghost small" onClick={() => foldAll(anyOpen)}>
        {anyOpen ? t("Fold all sections") : t("Unfold all sections")}
      </button>
    </div>
  );
}
