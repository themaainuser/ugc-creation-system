"use client";
import { useEffect, useState } from "react";
import Doc, { CopyButton } from "./Doc";
import Flipbook from "./Flipbook";
import { fileUrl, fmtT, type JobView as JV, type Persona } from "./types";

const ORDER = ["download", "audio", "transcribe", "flipbook", "mastermind"];
const SHORT: Record<string, string> = { download: "Download", audio: "Audio", transcribe: "Transcript", flipbook: "Flipbook", mastermind: "Opus 5.5" };
type Tab = "flow" | "prompts" | "flipbook" | "transcript" | "inputs";

function elapsed(a?: number, b?: number) {
  if (!a) return "";
  const s = Math.max(0, (b ?? Date.now() / 1000) - a);
  return s < 60 ? `${s.toFixed(0)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export default function JobView({
  job, personas, onRemix, onAction, busy,
}: {
  job: JV; personas: Persona[]; busy: boolean;
  onRemix: () => void; onAction: (a: "retry" | "rewrite") => void;
}) {
  const st = job.status;
  const running = st?.state === "running" || st?.state === "queued";
  const hasFlow = !!job.docs.reel_flow;
  const hasPrompts = !!job.docs.generation_prompts;
  const [tab, setTab] = useState<Tab>(hasFlow ? "flow" : "flipbook");
  const [, tick] = useState(0);

  // Land on the documents the moment they exist.
  useEffect(() => {
    if (hasFlow) setTab((t) => (t === "flipbook" || t === "transcript" ? "flow" : t));
  }, [hasFlow]);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [running]);

  const persona = personas.find((p) => p.id === job.spec.persona);
  const plat = (job.info?.platform ?? {}) as Record<string, string | number>;
  const title =
    job.blueprint?.title ||
    (job.spec.idea ? job.spec.idea.split(/[.\n]/)[0].slice(0, 90) : "") ||
    (plat.title as string) || "Untitled reel";
  const mmRunning = st?.stages?.mastermind?.state === "running";
  const segs = job.transcript?.segments ?? [];

  const docTab = (md: string | null, name: string, file: string) => {
    if (md) {
      return (
        <>
          <div className="rl-doc-bar">
            <span className="hint">{name === "flow" ? "How the source reel flows — hooks, beats, graphics, audio, ending." : "Shot-by-shot prompts for your image + video models. Every prompt block has a copy button."}</span>
            <CopyButton text={md} label="Copy markdown" />
            <a className="rl-btn" href={`${fileUrl(job.id, `out/${file}`)}?download=1`}>Download .md</a>
          </div>
          <Doc markdown={md} />
        </>
      );
    }
    if (mmRunning && job.docs.partial) {
      return (
        <div className="rl-live">
          <div className="rl-livebar"><span className="rl-spin" style={{ color: "var(--accent)" }} />Opus is writing — this updates live.</div>
          <Doc markdown={job.docs.partial.replace(/<\/?(reel_flow|generation_prompts|blueprint)>/g, "")} />
        </div>
      );
    }
    return (
      <div className="rl-placeholder">
        <b>{running ? "Not written yet" : st?.state === "error" ? "Stopped before this was written" : "Nothing here"}</b>
        {running ? "Opus writes this after the reel is downloaded, transcribed and flipped through." : st?.error ? "Fix the error above and press Retry — finished stages are reused." : ""}
      </div>
    );
  };

  return (
    <div>
      <header className="rl-job-head">
        <div style={{ minWidth: 0, flex: "1 1 420px" }}>
          <h2>{title}</h2>
          <div className="rl-meta">
            <span>{job.spec.mode === "recreate" ? "Recreate" : "Remix"} for <b style={{ color: "var(--text)" }}>{persona?.name ?? job.spec.persona ?? "no persona"}</b></span>
            {job.spec.url ? <a href={job.spec.url} target="_blank" rel="noreferrer">source reel ↗</a> : <span>uploaded video</span>}
            {plat.uploader && <span>by @{String(plat.uploader_id || plat.uploader)}</span>}
            {job.info?.probe?.duration ? <span className="mono">{job.info.probe.duration.toFixed(1)}s</span> : null}
            {job.usage && <span className="mono">{job.usage.output_tokens.toLocaleString()} tok · ~${job.usage.est_cost_usd.toFixed(2)}</span>}
            <span className="mono">{job.id}</span>
          </div>
        </div>
        <div className="rl-actions">
          {st?.state === "error" && <button type="button" className="rl-btn primary" disabled={busy} onClick={() => onAction("retry")}>Retry from failed step</button>}
          {st?.state === "done" && (
            <>
              <button type="button" className="rl-btn" disabled={busy} onClick={() => onAction("rewrite")} title="Keep the analysis, ask Opus to write both documents again">Rewrite with Opus</button>
              <button type="button" className="rl-btn primary" onClick={onRemix} title="New idea on the same reel — no re-download">Remix with a new idea</button>
            </>
          )}
        </div>
      </header>

      <ol className="rl-pipe" style={{ listStyle: "none", padding: 0, margin: "0 0 26px" }}>
        {ORDER.map((k, n) => {
          const s = st?.stages?.[k];
          const state = s?.state ?? "pending";
          return (
            <li key={k} className={`rl-stage ${state}`} aria-label={`${s?.label ?? k}: ${state}`}>
              <div className="top">
                <span className="idx">0{n + 1}</span>
                <b>{SHORT[k]}</b>
                <span className="st">{state === "running" ? elapsed(s?.started_at) || "live" : state === "done" ? `✓ ${elapsed(s?.started_at, s?.finished_at)}` : state}</span>
              </div>
              <p>{s?.message || (state === "pending" ? "waiting" : "")}</p>
            </li>
          );
        })}
      </ol>

      <div className="rl-tabs" role="tablist">
        {([
          ["flow", "Reel flow", hasFlow ? "" : mmRunning ? "…" : ""],
          ["prompts", "Generation prompts", ""],
          ["flipbook", "Flipbook", job.flipbook ? String(job.flipbook.frames.length) : ""],
          ["transcript", "Transcript", segs.length ? String(segs.length) : ""],
          ["inputs", "Your brief", ""],
        ] as [Tab, string, string][]).map(([k, label, count]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
            {label}{count && <span className="count">{count}</span>}
            {k === "prompts" && hasPrompts && <span className="count">✓</span>}
          </button>
        ))}
      </div>

      {tab === "flow" && docTab(job.docs.reel_flow, "flow", "reel_flow.md")}
      {tab === "prompts" && docTab(job.docs.generation_prompts, "prompts", "generation_prompts.md")}
      {tab === "flipbook" &&
        (job.flipbook ? (
          <Flipbook jobId={job.id} fb={job.flipbook} video={job.video} duration={job.info?.probe?.duration} />
        ) : (
          <div className="rl-placeholder"><b>{running ? "Flipping through the reel…" : "No flipbook yet"}</b>Keyframes appear here: every 0.5s of the hook, every scene cut, and the ending.</div>
        ))}
      {tab === "transcript" &&
        (segs.length ? (
          <div>
            <div className="rl-tr-meta">
              {job.transcript?.provider} · language {job.transcript?.language ?? "?"} ·{" "}
              <CopyButton text={segs.map((s) => `[${fmtT(s.start)}] ${s.text}`).join("\n")} label="Copy transcript" className="rl-btn" />
            </div>
            <div className="rl-tr">
              {segs.map((s, n) => (
                <div key={n} className={`rl-line${s.start < 3 ? " hook" : ""}`}>
                  <span className="mono">{fmtT(s.start)} – {fmtT(s.end)}</span>
                  <p>{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="rl-placeholder">
            <b>{running ? "Listening…" : "No speech"}</b>
            {job.transcript?.note ?? (running ? "The transcript shows up here once audio is processed." : "This reel has no spoken words — it likely runs on a trending sound. Opus is told so.")}
          </div>
        ))}
      {tab === "inputs" && (
        <div className="rl-doc">
          <h3>Why this reel fits {persona?.name ?? "the persona"}</h3>
          <p>{job.spec.context || <em>Not given — Opus inferred it.</em>}</p>
          <h3>Idea / twist</h3>
          <p>{job.spec.idea || <em>Not given — Opus proposed one.</em>}</p>
          <h3>Target models</h3>
          <p>Image: {job.spec.targets?.image || "any"} · Video: {job.spec.targets?.video || "any"}</p>
          <h3>Your assets</h3>
          {job.spec.assets.length ? (
            <div className="rl-strip" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}>
              {job.spec.assets.map((a) => (
                <figure key={a.file} style={{ margin: 0 }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={fileUrl(job.id, a.file)} alt={a.label || a.kind} style={{ width: "100%", aspectRatio: "1", objectFit: "cover", borderRadius: 8, border: "1px solid var(--line)" }} />
                  <figcaption style={{ fontSize: 12, marginTop: 4 }}><b style={{ color: "var(--text)" }}>{a.kind}</b> · {a.label || a.file.split("/").pop()}</figcaption>
                </figure>
              ))}
            </div>
          ) : (
            <p>None — Opus wrote generation prompts for every asset.</p>
          )}
          {job.spec.source_job && <p style={{ marginTop: 18 }}>Analysis reused from job <code>{job.spec.source_job}</code>.</p>}
        </div>
      )}
    </div>
  );
}
