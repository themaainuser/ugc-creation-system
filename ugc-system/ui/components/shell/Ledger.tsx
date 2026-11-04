/* Decision Ledger — the right rail. Every JEV Decision for the current run,
   the escalation work queue, and outcome capture (honest option-name Brier).
   Full detail lives in the stations; this is the operator's at-a-glance queue. */
import { useEffect, useMemo, useState } from "react";
import type { ConsoleState, DecisionVerb } from "../../lib/state";
import { decisionFor, openEscalations } from "../../lib/state";
import type { Decision } from "../../lib/types";
import { pct } from "../../lib/format";
import { Btn, Chip } from "../ui";

const VERB_TITLES: Record<DecisionVerb, string> = {
  verdict: "Verdict",
  outfit: "Outfit",
  expression: "Expression",
};

const VERB_STATION: Record<DecisionVerb, string> = {
  verdict: "station-analyzer",
  outfit: "station-stylist",
  expression: "station-expression",
};

const ESC_STATION: Record<string, string> = {
  verdict: "station-analyzer",
  outfit: "station-stylist",
  expression: "station-expression",
  wardrobe: "station-stylist",
};

interface Props {
  state: ConsoleState;
  onToggleLock: (verb: DecisionVerb) => void;
  onJump: (stationId: string) => void;
  onAck: (text: string) => void;
  onSaveOutcome: (verb: DecisionVerb, option: string) => Promise<void> | void;
  onReset: () => void;
}

function DecisionRow({
  verb,
  decision,
  effective,
  locked,
  onToggleLock,
  onJump,
  busy,
}: {
  verb: DecisionVerb;
  decision: Decision | null;
  effective: string | null;
  locked: boolean;
  onToggleLock: () => void;
  onJump: () => void;
  busy: boolean;
}) {
  return (
    <li className={`led-row ${locked ? "locked" : ""}`}>
      <button type="button" className="led-jump" onClick={onJump}
              title={`Open ${VERB_TITLES[verb]} station`}>
        <span className="lr-verb">{VERB_TITLES[verb]}</span>
        <span className="lr-choice" title={effective ?? undefined}>
          {decision ? (effective ?? decision.chosen) : "—"}
        </span>
      </button>
      {decision ? (
        <>
          <span className="lr-bar bar" aria-hidden="true">
            <i className={locked ? "lock" : decision.gate === "automate" ? "ok" : "warn"}
               style={{ width: `${Math.max(0, Math.min(1, decision.confidence)) * 100}%` }} />
          </span>
          <span className="lr-p tnum"
                title={`P(${locked && effective ? effective : decision.chosen})`}>
            {pct(locked && effective
              ? (decision.options.find((o) => o.name === effective)?.p ?? decision.confidence)
              : decision.confidence)}
          </span>
          <Chip tone={decision.gate === "automate" ? "ok" : "warn"}>
            {decision.gate === "automate" ? "Auto" : "Escalate"}
          </Chip>
          <button
            type="button"
            className={`lockbtn ${locked ? "on" : ""}`}
            onClick={onToggleLock}
            disabled={busy}
            aria-pressed={locked}
            title={locked ? "Unlock the call" : "Lock the call — freeze against re-dress"}
          >
            {locked ? "Unlock" : "Lock"}
          </button>
        </>
      ) : (
        <span className="lr-empty">no decision yet</span>
      )}
    </li>
  );
}

