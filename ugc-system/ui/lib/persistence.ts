/* localStorage view-cache for the console session.
   Draft (intake) always saves; the line's output saves once it exists.
   This is a view cache — data/briefs/ via the Python engine stays authoritative. */
import type { ConsoleState, Draft, Lock, OutcomeState } from "./state";
import type { Analysis, Brief, Decision } from "./types";

const KEY = "ugc-factory/console-v1";
const VERSION = 1;

interface StoredSession {
  analysis: Analysis | null;
  verdictDecision: Decision | null;
  brief: Brief | null;
  locks: Partial<Record<string, Lock>>;
  ackedEscalations: string[];
  outcome: OutcomeState | null;
}

interface Stored {
  version: number;
  draft: Partial<Draft>;
  session: StoredSession | null;
}

export function loadSnapshot(): Partial<ConsoleState> | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Stored;
    if (data.version !== VERSION) return null;
    const out: Partial<ConsoleState> = {};
    if (data.draft) out.draft = data.draft as Draft;
    if (data.session) {
      out.analysis = data.session.analysis ?? null;
      out.verdictDecision = data.session.verdictDecision ?? null;
      out.brief = data.session.brief ?? null;
      out.locks = (data.session.locks ?? {}) as ConsoleState["locks"];
      out.ackedEscalations = data.session.ackedEscalations ?? [];
      out.outcome = data.session.outcome ?? null;
    }
    return out;
  } catch {
    return null;
  }
}

export function saveSnapshot(s: ConsoleState): void {
  try {
    const hasOutput = Boolean(s.brief || s.analysis);
    const session: StoredSession | null = hasOutput
      ? {
          analysis: s.analysis,
          verdictDecision: s.verdictDecision,
          brief: s.brief,
          locks: s.locks,
          ackedEscalations: s.ackedEscalations,
          outcome: s.outcome,
        }
      : null;
    const data: Stored = { version: VERSION, draft: s.draft, session };
    window.localStorage.setItem(KEY, JSON.stringify(data));
  } catch {
    // storage full / private mode — session simply won't survive refresh
  }
}
