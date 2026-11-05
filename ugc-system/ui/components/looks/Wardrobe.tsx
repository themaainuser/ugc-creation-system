"use client";
import "../../app/lab.css";
import { useEffect, useMemo, useRef, useState } from "react";
import TopBar from "../lab/TopBar";

type Item = { id: string; file: string; name: string; category: string; subcategory?: string; brand?: string; tier?: string; colors?: { name: string; hex: string }[]; formality: number; warmth: number; statement: number; style_tags?: string[]; description?: string; story?: string; tagged_by: string; demo?: boolean };
const CATS = ["all", "top", "bottom", "dress", "outerwear", "footwear", "jewelry", "bag", "accessory"];
const img = (it: Item) => `/api/wardrobe/file/${it.demo ? "demo" : "wardrobe"}/${it.file}`;

export default function Wardrobe() {
  const [items, setItems] = useState<Item[]>([]);
  const [demo, setDemo] = useState(false);
  const [cat, setCat] = useState("all");
  const [folder, setFolder] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const load = (d: { items?: Item[]; demo?: boolean; error?: string }) => {
    if (d.error) { setMsg(d.error); return; }
    setItems(d.items ?? []);
    setDemo(!!d.demo);
  };
  const rescan = () => {
    setBusy("Scanning…");
    fetch("/api/styling?cmd=scan").then((r) => r.json()).then(load).finally(() => setBusy(null));
  };
  useEffect(rescan, []);

  const upload = async (files: FileList | File[]) => {
    const fd = new FormData();
    fd.set("folder", folder);
    let n = 0;
    for (const f of Array.from(files)) if (/^image\//.test(f.type)) { fd.append("files", f); n++; }
    if (!n) return;
    setBusy(`Uploading ${n} image${n > 1 ? "s" : ""}…`);
    setMsg(null);
    const d = await fetch("/api/wardrobe", { method: "POST", body: fd }).then((r) => r.json());
    load(d);
    setBusy(null);
    setMsg(`Added ${d.saved} image${d.saved === 1 ? "" : "s"}${folder ? ` to wardrobe/${folder}` : ""}. Tagged from file names for now — run “Tag with Opus” for real tags.`);
  };
  const tag = async () => {
    setBusy("Opus is looking at each item…");
    setMsg(null);
    const d = await fetch("/api/styling", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cmd: "tag" }) }).then((r) => r.json());
    setMsg(d.error ? d.error : `Tagged ${d.tagged} item${d.tagged === 1 ? "" : "s"} · ~$${d.cost_usd.toFixed(3)}${d.remaining ? ` · ${d.remaining} left` : ""}`);
    rescan();
  };

  const shown = useMemo(() => (cat === "all" ? items : items.filter((i) => i.category === cat)), [items, cat]);
  const untagged = items.filter((i) => i.tagged_by === "guess" || i.tagged_by === "legacy").length;
  const counts = useMemo(() => Object.fromEntries(CATS.map((c) => [c, c === "all" ? items.length : items.filter((i) => i.category === c).length])), [items]);

  return (
    <div className="lab">
      <TopBar active="wardrobe" />
      <main className="rl-main" style={{ maxWidth: 1400, margin: "0 auto" }}>
        <div className="wd-head">
          <div>
            <h2>Wardrobe</h2>
            <div className="stats">{items.length} pieces · {untagged} waiting for Opus tags · folder <span className="mono">ugc-system/{demo ? "assets/seed (demo)" : "wardrobe"}</span></div>
          </div>
          <div className="actions">
            <button type="button" className="rl-btn" disabled={!!busy} onClick={rescan}>Rescan folder</button>
            <button type="button" className="rl-btn primary" disabled={!!busy || !untagged || demo} onClick={tag} title={demo ? "Add your own images first" : ""}>Tag with Opus{untagged ? ` (${untagged})` : ""}</button>
          </div>
        </div>

        {demo && (
          <div className="rl-banner" style={{ marginBottom: 18 }}>
            <span>These are <b>demo placeholders</b>. Drop your real PNG/JPEGs below (or straight into <span className="mono">ugc-system/wardrobe/</span>) and the stylist switches to them.</span>
          </div>
        )}

        <div className="rl-field" style={{ maxWidth: 760 }}>
          <div className="rl-inline" style={{ gridTemplateColumns: "minmax(0, 220px) minmax(0, 1fr)" }}>
            <input className="rl-input" placeholder="folder hint: gucci, thrift, handmade" value={folder} onChange={(e) => setFolder(e.target.value)} aria-label="Folder hint" />
            <div
              className={`rl-drop${over ? " over" : ""}`} role="button" tabIndex={0}
              onClick={() => input.current?.click()}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setOver(true); }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></svg>
              <span>Drop clothing, jewelry and footwear images <span style={{ color: "var(--muted)" }}>— the folder hint helps tagging</span></span>
            </div>
          </div>
          <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={(e) => { if (e.target.files) upload(e.target.files); e.target.value = ""; }} />
          {busy && <p className="rl-note" style={{ display: "flex", gap: 8, alignItems: "center" }}><span className="rl-spin" />{busy}</p>}
          {msg && <p className="rl-note">{msg}</p>}
        </div>

        <div className="rl-tabs" role="tablist">
          {CATS.map((c) => (
            <button key={c} type="button" role="tab" aria-selected={cat === c} onClick={() => setCat(c)} disabled={!counts[c]}>
              {c === "all" ? "All" : c[0].toUpperCase() + c.slice(1)}<span className="count">{counts[c]}</span>
            </button>
          ))}
        </div>

        <div className="wd-grid">
          {shown.map((it) => (
            <div key={it.id} className="wd-card">
              <div className="lk-item">
                <div className="img">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={img(it)} alt={it.name} loading="lazy" />
                </div>
                <span className={`wd-by ${it.tagged_by}`} title={it.tagged_by === "opus" ? "Tagged by Opus from the image" : it.tagged_by === "manual" ? "You edited the sidecar" : "Guessed from the file name — tag with Opus"}>{it.tagged_by}</span>
                <div className="body">
                  <b>{it.name}</b>
                  <small>{[it.brand, it.tier?.replace("_", " "), it.subcategory || it.category].filter(Boolean).join(" · ")}</small>
                  <small>formality {it.formality}/10 · warmth {it.warmth}/5 · statement {Math.round(it.statement * 100)}%</small>
                  {!!it.colors?.length && <div className="lk-sw">{it.colors.map((c) => <i key={c.hex + c.name} style={{ background: c.hex }} title={c.name} />)}</div>}
                  {!!it.style_tags?.length && <div className="wd-tags">{it.style_tags.map((t) => <span key={t}>{t}</span>)}</div>}
                  {it.description && <small style={{ marginTop: 6, color: "var(--text-2)" }}>{it.description}</small>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
