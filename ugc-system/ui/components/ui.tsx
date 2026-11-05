/* Shared console primitives — every station composes from these.
   Visual rules: hairline borders, mono numerals, motion ≤150ms, no bounce. */
import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

export type StampTone = "active" | "done" | "warn" | "error";

/** Per-station error boundary: one station's render fault shows an inline
    alert instead of unmounting the whole console. */
export class StationBoundary extends Component<
  { label: string; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[station:${this.props.label}]`, error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="station station-failed" role="alert">
          <header className="station-head">
            <h2>{this.props.label}</h2>
            <span className="spacer" />
            <span className="status-pill error">render error</span>
          </header>
          <div className="station-body">
            <p className="empty-note">
              This station hit a render error — the rest of the console is
              unaffected. Refresh the page or Reset the console to recover.
            </p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

/** One numbered station of the assembly line. */
export function Station({
  id,
  idx,
  title,
  stamp,
  stampTone,
  children,
}: {
  id: string;
  idx: string;
  title: string;
  stamp?: string;
  stampTone?: StampTone;
  children: ReactNode;
}) {
  return (
    <section className="station" id={id} tabIndex={-1} aria-labelledby={`${id}-h`}>
      <header className="station-head">
        <span className="idx tnum" aria-hidden="true">{idx}</span>
        <h2 id={`${id}-h`}>{title}</h2>
        <span className="spacer" />
        {stamp && <span className={`status-pill ${stampTone ?? ""}`}>{stamp}</span>}
      </header>
      <div className="station-body">{children}</div>
    </section>
  );
}

export function Chip({
  tone = "default",
  title,
  children,
}: {
  tone?: "default" | "accent" | "ok" | "warn" | "bad";
  title?: string;
  children: ReactNode;
}) {
  return (
    <span className={`chip ${tone}`} title={title}>
      {children}
    </span>
  );
}

export function SkeletonStack({ n = 3 }: { n?: number }) {
  return (
    <div className="skel-stack" aria-label="loading" aria-busy="true">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className={`skel skel-line ${i % 2 ? "mid" : "short"}`} />
      ))}
      <div className="skel skel-block" />
    </div>
  );
}

export function Empty({
  title,
  hint,
  action,
}: {
  title: string;
  hint: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="t">{title}</div>
      <div className="s">{hint}</div>
      {action}
    </div>
  );
}

export function Btn({
  variant = "secondary",
  loading = false,
  disabled = false,
  onClick,
  title,
  ariaLabel,
  children,
}: {
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  title?: string;
  ariaLabel?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`btn btn-${variant}`}
      onClick={onClick}
      disabled={disabled || loading}
      title={title}
      aria-label={ariaLabel}
      aria-busy={loading || undefined}
    >
      {children}
    </button>
  );
}

/** Formality 1..10 meter for one Asset. */
export function Meter({ value }: { value: number }) {
  const tone = value >= 6 ? "high" : "ok";
  return (
    <div className="meter-wrap">
      <div className="n tnum">{value}/10</div>
      <div className="bar" title={`formality ${value}/10`}>
        <i className={tone} style={{ width: `${Math.max(0, Math.min(10, value)) * 10}%` }} />
      </div>
      <div className="cap">formality</div>
    </div>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  count,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  count?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {count !== undefined && <span className="count tnum">{count}</span>}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}
