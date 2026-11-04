/* Reducer smoke test — compiles against lib/state.ts and asserts the
   pipeline transitions, lock survival, and escalation derivation. */
import { reducer, initialState, decisionFor, openEscalations, canRun } from "./state";
import type { Action, ConsoleState, Draft } from "./state";
import type { Analysis, Brief, Decision } from "./types";

let failures = 0;
function ok(name: string, cond: boolean, extra = "") {
  if (cond) console.log(`PASS  ${name}`);
  else { failures++; console.log(`FAIL  ${name} ${extra}`); }
}

const decision = (verb: string, chosen: string, gate: "automate" | "escalate", p: number): Decision => ({
  verb, chosen, confidence: p, gate, calibrated: true, rationale: "test",
  options: [{ name: chosen, p, raw: 0.1, signals: [] },
            { name: chosen === "remix" ? "recreate" : "remix", p: 1 - p, raw: -0.1, signals: [] }],
});

const analysis: Analysis = {
  hook: { text_or_action: "h", hook_type: "bold-claim", why_it_works: "w", first_3_seconds: "f" },
  beats: [{ order: 1, timestamp: "0:00", purpose: "hook", what_happens: "x", technique: "t" }],
  ending: { style: "cliffhanger", detail: "", loop_close: false },
  verdict: "remix", verdict_reason: "r", remix_ideas: [], niche_tags: [],
};

const mkBrief = (opts: { vGate?: "automate" | "escalate"; oGate?: "automate" | "escalate"; mode?: "remix" | "recreate" } = {}): Brief => ({
  persona_id: "aria",
  mdep: { mood: "playful", day: "casual weekday", environment: "mall", place: "mall" },
  mode: opts.mode ?? "remix",
  hook: "hook text",
  script_outline: ["0:00 [hook] h"],
  style: {
    outfit: { items: [], jewelry: null, footwear: null, rationale: "r" },
    pose: { poses: ["stance"], shot_notes: "" }, location_notes: "",
  },
  expressions: {
    primary: { name: "genuine_smile", genuine: true, when_to_use: "", micro_details: "" },
    secondary: [], avoid: [], audio_note: "", rationale: "",
  },
  caption_idea: "c", hashtags: ["#a"],
  decisions: {
    verdict: decision("verdict", "remix", opts.vGate ?? "automate", 0.8),
    outfit: decision("outfit", "dress", opts.oGate ?? "automate", 0.75),
    expression: decision("expression", "genuine_smile", "automate", 0.9),
  },
  escalations: [],
});

const draft = (over: Partial<Draft> = {}): Draft => ({
  personaId: "aria", transcript: "t", context: "", idea: "",
  mdep: { mood: "playful", day: "casual weekday", environment: "mall", place: "mall" },
  folder: "", ...over,
});

// 1. boot → meta → draft → canRun
let s: ConsoleState = reducer(initialState, { type: "META_OK", personas: [{ id: "aria", name: "Aria" }], health: null });
ok("META_OK sets persona", s.draft.personaId === "aria");
s = reducer(s, { type: "DRAFT_SET", patch: draft() });
ok("canRun true with transcript", canRun(s));

// 2. run pipeline: start → analyze → stage → brief
s = reducer(s, { type: "RUN_START", runId: 1 });
ok("RUN_START clears output + running", s.phase === "running" && s.brief === null && s.activeStage === "analyze");
s = reducer(s, { type: "ANALYZE_OK", runId: 1, analysis, decision: decision("verdict", "remix", "escalate", 0.55) });
ok("ANALYZE_OK stores analysis + verdict decision", s.analysis !== null && s.verdictDecision?.chosen === "remix");
s = reducer(s, { type: "STAGE_SET", runId: 1, stage: "build" });
ok("STAGE_SET build", s.activeStage === "build");
s = reducer(s, { type: "BRIEF_OK", runId: 1, brief: mkBrief({ vGate: "escalate" }) });
ok("BRIEF_OK → ready", s.phase === "ready" && s.brief !== null);
ok("stale runId ignored", reducer(s, { type: "BRIEF_OK", runId: 99, brief: mkBrief() }) === s);

