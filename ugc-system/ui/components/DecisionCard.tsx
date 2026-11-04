/* JEV DecisionCard — the one surface every calibrated decision renders on.
   Shows the full distribution (never a bare label), the gate, and the
   operator's authority: lock the call / override (verdict only). */
import type { Decision } from "../lib/types";
import type { Lock } from "../lib/state";
import { pct } from "../lib/format";
import { Btn, Chip } from "./ui";

interface Props {
  title: string;
  decision: Decision | null;
  emptyNote?: string;
  lock: Lock | null;
  effectiveChoice: string | null;
  onToggleLock: () => void;
  onOverride?: (choice: string) => void; // provided for verdict only
  busy?: boolean;
}

export function DecisionCard({
  title,
  decision,
  emptyNote,
  lock,
  effectiveChoice,
  onToggleLock,
  onOverride,
  busy = false,
}: Props) {
  if (!decision) {
    return (
      <div className="jev" aria-label={`${title} JEV Decision`}>
        <div className="jev-head">
          <span className="verb">JEV · {title}</span>
          <span className="spacer" />
          <Chip>No decision</Chip>
        </div>
        <div className="jev-body">
          <p className="empty-note">{emptyNote ?? "Awaiting engine output."}</p>
        </div>
      </div>
    );
  }

  const sorted = [...decision.options].sort((a, b) => b.p - a.p);
  const chosenOpt = decision.options.find((o) => o.name === decision.chosen);
  const effective = lock?.choice ?? effectiveChoice ?? decision.chosen;
  const overridden = Boolean(lock?.overridden);
  // When the operator locked a different choice, caption the engine's P for
  // *that* choice — the number must never look like it belongs to the other.
  const shownP = lock
    ? (decision.options.find((o) => o.name === effective)?.p ?? decision.confidence)
    : decision.confidence;

  return (
    <div className={`jev ${lock ? "locked" : ""}`} aria-label={`${title} JEV Decision`}>
      <div className="jev-head">
        <span className="verb">JEV · {title}</span>
        <span className="chosen">{effective}</span>
        <Chip tone={decision.gate === "automate" ? "ok" : "warn"}>
          {decision.gate === "automate" ? "Automate" : "Escalate"}
        </Chip>
        {lock && <Chip tone="accent" title="Operator has locked this call">Locked</Chip>}
        <div className="jev-bigp">
          <div className="p tnum">{pct(shownP)}</div>
          <div className="cap">P({effective})</div>
        </div>
      </div>

      <div className="jev-body">
        {overridden && lock && (
          <p className="override-note">
            Operator override — locked to <strong>{lock.choice}</strong>. Engine called{" "}
            {lock.modelChoice} (P&nbsp;=&nbsp;{pct(lock.modelP)}).
          </p>
        )}

        <ul className="jev-opts" aria-label={`${title} option probabilities`}>
          {sorted.map((o) => {
            const isEffective = o.name === effective;
            const canOverride = Boolean(onOverride) && !lock && o.name !== decision.chosen;
            return (
              <li key={o.name} className={`jev-opt ${isEffective ? "chosen" : ""}`}>
                <span className="name" title={o.name}>{o.name}</span>
                <span className="bar">
                  <i className={isEffective ? "chosen" : ""} style={{ width: `${Math.max(0, Math.min(1, o.p)) * 100}%` }} />
                </span>
                <span className="p tnum">{pct(o.p)}</span>
                {onOverride ? (
                  canOverride ? (
                    <button
                      type="button"
                      className="opt-override"
                      onClick={() => onOverride(o.name)}
                      disabled={busy}
                      title={`Override the Verdict call to ${o.name}`}
                    >
                      {busy ? "…" : "Override"}
                    </button>
                  ) : (
                    <span className="opt-override ghost" aria-hidden="true" />
                  )
                ) : null}
              </li>
            );
          })}
        </ul>

        {decision.rationale && <p className="jev-rationale">{decision.rationale}</p>}

        {chosenOpt && chosenOpt.signals.length > 0 && (
          <div className="jev-signals">
            {chosenOpt.signals.filter(Boolean).map((sg, i) => (
              <Chip key={i}>{sg}</Chip>
            ))}
          </div>
        )}

        <div className="jev-meta tnum">
          calibrated: {decision.calibrated ? "yes" : "no"}
          {decision.brier_estimate != null && <> · brier≈{decision.brier_estimate.toFixed(3)}</>}
          <span className="meta-note">scores are calibrated, not raw sorts</span>
        </div>

        <div className="jev-lockrow">
          <Btn
            variant={lock ? "secondary" : "ghost"}
            onClick={onToggleLock}
            disabled={busy}
            title={
              lock
                ? "Release your lock — engine output will apply again on re-dress"
                : "Operator authority: stand behind this call so re-dress cannot change it"
            }
          >
            {lock ? "Unlock the call" : "Lock the call"}
          </Btn>
          {lock && (
            <span className="lock-stamp tnum" title={new Date(lock.at).toLocaleString()}>
              locked by operator
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
