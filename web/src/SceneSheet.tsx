import { useEffect, useRef, useState } from "react";

import { eighths, stripColor, titleCase } from "./format";
import { light, t } from "./i18n";
import type { Category, Element, Script } from "./types";

type Draft = { name: string; notes: string };
type Editing = { category: string; index: number | null }; // index null: adding a new element

/** The breakdown sheet of one scene, editable: what each department needs for it. */
export default function SceneSheet(props: {
  script: Script;
  number: string;
  categories: Category[];
  onNavigate: (number: string) => void;
  onClose: () => void;
  onSave: (number: string, elements: Element[]) => Promise<void>;
}) {
  const { script, number, categories } = props;
  const scenes = script.breakdown.scenes;
  const position = scenes.findIndex((s) => s.number === number);
  const scene = scenes[position];
  const note = script.analysis?.scenes.find((n) => n.number === number);
  const items = script.elements?.scenes[number] ?? [];
  const revision = script.elements?.revision ?? null;
  const match = revision?.scenes[number];
  const isNew = revision?.new.includes(number) ?? false;

  const [editing, setEditing] = useState<Editing | null>(null);
  const [draft, setDraft] = useState<Draft>({ name: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const body = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setEditing(null);
    setError(null);
    body.current?.scrollTo({ top: 0 });
  }, [number]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (typing) return;
      if (e.key === "Escape") props.onClose();
      if (e.key === "ArrowLeft" && position > 0) props.onNavigate(scenes[position - 1].number);
      if (e.key === "ArrowRight" && position < scenes.length - 1) props.onNavigate(scenes[position + 1].number);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [position, scenes, props]);

  if (!scene) return null;

  async function save(next: Element[]) {
    setSaving(true);
    setError(null);
    try {
      await props.onSave(number, next);
      setEditing(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("The change could not be saved."));
    } finally {
      setSaving(false);
    }
  }

  function startEdit(category: string, index: number | null) {
    const current = index === null ? null : items[index];
    setDraft({ name: current?.name ?? "", notes: current?.notes ?? "" });
    setEditing({ category, index });
    setError(null);
  }

  function submit() {
    if (!editing || !draft.name.trim()) return;
    const element: Element = { category: editing.category, name: draft.name.trim(), notes: draft.notes.trim(), source: "manual" };
    const next = editing.index === null ? [...items, element] : items.map((e, i) => (i === editing.index ? element : e));
    void save(next);
  }

  const suggested = items.filter((e) => e.source === "ai").length;

  return (
    <aside className="drawer sheet" aria-label={t("Breakdown sheet, scene {n}", { n: number })}>
      <header className="drawer-head">
        <div className="sheet-title">
          <span className="sheet-strip" style={{ background: stripColor(scene.int_ext, scene.day_night) }} />
          <div>
            <p className="eyebrow">{t("Scene {n}", { n: scene.number })}</p>
            <h2 className="slug">{scene.heading}</h2>
          </div>
        </div>
        <div className="drawer-actions">
          <button className="ghost small" disabled={position <= 0} onClick={() => props.onNavigate(scenes[position - 1].number)} aria-label={t("Previous scene")}>
            ‹
          </button>
          <button
            className="ghost small"
            disabled={position >= scenes.length - 1}
            onClick={() => props.onNavigate(scenes[position + 1].number)}
            aria-label={t("Next scene")}
          >
            ›
          </button>
          <button className="ghost small" onClick={props.onClose}>
            {t("Close")}
          </button>
        </div>
      </header>

      <div className="drawer-body" ref={body}>
        <dl className="sheet-meta">
          <div>
            <dt>{t("Int./Ext.")}</dt>
            <dd>{scene.int_ext ?? "–"}</dd>
          </div>
          <div>
            <dt>{t("Day/Night")}</dt>
            <dd>{light(scene.day_night)}</dd>
          </div>
          <div>
            <dt>{t("Length")}</dt>
            <dd>{t("{n} pp.", { n: eighths(scene.eighths) })}</dd>
          </div>
          <div>
            <dt>{t("Starts")}</dt>
            <dd>{t("p. {n}", { n: Math.floor(scene.start_page) })}</dd>
          </div>
        </dl>

        {note && <p className="sheet-summary">{note.summary}</p>}

        {match?.status === "changed" && (
          <div className="revision-note">
            <p>
              <strong>{t("Rewritten in this draft")}</strong>
              {match.old !== number && ` ${t("(it was scene {n})", { n: match.old })}`}.{" "}
              {t("The elements below come from the previous draft: check them against the new text.")}
            </p>
            <button className="primary small" disabled={saving} onClick={() => void save(items)}>
              {t("Mark as reviewed")}
            </button>
          </div>
        )}
        {isNew && (
          <div className="revision-note">
            <p>
              <strong>{t("New in this draft.")}</strong> {t("It has no elements from the previous draft.")}
            </p>
          </div>
        )}

        <section className="dept">
          <h3>{t("Cast")}</h3>
          <p>{scene.characters.map(titleCase).join(", ") || "–"}</p>
          {scene.silent.length > 0 && (
            <p className="muted">
              {t("No lines")}: {scene.silent.map(titleCase).join(", ")}
            </p>
          )}
        </section>

        {suggested > 0 && (
          <p className="sheet-hint">
            {t("{n} suggested by Claude. Check them against the scene: edit or remove what's wrong.", { n: suggested })}
          </p>
        )}
        {error && <p className="notice error">{error}</p>}

        {categories.map((category) => {
          const indexed = items.map((e, i) => [e, i] as const).filter(([e]) => e.category === category.key);
          const adding = editing?.category === category.key && editing.index === null;
          return (
            <section className="dept" key={category.key}>
              <div className="dept-head">
                <h3>
                  <span className="swatch" style={{ background: category.color }} />
                  {t(category.label)}
                </h3>
                {!adding && (
                  <button className="link small-link" onClick={() => startEdit(category.key, null)} disabled={saving}>
                    + {t("Add")}
                  </button>
                )}
              </div>
              {indexed.length > 0 && (
                <ul className="items">
                  {indexed.map(([e, i]) =>
                    editing?.index === i ? (
                      <li key={i}>
                        <ElementForm draft={draft} setDraft={setDraft} saving={saving} onSubmit={submit} onCancel={() => setEditing(null)} />
                      </li>
                    ) : (
                      <li key={i} className="item">
                        <button className="item-main" onClick={() => startEdit(category.key, i)} disabled={saving} title={t("Edit")}>
                          <span className="item-name">{e.name}</span>
                          {e.notes && <span className="item-notes">{e.notes}</span>}
                          {e.source === "ai" && (
                            <span className="tag" title={t("Suggested by Claude")}>
                              {t("suggested")}
                            </span>
                          )}
                        </button>
                        <button
                          className="item-remove"
                          aria-label={t("Remove {name}", { name: e.name })}
                          disabled={saving}
                          onClick={() => void save(items.filter((_, k) => k !== i))}
                        >
                          ×
                        </button>
                      </li>
                    ),
                  )}
                </ul>
              )}
              {adding && <ElementForm draft={draft} setDraft={setDraft} saving={saving} onSubmit={submit} onCancel={() => setEditing(null)} />}
            </section>
          );
        })}
      </div>
    </aside>
  );
}

function ElementForm(props: {
  draft: Draft;
  setDraft: (d: Draft) => void;
  saving: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const { draft, setDraft } = props;
  return (
    <form
      className="item-form"
      onSubmit={(e) => {
        e.preventDefault();
        props.onSubmit();
      }}
      onKeyDown={(e) => e.key === "Escape" && (e.stopPropagation(), props.onCancel())}
    >
      <input autoFocus placeholder={t("Element, e.g. Revolver")} value={draft.name} maxLength={120} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
      <input placeholder={t("Notes (optional)")} value={draft.notes} maxLength={300} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
      <div className="item-form-actions">
        <button type="button" className="ghost small" onClick={props.onCancel}>
          {t("Cancel")}
        </button>
        <button type="submit" className="primary small" disabled={props.saving || !draft.name.trim()}>
          {props.saving ? t("Saving…") : t("Save")}
        </button>
      </div>
    </form>
  );
}
