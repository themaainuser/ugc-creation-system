"use client";
import "../../app/lab.css";
import { useCallback, useEffect, useRef, useState } from "react";
import Composer, { emptyDraft, type Draft } from "./Composer";
import JobView from "./JobView";
import type { Health, JobSummary, JobView as JV } from "./types";

const STEPS = [
  ["01", "Download", "yt-dlp pulls the reel into a temp job folder"],
  ["02", "Audio", "ffmpeg splits the audio and maps silence vs sound"],
  ["03", "Transcript", "Whisper writes every line with timestamps"],
  ["04", "Flipbook", "keyframes: the hook, every cut, the ending"],
  ["05", "Opus 5.5", "writes the flow + your generation prompts"],
];

export default function ReelLab() {
  const [health, setHealth] = useState<Health | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JV | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft());
  const [submitting, setSubmitting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const poll = useRef<ReturnType<typeof setTimeout> | null>(null);
  const personas = health?.personas ?? [];

  const loadJobs = useCallback(async () => {
    const r = await fetch("/api/reel").then((x) => x.json()).catch(() => null);
    if (r?.jobs) setJobs(r.jobs);
  }, []);

  useEffect(() => {
    fetch("/api/reel?health=1").then((r) => r.json()).then(setHealth).catch(() => setHealth({ error: "API unreachable" }));
    loadJobs();
    const q = new URLSearchParams(window.location.search).get("job");
    if (q) setJobId(q);
  }, [loadJobs]);

  // Poll the open job while it runs.
  useEffect(() => {
    if (poll.current) clearTimeout(poll.current);
    if (!jobId) { setJob(null); return; }
    let alive = true;
    const tick = async () => {
      const r = await fetch(`/api/reel/${jobId}`, { cache: "no-store" }).then((x) => (x.ok ? x.json() : null)).catch(() => null);
      if (!alive) return;
      if (r) setJob(r);
      const s = r?.status?.state;
      if (s === "running" || s === "queued") poll.current = setTimeout(tick, 1500);
      else loadJobs();
    };
    tick();
    return () => { alive = false; if (poll.current) clearTimeout(poll.current); };
  }, [jobId, loadJobs]);

  const open = (id: string | null) => {
    setJobId(id);
    const u = new URL(window.location.href);
    if (id) u.searchParams.set("job", id); else u.searchParams.delete("job");
    window.history.replaceState(null, "", u);
  };

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    const fd = new FormData();
    if (draft.sourceJob) fd.set("source_job", draft.sourceJob);
    else if (draft.video) fd.set("video", draft.video);
    else fd.set("url", draft.url.trim());
    fd.set("persona", draft.persona);
    fd.set("mode", draft.mode);
    fd.set("context", draft.context);
    fd.set("idea", draft.idea);
    fd.set("image_model", draft.imageModel);
    fd.set("video_model", draft.videoModel);
    for (const a of draft.assets) {
      fd.append("assets", a.file);
      fd.append("asset_kinds", a.kind);
      fd.append("asset_labels", a.label);
    }
    try {
      const r = await fetch("/api/reel", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      open(data.id);
      loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const act = async (action: "retry" | "rewrite") => {
    if (!jobId) return;
    setBusy(true);
    const r = await fetch(`/api/reel/${jobId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
    if (!r.ok) setError((await r.json().catch(() => ({}))).error ?? "action failed");
    setBusy(false);
    const id = jobId;
    setJobId(null);
    setTimeout(() => setJobId(id), 0); // restart polling
  };

  const remix = () => {
    if (!job) return;
    setDraft({ ...emptyDraft(job.spec.persona ?? ""), sourceJob: job.id, context: job.spec.context, imageModel: job.spec.targets?.image ?? "", videoModel: job.spec.targets?.video ?? "" });
    document.querySelector(".rl-side")?.scrollTo({ top: 0, behavior: "smooth" });
    window.scrollTo({ top: 0, behavior: "smooth" });
    setTimeout(() => (document.getElementById("rl-idea") as HTMLTextAreaElement | null)?.focus(), 300);
  };

  const pills: [string, boolean, string][] = health
    ? health.error
      ? [["Python", false, health.error]]
      : [
          ["ffmpeg", !!health.ffmpeg, health.ffmpeg ? "installed" : "missing — install ffmpeg"],
          ["yt-dlp", !!health.ytdlp, health.ytdlp ? "installed" : "pip install yt-dlp"],
          [`Transcript · ${health.transcriber === "none" ? "off" : health.transcriber}`, health.transcriber !== "none", health.transcriber === "none" ? "pip install faster-whisper, or set GROQ_API_KEY" : "ready"],
          [health.mastermind ? `Opus via ${health.mastermind}` : "Opus · no key", !!health.mastermind, health.mastermind ? String(health.mastermind_model) : "set ANTHROPIC_API_KEY or OPEN_ROUTER_API_KEY in ugc-system/.env"],
        ]
    : [];
  const ready = !!health && !health.error && !!health.ffmpeg && !!health.mastermind;

  return (
    <div className="lab">
      <header className="rl-top">
        <a className="rl-brand" href="/"><b>UGC Studio</b><span>Reel Lab</span></a>
        <nav className="rl-nav" aria-label="Sections">
          <a href="/" aria-current="page">Reel Lab</a>
          <a href="/console">Operator console</a>
        </nav>
        <div className="rl-health">
          {health?.dry_run && <span className="rl-pill" title="UGC_MASTERMIND_DRY_RUN=1 — Opus is not called"><i />dry run</span>}
          {pills.map(([label, ok, title]) => (
            <span key={label} className={`rl-pill ${ok ? "ok" : "bad"}`} title={title}><i />{label}</span>
          ))}
        </div>
      </header>

      <div className="rl-shell">
        <aside className="rl-side">
          <Composer draft={draft} setDraft={setDraft} personas={personas} onSubmit={submit} submitting={submitting} error={error} ready={ready} />
          {jobs.length > 0 && (
            <section className="rl-recent">
              <h3>Recent reels</h3>
              <ul>
                {jobs.map((j) => (
                  <li key={j.id}>
                    <button type="button" aria-current={j.id === jobId} onClick={() => open(j.id)}>
                      <span className={`rl-dot ${j.state}`} aria-label={j.state} />
                      <span className="t">
                        <b>{j.title || j.idea || j.url?.replace(/^https?:\/\/(www\.)?/, "") || "Uploaded video"}</b>
                        <small>{personas.find((p) => p.id === j.persona)?.name ?? j.persona ?? "no persona"} · {j.mode}</small>
                      </span>
                      <small className="mono" style={{ color: "var(--muted)", fontSize: 11 }}>{j.id.slice(4, 8).replace(/(\d\d)(\d\d)/, "$2/$1")}</small>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>

        <main className="rl-main">
          {job ? (
            <JobView key={job.id} job={job} personas={personas} onRemix={remix} onAction={act} busy={busy} />
          ) : jobId ? (
            <div className="rl-placeholder"><span className="rl-spin" style={{ display: "inline-block" }} /></div>
          ) : (
            <div className="rl-empty">
              <h2>Every great reel has a playbook.<br />This pulls it out.</h2>
              <p>Paste a reel and tell the lab why it fits your persona. You get two files back: how the reel flows — every hook, cut, graphic and sound — and shot-by-shot prompts to make your own version with your model.</p>
              <div className="rl-steps">
                {STEPS.map(([n, b, s]) => (
                  <div key={n}><span className="mono">{n}</span><b>{b}</b><small>{s}</small></div>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
