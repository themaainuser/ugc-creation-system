/* Command bar: brand, persona switcher, engine health, day stamp. */
import type { Health, Persona } from "../../lib/types";
import { Btn } from "../ui";

interface Props {
  personas: Persona[];
  personaId: string;
  health: Health | null;
  onPersona: (id: string) => void;
  onRefresh: () => void;
}

function Led({ ok, warn, label, value }: { ok?: boolean; warn?: boolean; label: string; value: string }) {
  return (
    <span className={`led ${ok ? "on" : warn ? "warn" : ""}`}>
      <span className="dot" />
      {label} <b>{value}</b>
    </span>
  );
}

export function TopRail({ personas, personaId, health, onPersona, onRefresh }: Props) {
  const persona = personas.find((p) => p.id === personaId);
  const day = new Date().toLocaleDateString("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });

  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">UG</span>
        <span className="brand-name">UGC Factory</span>
        <span className="brand-mode">Operate</span>
      </div>

      <div className="persona-switch">
        <label htmlFor="persona-select" className="persona-label">Persona</label>
        <select
          id="persona-select"
          value={personaId}
          onChange={(e) => onPersona(e.target.value)}
          disabled={personas.length === 0}
        >
          {personas.length === 0 && <option value="">Loading…</option>}
          {personas.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.id})
            </option>
          ))}
        </select>
        {persona && (
          <span className="persona-echo tnum">
            {persona.niche ?? "—"} · {persona.aesthetic ?? "—"}
          </span>
        )}
      </div>

      <div className="health" aria-label="engine health" aria-live="polite">
        <Led ok={health?.jev} warn={health ? !health.jev : undefined} label="JEV"
             value={health ? (health.jev ? "online" : "local") : "…"} />
        <Led ok={health?.llm} warn={health ? !health.llm : undefined} label="LLM"
             value={health ? (health.llm ? "configured" : "off") : "…"} />
        <Led ok label="Assets" value={health ? String(health.assets) : "…"} />
        <Led ok label="Personas" value={health ? String(health.personas) : "…"} />
      </div>

      <div className="top-actions">
        <span className="daystamp tnum" aria-label="today">{day}</span>
        <Btn variant="ghost" onClick={onRefresh} ariaLabel="Reload personas and engine health"
             title="Reload personas + health from the engine">
          ↻ Refresh
        </Btn>
      </div>
    </header>
  );
}
