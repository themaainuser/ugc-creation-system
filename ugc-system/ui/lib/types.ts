/* Mirrored engine contract — keep 1:1 with ugc_system/core/models.py + bridge.py.
   Python stays the single source of truth; these types only describe its JSON. */

export type VerdictMode = "remix" | "recreate";
export type DecisionVerb = "verdict" | "outfit" | "expression";
export type Gate = "automate" | "escalate";

/* Pipeline stages shown on the StageRail (order is the assembly line). */
export type Stage = "intake" | "analyze" | "style" | "express" | "dispatch";
/* While the brief builds, style+express+dispatch all compute behind one call;
   "redress" is the MDEP re-dress pass over style + expression. */
export type ActiveStage = Stage | "build" | "redress" | null;

export type Phase = "idle" | "running" | "overriding" | "redressing" | "ready";

export interface MDEP {
  mood: string;
  day: string;
  environment: string;
  place: string;
}

/* MDEP option keys mirror engine rule tables (stylist._PLACE_RULES,
   expressions._MOOD_MAP). Changing engine keys requires updating these. */
export const MOODS = ["neutral", "confident", "cozy", "playful", "elegant", "edgy", "relaxed", "focused", "grateful"];
export const DAYS = ["casual weekday", "weekend", "vacation day", "event night", "workday", "festival"];
export const ENVIRONMENTS = ["home", "mall", "fastfood", "vacation", "work", "studio", "ramp", "beach", "restaurant", "gym", "party"];
export const PLACES = ["home", "fastfood", "mall", "vacation", "work", "studio", "ramp", "beach", "restaurant", "gym", "party"];

export interface Persona {
  id: string;
  name: string;
  gender?: string;
  age_range?: string;
  niche?: string;
  aesthetic?: string;
  brand_tier?: string[];
  jewelry_style?: string;
  voice_tone?: string;
  follower_style?: string;
  banned_topics?: string[];
  notes?: string;
}

export interface Health {
  ok: boolean;
  jev: boolean;
  llm: boolean;
  models?: { jev?: string | null; llm?: string | null };
  assets: number;
  personas: number;
}

export interface Hook {
  text_or_action: string;
  hook_type: string;
  why_it_works: string;
  first_3_seconds: string;
}

export interface Beat {
  order: number;
  timestamp: string;
  purpose: string;
  what_happens: string;
  technique: string;
}

export interface Ending {
  style: string;
  detail: string;
  loop_close: boolean;
}

export interface Analysis {
  source?: string;
  hook: Hook;
  beats: Beat[];
  ending: Ending;
  verdict: VerdictMode;
  verdict_reason: string;
  user_context?: string;
  remix_ideas: string[];
  niche_tags: string[];
}

export interface Asset {
  path: string;
  category: string;
  brands: string[];
  colors: string[];
  style_tags: string[];
  formality: number;
}

export interface Expression {
  name: string;
  genuine: boolean;
  when_to_use: string;
  micro_details: string;
}

export interface OptionScore {
  name: string;
  p: number;
  raw: number;
  signals: string[];
}

export interface Decision {
  verb: string;
  chosen: string;
  confidence: number;
  gate: Gate;
  calibrated: boolean;
  rationale: string;
  brier_estimate?: number;
  options: OptionScore[];
}

export interface OutfitPlan {
  items: Asset[];
  jewelry: Asset | null;
  footwear: Asset | null;
  rationale: string;
}

export interface StylePlan {
  mdep?: MDEP;
  outfit: OutfitPlan;
  pose: { poses: string[]; shot_notes: string };
  location_notes: string;
}

export interface ExpressionPlan {
  primary: Expression;
  secondary: Expression[];
  avoid: string[];
  audio_note: string;
  rationale: string;
}

export interface Brief {
  persona_id: string;
  mdep: MDEP;
  mode: VerdictMode;
  hook: string;
  script_outline: string[];
  style: StylePlan;
  expressions: ExpressionPlan;
  caption_idea: string;
  hashtags: string[];
  decisions: {
    verdict: Decision | null;
    outfit: Decision | null;
    expression: Decision | null;
  };
  escalations: string[];
}

/* ---- bridge command payloads / responses ---- */

export interface AnalyzeRes {
  analysis: Analysis;
  decision: Decision;
}

export interface BriefRes {
  brief: Brief;
  analysis: Analysis | null;
}

export interface PlanDayRes {
  style: StylePlan;
  expressions: ExpressionPlan;
  decisions: { outfit: Decision | null; expression: Decision | null };
  escalations: string[];
}

export interface OutcomeRes {
  brier: number;
  record: {
    verb: string;
    chosen: string;
    confidence: number;
    gate: string;
    outcome: string;
    brier: number;
  };
}

export interface ScanRes {
  count: number;
  by_category: Record<string, number>;
}
