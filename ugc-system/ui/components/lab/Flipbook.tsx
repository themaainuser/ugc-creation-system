"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { fileUrl, fmtT, type Flipbook as FB, type Frame } from "./types";

const KIND_LABEL: Record<Frame["kind"], string> = { hook: "HOOK", cut: "CUT", coverage: "", end: "END" };

export default function Flipbook({ jobId, fb, video, duration }: { jobId: string; fb: FB; video: string | null; duration?: number }) {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [mode, setMode] = useState<"flip" | "video">("flip");
  const frames = fb.frames;
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Play at the reel's real pace: each frame stays up until the next timestamp.
  useEffect(() => {
    if (!playing || mode !== "flip" || !frames.length) return;
    const cur = frames[i];
    const next = frames[i + 1];
    const wait = next ? Math.max(120, (next.t - cur.t) * 1000) : 900;
    timer.current = setTimeout(() => setI((n) => (n + 1 < frames.length ? n + 1 : 0)), wait);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [playing, i, frames, mode]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight") setI((n) => Math.min(frames.length - 1, n + 1));
      if (e.key === "ArrowLeft") setI((n) => Math.max(0, n - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [frames.length]);

  const groups = useMemo(
    () => [
      { title: "Hook · first 3 seconds", items: frames.filter((f) => f.t <= 3) },
      { title: "Body", items: frames.filter((f) => f.t > 3 && f.kind !== "end") },
      { title: "Ending", items: frames.filter((f) => f.kind === "end") },
    ],
    [frames],
  );

  if (!frames.length) return <div className="rl-placeholder"><b>No frames</b>The flipbook stage didn&apos;t produce frames.</div>;
  const cur = frames[i];
  const s = fb.stats;

  return (
    <div className="rl-fb">
      <div className="rl-viewer">
        <div className="rl-screen">
          {mode === "video" && video ? (
            <video src={fileUrl(jobId, video)} controls playsInline />
          ) : (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={fileUrl(jobId, cur.file)} alt={`Frame at ${cur.t.toFixed(2)}s`} />
              <div className="stamp">
                <span className="mono">{fmtT(cur.t)}</span>
                {cur.cut && <span className="mono cut">CUT</span>}
                {cur.kind === "hook" && <span className="mono">HOOK</span>}
              </div>
            </>
          )}
        </div>
        {mode === "flip" && (
          <div className="rl-controls">
            <button type="button" className="rl-play" aria-label={playing ? "Pause" : "Play flipbook"} onClick={() => setPlaying((p) => !p)}>
              {playing ? (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><rect x="2" y="1" width="3.5" height="12" rx="1" /><rect x="8.5" y="1" width="3.5" height="12" rx="1" /></svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor"><path d="M3 1.5v11a.5.5 0 0 0 .76.43l9-5.5a.5.5 0 0 0 0-.86l-9-5.5A.5.5 0 0 0 3 1.5Z" /></svg>
              )}
            </button>
            <input type="range" min={0} max={frames.length - 1} value={i} onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }} aria-label="Scrub frames" />
            <span className="mono" style={{ fontSize: 12, color: "var(--muted)" }}>{i + 1}/{frames.length}</span>
          </div>
        )}
        {video && (
          <div className="rl-viewtoggle">
            <button type="button" aria-pressed={mode === "flip"} onClick={() => setMode("flip")}>Flipbook</button>
            <button type="button" aria-pressed={mode === "video"} onClick={() => { setPlaying(false); setMode("video"); }}>Original video</button>
          </div>
        )}
      </div>

      <div>
        <div className="rl-stats">
          <div className="rl-stat"><b>{duration ? `${duration.toFixed(1)}s` : "—"}</b><small>duration</small></div>
          <div className="rl-stat"><b>{s.shots}</b><small>shots</small></div>
          <div className="rl-stat"><b>{s.avg_shot_s ?? "—"}s</b><small>avg shot length</small></div>
          <div className="rl-stat"><b>{s.cuts_in_first_3s}</b><small>cuts in first 3s</small></div>
        </div>
        {groups.map((g) =>
          g.items.length ? (
            <section key={g.title}>
              <div className="rl-group">{g.title}</div>
              <div className="rl-strip">
                {g.items.map((f) => {
                  const idx = frames.indexOf(f);
                  const badge = f.cut ? "cut" : f.kind === "hook" || f.kind === "end" ? "hook" : "";
                  return (
                    <button key={f.n} type="button" className="rl-frame" aria-current={idx === i} onClick={() => { setMode("flip"); setPlaying(false); setI(idx); }} aria-label={`Frame at ${f.t.toFixed(2)} seconds`}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={fileUrl(jobId, f.file)} alt="" loading="lazy" />
                      <span className="ts">{f.t.toFixed(1)}s</span>
                      {badge && <span className={`k ${badge}`}>{f.cut ? "CUT" : KIND_LABEL[f.kind]}</span>}
                    </button>
                  );
                })}
              </div>
            </section>
          ) : null,
        )}
        {fb.sheet && (
          <p style={{ marginTop: 18 }}>
            <a className="rl-btn" href={`${fileUrl(jobId, `flipbook/${fb.sheet}`)}?download=1`}>Download contact sheet</a>
          </p>
        )}
      </div>
    </div>
  );
}
