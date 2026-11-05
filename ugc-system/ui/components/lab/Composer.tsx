"use client";
import { useEffect, useRef, useState } from "react";
import type { Persona } from "./types";

export type Draft = {
  url: string; video: File | null; persona: string; mode: "remix" | "recreate";
  context: string; idea: string; imageModel: string; videoModel: string;
  assets: { file: File; kind: string; label: string; preview: string }[];
  sourceJob: string | null;
};
export const emptyDraft = (persona = ""): Draft => ({
  url: "", video: null, persona, mode: "remix", context: "", idea: "",
  imageModel: "", videoModel: "", assets: [], sourceJob: null,
});

const KINDS = ["character", "outfit", "jewelry", "footwear", "location", "product", "prop", "other"];
const IMAGE_MODELS = ["", "Nano Banana Pro", "Flux 2", "Midjourney v8", "Seedream 4", "GPT-Image 2"];
const VIDEO_MODELS = ["", "Kling 3", "Veo 4", "Sora 3", "Seedance 2", "Runway Gen-5", "Hailuo 03"];

function guessKind(name: string) {
  const n = name.toLowerCase();
  if (/face|ref|model|char|selfie|portrait/.test(n)) return "character";
  if (/ring|neck|chain|earring|jewel|brace/.test(n)) return "jewelry";
  if (/shoe|sneaker|heel|sandal|boot/.test(n)) return "footwear";
  if (/dress|top|tee|shirt|jean|skirt|hoodie|jacket|blazer|trouser|outfit/.test(n)) return "outfit";
  if (/room|cafe|street|beach|studio|mall|place|bg|location/.test(n)) return "location";
  return "other";
}

