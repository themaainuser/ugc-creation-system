/* Station 01 — Intake: persona context, reel transcript, operator context/idea,
   the MDEP shoot-day quad, run control, and asset library scan. */
import { useState } from "react";
import type { ConsoleState } from "../../lib/state";
import type { Health, MDEP, Persona } from "../../lib/types";
import { DAYS, ENVIRONMENTS, MOODS, PLACES } from "../../lib/types";
import { engine } from "../../lib/engine";
import { mdepLine } from "../../lib/format";
import { Btn, Field, Station } from "../ui";

interface Props {
  state: ConsoleState;
  onDraft: (patch: Partial<ConsoleState["draft"]>) => void;
  onRun: () => void;
  canRun: boolean;
  onScanned: () => void;
}

function MdepQuad({ mdep, onChange }: { mdep: MDEP; onChange: (m: MDEP) => void }) {
  const sel = (id: string, label: string, value: string, options: string[], set: (v: string) => void) => (
    <Field label={label} htmlFor={id}>
      <select id={id} value={value} onChange={(e) => set(e.target.value)}>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </Field>
  );
  return (
    <div className="mdep-wrap">
      <span className="flabel" id="mdep-label">Shoot day (MDEP)</span>
      <div className="mdep-grid" role="group" aria-labelledby="mdep-label">
        {sel("m-mood", "Mood", mdep.mood, MOODS, (v) => onChange({ ...mdep, mood: v }))}
        {sel("m-day", "Day", mdep.day, DAYS, (v) => onChange({ ...mdep, day: v }))}
        {sel("m-env", "Environment", mdep.environment, ENVIRONMENTS, (v) =>
          onChange({ ...mdep, environment: v, place: v }))}
        {sel("m-place", "Place", mdep.place, PLACES, (v) => onChange({ ...mdep, place: v }))}
      </div>
      <span className="mdep-readout tnum">{mdepLine(mdep)}</span>
    </div>
  );
}

export function IntakeStation({ state, onDraft, onRun, canRun, onScanned }: Props) {
  const { draft, phase, personas } = state;
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState("");

  const persona: Persona | undefined = personas.find((p) => p.id === draft.personaId);
  const health: Health | null = state.health;
  const running = phase === "running" || phase === "overriding";

  // During redress the button stays live and starts a fresh run — so the
  // label must say what a click does, not what the console is doing.
  const runLabel = running
    ? state.activeStage === "analyze"
      ? "Analyzing…"
      : "Building brief…"
    : state.brief
      ? "Re-run line"
      : "Run line";

  const scan = async () => {
    const f = draft.folder.trim();
    if (scanning || !f) return;
    setScanning(true);
    setScanMsg("");
    try {
      const d = await engine<{ count: number; by_category: Record<string, number> }>("scan", { folder: f });
      const by = Object.entries(d.by_category).map(([k, v]) => `${k}: ${v}`).join(" · ");
      setScanMsg(`${d.count} asset${d.count === 1 ? "" : "s"} indexed · ${by || "no categories"}`);
      onScanned(); // refresh health LEDs — the asset count just changed
    } catch (e) {
      setScanMsg(`scan failed — ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="col col-intake">
      <Station
        id="station-intake"
        idx="01"
        title="Intake"
        stamp={running ? "Feeding" : phase === "ready" ? "Fed" : undefined}
        stampTone={running ? "active" : "done"}
      >
        {persona && (
          <div className="persona-card">
            <span className="pc-name">{persona.name}</span>
            <span className="pc-meta">
              {persona.niche ?? "—"} · {persona.gender ?? "—"} · {persona.aesthetic ?? "—"}
            </span>
            {persona.voice_tone && <span className="pc-tone">voice: “{persona.voice_tone}”</span>}
          </div>
        )}

        <Field
          label="Reel transcript"
          htmlFor="f-transcript"
          count={`${draft.transcript.length} chars`}
          hint="Paste the reel transcript or script."
        >
          <textarea
            id="f-transcript"
            rows={7}
            placeholder="Paste the reel transcript or script here…"
            value={draft.transcript}
            onChange={(e) => onDraft({ transcript: e.target.value })}
          />
        </Field>

        <Field
          label="Context — why it fits this persona"
          htmlFor="f-context"
          hint="Operator's note; the analyzer reads it as user context."
        >
          <input
            id="f-context"
            type="text"
            placeholder="e.g. pacing and lighting suit Aria's audience"
            value={draft.context}
            onChange={(e) => onDraft({ context: e.target.value })}
          />
        </Field>

        <Field
          label="Idea / twist (optional)"
          htmlFor="f-idea"
          hint="Your twist lands in the brief as an operator line."
        >
          <input
            id="f-idea"
            type="text"
            placeholder="e.g. same script, but in a thrift store"
            value={draft.idea}
            onChange={(e) => onDraft({ idea: e.target.value })}
          />
        </Field>

        <MdepQuad mdep={draft.mdep} onChange={(m) => onDraft({ mdep: m })} />

        <div className="actions">
          <Btn variant="primary" onClick={onRun} disabled={!canRun || running} loading={running}>
            {runLabel}
          </Btn>
        </div>
        {!draft.personaId && <p className="hint">No persona loaded — check the engine is reachable.</p>}
        {draft.personaId && !draft.transcript.trim() && !draft.idea.trim() && (
          <p className="hint">Add a reel transcript or an idea to run the line.</p>
        )}

        <div className="scan-block">
          <Field label="Asset folder" htmlFor="f-folder"
                  hint={`Indexed library: ${health?.assets ?? "—"} assets`}>
            <input
              id="f-folder"
              type="text"
              placeholder="C:\path\to\assets (or relative to ugc-system)"
              value={draft.folder}
              onChange={(e) => onDraft({ folder: e.target.value })}
              onKeyDown={(e) => { if (e.key === "Enter") scan(); }}
            />
          </Field>
          <Btn onClick={scan} loading={scanning} disabled={!draft.folder.trim()}
               title="POST scan — indexes the folder and refreshes the asset count">
            {scanning ? "Scanning…" : "Scan assets"}
          </Btn>
          {scanMsg && <p className="scan-result" role="status">{scanMsg}</p>}
        </div>
      </Station>
    </div>
  );
}
