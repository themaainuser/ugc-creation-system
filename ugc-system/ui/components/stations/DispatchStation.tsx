/* Station 05 — Dispatch: the shoot-ready Content Brief ticket.
   Escalations and outcome capture live in the Decision Ledger; this station
   is the artifact itself, plus copy-to-clipboard for downstream generation. */
import { useState } from "react";
import type { ConsoleState } from "../../lib/state";
import { openEscalations } from "../../lib/state";
import { mdepLine } from "../../lib/format";
import { Btn, Chip, Empty, SkeletonStack, Station } from "../ui";

interface Props {
  state: ConsoleState;
}

export function DispatchStation({ state }: Props) {
  const { phase, brief, locks, outcome } = state;
  const running = (phase === "running" || phase === "overriding") && state.activeStage !== "analyze";
  const [copied, setCopied] = useState(false);
  const escalations = openEscalations(state);

  const copy = () => {
    if (!brief) return;
    const payload = {
      ...brief,
      operator: {
        locks: Object.fromEntries(
          Object.entries(locks).map(([v, l]) => [
            v,
            { choice: l!.choice, overridden: l!.overridden, at: new Date(l!.at).toISOString() },
          ]),
        ),
        outcome,
      },
    };
    const txt = JSON.stringify(payload, null, 2);
    if (navigator.clipboard) {
      navigator.clipboard
        .writeText(txt)
        .then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1600);
        })
        .catch(() => window.alert("Clipboard write failed — select the ticket JSON manually."));
    }
  };

  return (
    <Station
      id="station-dispatch"
      idx="05"
      title="Dispatch"
      stamp={running ? "Assembling" : brief ? (escalations.length ? "Review" : "Ready") : undefined}
      stampTone={running ? "active" : escalations.length ? "warn" : "done"}
    >
      {running ? (
        <SkeletonStack n={4} />
      ) : !brief ? (
        <Empty
          title="No Content Brief yet"
          hint="The shoot-ready ticket appears after the line runs — one idea in, one brief out."
        />
      ) : (
        <>
          <div className="ticket">
            <div className="ticket-head">
              <Chip tone={brief.mode === "recreate" ? "ok" : "accent"}>{brief.mode}</Chip>
              <Chip>{brief.persona_id}</Chip>
              <Chip>{brief.mdep.place}</Chip>
              <span className="spacer" />
              <span className="ticket-mdep tnum">{mdepLine(brief.mdep)}</span>
            </div>
            <div className="ticket-body">
              <div>
                <h4>Hook</h4>
                <p>{brief.hook}</p>
              </div>
              <div>
                <h4>Script outline</h4>
                <ol className="script-list">
                  {brief.script_outline.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ol>
              </div>
              <div>
                <h4>Caption</h4>
                <p>{brief.caption_idea}</p>
                <p className="muted hashtags">{brief.hashtags.join(" ")}</p>
              </div>
            </div>
          </div>

          <div className="dispatch-actions">
            <Btn variant="secondary" onClick={copy}>
              {copied ? "Copied ✓" : "Copy brief JSON"}
            </Btn>
            <span className="hint">
              JSON carries the brief plus your locks and outcome under{" "}
              <span className="mono">operator</span>.
            </span>
          </div>
        </>
      )}
    </Station>
  );
}