// 3. escalations derived from escalate gate
const escs = openEscalations(s);
ok("escalate gate → escalation line", escs.some((e) => e.startsWith("verdict:")), JSON.stringify(escs));

// 4. lock outfit → redress keeps locked half, drops escalation for locked verb
s = reducer(s, { type: "LOCK_SET", verb: "outfit", lock: { choice: "dress", modelChoice: "dress", modelP: 0.75, overridden: false, at: 1 } });
s = reducer(s, { type: "REDRESS_START" });
ok("REDRESS_START → redressing", s.phase === "redressing");
const newBrief = mkBrief({ oGate: "escalate" });
newBrief.style.outfit.rationale = "NEW-STYLE";
newBrief.expressions.rationale = "NEW-EXPR";
s = reducer(s, { type: "REDRESS_OK", style: newBrief.style, expressions: newBrief.expressions,
                 decisions: newBrief.decisions, escalations: [] });
ok("redress → ready", s.phase === "ready");
ok("locked outfit survives redress", s.brief!.style.outfit.rationale !== "NEW-STYLE");
ok("unlocked expression updates", s.brief!.expressions.rationale === "NEW-EXPR");
ok("locked outfit escalation dropped", !openEscalations(s).some((e) => e.startsWith("outfit:")), JSON.stringify(openEscalations(s)));

// 5. unlock clears lock; override sets lock with overridden flag
s = reducer(s, { type: "LOCK_CLEAR", verb: "outfit" });
ok("LOCK_CLEAR removes lock", !s.locks.outfit);
s = reducer(s, { type: "LOCK_SET", verb: "verdict", lock: { choice: "recreate", modelChoice: "remix", modelP: 0.55, overridden: true, at: 2 } });
const vf = decisionFor(s, "verdict");
ok("override: effective = operator choice", vf.effective === "recreate");
ok("override: escalation for locked verb dropped", !openEscalations(s).some((e) => e.startsWith("verdict:")));

// 6. persona switch clears output
s = reducer(s, { type: "DRAFT_SET", patch: { personaId: "kai" } });
ok("persona switch clears line output", s.brief === null && s.analysis === null && Object.keys(s.locks).length === 0);

// 6b. a late RUN_FAIL from the abandoned run must not push a stray error
s = reducer(s, { type: "RUN_FAIL", runId: s.runId, cmd: "brief", message: "late failure" });
ok("late RUN_FAIL after persona switch ignored", s.errors.length === 0, JSON.stringify(s.errors));

// 7. errors queue + dismiss
s = reducer(s, { type: "ERROR_PUSH", cmd: "plan-day", message: "boom" });
s = reducer(s, { type: "ERROR_PUSH", cmd: "brief", message: "bust" });
ok("errors queue", s.errors.length === 2);
s = reducer(s, { type: "ERROR_DISMISS", id: s.errors[0].id });
ok("error dismiss", s.errors.length === 1);

// 8. hydrate restores session and lands in ready
const hydrated = reducer(initialState, { type: "HYDRATE", snapshot: { brief: mkBrief(), analysis, draft: draft() } });
ok("HYDRATE → ready with brief", hydrated.phase === "ready" && hydrated.brief !== null && hydrated.draft.transcript === "t");

// 9. reset keeps personas
const reset = reducer({ ...s, personas: [{ id: "aria", name: "Aria" }] }, { type: "RESET" });
ok("RESET keeps personas, clears output", reset.personas.length === 1 && reset.brief === null && reset.errors.length === 0);

// 10. outcome records
const withOutcome = reducer(s, { type: "OUTCOME_OK", outcome: { verb: "verdict", option: "remix", brier: 0.31, at: 3 } });
ok("OUTCOME_OK stores outcome", withOutcome.outcome?.brier === 0.31);

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