export default function Composer({
  draft, setDraft, personas, onSubmit, submitting, error, ready,
}: {
  draft: Draft; setDraft: (d: Draft) => void; personas: Persona[];
  onSubmit: () => void; submitting: boolean; error: string | null; ready: boolean;
}) {
  const [over, setOver] = useState<"video" | "assets" | null>(null);
  const videoInput = useRef<HTMLInputElement>(null);
  const assetInput = useRef<HTMLInputElement>(null);
  const set = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });
  const hasSource = !!(draft.url.trim() || draft.video || draft.sourceJob);

  const addAssets = (files: FileList | File[]) => {
    const imgs = Array.from(files).filter((f) => /^image\//.test(f.type));
    set({ assets: [...draft.assets, ...imgs.map((f) => ({ file: f, kind: guessKind(f.name), label: "", preview: URL.createObjectURL(f) }))] });
  };
  useEffect(() => () => draft.assets.forEach((a) => URL.revokeObjectURL(a.preview)), []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (hasSource && !submitting) onSubmit(); }}>
      <h1 className="rl-h1">Drop a reel.<br /><em>Get its playbook.</em></h1>
      <p className="rl-sub">The lab downloads it, splits the audio, transcribes it, flips through every shot, then Opus 5.5 writes the flow breakdown and the prompts for your version.</p>

      {draft.sourceJob ? (
        <div className="rl-banner">
          <span>Remixing <span className="mono">{draft.sourceJob}</span> — no re-download, only Opus runs.</span>
          <button type="button" onClick={() => set({ sourceJob: null })}>Use a new reel</button>
        </div>
      ) : (
        <div className="rl-field">
          <label className="rl-label" htmlFor="rl-url"><span className="n">01</span>Reel</label>
          <input id="rl-url" className="rl-input" type="url" inputMode="url" placeholder="https://www.instagram.com/reel/…" value={draft.url} onChange={(e) => set({ url: e.target.value })} disabled={!!draft.video} />
          <div className="rl-or">or</div>
          <div
            className={`rl-drop${over === "video" ? " over" : ""}`}
            role="button" tabIndex={0}
            onClick={() => videoInput.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && videoInput.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setOver("video"); }}
            onDragLeave={() => setOver(null)}
            onDrop={(e) => { e.preventDefault(); setOver(null); const f = e.dataTransfer.files[0]; if (f && /^video\//.test(f.type)) set({ video: f, url: "" }); }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="13" height="14" rx="2" /><path d="m16 10 5-3v10l-5-3" /></svg>
            {draft.video ? (
              <>
                <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{draft.video.name} · {(draft.video.size / 1e6).toFixed(1)} MB</span>
                <button type="button" className="x" onClick={(e) => { e.stopPropagation(); set({ video: null }); }}>Remove</button>
              </>
            ) : (
              <span>Upload the video file <span style={{ color: "var(--muted)" }}>— best for private or login-walled reels</span></span>
            )}
          </div>
          <input ref={videoInput} type="file" accept="video/*" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) set({ video: f, url: "" }); e.target.value = ""; }} />
        </div>
      )}

      <div className="rl-field">
        <div className="rl-label"><span className="n">02</span>Persona</div>
        <div className="rl-chips">
          {personas.map((p) => (
            <button key={p.id} type="button" className="rl-chip" aria-pressed={draft.persona === p.id} onClick={() => set({ persona: draft.persona === p.id ? "" : p.id })}>
              <b>{p.name}</b>
              <small>{[p.niche, p.gender].filter(Boolean).join(" · ")}</small>
            </button>
          ))}
          {!personas.length && <span className="rl-note">No personas found in ugc-system/personas/.</span>}
        </div>
      </div>

      <div className="rl-field">
        <div className="rl-label"><span className="n">03</span>Mode</div>
        <div className="rl-seg">
          <button type="button" aria-pressed={draft.mode === "remix"} onClick={() => set({ mode: "remix" })}><b>Remix</b><small>same essence, my idea</small></button>
          <button type="button" aria-pressed={draft.mode === "recreate"} onClick={() => set({ mode: "recreate" })}><b>Recreate</b><small>same script, my model</small></button>
        </div>
      </div>

      <div className="rl-field">
        <label className="rl-label" htmlFor="rl-ctx"><span className="n">04</span>Why it fits this persona<span className="opt">optional</span></label>
        <textarea id="rl-ctx" className="rl-textarea" placeholder="e.g. The deadpan hook matches Aria's dry humor, and thrift is her whole brand." value={draft.context} onChange={(e) => set({ context: e.target.value })} />
      </div>

      <div className="rl-field">
        <label className="rl-label" htmlFor="rl-idea"><span className="n">05</span>{draft.mode === "remix" ? "Idea / twist" : "What to adapt"}<span className="opt">{draft.mode === "remix" ? "blank = Opus pitches one" : "optional"}</span></label>
        <textarea id="rl-idea" className="rl-textarea" style={{ minHeight: 96 }} placeholder={draft.mode === "remix" ? "e.g. Same 'rating my purchases' format, but she rates thrift finds against the luxury pieces they copy." : "e.g. Move it from a kitchen to a hotel room in Goa."} value={draft.idea} onChange={(e) => set({ idea: e.target.value })} />
      </div>

      <div className="rl-field">
        <div className="rl-label"><span className="n">06</span>Your assets<span className="opt">face refs, outfits, products, places</span></div>
        <div
          className={`rl-drop${over === "assets" ? " over" : ""}`}
          role="button" tabIndex={0}
          onClick={() => assetInput.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && assetInput.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setOver("assets"); }}
          onDragLeave={() => setOver(null)}
          onDrop={(e) => { e.preventDefault(); setOver(null); addAssets(e.dataTransfer.files); }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="9" cy="9" r="2" /><path d="m21 15-5-5L5 21" /></svg>
          <span>Add images <span style={{ color: "var(--muted)" }}>— anything missing gets a generation prompt</span></span>
        </div>
        <input ref={assetInput} type="file" accept="image/*" multiple hidden onChange={(e) => { if (e.target.files) addAssets(e.target.files); e.target.value = ""; }} />
        {draft.assets.length > 0 && (
          <div className="rl-assets">
            {draft.assets.map((a, n) => (
              <div key={a.preview} className="rl-asset">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={a.preview} alt="" />
                <div className="meta">
                  <div className="row">
                    <select className="rl-select" value={a.kind} aria-label="Asset type" onChange={(e) => set({ assets: draft.assets.map((x, i) => (i === n ? { ...x, kind: e.target.value } : x)) })}>
                      {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                    </select>
                    <input className="rl-input" placeholder="note, e.g. 'Aria face ref'" value={a.label} aria-label="Asset note" onChange={(e) => set({ assets: draft.assets.map((x, i) => (i === n ? { ...x, label: e.target.value } : x)) })} />
                  </div>
                  <small style={{ color: "var(--muted)", fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.file.name}</small>
                </div>
                <button type="button" className="rl-icon-btn" aria-label={`Remove ${a.file.name}`} onClick={() => { URL.revokeObjectURL(a.preview); set({ assets: draft.assets.filter((_, i) => i !== n) }); }}>
                  <svg width="14" height="14" viewBox="0 0 14 14" stroke="currentColor" strokeWidth="1.6"><path d="m3 3 8 8M11 3l-8 8" /></svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rl-field">
        <div className="rl-label"><span className="n">07</span>Target models<span className="opt">tunes prompt style</span></div>
        <div className="rl-two">
          <select className="rl-select" value={draft.imageModel} aria-label="Image model" onChange={(e) => set({ imageModel: e.target.value })}>
            {IMAGE_MODELS.map((m) => <option key={m} value={m}>{m || "Image model: any"}</option>)}
          </select>
          <select className="rl-select" value={draft.videoModel} aria-label="Video model" onChange={(e) => set({ videoModel: e.target.value })}>
            {VIDEO_MODELS.map((m) => <option key={m} value={m}>{m || "Video model: any"}</option>)}
          </select>
        </div>
      </div>

      <button type="submit" className="rl-run" disabled={!hasSource || submitting}>
        {submitting ? <><span className="rl-spin" /> Starting…</> : <>Run the reel <span aria-hidden>→</span></>}
      </button>
      {!ready && <p className="rl-note">Setup isn&apos;t complete — check the status pills at the top.</p>}
      {error && <div className="rl-err-box" role="alert">{error}</div>}
    </form>
  );
}
