import { useState } from "react";

import { activateLicense, removeLicense, saveSettings } from "./api";
import { type Language, language, t } from "./i18n";
import type { LicenseStatus, Settings } from "./types";

const KINDS: Record<string, string> = { pro: "Professional", school: "School", studio: "Production company", pilot: "Pilot" };

const MODEL_NOTES: Record<string, string> = {
  "claude-opus-5-5": "Recommended: the best balance of quality and cost.",
  "claude-sonnet-5-5": "Cheaper and faster, for long scripts or tight budgets.",
  "claude-haiku-5-5": "The cheapest. Fine for summaries, weaker at breakdowns.",
  "claude-fable-5-2": "The most capable and the most expensive.",
};

/** Settings: the user's own Anthropic API key, the model and the language. */
export default function SettingsPanel(props: {
  settings: Settings | null;
  license: LicenseStatus | null;
  language: Language;
  onLanguage: (language: Language) => void;
  onSaved: () => Promise<void>;
  onClose: () => void;
}) {
  const { settings } = props;
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  async function save(changes: { anthropic_api_key?: string; model?: string }, done: string) {
    setBusy(true);
    setMessage(null);
    try {
      await saveSettings(changes);
      await props.onSaved();
      setKey("");
      setMessage({ kind: "ok", text: done });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : t("The settings could not be saved.") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="drawer" aria-label={t("Settings")}>
      <header className="drawer-head">
        <h2>{t("Settings")}</h2>
        <button className="ghost small" onClick={props.onClose}>
          {t("Close")}
        </button>
      </header>
      <div className="drawer-body settings">
        <LicenseSection license={props.license} onChanged={props.onSaved} />

        <section className="dept">
          <h3>{t("AI features")}</h3>
          <p>
            {t(
              "Story notes, element suggestions and the script assistant use Claude through your own Anthropic account. Everything else works without it.",
            )}
          </p>
          {settings?.api_key_source === "environment" ? (
            <p className="notice">{t("Using the key in the ANTHROPIC_API_KEY environment variable ({hint}).", { hint: settings.api_key_hint ?? "" })}</p>
          ) : settings?.has_api_key ? (
            <div className="key-row">
              <span>
                {t("Key saved")}: <code>{settings.api_key_hint}</code>
              </span>
              <button className="ghost small" disabled={busy} onClick={() => void save({ anthropic_api_key: "" }, t("Key removed."))}>
                {t("Remove")}
              </button>
            </div>
          ) : null}
          {settings?.api_key_source !== "environment" && (
            <form
              className="key-form"
              onSubmit={(e) => {
                e.preventDefault();
                if (key.trim()) void save({ anthropic_api_key: key.trim() }, t("Key saved. The AI features are on."));
              }}
            >
              <label htmlFor="api-key">{settings?.has_api_key ? t("Replace the key") : t("Anthropic API key")}</label>
              <input
                id="api-key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                placeholder="sk-ant-…"
                value={key}
                onChange={(e) => setKey(e.target.value)}
              />
              <button className="primary small" type="submit" disabled={busy || !key.trim()}>
                {busy ? t("Saving…") : t("Save key")}
              </button>
            </form>
          )}
          <p className="fine">
            {t("Get a key at console.anthropic.com. It is stored only on this computer. Each analysis is billed to your Anthropic account, and using it sends the script to Anthropic.")}
          </p>
          {message && <p className={message.kind === "error" ? "notice error" : "notice"}>{message.text}</p>}
        </section>

        <section className="dept">
          <h3>{t("Model")}</h3>
          <select
            value={settings?.model ?? ""}
            disabled={busy || !settings}
            onChange={(e) => void save({ model: e.target.value }, t("Model changed."))}
            aria-label={t("Model")}
          >
            {(settings?.models ?? []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          {settings && <p className="fine">{t(MODEL_NOTES[settings.model] ?? "")}</p>}
        </section>

        <section className="dept">
          <h3>{t("Language")}</h3>
          <select value={props.language} onChange={(e) => props.onLanguage(e.target.value as Language)} aria-label={t("Language")}>
            <option value="es">Español</option>
            <option value="en">English</option>
          </select>
          <p className="fine">{t("PDF exports use this language too. AI notes keep the language of the script.")}</p>
        </section>
      </div>
    </aside>
  );
}

function LicenseSection(props: { license: LicenseStatus | null; onChanged: () => Promise<void> }) {
  const { license } = props;
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  if (!license) return null;
  const date = (iso: string) =>
    new Date(iso).toLocaleDateString(language() === "es" ? "es-ES" : "en-GB", { day: "numeric", month: "long", year: "numeric" });

  async function run(task: () => Promise<unknown>, done: string) {
    setBusy(true);
    setMessage(null);
    try {
      await task();
      await props.onChanged();
      setKey("");
      setMessage({ kind: "ok", text: done });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : t("The licence could not be activated.") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="dept">
      <h3>{t("Licence")}</h3>
      {license.licensed && license.license ? (
        <>
          <p>
            {t("{kind} licence for {name}.", { kind: t(KINDS[license.license.kind] ?? license.license.kind), name: license.license.name })}{" "}
            {license.license.expires ? t("Valid until {date}.", { date: date(license.license.expires) }) : t("It does not expire.")}
          </p>
          <div className="key-row">
            <span className="muted">{t("Thank you for supporting Slugline.")}</span>
            <button className="ghost small" disabled={busy} onClick={() => void run(removeLicense, t("Licence removed from this computer."))}>
              {t("Remove")}
            </button>
          </div>
        </>
      ) : (
        <>
          <p>
            {t("Trial version: everything works, but your library keeps {n} scripts ({used} used) and PDFs are marked as a trial.", {
              n: license.free_scripts,
              used: Math.min(license.scripts, license.free_scripts),
            })}
          </p>
          <form
            className="key-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (key.trim()) void run(() => activateLicense(key.trim()), t("Licence activated. Thank you!"));
            }}
          >
            <label htmlFor="licence">{t("Licence key")}</label>
            <textarea id="licence" rows={3} spellCheck={false} placeholder="SLUG1-…" value={key} onChange={(e) => setKey(e.target.value)} />
            <button className="primary small" type="submit" disabled={busy || !key.trim()}>
              {busy ? t("Checking…") : t("Activate")}
            </button>
          </form>
          {license.purchase_url && (
            <a className="ghost small button-link" href={license.purchase_url} target="_blank" rel="noreferrer">
              {t("Buy a licence")}
            </a>
          )}
        </>
      )}
      {message && <p className={message.kind === "error" ? "notice error" : "notice"}>{message.text}</p>}
    </section>
  );
}
