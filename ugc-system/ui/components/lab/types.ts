export type StageState = "pending" | "running" | "done" | "skipped" | "error";
export type Stage = { state: StageState; message: string; label: string; started_at?: number; finished_at?: number };
export type Status = { state: "queued" | "running" | "done" | "error"; error: string | null; updated_at: number; stages: Record<string, Stage> };
export type Frame = { n: number; t: number; kind: "hook" | "cut" | "coverage" | "end"; cut?: boolean; file: string };
export type Flipbook = {
  frames: Frame[];
  scene_cuts: number[];
  sheet?: string;
  stats: { shots: number; avg_shot_s: number | null; cuts_in_first_3s: number; cuts_per_10s: number | null };
};
export type Segment = { start: number; end: number; text: string };
export type Transcript = { provider: string; language: string | null; segments: Segment[]; note?: string; text?: string };
export type Asset = { file: string; kind: string; label: string };
export type Spec = {
  id: string; url: string | null; persona: string | null; mode: "remix" | "recreate";
  context: string; idea: string; targets?: { image?: string; video?: string };
  assets: Asset[]; source_job: string | null; created_at: string;
};
export type Usage = { provider: string; model: string; images: number; input_tokens: number; output_tokens: number; est_cost_usd: number; stop_reason: string | null };
export type JobView = {
  id: string; spec: Spec; status: Status | null;
  info: { platform?: Record<string, unknown>; probe?: { duration: number; width: number; height: number; fps: number }; audio?: { silent_ratio: number | null } } | null;
  transcript: Transcript | null; flipbook: Flipbook | null; usage: Usage | null;
  blueprint: { title?: string; essence?: string; formula?: string } | null;
  video: string | null;
  docs: { reel_flow: string | null; generation_prompts: string | null; partial: string | null };
};
export type JobSummary = { id: string; state: string; persona: string | null; url: string | null; mode: string; title: string | null; idea: string; created_at: string | null };
export type Persona = { id: string; name: string; gender?: string; niche?: string; aesthetic?: string; voice_tone?: string };
export type Health = {
  ffmpeg?: boolean; ytdlp?: boolean; transcriber?: string; mastermind?: string | null;
  mastermind_model?: string; dry_run?: boolean; personas?: Persona[]; error?: string;
};
export const fileUrl = (id: string, rel: string) => `/api/reel/${id}/file/${rel}`;
export const fmtT = (t: number) => {
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
};
