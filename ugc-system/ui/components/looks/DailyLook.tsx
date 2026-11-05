"use client";
import "../../app/lab.css";
import { useCallback, useEffect, useState } from "react";
import TopBar from "../lab/TopBar";
import { CopyButton } from "../lab/Doc";
import type { Persona } from "../lab/types";

type Item = { id: string; file: string; name: string; category: string; subcategory?: string; brand?: string; tier?: string; colors?: { name: string; hex: string }[]; formality: number; statement?: number; story?: string; description?: string; demo?: boolean };
type Alt = { items: Item[]; x: number[]; meta: { harmony: string; hero: string | null }; p_best: number; predicted_approval: number; describe: string };
type Expr = { id: string; name: string; mode: "genuine" | "performed"; v: number; a: number; face?: string; motion?: string; reason?: string };
type Shot = { n: number; pose: { id: string; name: string; shot: string; showcases: string[]; prompt: string; camera: string }; expression: Expr; image_prompt: string; video_prompt: string; negative_prompt: string; reference_images: string[] };
type Look = {
  id: string; persona: string; persona_name: string; seed: number;
  scene: { mood: string; place: string; environment: string; music: string; date: string; weekday: string; time_of_day: string; weather: string; season: string; settings: string[]; formality: number[]; terrain: string; footwear: string[]; jewelry: string; lighting: string; contexts: string[]; target_va: number[]; va_parts: Record<string, number[]>; matched: string[]; source: string; brand: string };
  outfit: { chosen: number; chosen_by: string; alternatives: Alt[]; gate: "automate" | "review"; margin: number; explain: { feature: string; value: number; weight: number; contribution: number }[]; calibration: { n: number; brier: number | null; note?: string; approval_rate?: number } };
  expression: { target_va: number[]; primary: Expr; secondary: Expr | null; nearby_allowed: Expr[]; avoid: Expr[] };
  shots: Shot[]; notes: string[]; feedback: { verdict: string; alt: number | null } | null;
  art_director: { pick: number; why: string; styling_notes: string; caption: string; hashtags: string[]; cost_usd: number } | null;
};
type LookRow = { id: string; persona: string; persona_name: string; place: string; mood: string; date: string; verdict: string | null; thumb: Item };

const PLACES = ["Home", "Bedroom", "Kitchen", "Café", "Fast food joint", "Mall", "Office", "Studio photoshoot", "Ramp walk", "Beach vacation", "Gym", "Wedding / festive", "Night out", "Airport"];
const MOODS = ["happy", "cozy", "confident", "playful", "nostalgic", "elegant", "excited", "tired", "romantic", "focused"];
const TIMES = ["morning", "afternoon", "golden hour", "evening", "night"];
const FEATURE_LABEL: Record<string, string> = {
  formality_fit: "Formality fit", weather_fit: "Weather fit", persona_fit: "Persona fit", color_harmony: "Colour harmony",
  style_coherence: "Style coherence", hero_balance: "One hero piece", novelty: "Freshness", story: "Story / gift",
  brand_fit: "Sponsor fit", footwear_fit: "Footwear for ground",
};
const img = (it: Item) => `/api/wardrobe/file/${it.demo ? "demo" : "wardrobe"}/${it.file}`;
const today = () => new Date().toISOString().slice(0, 10);

