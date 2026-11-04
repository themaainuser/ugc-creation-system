/* Station 02 — Analyzer: Hook → Flow/Beats → Ending → Verdict.
   The Verdict stamp is the effective call; the JEV card under it carries
   the full distribution plus the operator's lock/override controls. */
import type { ConsoleState, Lock } from "../../lib/state";
import type { Analysis, Decision, VerdictMode } from "../../lib/types";
import { pct } from "../../lib/format";
import { DecisionCard } from "../DecisionCard";
import { Chip, Empty, SkeletonStack, Station } from "../ui";

interface Props {
  state: ConsoleState;
  analysis: Analysis | null;
  decision: Decision | null;
  lock: Lock | null;
  onToggleLock: () => void;
  onOverride: (choice: VerdictMode) => void;
}

export function AnalyzerStation({ state, analysis, decision, lock, onToggleLock, onOverride }: Props) {
  const { phase, brief } = state;
  const running = phase === "running" && state.activeStage === "analyze";
  const building = (phase === "running" || phase === "overriding") && state.activeStage !== "analyze";
  // Effective call: operator lock > brief mode (engine-derived from the
  // calibrated decision) > the JEV decision itself > heuristic typing last.
  const effectiveVerdict: VerdictMode | null = (lock?.choice
    ? lock.choice
    : (brief?.mode ?? decision?.chosen ?? analysis?.verdict ?? null)) as VerdictMode | null;
  const otherVerdict: VerdictMode | null = effectiveVerdict
    ? effectiveVerdict === "remix" ? "recreate" : "remix"
    : null;

  return (
    <Station
      id="station-analyzer"
      idx="02"
      title="Analyzer"
      stamp={running ? "Scanning" : building ? "Queued" : analysis ? "Complete" : undefined}
      stampTone={running ? "active" : "done"}
    >
      {running ? (
        <SkeletonStack n={4} />
      ) : !analysis ? (
        <Empty
          title="No analysis yet"
          hint="Run the line to score the Hook, Flow/Beats, Ending, and Verdict. Live engine output only — nothing is pre-filled."
        />
      ) : (
        <>
          <div className="hook-card">
            <div className="chips">
              <Chip tone="accent">{analysis.hook.hook_type}</Chip>
              {analysis.niche_tags.map((t) => (
                <Chip key={t}>#{t}</Chip>
              ))}
            </div>
            <div className="hook-text">{analysis.hook.text_or_action}</div>
            <p className="hook-why">{analysis.hook.why_it_works}</p>
            <div className="hook-first tnum">first 3s: {analysis.hook.first_3_seconds}</div>
          </div>

          <div>
            <span className="flabel">Flow / Beats</span>
            <ol className="beats">
              {analysis.beats.map((b) => (
                <li className="beat" key={b.order}>
                  <span className="ts tnum">{b.timestamp}</span>
                  <span>
                    <span className="purpose">{b.purpose}</span>
                    <div className="what">{b.what_happens}</div>
                    <div className="tech">{b.technique}</div>
                  </span>
                </li>
              ))}
            </ol>
          </div>

          <div>
            <span className="flabel">Ending</span>
            <p className="ending">
              <strong>{analysis.ending.style}</strong>
              {analysis.ending.detail ? <span className="detail"> — {analysis.ending.detail}</span> : null}
              {analysis.ending.loop_close && <Chip tone="ok">loop close</Chip>}
            </p>
            <p className="ending verdict-reason">{analysis.verdict_reason}</p>
          </div>

          <div className="verdict-row">
            <span className={`stamp ${effectiveVerdict === "recreate" ? "green" : ""}`}>
              {effectiveVerdict ?? analysis.verdict}
            </span>
            <div className="verdict-tools">
              {brief && otherVerdict && !lock && (
                <button
                  type="button"
                  className="mini"
                  onClick={() => onOverride(otherVerdict)}
                  disabled={phase !== "ready"}
                  title={`Override the Verdict call to ${otherVerdict} — the brief rebuilds with the new mode`}
                >
                  switch to {otherVerdict}
                </button>
              )}
              {lock && (
                <span className="lock-hint tnum">
                  locked to {lock.choice}{lock.overridden ? " · operator override" : " · accepted"}
                </span>
              )}
              {brief && (
                <span className="model-note tnum">
                  engine P({decision?.chosen ?? "—"}) = {decision ? pct(decision.confidence) : "—"}
                </span>
              )}
            </div>
          </div>

          <DecisionCard
            title="Verdict"
            decision={decision}
            emptyNote="The Verdict decision appears after the analyze step."
            lock={lock}
            effectiveChoice={effectiveVerdict}
            onToggleLock={onToggleLock}
            onOverride={(name) => onOverride(name as VerdictMode)}
            busy={phase === "overriding"}
          />

          {analysis.remix_ideas.length > 0 && (
            <div>
              <span className="flabel">Remix ideas</span>
              <ul className="idea-list">
                {analysis.remix_ideas.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </Station>
  );
}