export function Ledger({ state, onToggleLock, onJump, onAck, onSaveOutcome, onReset }: Props) {
  const escalations = openEscalations(state);
  const verbs: DecisionVerb[] = ["verdict", "outfit", "expression"];
  const available = useMemo(
    () => verbs.filter((v) => decisionFor(state, v).decision),
    [state], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const [selVerb, setSelVerb] = useState<DecisionVerb>("verdict");
  const [selOption, setSelOption] = useState<string>("");
  const [saving, setSaving] = useState(false);

  // keep the selector on a verb that still has a decision
  useEffect(() => {
    if (available.length && !available.includes(selVerb)) {
      setSelVerb(available[0]);
      setSelOption("");
    }
  }, [available.join(","), selVerb]); // eslint-disable-line react-hooks/exhaustive-deps

  const selDecision = available.includes(selVerb) ? decisionFor(state, selVerb).decision : null;
  const outcome = state.outcome;

  const save = async () => {
    if (!selDecision || !selOption) return;
    setSaving(true);
    try {
      await onSaveOutcome(selVerb, selOption);
    } finally {
      setSaving(false);
    }
  };

  return (
    <aside className="ledger" aria-label="decision ledger">
      <div className="ledger-head">
        <h2>Decision Ledger</h2>
        <span className="spacer" />
        {escalations.length > 0 ? (
          <Chip tone="warn">{escalations.length} open</Chip>
        ) : (
          <Chip tone="ok">clear</Chip>
        )}
      </div>

      <ul className="led-rows" aria-label="JEV decisions">
        {verbs.map((v) => {
          const { decision, lock, effective } = decisionFor(state, v);
          return (
            <DecisionRow
              key={v}
              verb={v}
              decision={decision}
              effective={effective}
              locked={Boolean(lock)}
              busy={state.phase === "running" || state.phase === "overriding"}
              onToggleLock={() => onToggleLock(v)}
              onJump={() => onJump(VERB_STATION[v])}
            />
          );
        })}
      </ul>

      <section className="ledger-block" aria-labelledby="esc-h">
        <h3 id="esc-h">Escalations</h3>
        {escalations.length === 0 ? (
          <p className="esc-clear">✓ No open escalations — decisions cleared to automate or locked by operator.</p>
        ) : (
          <ul className="esc-list">
            {escalations.map((e) => (
              <li key={e} className="esc">
                <span className="ico" aria-hidden="true">!</span>
                <span className="esc-text">{e}</span>
                <span className="esc-actions">
                  <button type="button" className="mini" onClick={() => onJump(ESC_STATION[e.split(":")[0]] ?? "station-dispatch")}>
                    Review
                  </button>
                  <button type="button" className="mini" onClick={() => onAck(e)}>Ack</button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="ledger-block" aria-labelledby="out-h">
        <h3 id="out-h">Realised outcome</h3>
        {available.length === 0 ? (
          <p className="hint">Run the line to capture an outcome.</p>
        ) : (
          <>
            <div className="seg" role="group" aria-label="decision to score">
              {available.map((v) => (
                <button
                  key={v}
                  type="button"
                  aria-pressed={selVerb === v}
                  className={`seg-btn ${selVerb === v ? "sel" : ""}`}
                  onClick={() => { setSelVerb(v); setSelOption(""); }}
                >
                  {VERB_TITLES[v]}
                </button>
              ))}
            </div>
            <div className="outcome-opts" role="group" aria-label="realised option">
              {(selDecision?.options ?? []).map((o) => (
                <button
                  key={o.name}
                  type="button"
                  aria-pressed={selOption === o.name}
                  className={`opt-chip ${selOption === o.name ? "sel" : ""}`}
                  onClick={() => setSelOption(o.name)}
                >
                  {o.name}
                </button>
              ))}
            </div>
            <div className="outcome-actions">
              <Btn variant="secondary" onClick={save} loading={saving}
                   disabled={!selOption}
                   title="POST outcome — logs the Brier-scored result for this decision">
                Save outcome
              </Btn>
            </div>
            {outcome && outcome.verb === selVerb && (
              <p className="outcome-result tnum" role="status">
                Logged — {outcome.verb} → {outcome.option}, Brier {outcome.brier.toFixed(3)}
                <span className="hint"> · lower is better, 0 = the call was exactly right</span>
              </p>
            )}
            <p className="hint">
              Outcome = which option actually proved correct; it scores the engine's
              decision distribution (your lock doesn't change it). Written to{" "}
              <span className="mono">data/decisions/outcomes.jsonl</span> for calibration.
            </p>
          </>
        )}
      </section>

      <div className="ledger-foot">
        <Btn variant="ghost" onClick={onReset} title="Clear the console and start a fresh line">
          Reset console
        </Btn>
      </div>
    </aside>
  );
}
