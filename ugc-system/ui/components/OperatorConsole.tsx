"use client";

/* OperatorConsole — composes the assembly line.

   Logic spine: one reducer (lib/state.ts) + async callbacks guarded by
   runId/AbortController. The pipeline runs analyze → brief as two real
   engine calls so the StageRail shows honest progress. MDEP changes
   re-dress via a debounced, abortable plan-day that respects operator locks.
*/
import { useCallback, useEffect, useReducer, useRef } from "react";
import { EngineError, engine, isAbort } from "../lib/engine";
import { loadSnapshot, saveSnapshot } from "../lib/persistence";
import {
  canRun as canRunSel,
  decisionFor,
  initialState,
  openEscalations,
  reducer,
} from "../lib/state";
import type { DecisionVerb, VerdictMode } from "../lib/types";
import type {
  AnalyzeRes,
  BriefRes,
  Health,
  OutcomeRes,
  Persona,
  PlanDayRes,
} from "../lib/types";
import { TopRail } from "./shell/TopRail";
import { StageRail } from "./shell/StageRail";
import { Ledger } from "./shell/Ledger";
import { StationBoundary } from "./ui";
import { IntakeStation } from "./stations/IntakeStation";
import { AnalyzerStation } from "./stations/AnalyzerStation";
import { StylistStation } from "./stations/StylistStation";
import { ExpressionStation } from "./stations/ExpressionStation";
import { DispatchStation } from "./stations/DispatchStation";

const errText = (e: unknown): string =>
  e instanceof EngineError ? `${e.cmd}: ${e.message}` : e instanceof Error ? e.message : String(e);

const redressKey = (personaId: string, mdep: unknown) => `${personaId}|${JSON.stringify(mdep)}`;

