/* Console state machine — one pure reducer for the whole assembly line.

   Design rules:
   - Engine output is data, never state we mutate: BRIEF_OK / REDRESS_OK merge
     through mergeBrief() so operator locks survive re-dress.
   - runId guards against stale async responses (runs and redress both bump it).
   - Escalations are derived from the *effective* decisions (post-lock) using
     the same wording as orchestrator.escalation_list — the gate itself always
     comes from the engine.
*/
import type {
  ActiveStage,
  Analysis,
  Brief,
  Decision,
  DecisionVerb,
  ExpressionPlan,
  Health,
  MDEP,
  Persona,
  Phase,
  StylePlan,
} from "./types";

export interface Draft {
  personaId: string;
  transcript: string;
  context: string;
  idea: string;
  mdep: MDEP;
  folder: string;
}

/* Operator authority over a decision (Product principle 3: the human locks the call). */
export interface Lock {
  choice: string; // effective choice the operator stands behind
  modelChoice: string; // what the engine picked
  modelP: number; // engine P(modelChoice)
  overridden: boolean; // true when choice !== modelChoice
  at: number;
}

export interface ErrItem {
  id: number;
  cmd: string;
  message: string;
}

export interface OutcomeState {
  verb: DecisionVerb;
  option: string;
  brier: number;
  at: number;
}

export interface ConsoleState {
  personas: Persona[];
  health: Health | null;
  draft: Draft;
  phase: Phase;
  activeStage: ActiveStage;
  runId: number;
  analysis: Analysis | null;
  verdictDecision: Decision | null; // from the analyze step — available before brief lands
  brief: Brief | null;
  locks: Partial<Record<DecisionVerb, Lock>>;
  ackedEscalations: string[];
  errors: ErrItem[];
  outcome: OutcomeState | null;
}

export const INITIAL_DRAFT: Draft = {
  personaId: "",
  transcript: "",
  context: "",
  idea: "",
  mdep: { mood: "playful", day: "casual weekday", environment: "mall", place: "mall" },
  folder: "",
};

export const initialState: ConsoleState = {
  personas: [],
  health: null,
  draft: INITIAL_DRAFT,
  phase: "idle",
  activeStage: null,
  runId: 0,
  analysis: null,
  verdictDecision: null,
  brief: null,
  locks: {},
  ackedEscalations: [],
  errors: [],
  outcome: null,
};

export type Action =
  | { type: "META_OK"; personas: Persona[]; health: Health | null }
  | { type: "HEALTH_OK"; health: Health }
  | { type: "DRAFT_SET"; patch: Partial<Draft> }
  | { type: "RUN_START"; runId: number }
  | { type: "STAGE_SET"; runId: number; stage: ActiveStage }
  | { type: "ANALYZE_OK"; runId: number; analysis: Analysis; decision: Decision }
  | { type: "OVERRIDE_START"; runId: number }
  | { type: "BRIEF_OK"; runId: number; brief: Brief }
  | { type: "RUN_FAIL"; runId: number; cmd: string; message: string }
  | { type: "REDRESS_START" }
  | { type: "REDRESS_OK"; style: StylePlan; expressions: ExpressionPlan; decisions: { outfit: Decision | null; expression: Decision | null }; escalations: string[] }
  | { type: "REDRESS_FAIL"; cmd: string; message: string }
  | { type: "ERROR_PUSH"; cmd: string; message: string }
  | { type: "LOCK_SET"; verb: DecisionVerb; lock: Lock }
  | { type: "LOCK_CLEAR"; verb: DecisionVerb }
  | { type: "ESC_TOGGLE"; text: string }
  | { type: "ERROR_DISMISS"; id: number }
  | { type: "OUTCOME_OK"; outcome: OutcomeState }
  | { type: "HYDRATE"; snapshot: Partial<ConsoleState> }
  | { type: "RESET" };

/* ---------------------------------------------------------------- helpers */

const DECISION_VERBS: DecisionVerb[] = ["verdict", "outfit", "expression"];

