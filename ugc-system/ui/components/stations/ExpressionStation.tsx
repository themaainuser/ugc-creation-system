/* Station 04 — Expression: genuine vs performed direction and the
   Expression JEV Decision (lockable against re-dress). */
import type { ConsoleState, Lock } from "../../lib/state";
import type { Decision } from "../../lib/types";
import { pretty } from "../../lib/format";
import { DecisionCard } from "../DecisionCard";
import { Chip, Empty, SkeletonStack, Station } from "../ui";

interface Props {
  state: ConsoleState;
  decision: Decision | null;
  lock: Lock | null;
  onToggleLock: () => void;
}

export function ExpressionStation({ state, decision, lock, onToggleLock }: Props) {
  const { phase, brief } = state;
  const redressing = phase === "redressing";
  const running = (phase === "running" || phase === "overriding") && state.activeStage !== "analyze";
  const expr = brief?.expressions;

  return (
    <Station
      id="station-expression"
      idx="04"
      title="Expression"
      stamp={redressing ? "Updating" : running ? "Directing" : brief ? "Complete" : undefined}
      stampTone={redressing || running ? "active" : "done"}
    >
      {running ? (
        <SkeletonStack n={3} />
      ) : !expr || !brief ? (
        <Empty
          title="No expression plan yet"
          hint="Genuine vs performed direction appears after the line runs."
        />
      ) : (
        <>
          <div className="expr-primary-row">
            <span className="expr-name">{pretty(expr.primary.name)}</span>
            <span className={`pill ${expr.primary.genuine ? "genuine" : "performed"}`}>
              {expr.primary.genuine ? "Genuine" : "Performed"}
            </span>
          </div>
          {expr.primary.when_to_use && <p className="when">{expr.primary.when_to_use}</p>}
          {expr.primary.micro_details && (
            <p className="micro"><strong>Micro:</strong> {expr.primary.micro_details}</p>
          )}

          {expr.secondary.length > 0 && (
            <div>
              <span className="flabel">Secondary</span>
              <ul className="simple-list">
                {expr.secondary.map((e) => (
                  <li key={e.name}>{pretty(e.name)} — {e.micro_details}</li>
                ))}
              </ul>
            </div>
          )}

          {expr.avoid.length > 0 && (
            <div>
              <span className="flabel">Avoid</span>
              <ul className="simple-list avoid">
                {expr.avoid.map((e) => (
                  <li key={e}>{pretty(e)}</li>
                ))}
              </ul>
            </div>
          )}

          {expr.audio_note && <p className="audio-note">{expr.audio_note}</p>}
          <p className="rationale">{expr.rationale}</p>

          <DecisionCard
            verb="expression"
            title="Expression"
            decision={decision}
            lock={lock}
            effectiveChoice={lock?.choice ?? decision?.chosen ?? null}
            onToggleLock={onToggleLock}
          />
        </>
      )}
    </Station>
  );
}