function VAPlot({ e }: { e: Look["expression"] }) {
  const X = (v: number) => 30 + ((v + 1) / 2) * 260;
  const Y = (a: number) => 270 - ((a + 1) / 2) * 240;
  const [tv, ta] = e.target_va;
  return (
    <svg className="lk-va" viewBox="0 0 320 300" role="img" aria-label={`Emotion map: target valence ${tv}, arousal ${ta}; primary ${e.primary.name}`}>
      <rect x="30" y="30" width="260" height="240" fill="none" stroke="rgba(255,255,255,0.08)" />
      <line x1="160" y1="30" x2="160" y2="270" stroke="rgba(255,255,255,0.1)" />
      <line x1="30" y1="150" x2="290" y2="150" stroke="rgba(255,255,255,0.1)" />
      <text x="160" y="20" textAnchor="middle" fill="#8b8b94" fontSize="10">high energy</text>
      <text x="160" y="290" textAnchor="middle" fill="#8b8b94" fontSize="10">low energy</text>
      <text x="26" y="154" textAnchor="end" fill="#8b8b94" fontSize="10" transform="rotate(-90 22 150)">negative</text>
      <text x="298" y="146" fill="#8b8b94" fontSize="10" transform="rotate(90 298 150)" textAnchor="middle">positive</text>
      {[["excited · joyful", 286, 44, "end"], ["calm · content", 286, 262, "end"], ["tense · angry", 34, 44, "start"], ["sad · tired", 34, 262, "start"]].map(([t, x, y, a]) => (
        <text key={t as string} x={x as number} y={y as number} textAnchor={a as "end" | "start"} fill="#55555c" fontSize="9.5">{t}</text>
      ))}
      {e.nearby_allowed.map((n) => (
        <circle key={n.id} cx={X(n.v)} cy={Y(n.a)} r="3" fill="#6d6d75"><title>{`${n.name} (${n.mode})`}</title></circle>
      ))}
      {e.avoid.map((n) => (
        <g key={n.id} stroke="#ff6f61" strokeWidth="1.6"><title>{`${n.name}: ${n.reason}`}</title>
          <line x1={X(n.v) - 4} y1={Y(n.a) - 4} x2={X(n.v) + 4} y2={Y(n.a) + 4} /><line x1={X(n.v) - 4} y1={Y(n.a) + 4} x2={X(n.v) + 4} y2={Y(n.a) - 4} />
        </g>
      ))}
      {e.secondary && (
        <g><circle cx={X(e.secondary.v)} cy={Y(e.secondary.a)} r="6" fill="none" stroke="#f4f4f5" strokeWidth="1.6" />
          <text x={X(e.secondary.v) + 9} y={Y(e.secondary.a) + 4} fill="#b4b4bb" fontSize="11">{e.secondary.name}</text></g>
      )}
      <g><circle cx={X(e.primary.v)} cy={Y(e.primary.a)} r="7" fill="#c6f432" />
        <text x={X(e.primary.v) + 10} y={Y(e.primary.a) - 6} fill="#f4f4f5" fontSize="11.5" fontWeight="600">{e.primary.name}</text></g>
      <g stroke="#c6f432" strokeWidth="1.4"><title>target from mood, music and place</title>
        <circle cx={X(tv)} cy={Y(ta)} r="11" fill="none" strokeDasharray="3 3" />
        <line x1={X(tv) - 16} y1={Y(ta)} x2={X(tv) - 12} y2={Y(ta)} /><line x1={X(tv) + 12} y1={Y(ta)} x2={X(tv) + 16} y2={Y(ta)} />
      </g>
    </svg>
  );
}

function ItemCard({ it, hero }: { it: Item; hero: boolean }) {
  return (
    <div className="lk-item">
      <div className="img">{/* eslint-disable-next-line @next/next/no-img-element */}<img src={img(it)} alt={it.name} loading="lazy" /></div>
      {hero && <span className="hero">HERO</span>}
      <div className="body">
        <b>{it.name}</b>
        <small>{[it.brand, it.tier?.replace("_", " "), it.subcategory || it.category].filter(Boolean).join(" · ")} · f{it.formality}</small>
        {!!it.colors?.length && <div className="lk-sw">{it.colors.map((c) => <i key={c.hex + c.name} style={{ background: c.hex }} title={c.name} />)}</div>}
        {it.story && it.tier === "handmade" && <div className="story">“{it.story}”</div>}
      </div>
    </div>
  );
}