export default function OperatorConsole() {
  const [s, dispatch] = useReducer(reducer, initialState);
  const stateRef = useRef(s);
  stateRef.current = s;

  const runRef = useRef({ runId: 0, ac: null as AbortController | null });
  const redressRef = useRef({ seq: 0, ac: null as AbortController | null });
  const lastRedressKey = useRef<string | null>(null);

  /* ---------- boot: hydrate session, then load meta ---------- */

  useEffect(() => {
    const snap = loadSnapshot();
    if (snap && (snap.brief || snap.analysis || (snap.draft?.transcript ?? "") || (snap.draft?.idea ?? ""))) {
      dispatch({ type: "HYDRATE", snapshot: snap });
    }
  }, []);

  const loadMeta = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([
        engine<{ personas: Persona[] }>("personas", {}),
        engine<Health>("health", {}),
      ]);
      dispatch({ type: "META_OK", personas: p.personas, health: h });
    } catch (e) {
      // Poll retries hit this too — dedupe so a dead bridge shows one error
      // instead of one every 30 seconds.
      const message = errText(e);
      const last = stateRef.current.errors.at(-1);
      if (last?.cmd === "personas" && last.message === message) return;
      dispatch({ type: "ERROR_PUSH", cmd: "personas", message });
    }
  }, []);

  useEffect(() => {
    void loadMeta();
    // Liveness: re-check health every 30s so LEDs reflect the engine without
    // waiting for the operator to press Refresh.
    const t = window.setInterval(() => void loadMeta(), 30_000);
    return () => window.clearInterval(t);
  }, [loadMeta]);

  /* ---------- persistence (debounced view-cache) ---------- */

  useEffect(() => {
    const t = window.setTimeout(() => saveSnapshot(stateRef.current), 400);
    return () => window.clearTimeout(t);
  }, [s]);

  /* ---------- MDEP re-dress: debounced + abortable + stale-guarded ---------- */

  useEffect(() => {
    const cur = stateRef.current;
    if (!cur.brief || (cur.phase !== "ready" && cur.phase !== "redressing")) return;
    const key = redressKey(cur.draft.personaId, cur.draft.mdep);
    if (lastRedressKey.current === null) {
      lastRedressKey.current = key;
      return;
    }
    if (key === lastRedressKey.current) return;

    const t = window.setTimeout(async () => {
      lastRedressKey.current = key;
      redressRef.current.ac?.abort();
      const seq = ++redressRef.current.seq;
      const ac = new AbortController();
      redressRef.current.ac = ac;
      const runIdAtStart = stateRef.current.runId;
      const { personaId, mdep } = stateRef.current.draft;
      const briefAtStart = stateRef.current.brief;
      const hookType = stateRef.current.analysis?.hook.hook_type ?? "";
      dispatch({ type: "REDRESS_START" });
      try {
        const d = await engine<PlanDayRes>(
          "plan-day",
          {
            persona: personaId,
            mdep,
            hook_text: briefAtStart?.hook ?? "",
            verdict: briefAtStart?.mode ?? "remix",
            hook_type: hookType,
            // the engine composes the full escalation list (verdict included)
            // from this decision — the UI only filters it by locks.
            verdict_decision:
              briefAtStart?.decisions.verdict ?? stateRef.current.verdictDecision ?? null,
          },
          { signal: ac.signal },
        );
        if (seq !== redressRef.current.seq || runIdAtStart !== stateRef.current.runId) return;
        dispatch({
          type: "REDRESS_OK",
          style: d.style,
          expressions: d.expressions,
          decisions: d.decisions,
          escalations: d.escalations ?? [],
        });
      } catch (e) {
        if (isAbort(e) || seq !== redressRef.current.seq) return;
        dispatch({ type: "REDRESS_FAIL", cmd: "plan-day", message: errText(e) });
      }
    }, 450);
    return () => window.clearTimeout(t);
  }, [s.draft.mdep, s.draft.personaId, s.phase, s.brief]);

  /* ---------- the line: analyze → brief ---------- */

  const runLine = useCallback(async () => {
    const st = stateRef.current;
    if (st.phase === "running" || st.phase === "overriding" || !canRunSel(st)) return;

    // cancel any in-flight redress — a new run supersedes it
    redressRef.current.ac?.abort();
    redressRef.current.seq += 1;
    runRef.current.ac?.abort();
    const ac = new AbortController();
    runRef.current.ac = ac;
    const runId = ++runRef.current.runId;

    dispatch({ type: "RUN_START", runId });
    const { transcript, context, idea, personaId, mdep } = st.draft;
    const persona = st.personas.find((p) => p.id === personaId);
    let cmd = "analyze";
    let echo: AnalyzeRes | null = null;
    try {
      // idea-only runs have nothing to analyze — skip straight to the brief
      if (transcript.trim()) {
        echo = await engine<AnalyzeRes>(
          "analyze",
          { transcript, context, persona_niche: persona?.niche ?? "" },
          { signal: ac.signal },
        );
        dispatch({ type: "ANALYZE_OK", runId, analysis: echo.analysis, decision: echo.decision });
      }
      dispatch({ type: "STAGE_SET", runId, stage: "build" });
      cmd = "brief";
      // log:false — drafts never touch the stylist's cooldown log; the
      // operator commits usage explicitly via Save brief (save-brief).
      // The analysis/decision echo rides along: the brief reuses this exact
      // analysis instead of re-running the analyzer (one analysis, one cost).
      const b = await engine<BriefRes>(
        "brief",
        {
          persona: personaId, mdep, transcript, context, idea, mode: null, log: false,
          analysis: echo?.analysis ?? null,
          verdict_decision: echo?.decision ?? null,
        },
        { signal: ac.signal },
      );
      dispatch({ type: "BRIEF_OK", runId, brief: b.brief, analysis: b.analysis });
      // seed from the brief's own MDEP: if the operator edited MDEP while the
      // line ran, keys differ and a reconciling re-dress fires.
      lastRedressKey.current = redressKey(stateRef.current.draft.personaId, b.brief.mdep);
    } catch (e) {
      if (isAbort(e)) return;
      dispatch({ type: "RUN_FAIL", runId, cmd, message: errText(e) });
    }
  }, []);

  /* ---------- operator cancel: abort the fetch, stale-guard the rest ---------- */

  const cancelRun = useCallback(() => {
    runRef.current.ac?.abort();
    redressRef.current.ac?.abort();
    redressRef.current.seq += 1;
    // Component counter and reducer runId both move past the cancelled run,
    // so nothing it produces can land afterwards.
    ++runRef.current.runId;
    dispatch({ type: "RUN_CANCEL" });
  }, []);

  /* ---------- shared: rebuild the brief with a given Verdict mode ---------- */

  const rebuildBrief = useCallback(async (mode: VerdictMode, onFail?: () => void) => {
    const st = stateRef.current;
    if (!st.brief) return;
    if (st.phase !== "ready" && st.phase !== "overriding" && st.phase !== "redressing") return;

    // supersede anything in flight
    redressRef.current.ac?.abort();
    redressRef.current.seq += 1;
    runRef.current.ac?.abort();
    const ac = new AbortController();
    runRef.current.ac = ac;
    const runId = ++runRef.current.runId;
    dispatch({ type: "OVERRIDE_START", runId });
    const { transcript, context, idea, personaId, mdep } = st.draft;
    try {
      // Echo the analysis/decision that already shaped the on-screen brief:
      // an override changes the mode only — the Analyzer station and the
      // rebuilt ticket keep sharing one analysis (and no extra LLM call).
      const b = await engine<BriefRes>(
        "brief",
        {
          persona: personaId, mdep, transcript, context, idea, mode, log: false,
          analysis: st.analysis,
          verdict_decision: st.verdictDecision,
        },
        { signal: ac.signal },
      );
      dispatch({ type: "BRIEF_OK", runId, brief: b.brief, analysis: b.analysis });
      lastRedressKey.current = redressKey(stateRef.current.draft.personaId, b.brief.mdep);
    } catch (e) {
      if (isAbort(e)) return;
      onFail?.();
      dispatch({ type: "RUN_FAIL", runId, cmd: "brief", message: errText(e) });
    }
  }, []);

  /* ---------- verdict override: rebuild with the operator's mode ---------- */

  const overrideVerdict = useCallback(async (choice: VerdictMode) => {
    const st = stateRef.current;
    const d = st.brief?.decisions.verdict ?? st.verdictDecision;
    if (!st.brief || !d || st.phase !== "ready") return;
    const current = (st.locks.verdict?.choice ?? st.brief.mode) as VerdictMode;
    if (choice === current) return;

    dispatch({
      type: "LOCK_SET",
      verb: "verdict",
      lock: {
        choice,
        modelChoice: d.chosen,
        modelP: d.confidence,
        overridden: choice !== d.chosen,
        at: Date.now(),
      },
    });
    await rebuildBrief(choice, () => dispatch({ type: "LOCK_CLEAR", verb: "verdict" }));
  }, [rebuildBrief]);

  /* ---------- operator authority ---------- */

  const toggleLock = useCallback((verb: DecisionVerb) => {
    const st = stateRef.current;
    const { decision, lock } = decisionFor(st, verb);
    if (!decision) return;
    if (lock) {
      dispatch({ type: "LOCK_CLEAR", verb });
      // An override left brief.mode at the operator's choice — rebuild with
      // the engine's calibrated call so stamp, card, and script agree again.
      if (verb === "verdict" && st.brief && st.brief.mode !== decision.chosen &&
          (st.phase === "ready" || st.phase === "redressing")) {
        void rebuildBrief(
          decision.chosen as VerdictMode,
          () => dispatch({ type: "LOCK_SET", verb: "verdict", lock }),
        );
      }
      return;
    }
    const choice = verb === "verdict" ? (st.brief?.mode ?? decision.chosen) : decision.chosen;
    dispatch({
      type: "LOCK_SET",
      verb,
      lock: {
        choice,
        modelChoice: decision.chosen,
        modelP: decision.confidence,
        overridden: choice !== decision.chosen,
        at: Date.now(),
      },
    });
  }, [rebuildBrief]);

  /* ---------- outcome capture (honest option-name Brier) ---------- */

  const saveOutcome = useCallback(async (verb: DecisionVerb, option: string) => {
    const st = stateRef.current;
    const { decision } = decisionFor(st, verb);
    if (!decision) return;
    try {
      const out = await engine<OutcomeRes>("outcome", {
        verb: decision.verb,
        chosen: decision.chosen,
        confidence: decision.confidence,
        gate: decision.gate,
        options: decision.options,
        outcome: option,
      });
      dispatch({
        type: "OUTCOME_OK",
        outcome: { verb, option, brier: out.brier, at: Date.now() },
      });
    } catch (e) {
      dispatch({ type: "ERROR_PUSH", cmd: "outcome", message: errText(e) });
    }
  }, []);

  /* ---------- navigation ---------- */

  const jump = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    el.focus({ preventScroll: true });
  }, []);

  /* ---------- derived ---------- */

  const verdict = decisionFor(s, "verdict");
  const outfit = decisionFor(s, "outfit");
  const expression = decisionFor(s, "expression");
  const escalations = openEscalations(s);

  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to the line</a>

      <TopRail
        personas={s.personas}
        personaId={s.draft.personaId}
        health={s.health}
        onPersona={(id) => {
          if (id !== s.draft.personaId) {
            // persona switch abandons the line — stop paying for its calls
            runRef.current.ac?.abort();
            redressRef.current.ac?.abort();
            redressRef.current.seq += 1;
          }
          dispatch({ type: "DRAFT_SET", patch: { personaId: id } });
        }}
        onRefresh={() => void loadMeta()}
      />

      <StageRail state={s} onJump={jump} />

      {s.errors.length > 0 && (
        <div className="errorbar" role="alert">
          {s.errors.map((e) => (
            <div className="err-item" key={e.id}>
              <strong>Engine error · {e.cmd}</strong>
              <span>{e.message}</span>
              <button
                type="button"
                className="dismiss"
                onClick={() => dispatch({ type: "ERROR_DISMISS", id: e.id })}
                aria-label={`Dismiss error from ${e.cmd}`}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      <main className="console" id="main" tabIndex={-1}>
        <StationBoundary label="Intake">
          <IntakeStation
            state={s}
            onDraft={(patch) => dispatch({ type: "DRAFT_SET", patch })}
            onRun={() => void runLine()}
            onCancel={cancelRun}
            canRun={canRunSel(s)}
            onScanned={() => void loadMeta()}
          />
        </StationBoundary>

        <div className="col col-line">
          <StationBoundary label="Analyzer">
            <AnalyzerStation
              state={s}
              analysis={s.analysis}
              decision={verdict.decision}
              lock={verdict.lock}
              onToggleLock={() => toggleLock("verdict")}
              onOverride={(c) => void overrideVerdict(c)}
            />
          </StationBoundary>
          <StationBoundary label="Stylist">
            <StylistStation
              state={s}
              decision={outfit.decision}
              lock={outfit.lock}
              onToggleLock={() => toggleLock("outfit")}
              onJumpIntake={() => jump("station-intake")}
            />
          </StationBoundary>
          <StationBoundary label="Expression">
            <ExpressionStation
              state={s}
              decision={expression.decision}
              lock={expression.lock}
              onToggleLock={() => toggleLock("expression")}
            />
          </StationBoundary>
          <StationBoundary label="Dispatch">
            <DispatchStation state={s} />
          </StationBoundary>
        </div>

        <Ledger
          state={s}
          onToggleLock={toggleLock}
          onJump={jump}
          onAck={(text) => dispatch({ type: "ESC_TOGGLE", text })}
          onSaveOutcome={saveOutcome}
          onReset={() => {
            lastRedressKey.current = null;
            dispatch({ type: "RESET" });
          }}
        />
      </main>

      <footer className="foot">
        <span>Live engine only · no demo data</span>
        <span className="tnum">open escalations: {escalations.length}</span>
        <span className="tnum">/api/engine {"{cmd, payload}"}</span>
        <span>personas · health · scan · analyze · brief · line · plan-day · outcome</span>
      </footer>
    </div>
  );
}
