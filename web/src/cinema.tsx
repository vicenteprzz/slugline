import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { language, t } from "./i18n";

/**
 * The touches of film set around the dashboard: a clapperboard while a script
 * loads, the slate that opens a script, and numbers that roll up like a
 * counter. All of it stays still for people who ask for less motion.
 */

export const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** A small clapperboard. `clapping` makes the stick snap shut over and over. */
export function Clapper(props: { size?: number; clapping?: boolean; className?: string }) {
  const size = props.size ?? 56;
  return (
    <svg
      className={`clapper${props.clapping ? " clapping" : ""}${props.className ? ` ${props.className}` : ""}`}
      width={size}
      height={size}
      viewBox="0 0 64 64"
      aria-hidden="true"
    >
      <g className="clapper-stick">
        <rect x="6" y="14" width="52" height="10" rx="1.5" fill="currentColor" />
        <path d="M14 14h7l-6 10H8zM29 14h7l-6 10h-7zM44 14h7l-6 10h-7z" fill="var(--page)" />
      </g>
      <rect x="6" y="27" width="52" height="31" rx="2" fill="currentColor" />
      <path d="M14 27h7l-6 6H8zM29 27h7l-6 6h-7zM44 27h7l-6 6h-7z" fill="var(--page)" />
      <path d="M12 41h40M12 49h24" stroke="var(--page)" strokeWidth="2" strokeLinecap="round" opacity="0.55" />
    </svg>
  );
}

/** The loading screen: the clapper keeps clapping until the script is in. */
export function Loading({ text }: { text: string }) {
  return (
    <div className="empty loading">
      <Clapper clapping size={64} />
      <p>{text}</p>
    </div>
  );
}

/**
 * The slate that opens a script: the production's name, scene one, take one,
 * the stick claps and the picture cuts to the dashboard. A click skips it.
 */
export function Slate(props: { title: string; scenes: number; onDone: () => void }) {
  const [phase, setPhase] = useState<"in" | "clap" | "out">("in");
  const { onDone } = props;
  useEffect(() => {
    if (reducedMotion()) {
      onDone();
      return;
    }
    const timers = [
      window.setTimeout(() => setPhase("clap"), 380),
      window.setTimeout(() => setPhase("out"), 1150),
      window.setTimeout(onDone, 1550),
    ];
    return () => timers.forEach(window.clearTimeout);
  }, [onDone]);
  const today = new Date().toLocaleDateString(language() === "es" ? "es-ES" : "en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
  return (
    <div className={`slate-veil ${phase}`} onClick={onDone} role="presentation">
      <div className="slate">
        <div className="slate-stick" />
        <div className="slate-hinge" />
        <div className="slate-body">
          <span className="slate-label">{t("Production")}</span>
          <strong className="slate-title">{props.title}</strong>
          <div className="slate-row">
            <span>
              <span className="slate-label">{t("Scene")}</span>1
            </span>
            <span>
              <span className="slate-label">{t("Take")}</span>1
            </span>
            <span>
              <span className="slate-label">{t("Scenes")}</span>
              {props.scenes}
            </span>
          </div>
          <div className="slate-row">
            <span>
              <span className="slate-label">{t("Date")}</span>
              {today}
            </span>
            <span className="slate-action">{t("Action!")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/** A number that rolls up from zero the first time it is shown. */
export function CountUp(props: { value: number; format: (n: number) => string; ms?: number }) {
  const { value, format } = props;
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0));
  const from = useRef(0);
  useLayoutEffect(() => {
    if (reducedMotion()) {
      setShown(value);
      return;
    }
    const start = performance.now();
    const begin = from.current;
    const ms = props.ms ?? 700;
    let frame = 0;
    const step = (now: number) => {
      const k = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - k, 3);
      setShown(begin + (value - begin) * eased);
      if (k < 1) frame = requestAnimationFrame(step);
      else from.current = value;
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value, props.ms]);
  return <>{format(shown)}</>;
}
