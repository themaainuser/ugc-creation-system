/* StageRail — the assembly line made visible.
   Five nodes: Intake → Analyzer → Stylist → Expression → Dispatch.
   States: idle | running | done | skipped | escalate | error. Click jumps to the station. */
import type { ConsoleState } from "../../lib/state";
import { analyzeSkipped, openEscalations } from "../../lib/state";
import type { ActiveStage, Stage } from "../../lib/types";

interface NodeDef {
  stage: Stage;
  idx: string;
  label: string;
  station: string;
}

const NODES: NodeDef[] = [
  { stage: "intake", idx: "01", label: "Intake", station: "station-intake" },
  { stage: "analyze", idx: "02", label: "Analyzer", station: "station-analyzer" },
  { stage: "style", idx: "03", label: "Stylist", station: "station-stylist" },
  { stage: "express", idx: "04", label: "Expression", station: "station-expression" },
  { stage: "dispatch", idx: "05", label: "Dispatch", station: "station-dispatch" },
];

type NodeState = "idle" | "running" | "done" | "skipped" | "escalate" | "error";

const ESC_STAGE: Record<string, Stage> = {
  verdict: "analyze",
  outfit: "style",
  expression: "express",
  wardrobe: "style",
};

function liveText(s: ConsoleState): string {
  switch (s.phase) {
    case "running":
      return s.activeStage === "analyze" ? "Analyzing reel" : "Building brief — style, expression, dispatch";
    case "overriding":
      return "Rebuilding brief with operator override";
    case "redressing":
      return "Re-dressing — style and expression updating";
    case "ready":
      if (analyzeSkipped(s)) return "idea-only brief — no reel analysed";
      return openEscalations(s).length
        ? `Line ready — ${openEscalations(s).length} escalation(s) need review`
        : "Line ready — all decisions cleared to automate";
    default:
      return "Line idle";
  }
}

export function StageRail({
  state,
  onJump,
}: {
  state: ConsoleState;
  onJump: (stationId: string) => void;
}) {
  const { phase, activeStage, analysis, brief, errors } = state;
  const lastCmd = errors.at(-1)?.cmd;
  const openEsc = openEscalations(state);
  const escStages = new Set(
    openEsc.map((e) => ESC_STAGE[e.split(":")[0].trim().toLowerCase()] ?? "dispatch"),
  );
  const skipped = analyzeSkipped(state);

  const stateFor = (stage: Stage): NodeState => {
    // escalations tint completed nodes until acknowledged
    const tint = (base: NodeState): NodeState =>
      base === "done" && escStages.has(stage) ? "escalate" : base;

    if (phase === "running" || phase === "overriding") {
      if (activeStage === "analyze") {
        if (stage === "analyze") return "running";
        return stage === "intake" ? "done" : "idle";
      }
      // building the brief — the analyzer only counts as done if it ran
      if (stage === "intake") return "done";
      if (stage === "analyze") return analysis ? "done" : "skipped";
      if (phase === "overriding") return "running";
      return activeStage === "build" ? "running" : "idle";
    }
    if (phase === "redressing") {
      if (stage === "style" || stage === "express") return "running";
      if (stage === "intake") return "done";
      if (stage === "analyze") return analysis ? "done" : "skipped";
      return "idle"; // dispatch keeps its previous state below
    }
    if (phase === "ready") {
      if (stage === "analyze" && skipped) return "skipped";
      return tint("done");
    }
    // idle — a failed run leaves its mark on the node it died in
    if (errors.length && lastCmd) {
      if (lastCmd === "analyze" && stage === "analyze") return "error";
      if (lastCmd === "brief" && (stage === "style" || stage === "express" || stage === "dispatch")) return "error";
      if (lastCmd === "plan-day" && (stage === "style" || stage === "express")) return "error";
    }
    if (stage === "analyze" && analysis) return "done";
    if (stage === "intake" && (state.draft.transcript.trim() || state.draft.idea.trim())) return "done";
    if (brief && stage === "dispatch") return "done";
    return "idle";
  };

  // redressing keeps dispatch's prior state
  const displayState = (stage: Stage): NodeState => {
    if (phase === "redressing" && stage === "dispatch") {
      return brief ? "done" : "idle";
    }
    return stateFor(stage);
  };

  return (
    <nav className="stagerail" aria-label="production line">
      <ol className="stagenodes">
        {NODES.map((n, i) => {
          const st = displayState(n.stage);
          const current =
            (phase === "running" || phase === "overriding") &&
            ((activeStage === "analyze" && n.stage === "analyze") ||
              (activeStage === "build" && (n.stage === "style" || n.stage === "express" || n.stage === "dispatch")));
          return (
            <li key={n.stage} className="stagenode-item">
              {i > 0 && <span className={`stage-link ${st !== "idle" || displayState(NODES[i - 1].stage) !== "idle" ? "live" : ""}`} aria-hidden="true" />}
              <button
                type="button"
                className={`stagenode ${st} ${current ? "current" : ""}`}
                onClick={() => onJump(n.station)}
                aria-current={current ? "step" : undefined}
                aria-label={`${n.idx} ${n.label} — ${st}`}
                title={`Jump to ${n.label}`}
              >
                <span className="sn-idx tnum">{n.idx}</span>
                <span className="sn-label">{n.label}</span>
                <span className="sn-dot" aria-hidden="true" />
                <span className="sn-state">{st}</span>
              </button>
            </li>
          );
        })}
      </ol>
      <p className="sr-live" aria-live="polite">{liveText(state)}</p>
    </nav>
  );
}
