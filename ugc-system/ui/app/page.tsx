"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/* ---------------- engine types (mirror bridge.py / Python models) ---------------- */

interface Hook {
  text_or_action: string;
  hook_type: string;
  why_it_works: string;
  first_3_seconds: string;
}
interface Beat {
  order: number;
  timestamp: string;
  purpose: string;
  what_happens: string;
  technique: string;
}
interface Analysis {
  hook: Hook;
  beats: Beat[];
  ending: { style: string; detail: string; loop_close: boolean };
  verdict: "remix" | "recreate";
  verdict_reason: string;
  remix_ideas: string[];
  niche_tags: string[];
}
interface Asset {
  path: string;
  category: string;
  brands: string[];
  colors: string[];
  style_tags: string[];
  formality: number;
}
interface Expression {
  name: string;
  genuine: boolean;
  when_to_use: string;
  micro_details: string;
}
interface OptionScore {
  name: string;
  p: number;
  raw: number;
  signals: string[];
}
interface Decision {
  verb: string;
  chosen: string;
  confidence: number;
  gate: "automate" | "escalate";
  calibrated: boolean;
  rationale: string;
  brier_estimate?: number;
  options: OptionScore[];
}
interface Decisions {
  verdict: Decision | null;
  outfit: Decision | null;
  expression: Decision | null;
}
interface Brief {
  persona_id: string;
  mode: "remix" | "recreate";
  hook: string;
  script_outline: string[];
  style: {
    outfit: { items: Asset[]; jewelry: Asset | null; footwear: Asset | null; rationale: string };
    pose: { poses: string[]; shot_notes: string };
    location_notes: string;
  };
  expressions: {
    primary: Expression;
    secondary: Expression[];
    avoid: string[];
    audio_note: string;
    rationale: string;
  };
  caption_idea: string;
  hashtags: string[];
  decisions?: Decisions;
  escalations?: string[];
}
interface Persona {
  id: string;
  name: string;
  niche?: string;
  gender?: string;
  aesthetic?: string;
  voice_tone?: string;
}
interface Health {
  ok: boolean;
  jev: boolean;
  llm: boolean;
  assets: number;
  personas: number;
}

/* ---------------- MDEP options (keys match engine rules) ---------------- */

const MOODS = ["neutral", "confident", "cozy", "playful", "elegant", "edgy", "relaxed", "focused", "grateful"];
const DAYS = ["casual weekday", "weekend", "vacation day", "event night", "workday", "festival"];
const ENVIRONMENTS = ["home", "mall", "fastfood", "vacation", "work", "studio", "ramp", "beach", "restaurant", "gym", "party"];
const PLACES = ["home", "fastfood", "mall", "vacation", "work", "studio", "ramp", "beach", "restaurant", "gym", "party"];
const OUTCOME_ABC = ["A", "B", "C", "D"];

interface MDEP { mood: string; day: string; environment: string; place: string }

/* ---------------- helpers ---------------- */

const fileName = (p: string) => p.split("/").pop() ?? p;
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
const pretty = (s: string) => s.replace(/_/g, " ");

async function engine<T>(cmd: string, payload: unknown): Promise<T> {
  const res = await fetch("/api/engine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd, payload }),
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data as T;
}

/* ---------------- shared atoms ---------------- */

function Panel({
  idx, title, stamp, children,
}: {
  idx: string; title: string; stamp?: string; children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <header className="panel-head">
        <span className="idx tnum">{idx}</span>
        <h2>{title}</h2>
        {stamp && <span className="spacer" />}
        {stamp && <span className="status-pill">{stamp}</span>}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function SkeletonStack({ n = 3 }: { n?: number }) {
  return (
    <div className="skel-stack" aria-label="loading" aria-busy="true">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className={`skel skel-line ${i % 2 ? "mid" : "short"}`} />
      ))}
      <div className="skel skel-block" />
    </div>
  );
}