export default function DailyLook() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [form, setForm] = useState({ persona: "", date: today(), time_of_day: "", place: "", environment: "", mood: "", music: "", notes: "", brand: "", weather: "", shots: 3, opus: false });
  const [look, setLook] = useState<Look | null>(null);
  const [looks, setLooks] = useState<LookRow[]>([]);
  const [view, setView] = useState<number | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fbMsg, setFbMsg] = useState<string | null>(null);
  const set = (p: Partial<typeof form>) => setForm((f) => ({ ...f, ...p }));

  const loadLooks = useCallback(() => fetch("/api/styling?cmd=looks").then((r) => r.json()).then((d) => d.looks && setLooks(d.looks)).catch(() => {}), []);
  const open = useCallback(async (id: string) => {
    const r = await fetch(`/api/styling?cmd=show&look=${id}`).then((x) => x.json());
    if (!r.error) { setLook(r); setView(null); setFbMsg(null); const u = new URL(window.location.href); u.searchParams.set("look", id); window.history.replaceState(null, "", u); }
  }, []);
  useEffect(() => {
    fetch("/api/reel?health=1").then((r) => r.json()).then((h) => { setPersonas(h.personas ?? []); if (h.personas?.[0]) setForm((f) => (f.persona ? f : { ...f, persona: h.personas[0].id })); }).catch(() => {});
    loadLooks();
    const q = new URLSearchParams(window.location.search).get("look");
    if (q) open(q);
  }, [loadLooks, open]);

  const plan = async () => {
    setBusy(form.opus ? "Styling — Opus is looking at the shortlist…" : "Styling…");
    setError(null);
    try {
      const r = await fetch("/api/styling", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cmd: "plan", ...form }) });
      const d = await r.json();
      if (!r.ok || d.error) throw new Error(d.error || `HTTP ${r.status}`);
      setLook(d); setView(null); setFbMsg(null); loadLooks();
      const u = new URL(window.location.href); u.searchParams.set("look", d.id); window.history.replaceState(null, "", u);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  };

  const feedback = async (verdict: "approve" | "reject" | "swap", alt?: number) => {
    if (!look) return;
    setBusy("Learning from your call…");
    const r = await fetch("/api/styling", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cmd: "feedback", look: look.id, verdict, alt }) });
    const d = await r.json();
    setBusy(null);
    if (d.error) { setError(d.error); return; }
    setLook(d.look); setView(null); loadLooks();
    const c = d.calibration.outfit;
    setFbMsg(`${verdict === "approve" ? "Approved — items, poses and expressions logged as worn." : verdict === "swap" ? "Swapped — the learner now prefers outfits like this one." : "Rejected — the learner will steer away from this."} Calibration: ${c.n} decisions, Brier ${c.brier ?? "—"}.`);
  };

  const o = look?.outfit;
  const shownIdx = view ?? o?.chosen ?? 0;
  const shown = o?.alternatives[shownIdx];
  const done = !!look?.feedback;

  return (
    <div className="lab">
      <TopBar active="looks" />
      <div className="rl-shell">
        <aside className="rl-side">
          <form onSubmit={(e) => { e.preventDefault(); if (!busy) plan(); }}>
            <h1 className="rl-h1">Style the day.<br /><em>Decide, don&apos;t guess.</em></h1>
            <p className="rl-sub">Set the moment. The stylist dresses the persona from your wardrobe, picks poses that show off the hero piece, and directs real vs performed expressions — with the odds behind every pick.</p>

            <div className="rl-field">
              <div className="rl-label"><span className="n">01</span>Persona</div>
              <div className="rl-chips">
                {personas.map((p) => (
                  <button key={p.id} type="button" className="rl-chip" aria-pressed={form.persona === p.id} onClick={() => set({ persona: p.id })}>
                    <b>{p.name}</b><small>{[p.niche, p.gender].filter(Boolean).join(" · ")}</small>
                  </button>
                ))}
              </div>
            </div>
            <div className="rl-field">
              <div className="rl-label"><span className="n">02</span>Day</div>
              <div className="rl-inline">
                <input className="rl-input" type="date" value={form.date} onChange={(e) => set({ date: e.target.value })} aria-label="Date" />
                <input className="rl-input" placeholder="weather (auto)" value={form.weather} onChange={(e) => set({ weather: e.target.value })} aria-label="Weather" />
              </div>
              <div className="rl-suggest">{TIMES.map((t) => <button key={t} type="button" aria-pressed={form.time_of_day === t} onClick={() => set({ time_of_day: form.time_of_day === t ? "" : t })}>{t}</button>)}</div>
            </div>
            <div className="rl-field">
              <label className="rl-label" htmlFor="lk-place"><span className="n">03</span>Place</label>
              <input id="lk-place" className="rl-input" placeholder="e.g. nearby KFC, Goa beach, ramp walk at a fashion show" value={form.place} onChange={(e) => set({ place: e.target.value })} />
              <div className="rl-suggest">{PLACES.map((p) => <button key={p} type="button" aria-pressed={form.place === p} onClick={() => set({ place: p })}>{p}</button>)}</div>
            </div>
            <div className="rl-field">
              <label className="rl-label" htmlFor="lk-env"><span className="n">04</span>Environment<span className="opt">props, vibe</span></label>
              <input id="lk-env" className="rl-input" placeholder="e.g. bedroom with a big mirror, fairy lights, rain outside" value={form.environment} onChange={(e) => set({ environment: e.target.value })} />
            </div>
            <div className="rl-field">
              <label className="rl-label" htmlFor="lk-mood"><span className="n">05</span>Mood</label>
              <input id="lk-mood" className="rl-input" placeholder="how they feel today" value={form.mood} onChange={(e) => set({ mood: e.target.value })} />
              <div className="rl-suggest">{MOODS.map((m) => <button key={m} type="button" aria-pressed={form.mood.includes(m)} onClick={() => set({ mood: form.mood.includes(m) ? form.mood.replace(m, "").replace(/\s+/g, " ").trim() : `${form.mood} ${m}`.trim() })}>{m}</button>)}</div>
            </div>
            <div className="rl-field">
              <label className="rl-label" htmlFor="lk-music"><span className="n">06</span>Listening to<span className="opt">changes the face</span></label>
              <input id="lk-music" className="rl-input" placeholder="e.g. lofi, Arijit Singh, Punjabi party songs" value={form.music} onChange={(e) => set({ music: e.target.value })} />
            </div>
            <div className="rl-field">
              <label className="rl-label" htmlFor="lk-notes"><span className="n">07</span>What&apos;s happening<span className="opt">situations, named items</span></label>
              <textarea id="lk-notes" className="rl-textarea" placeholder={"e.g. my niece made pasta for me for the first time, it's too salty\nor: wearing the shell necklace my niece made"} value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
            </div>
            <div className="rl-field">
              <div className="rl-label"><span className="n">08</span>Post</div>
              <div className="rl-inline">
                <input className="rl-input" placeholder="sponsor brand (optional)" value={form.brand} onChange={(e) => set({ brand: e.target.value })} aria-label="Sponsor brand" />
                <select className="rl-select" value={form.shots} onChange={(e) => set({ shots: Number(e.target.value) })} aria-label="Number of shots">
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} shot{n > 1 ? "s" : ""}</option>)}
                </select>
              </div>
              <label className="rl-toggle" style={{ marginTop: 8 }}>
                <input type="checkbox" checked={form.opus} onChange={(e) => set({ opus: e.target.checked })} />
                <span>Opus art director<small>Looks at the shortlisted garments, makes the final pick, writes the caption (~$0.05–0.15)</small></span>
              </label>
            </div>
            <button type="submit" className="rl-run" disabled={!!busy || !form.persona || !form.place.trim()}>
              {busy ? <><span className="rl-spin" /> {busy}</> : <>Style the day <span aria-hidden>→</span></>}
            </button>
            {error && <div className="rl-err-box" role="alert">{error}</div>}
          </form>

          {looks.length > 0 && (
            <section className="rl-recent">
              <h3>Recent looks</h3>
              <ul>
                {looks.map((l) => (
                  <li key={l.id}>
                    <button type="button" aria-current={l.id === look?.id} onClick={() => open(l.id)}>
                      <span className={`rl-dot ${l.verdict === "reject" ? "error" : l.verdict ? "done" : "queued"}`} aria-label={l.verdict ?? "no feedback yet"} />
                      <span className="t"><b>{l.persona_name} · {l.place}</b><small>{l.mood || "—"} · {l.verdict ?? "awaiting your call"}</small></span>
                      <small className="mono" style={{ color: "var(--muted)", fontSize: 11 }}>{l.date.slice(5)}</small>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>

        <main className="rl-main">
          {!look || !o || !shown ? (
            <div className="rl-empty">
              <h2>Mood, day, environment, place.<br />Then the outfit.</h2>
              <p>Hard rules first — no heels on sand, nothing worn this week, jewelry that fits the moment. Then every full outfit is scored on colour harmony, style, one hero piece and the persona, and a learner that improves with each approve, swap or reject gives you the odds.</p>
              <div className="rl-steps">
                {[["01", "Scene", "place rules, weather, terrain, props"], ["02", "Outfit", "5 full looks with P(best)"], ["03", "Expression", "mood + music → target emotion"], ["04", "Poses", "show off the hero piece"], ["05", "Prompts", "image + video per shot"]].map(([n, b, s]) => (
                  <div key={n}><span className="mono">{n}</span><b>{b}</b><small>{s}</small></div>
                ))}
              </div>
            </div>
          ) : (
            <>
              <header className="rl-job-head">
                <div style={{ minWidth: 0, flex: "1 1 420px" }}>
                  <h2>{look.persona_name} at {look.scene.place}</h2>
                  <div className="rl-meta">
                    <span>{look.scene.weekday} {look.scene.date}{look.scene.time_of_day ? ` · ${look.scene.time_of_day}` : ""}</span>
                    <span>mood: {look.scene.mood}</span>
                    {look.scene.music && <span>listening: {look.scene.music}</span>}
                    <span className="mono">{look.id}</span>
                  </div>
                </div>
                <span className={`lk-gate ${o.gate}`} title={o.gate === "automate" ? "Confident: P(best) ≥ 50% and predicted approval ≥ 60%" : "Uncertain — compare the alternatives before posting"}>
                  {o.gate === "automate" ? "Confident pick" : "Review suggested"} · {Math.round(o.alternatives[o.chosen].p_best * 100)}%
                </span>
              </header>

              <section className="lk-section">
                <div className="lk-h"><h3>Scene, as understood</h3><span className="aside">{look.scene.source === "opus" ? "place read by Opus" : look.scene.matched.length ? `rules: ${look.scene.matched.join(", ")}` : "default rules"}</span></div>
                <div className="lk-chips">
                  <span className="lk-chip"><span>formality</span>{look.scene.formality.join("–")}</span>
                  <span className="lk-chip"><span>ground</span>{look.scene.terrain}</span>
                  <span className="lk-chip"><span>weather</span>{look.scene.weather} · {look.scene.season}</span>
                  <span className="lk-chip"><span>jewelry</span>{look.scene.jewelry}</span>
                  <span className="lk-chip"><span>shoes</span>{look.scene.footwear.join(", ")}</span>
                  <span className="lk-chip"><span>light</span>{look.scene.lighting}</span>
                  {look.scene.contexts.length > 0 && <span className="lk-chip"><span>context</span>{look.scene.contexts.join(", ").replace(/_/g, "-")}</span>}
                </div>
                {look.notes.length > 0 && <ul className="lk-notes">{look.notes.map((n) => <li key={n} className={/DEMO|No .* in the wardrobe/.test(n) ? "warn" : ""}>{n}</li>)}</ul>}
              </section>

              <section className="lk-section">
                <div className="lk-h"><h3>Outfit {view !== null && view !== o.chosen ? `· previewing alternative ${view + 1}` : ""}</h3><span className="aside">{shown.meta.harmony}</span></div>
                <div className="lk-outfit">
                  <div className="lk-items">{shown.items.map((it) => <ItemCard key={it.id} it={it} hero={it.id === shown.meta.hero} />)}</div>
                  <div className="lk-panel">
                    <h4>Why this outfit</h4>
                    <p className="sub">Chance each look is the best one, from 500 draws of what the learner believes{o.chosen_by === "opus" ? " · final pick by Opus" : o.chosen_by === "operator" ? " · you swapped" : ""}.</p>
                    {o.alternatives.map((a, i) => (
                      <button key={i} type="button" className={`lk-alt${i === o.chosen ? " chosen" : ""}`} aria-pressed={i === shownIdx} onClick={() => setView(i === o.chosen ? null : i)}>
                        <span className="n">{i + 1}</span>
                        <span>
                          <span className="thumbs">{a.items.slice(0, 6).map((it) => <img key={it.id} src={img(it)} alt="" />)}</span>
                          <span className="lk-bar"><i style={{ width: `${Math.max(2, a.p_best * 100)}%` }} /></span>
                        </span>
                        <span className="pct">{Math.round(a.p_best * 100)}%<small>approve {Math.round(a.predicted_approval * 100)}%</small></span>
                      </button>
                    ))}
                    {view !== null && view !== o.chosen && !done && (
                      <button type="button" className="rl-btn primary" style={{ marginTop: 10, width: "100%", justifyContent: "center" }} onClick={() => feedback("swap", view)}>Use alternative {view + 1} instead</button>
                    )}
                    <div className="lk-why">
                      {o.explain.slice(0, 6).map((f) => (
                        <div key={f.feature}><span>{FEATURE_LABEL[f.feature] ?? f.feature}</span><span className="lk-bar"><i style={{ width: `${Math.round(f.value * 100)}%` }} /></span><span className="mono">{f.value.toFixed(2)}</span></div>
                      ))}
                    </div>
                    <p className="sub" style={{ margin: "12px 0 0" }}>{o.calibration.n ? `Calibration: ${o.calibration.n} decisions, Brier ${o.calibration.brier} (lower is better; 0.25 = coin flip)` : "No feedback yet — odds come from the starting prior until you approve, swap or reject."}</p>
                  </div>
                </div>
              </section>

              {look.art_director && (
                <section className="lk-section">
                  <div className="lk-h"><h3>Opus art director</h3><span className="aside">~${look.art_director.cost_usd.toFixed(3)}</span></div>
                  <div className="lk-ad">
                    <p>{look.art_director.why}</p>
                    {look.art_director.styling_notes && <p><b style={{ color: "var(--text)" }}>Styling:</b> {look.art_director.styling_notes}</p>}
                    {look.art_director.caption && <p className="cap">“{look.art_director.caption}”</p>}
                    {look.art_director.hashtags?.length > 0 && <p className="mono" style={{ fontSize: 12 }}>{look.art_director.hashtags.map((h) => (h.startsWith("#") ? h : `#${h}`)).join(" ")}</p>}
                  </div>
                </section>
              )}

              <section className="lk-section">
                <div className="lk-h"><h3>Expression direction</h3><span className="aside">target from {Object.keys(look.scene.va_parts).join(" + ")}</span></div>
                <div className="lk-expr">
                  <VAPlot e={look.expression} />
                  <div className="lk-elist">
                    <div className="lk-e"><span className="role">Primary</span><div><b>{look.expression.primary.name}</b><span className={`lk-mode ${look.expression.primary.mode}`}>{look.expression.primary.mode}</span><p>{look.expression.primary.face}</p></div></div>
                    {look.expression.secondary && <div className="lk-e"><span className="role">Contrast</span><div><b>{look.expression.secondary.name}</b><span className={`lk-mode ${look.expression.secondary.mode}`}>{look.expression.secondary.mode}</span><p>{look.expression.secondary.face}</p></div></div>}
                    {look.expression.avoid.map((a) => (
                      <div key={a.id} className="lk-e avoid"><span className="role">Avoid</span><div><b>{a.name}</b><span className={`lk-mode ${a.mode}`}>{a.mode}</span><p>{a.reason}</p></div></div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="lk-section">
                <div className="lk-h"><h3>Shots</h3><span className="aside">{look.shots.length} for the carousel</span></div>
                <div className="lk-shots">
                  {look.shots.map((s) => (
                    <article key={s.n} className="lk-shot">
                      <header>
                        <span className="n">{s.n}</span>
                        <b>{s.pose.name}</b>
                        <small>{s.pose.shot.replace("_", "-")} · shows {s.pose.showcases.slice(0, 3).join(", ")}</small>
                        <small style={{ marginLeft: "auto" }}>{s.expression.name}<span className={`lk-mode ${s.expression.mode}`}>{s.expression.mode}</span></small>
                      </header>
                      <div className="grid">
                        <div><div className="label">Image prompt<CopyButton text={s.image_prompt} /></div><p className="prompt">{s.image_prompt}</p></div>
                        <div><div className="label">Video prompt<CopyButton text={s.video_prompt} /></div><p className="prompt">{s.video_prompt}</p></div>
                      </div>
                      <details><summary>Negative prompt + reference images</summary><p className="prompt">{s.negative_prompt}</p><p className="prompt" style={{ marginTop: 8 }}>{s.reference_images.join("\n")}</p></details>
                    </article>
                  ))}
                </div>
              </section>

              <div className="lk-feedback" role="region" aria-label="Feedback">
                {done ? (
                  <span className="msg done">{fbMsg ?? `You marked this look: ${look.feedback!.verdict}.`}</span>
                ) : (
                  <>
                    <span className="msg">Your call trains this persona&apos;s stylist.</span>
                    <button type="button" className="rl-btn" disabled={!!busy} onClick={() => feedback("reject")}>Reject</button>
                    <button type="button" className="rl-btn primary" disabled={!!busy} onClick={() => feedback("approve")}>Approve &amp; mark worn</button>
                  </>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
