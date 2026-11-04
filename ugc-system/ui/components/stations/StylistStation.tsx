/* Station 03 — Stylist: outfit from the asset library, poses, and the
   Outfit JEV Decision (lockable, no override — selection is engine-scored). */
import type { ConsoleState, Lock } from "../../lib/state";
import type { Asset, Decision } from "../../lib/types";
import { fileName } from "../../lib/format";
import { DecisionCard } from "../DecisionCard";
import { Btn, Chip, Empty, Meter, SkeletonStack, Station } from "../ui";

interface Props {
  state: ConsoleState;
  decision: Decision | null;
  lock: Lock | null;
  onToggleLock: () => void;
  onJumpIntake: () => void;
}

export function StylistStation({ state, decision, lock, onToggleLock, onJumpIntake }: Props) {
  const { phase, brief } = state;
  const redressing = phase === "redressing";
  const running = (phase === "running" || phase === "overriding") && state.activeStage !== "analyze";
  const outfit = brief?.style.outfit;
  const all: Asset[] = outfit
    ? [...outfit.items, ...(outfit.jewelry ? [outfit.jewelry] : []), ...(outfit.footwear ? [outfit.footwear] : [])]
    : [];
  const emptyWardrobe = Boolean(brief && all.length === 0);

  return (
    <Station
      id="station-stylist"
      idx="03"
      title="Stylist"
      stamp={redressing ? "Re-dressing" : running ? "Dressing" : brief ? "Complete" : undefined}
      stampTone={redressing || running ? "active" : "done"}
    >
      {running ? (
        <SkeletonStack n={3} />
      ) : !brief ? (
        <Empty
          title="No styling yet"
          hint="Outfit, jewelry, footwear, and poses appear after the line runs."
        />
      ) : emptyWardrobe ? (
        <>
          <Empty
            title="Wardrobe is empty"
            hint="Nothing scored — scan an asset folder to stock the library, then re-run the line."
            action={<Btn onClick={onJumpIntake}>Scan assets</Btn>}
          />
          <DecisionCard
            title="Outfit"
            decision={decision}
            emptyNote="No Outfit decision — the wardrobe was empty."
            lock={lock}
            effectiveChoice={lock?.choice ?? decision?.chosen ?? null}
            onToggleLock={onToggleLock}
          />
        </>
      ) : (
        <>
          <div>
            <span className="flabel">Outfit</span>
            <ul className="fit-list">
              {all.map((a, i) => (
                <li className="fit-item" key={`${a.path}-${i}`}>
                  <div>
                    <div className="name">{fileName(a.path)}</div>
                    <div className="meta tnum">
                      {a.category}
                      {a.brands.length > 0 && <> · {a.brands.join(", ")}</>}
                      {a.colors.length > 0 && <> · {a.colors.join(", ")}</>}
                      {a.style_tags.length > 0 && <> · {a.style_tags.join(", ")}</>}
                    </div>
                  </div>
                  <Meter value={a.formality} />
                </li>
              ))}
            </ul>
          </div>
          {brief.style.outfit.rationale && <p className="rationale">{brief.style.outfit.rationale}</p>}

          <DecisionCard
            title="Outfit"
            decision={decision}
            lock={lock}
            effectiveChoice={lock?.choice ?? decision?.chosen ?? null}
            onToggleLock={onToggleLock}
          />

          <div>
            <span className="flabel">Poses</span>
            <div className="poses">
              {brief.style.pose.poses.map((p) => (
                <Chip key={p}>{p}</Chip>
              ))}
            </div>
            {brief.style.pose.shot_notes && <p className="shot-notes">{brief.style.pose.shot_notes}</p>}
            {brief.style.location_notes && <p className="loc-notes">{brief.style.location_notes}</p>}
          </div>
        </>
      )}
    </Station>
  );
}