/** Merge incoming engine output with operator locks (locked halves are kept). */
function mergeBrief(prev: Brief | null, incoming: Brief, locks: ConsoleState["locks"]): Brief {
  if (!prev) return incoming;
  const outfitKept = Boolean(locks.outfit);
  const exprKept = Boolean(locks.expression);
  return {
    ...incoming,
    style: {
      ...incoming.style,
      outfit: outfitKept ? prev.style.outfit : incoming.style.outfit,
      pose: outfitKept ? prev.style.pose : incoming.style.pose,
    },
    expressions: exprKept ? prev.expressions : incoming.expressions,
    decisions: {
      verdict: incoming.decisions.verdict,
      outfit: outfitKept ? prev.decisions.outfit : incoming.decisions.outfit,
      expression: exprKept ? prev.decisions.expression : incoming.decisions.expression,
    },
    escalations: incoming.escalations,
  };
}

/** Same rule + wording as orchestrator.escalation_list, over *effective* decisions.
    Locked verbs are resolved (the operator made the call), so they drop out. */
function deriveEscalations(brief: Brief, locks: ConsoleState["locks"], incoming: string[]): string[] {
  const out: string[] = [];
  for (const verb of DECISION_VERBS) {
    if (locks[verb]) continue;
    const d = brief.decisions[verb];
    if (d && d.gate === "escalate") {
      out.push(`${verb}: P(${d.chosen})=${d.confidence.toFixed(2)} → escalate`);
    }
  }
  // keep engine-raised entries that are not per-decision (e.g. wardrobe)
  for (const e of incoming) {
    const head = e.split(":")[0];
    if (!DECISION_VERBS.includes(head as DecisionVerb)) out.push(e);
  }
  return out;
}

/** Apply a new lock set: re-derive escalations (locked verbs resolve) and
    prune acknowledgements that no longer apply. */
function applyLocks(state: ConsoleState, locks: ConsoleState["locks"]): ConsoleState {
  if (!state.brief) return { ...state, locks };
  const brief = { ...state.brief };
  brief.escalations = deriveEscalations(brief, locks, state.brief.escalations);
  return {
    ...state,
    locks,
    brief,
    ackedEscalations: state.ackedEscalations.filter((t) => brief.escalations.includes(t)),
  };
}

function clearOutput(s: ConsoleState): ConsoleState {
  return {
    ...s,
    phase: "idle",
    activeStage: null,
    analysis: null,
    verdictDecision: null,
    brief: null,
    locks: {},
    ackedEscalations: [],
    outcome: null,
  };
}

/* ---------------------------------------------------------------- reducer */