function DecisionCard({
  title, decision, emptyNote,
}: {
  title: string; decision: Decision | null | undefined; emptyNote?: string;
}) {
  if (!decision) {
    return (
      <div className="jev" aria-label={title}>
        <div className="jev-head">
          <span className="verb">JEV · {title}</span>
          <span className="status-pill">No decision</span>
        </div>
        <div className="jev-body">
          <p className="empty s" style={{ margin: 0 }}>{emptyNote ?? "Awaiting engine output."}</p>
        </div>
      </div>
    );
  }
  const sorted = [...decision.options].sort((a, b) => b.p - a.p);
  const topSignals = sorted[0]?.signals ?? [];
  return (
    <div className="jev" aria-label={`${title} decision`}>
      <div className="jev-head">
        <span className="verb">JEV · {title}</span>
        <span className="chosen">{decision.chosen}</span>
        <span className={`chip ${decision.gate === "automate" ? "ok" : "warn"}`}>
          {decision.gate === "automate" ? "Automate" : "Escalate"}
        </span>
        <div className="jev-bigp">
          <div className="p tnum">{pct(decision.confidence)}</div>
          <div className="cap">P({decision.chosen})</div>
        </div>
      </div>
      <div className="jev-body">
        <div className="jev-opts" role="table" aria-label="Option probabilities">
          {sorted.map((o) => (
            <div key={o.name} className={`jev-opt ${o.name === decision.chosen ? "chosen" : ""}`} role="row">
              <span className="name" title={o.name}>{o.name}</span>
              <span className="bar"><i className={o.name === decision.chosen ? "chosen" : ""} style={{ width: `${Math.max(0, Math.min(1, o.p)) * 100}%` }} /></span>
              <span className="p tnum">{pct(o.p)}</span>
            </div>
          ))}
        </div>
        {decision.rationale && <p className="jev-rationale">{decision.rationale}</p>}
        {topSignals.length > 0 && (
          <div className="jev-signals">
            {topSignals.map((s, i) => <span className="chip" key={i}>{s}</span>)}
          </div>
        )}
        <div className="jev-meta tnum">
          calibrated: {decision.calibrated ? "yes" : "no"}
          {decision.brier_estimate != null && <> · brier≈{decision.brier_estimate.toFixed(3)}</>}
          <span className="chip accent" style={{ marginLeft: 6 }}>scores are calibrated, not raw sorts</span>
        </div>
      </div>
    </div>
  );
}

/* ---------------- the console ---------------- */