export function reducer(state: ConsoleState, action: Action): ConsoleState {
  switch (action.type) {
    case "META_OK":
      return {
        ...state,
        personas: action.personas,
        health: action.health ?? state.health,
        draft: state.draft.personaId
          ? state.draft
          : { ...state.draft, personaId: action.personas[0]?.id ?? "" },
      };

    case "HEALTH_OK":
      return { ...state, health: action.health };

    case "DRAFT_SET": {
      const personaChanged =
        action.patch.personaId !== undefined && action.patch.personaId !== state.draft.personaId;
      const next = { ...state, draft: { ...state.draft, ...action.patch } };
      // A brief belongs to one persona — switching clears the line's output.
      return personaChanged ? clearOutput(next) : next;
    }

    case "RUN_START":
      return {
        ...clearOutput(state),
        phase: "running",
        activeStage: "analyze",
        runId: action.runId,
        errors: [],
      };

    case "STAGE_SET":
      if (action.runId !== state.runId) return state;
      return { ...state, activeStage: action.stage };

    case "ANALYZE_OK":
      if (action.runId !== state.runId) return state;
      return { ...state, analysis: action.analysis, verdictDecision: action.decision };

    case "OVERRIDE_START":
      return { ...state, phase: "overriding", activeStage: "build", runId: action.runId };

    case "BRIEF_OK": {
      if (action.runId !== state.runId) return state;
      const brief = mergeBrief(state.brief, action.brief, state.locks);
      brief.escalations = deriveEscalations(brief, state.locks, action.brief.escalations);
      return {
        ...state,
        brief,
        phase: "ready",
        activeStage: null,
        ackedEscalations: state.ackedEscalations.filter((t) => brief.escalations.includes(t)),
      };
    }

    case "RUN_FAIL": {
      if (action.runId !== state.runId) return state;
      return {
        ...state,
        phase: state.brief ? "ready" : "idle",
        activeStage: null,
        errors: [
          ...state.errors,
          { id: (state.errors.at(-1)?.id ?? 0) + 1, cmd: action.cmd, message: action.message },
        ],
      };
    }

    case "REDRESS_START":
      if (!state.brief || (state.phase !== "ready" && state.phase !== "redressing")) return state;
      return { ...state, phase: "redressing", activeStage: "redress" };

    case "REDRESS_OK": {
      if (state.phase !== "redressing" || !state.brief) return state;
      const merged: Brief = {
        ...state.brief,
        mdep: state.draft.mdep,
        style: {
          ...action.style,
          mdep: state.draft.mdep,
          outfit: state.locks.outfit ? state.brief.style.outfit : action.style.outfit,
          pose: state.locks.outfit ? state.brief.style.pose : action.style.pose,
        },
        expressions: state.locks.expression ? state.brief.expressions : action.expressions,
        decisions: {
          verdict: state.brief.decisions.verdict,
          outfit: state.locks.outfit ? state.brief.decisions.outfit : action.decisions.outfit,
          expression: state.locks.expression ? state.brief.decisions.expression : action.decisions.expression,
        },
        escalations: [],
      };
      merged.escalations = deriveEscalations(merged, state.locks, action.escalations);
      return {
        ...state,
        brief: merged,
        phase: "ready",
        activeStage: null,
        ackedEscalations: state.ackedEscalations.filter((t) => merged.escalations.includes(t)),
      };
    }

    case "REDRESS_FAIL":
      return {
        ...state,
        phase: "ready",
        activeStage: null,
        errors: [
          ...state.errors,
          { id: (state.errors.at(-1)?.id ?? 0) + 1, cmd: action.cmd, message: action.message },
        ],
      };

    case "LOCK_SET": {
      const locks = { ...state.locks, [action.verb]: action.lock };
      // Locking resolves the verb's escalation immediately — no wait for redress.
      return applyLocks(state, locks);
    }

    case "LOCK_CLEAR": {
      const locks = { ...state.locks };
      delete locks[action.verb];
      // Unlocking re-opens the engine's escalation for that verb.
      return applyLocks(state, locks);
    }

    case "ERROR_PUSH":
      return {
        ...state,
        errors: [
          ...state.errors,
          { id: (state.errors.at(-1)?.id ?? 0) + 1, cmd: action.cmd, message: action.message },
        ],
      };

    case "ESC_TOGGLE": {
      const has = state.ackedEscalations.includes(action.text);
      return {
        ...state,
        ackedEscalations: has
          ? state.ackedEscalations.filter((t) => t !== action.text)
          : [...state.ackedEscalations, action.text],
      };
    }

    case "ERROR_DISMISS":
      return { ...state, errors: state.errors.filter((e) => e.id !== action.id) };

    case "OUTCOME_OK":
      return { ...state, outcome: action.outcome };

    case "HYDRATE": {
      const snap = action.snapshot;
      return {
        ...state,
        ...snap,
        draft: { ...state.draft, ...(snap.draft ?? {}) },
        phase: snap.brief ? "ready" : "idle",
        activeStage: null,
      };
    }

    case "RESET":
      return {
        ...initialState,
        personas: state.personas,
        health: state.health,
        draft: { ...INITIAL_DRAFT, personaId: state.draft.personaId },
      };

    default:
      return state;
  }
}

/* ------------------------------------------------------------- selectors */

export const openEscalations = (s: ConsoleState): string[] =>
  (s.brief?.escalations ?? []).filter((e) => !s.ackedEscalations.includes(e));

export const canRun = (s: ConsoleState): boolean =>
  Boolean(
    s.draft.personaId &&
      (s.draft.transcript.trim() || s.draft.idea.trim()) &&
      (s.phase === "idle" || s.phase === "ready" || s.phase === "redressing"),
  );

export const decisionFor = (
  s: ConsoleState,
  verb: DecisionVerb,
): { decision: Decision | null; lock: Lock | null; effective: string | null } => {
  const decision =
    verb === "verdict"
      ? (s.brief?.decisions.verdict ?? s.verdictDecision)
      : (s.brief?.decisions[verb] ?? null);
  const lock = s.locks[verb] ?? null;
  return { decision, lock, effective: lock?.choice ?? decision?.chosen ?? null };
};

export type { MDEP, Persona, Health, DecisionVerb };