export default function OperatorConsole() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personaId, setPersonaId] = useState("");
  const [health, setHealth] = useState<Health | null>(null);

  const [transcript, setTranscript] = useState("");
  const [context, setContext] = useState("");
  const [idea, setIdea] = useState("");
  const [folder, setFolder] = useState("");

  const [mdep, setMdep] = useState<MDEP>({
    mood: "playful", day: "casual weekday", environment: "mall", place: "mall",
  });

  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [planDecisions, setPlanDecisions] = useState<{ outfit: Decision | null; expression: Decision | null } | null>(null);
  const [verdictDecision, setVerdictDecision] = useState<Decision | null>(null);

  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [err, setErr] = useState("");

  const [copied, setCopied] = useState(false);
  const [outcome, setOutcome] = useState("A");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [saveOk, setSaveOk] = useState<boolean | null>(null);
  const [scanMsg, setScanMsg] = useState("");

  const prevMdep = useRef<MDEP>(mdep);

  const loadMeta = useCallback(async () => {
    try {
      const [p, h] = await Promise.all([
        engine<{ personas: Persona[] }>("personas", {}),
        engine<Health>("health", {}),
      ]);
      setPersonas(p.personas);
      setHealth(h);
      setPersonaId((cur) => cur || p.personas[0]?.id || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { loadMeta(); }, [loadMeta]);

  /* MDEP change re-dresses + re-expresses live (plan-day), like before */
  useEffect(() => {
    if (!brief || !personaId || running) { prevMdep.current = mdep; return; }
    if (prevMdep.current === mdep) return;
    prevMdep.current = mdep;
    setRefreshing(true);
    const t = setTimeout(() => {
      engine<{ style: Brief["style"]; expressions: Brief["expressions"]; decisions: { outfit: Decision | null; expression: Decision | null } }>("plan-day", { persona: personaId, mdep })
        .then((d) => {
          setBrief((b) => (b ? { ...b, style: d.style, expressions: d.expressions, decisions: { ...(b.decisions ?? { verdict: null }), outfit: d.decisions.outfit, expression: d.decisions.expression } } : b));
          setPlanDecisions({ outfit: d.decisions.outfit, expression: d.decisions.expression });
        })
        .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
        .finally(() => setRefreshing(false));
    }, 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mdep]);

  const runLine = useCallback(async () => {
    if (running || !personaId || (!transcript.trim() && !idea.trim())) return;
    setErr("");
    setRunning(true);
    setAnalysis(null);
    setBrief(null);
    setVerdictDecision(null);
    setPlanDecisions(null);
    setSaveMsg("");
    setSaveOk(null);
    try {
      const out = await engine<{ analysis: Analysis | null; brief: Brief }>("line", {
        persona: personaId,
        mdep,
        transcript: transcript.trim(),
        context: context.trim(),
        idea: idea.trim(),
        mode: null,
      });
      setAnalysis(out.analysis);
      setBrief(out.brief);
      setVerdictDecision(out.brief.decisions?.verdict ?? null);
      setPlanDecisions({ outfit: out.brief.decisions?.outfit ?? null, expression: out.brief.decisions?.expression ?? null });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }, [running, personaId, transcript, idea, context, mdep]);

  const scanAssets = useCallback(async () => {
    const f = folder.trim();
    if (scanning || !f) return;
    setErr("");
    setScanning(true);
    setScanMsg("");
    try {
      const d = await engine<{ count: number; by_category: Record<string, number> }>("scan", { folder: f });
      const by = Object.entries(d.by_category).map(([k, v]) => `${k}: ${v}`).join(" · ");
      setScanMsg(`${d.count} asset${d.count === 1 ? "" : "s"} indexed (${by || "no categories"})`);
      const h = await engine<Health>("health", {});
      setHealth(h);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setScanning(false);
    }
  }, [folder, scanning]);

  const copyTicket = () => {
    if (!brief) return;
    const txt = JSON.stringify(brief, null, 2);
    if (navigator.clipboard) {
      navigator.clipboard.writeText(txt).then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      }).catch(() => setErr("Clipboard write failed — select the ticket JSON manually."));
    }
  };

  const saveOutcome = useCallback(async () => {
    if (!brief?.decisions?.verdict) { setSaveMsg("No verdict decision to score."); setSaveOk(false); return; }
    const d = brief.decisions.verdict;
    setSaving(true);
    setSaveMsg("");
    try {
      const out = await engine<{ brier: number }>("outcome", {
        verb: d.verb, chosen: d.chosen, confidence: d.confidence, gate: d.gate,
        options: d.options, outcome,
      });
      setSaveMsg(`Logged — Brier ${out.brier.toFixed(3)}`);
      setSaveOk(true);
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : String(e));
      setSaveOk(false);
    } finally {
      setSaving(false);
    }
  }, [brief, outcome]);

  const persona = personas.find((p) => p.id === personaId);
  const canRun = Boolean(personaId && (transcript.trim() || idea.trim()) && !running);
  const outfitEmpty = Boolean(brief && brief.style.outfit.items.length === 0 && !brief.style.outfit.jewelry && !brief.style.outfit.footwear);
  const outfitDecision = planDecisions?.outfit ?? brief?.decisions?.outfit ?? null;
  const exprDecision = planDecisions?.expression ?? brief?.decisions?.expression ?? null;
  const verdictDec = brief?.decisions?.verdict ?? verdictDecision;
  const escalations = brief?.escalations ?? [];

  return (
    <div className="shell">
      {/* ---------- header ---------- */}
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">UG</span>
          <div>
            <div className="brand-name">UGC Factory</div>
          </div>
          <span className="brand-mode">Operate</span>
        </div>

        <div className="health" aria-label="engine health">
          <span className={`led ${health ? (health.jev ? "on" : "warn") : ""}`}>
            <span className="dot" /> JEV <b>{health ? (health.jev ? "online" : "local") : "…"}</b>
          </span>
          <span className={`led ${health ? (health.llm ? "on" : "warn") : ""}`}>
            <span className="dot" /> LLM <b>{health ? (health.llm ? "configured" : "off") : "…"}</b>
          </span>
          <span className="led"><span className="dot" style={{ background: "var(--accent)" }} /> Assets <b className="tnum">{health?.assets ?? "—"}</b></span>
          <span className="led"><span className="dot" style={{ background: "var(--accent)" }} /> Personas <b className="tnum">{health?.personas ?? "—"}</b></span>
        </div>

        <div className="top-actions">
          <button className="btn-refresh" onClick={loadMeta} title="Reload personas + health from the engine">
            ↻ Refresh
          </button>
        </div>
      </header>

      {err && (
        <div className="errorbar" role="alert">
          <strong>Engine error</strong>
          <span>{err}</span>
          <button className="dismiss" onClick={() => setErr("")} aria-label="Dismiss error">✕</button>
        </div>
      )}

      {/* ---------- console ---------- */}
      <main className="console">
        {/* ----- left: Intake ----- */}
        <div className="col">
          <Panel idx="01" title="Intake">
            <div className="field">
              <label htmlFor="f-persona">Persona</label>
              <select
                id="f-persona"
                value={personaId}
                onChange={(e) => setPersonaId(e.target.value)}
                disabled={personas.length === 0}
              >
                {personas.length === 0 && <option value="">Loading personas…</option>}
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>{p.name} ({p.id})</option>
                ))}
              </select>
              {persona && (
                <span className="persona-meta">
                  {persona.niche ?? "—"} · {persona.gender ?? "—"} · {persona.aesthetic ?? "—"}
                  {persona.voice_tone ? <> · “{persona.voice_tone}”</> : null}
                </span>
              )}
            </div>

            <div className="field">
              <label htmlFor="f-transcript">Reel transcript</label>
              <textarea
                id="f-transcript"
                rows={6}
                placeholder="Paste the reel transcript or script here…"
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
              />
              <span className="count tnum">{transcript.length} chars</span>
            </div>

            <div className="field">
              <label htmlFor="f-context">Context — why it fits this persona</label>
              <input
                id="f-context"
                type="text"
                placeholder="e.g. pacing and lighting suit Aria's audience"
                value={context}
                onChange={(e) => setContext(e.target.value)}
              />
            </div>

            <div className="field">
              <label htmlFor="f-idea">Idea / twist (optional)</label>
              <input
                id="f-idea"
                type="text"
                placeholder="e.g. same script, but in a thrift store"
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
              />
            </div>

            <div className="field">
              <span className="flabel">Shoot day (MDEP)</span>
              <div className="mdep-grid">
                <div className="field">
                  <label htmlFor="m-mood">Mood</label>
                  <select id="m-mood" value={mdep.mood} onChange={(e) => setMdep((m) => ({ ...m, mood: e.target.value }))}>
                    {MOODS.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="m-day">Day</label>
                  <select id="m-day" value={mdep.day} onChange={(e) => setMdep((m) => ({ ...m, day: e.target.value }))}>
                    {DAYS.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="m-env">Environment</label>
                  <select id="m-env" value={mdep.environment} onChange={(e) => setMdep((m) => ({ ...m, environment: e.target.value, place: e.target.value }))}>
                    {ENVIRONMENTS.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="m-place">Place</label>
                  <select id="m-place" value={mdep.place} onChange={(e) => setMdep((m) => ({ ...m, place: e.target.value }))}>
                    {PLACES.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
              </div>
              <span className="hint tnum">{mdep.mood} | {mdep.day} | {mdep.environment} → {mdep.place}</span>
            </div>

            <div className="actions">
              <button className="btn-primary" onClick={runLine} disabled={!canRun}>
                {running ? "Running…" : "Run line"}
              </button>
            </div>
            {!personaId && <p className="hint">No persona loaded — check the engine is reachable.</p>}
            {personaId && !transcript.trim() && !idea.trim() && (
              <p className="hint">Add a transcript or an idea to enable Run line.</p>
            )}

            <div className="scan-row">
              <div className="field">
                <label htmlFor="f-folder">Asset folder</label>
                <input
                  id="f-folder"
                  type="text"
                  placeholder="C:\path\to\assets (or relative to ugc-system)"
                  value={folder}
                  onChange={(e) => setFolder(e.target.value)}
                />
              </div>
              <div className="actions">
                <button
                  className="btn-secondary"
                  onClick={scanAssets}
                  disabled={scanning || !folder.trim()}
                  title="POST scan — indexes the folder and refreshes the asset count"
                >
                  {scanning ? "Scanning…" : "Scan assets"}
                </button>
              </div>
              {scanMsg && <p className="scan-result">{scanMsg}</p>}
            </div>
          </Panel>
        </div>

        {/* ----- middle: Analyzer ----- */}
        <div className="col">
          <Panel idx="02" title="Analyzer" stamp={running ? "Scanning" : analysis ? "Complete" : undefined}>
            {running ? (
              <SkeletonStack n={4} />
            ) : !analysis ? (
              <div className="empty">
                <div className="t">No analysis yet</div>
                <div className="s">Run the line to score the hook, beats, ending, and verdict. Live engine output only — nothing is pre-filled.</div>
              </div>
            ) : (
              <>
                <div className="hook-card">
                  <div className="chips" style={{ marginBottom: 8 }}>
                    <span className="chip accent">{analysis.hook.hook_type}</span>
                    {analysis.niche_tags.map((t) => <span className="chip" key={t}>#{t}</span>)}
                  </div>
                  <div className="hook-text">{analysis.hook.text_or_action}</div>
                  <p className="hook-why">{analysis.hook.why_it_works}</p>
                  <div className="hook-first">first 3s: {analysis.hook.first_3_seconds}</div>
                </div>

                <div>
                  <span className="flabel">Beat ladder</span>
                  <div className="beats">
                    {analysis.beats.map((b) => (
                      <div className="beat" key={b.order}>
                        <span className="ts tnum">{b.timestamp}</span>
                        <span>
                          <span className="purpose">{b.purpose}</span>
                          <div className="what">{b.what_happens}</div>
                          <div className="tech">{b.technique}</div>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <span className="flabel">Ending</span>
                  <p className="ending">
                    <strong>{analysis.ending.style}</strong>
                    {analysis.ending.detail ? <span className="detail"> — {analysis.ending.detail}</span> : null}
                    {analysis.ending.loop_close ? <span className="chip ok" style={{ marginLeft: 7 }}>loop close</span> : null}
                  </p>
                  <p className="ending" style={{ marginTop: 4 }}>{analysis.verdict_reason}</p>
                </div>

                <div className="verdict-row">
                  <span className={`stamp ${analysis.verdict === "recreate" ? "green" : ""}`}>{analysis.verdict}</span>
                </div>

                <DecisionCard
                  title="Verdict"
                  decision={verdictDec}
                  emptyNote="The verdict decision will appear after Run line."
                />

                {analysis.remix_ideas.length > 0 && (
                  <div>
                    <span className="flabel">Remix ideas</span>
                    <ul className="idea-list">
                      {analysis.remix_ideas.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}
              </>
            )}
          </Panel>
        </div>

        {/* ----- right: Stylist + Expression + Dispatch ----- */}
        <div className="col col-right">
          <Panel idx="03" title="Stylist" stamp={refreshing ? "Re-dressing" : brief ? "Complete" : undefined}>
            {running ? (
              <SkeletonStack n={3} />
            ) : !brief ? (
              <div className="empty">
                <div className="t">No styling yet</div>
                <div className="s">Outfit, jewelry, footwear, and poses appear after Run line.</div>
              </div>
            ) : outfitEmpty ? (
              <>
                <div className="empty">
                  <div className="t">Wardrobe is empty</div>
                  <div className="s">Nothing scored — scan an asset folder to stock the library, then re-run the line.</div>
                  <button className="go" onClick={() => document.getElementById("f-folder")?.focus()}>
                    Scan assets
                  </button>
                </div>
                {brief.style.pose.poses.length > 0 && (
                  <div>
                    <span className="flabel">Poses</span>
                    <div className="poses">
                      {brief.style.pose.poses.map((p) => <span className="chip" key={p}>{p}</span>)}
                    </div>
                    {brief.style.pose.shot_notes && <p className="shot-notes" style={{ marginTop: 8 }}>{brief.style.pose.shot_notes}</p>}
                    {brief.style.location_notes && <p className="loc-notes">{brief.style.location_notes}</p>}
                  </div>
                )}
                <DecisionCard title="Outfit" decision={outfitDecision} emptyNote="No outfit decision — wardrobe was empty." />
              </>
            ) : (
              <>
                <div>
                  <span className="flabel">Outfit</span>
                  {[...brief.style.outfit.items, ...(brief.style.outfit.jewelry ? [brief.style.outfit.jewelry] : []), ...(brief.style.outfit.footwear ? [brief.style.outfit.footwear] : [])].map((a, i) => (
                    <div className="fit-item" key={`${a.path}-${i}`}>
                      <div>
                        <div className="name">{fileName(a.path)}</div>
                        <div className="meta tnum">
                          {a.category}
                          {a.brands.length > 0 && <> · {a.brands.join(", ")}</>}
                          {a.colors.length > 0 && <> · {a.colors.join(", ")}</>}
                          {a.style_tags.length > 0 && <> · {a.style_tags.join(", ")}</>}
                        </div>
                      </div>
                      <div className="meter-wrap">
                        <div className="n tnum">{a.formality}/10</div>
                        <div className="bar" title={`formality ${a.formality}/10`}><i className={a.formality >= 6 ? "chosen" : "ok"} style={{ width: `${a.formality * 10}%` }} /></div>
                        <div className="cap">formality</div>
                      </div>
                    </div>
                  ))}
                </div>
                {brief.style.outfit.rationale && <p className="rationale">{brief.style.outfit.rationale}</p>}
                <DecisionCard title="Outfit" decision={outfitDecision} />

                <div>
                  <span className="flabel">Poses</span>
                  <div className="poses">
                    {brief.style.pose.poses.map((p) => <span className="chip" key={p}>{p}</span>)}
                  </div>
                  {brief.style.pose.shot_notes && <p className="shot-notes" style={{ marginTop: 8 }}>{brief.style.pose.shot_notes}</p>}
                  {brief.style.location_notes && <p className="loc-notes">{brief.style.location_notes}</p>}
                </div>
              </>
            )}
          </Panel>

          <Panel idx="04" title="Expression" stamp={refreshing ? "Updating" : brief ? "Complete" : undefined}>
            {running ? (
              <SkeletonStack n={3} />
            ) : !brief ? (
              <div className="empty">
                <div className="t">No expression plan yet</div>
                <div className="s">Genuine vs performed direction appears after Run line.</div>
              </div>
            ) : (
              <>
                <div className="expr-primary-row">
                  <span className="expr-name">{pretty(brief.expressions.primary.name)}</span>
                  <span className={`pill ${brief.expressions.primary.genuine ? "genuine" : "performed"}`}>
                    {brief.expressions.primary.genuine ? "Genuine" : "Performed"}
                  </span>
                </div>
                {brief.expressions.primary.when_to_use && <p className="when">{brief.expressions.primary.when_to_use}</p>}
                {brief.expressions.primary.micro_details && <p className="micro"><strong>Micro:</strong> {brief.expressions.primary.micro_details}</p>}

                {brief.expressions.secondary.length > 0 && (
                  <div>
                    <span className="flabel">Secondary</span>
                    <ul className="simple-list">
                      {brief.expressions.secondary.map((e) => (
                        <li key={e.name}>{pretty(e.name)} — {e.micro_details}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {brief.expressions.avoid.length > 0 && (
                  <div>
                    <span className="flabel">Avoid</span>
                    <ul className="simple-list avoid">
                      {brief.expressions.avoid.map((e) => <li key={e}>{pretty(e)}</li>)}
                    </ul>
                  </div>
                )}
                {brief.expressions.audio_note && <p className="audio-note">{brief.expressions.audio_note}</p>}
                <DecisionCard title="Expression" decision={exprDecision} />
              </>
            )}
          </Panel>

          <Panel idx="05" title="Dispatch" stamp={brief ? (escalations.length ? "Review" : "Ready") : undefined}>
            {running ? (
              <SkeletonStack n={4} />
            ) : !brief ? (
              <div className="empty">
                <div className="t">No dispatch packet yet</div>
                <div className="s">The shoot-ready ticket appears after Run line.</div>
              </div>
            ) : (
              <>
                <div className="ticket">
                  <div className="ticket-head">
                    <span className={`chip ${brief.mode === "recreate" ? "ok" : "accent"}`}>{brief.mode}</span>
                    <span className="chip">{brief.persona_id}</span>
                    <span className="chip">{mdep.place}</span>
                  </div>
                  <div className="ticket-body">
                    <div>
                      <h4>Hook</h4>
                      <p>{brief.hook}</p>
                    </div>
                    <div>
                      <h4>Script outline</h4>
                      <ul className="script-list">
                        {brief.script_outline.map((l, i) => <li key={i}>{l}</li>)}
                      </ul>
                    </div>
                    <div>
                      <h4>Caption</h4>
                      <p>{brief.caption_idea}</p>
                      <p className="muted" style={{ marginTop: 4 }}>{brief.hashtags.join(" ")}</p>
                    </div>
                  </div>
                </div>

                <div>
                  <span className="flabel">Escalations</span>
                  {escalations.length === 0 ? (
                    <p className="esc-clear">✓ No escalations — all decisions cleared to automate.</p>
                  ) : (
                    <div className="esc-list">
                      {escalations.map((e, i) => (
                        <div className="esc" key={i}><span className="ico" aria-hidden="true">!</span><span>{e}</span></div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="outcome-row">
                  <span className="flabel">Realised outcome (A–D)</span>
                  <div className="thumb-row" role="radiogroup" aria-label="Realised outcome">
                    {OUTCOME_ABC.map((o) => (
                      <button
                        key={o}
                        className={`thumb ${outcome === o ? "sel" : ""}`}
                        onClick={() => setOutcome(o)}
                        role="radio"
                        aria-checked={outcome === o}
                      >
                        {o}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="save-row">
                  <button className="btn-secondary" onClick={copyTicket}>
                    {copied ? "Copied ✓" : "Copy JSON"}
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={saveOutcome}
                    disabled={saving}
                    title="POST outcome — logs the Brier-scored result for the verdict decision"
                  >
                    {saving ? "Logging…" : "Save"}
                  </button>
                  {saveMsg && <span className={`save-status ${saveOk === true ? "ok" : saveOk === false ? "bad" : ""}`}>{saveMsg}</span>}
                </div>
                <p className="hint">Save logs the verdict outcome (Brier) via POST <span className="mono">outcome</span>. Copy JSON copies the full brief.</p>
              </>
            )}
          </Panel>
        </div>
      </main>

      <footer className="foot">
        <span>Live engine only · no demo data</span>
        <span>/api/engine {"{cmd, payload}"}</span>
        <span>commands: personas · assets · health · scan · analyze · brief · line · plan-day · outcome</span>
      </footer>
    </div>
  );
}
