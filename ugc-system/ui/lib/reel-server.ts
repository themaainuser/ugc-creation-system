// Server-only helpers for the Reel Lab API routes. The Python pipeline
// (ugc_system/reel_lab) owns all the work; these routes only create job
// folders, start the runner, and read its files back.
import { spawn, execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";

export const UGC_ROOT = path.join(/* turbopackIgnore: true */ process.cwd(), "..");
export const JOBS_DIR = path.join(UGC_ROOT, "data", "jobs");
export const PYTHON =
  process.env.PYC || process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");

export const validId = (id: string) => /^[\w-]{6,64}$/.test(id);

export function jobPath(id: string, ...rel: string[]) {
  const base = path.join(/* turbopackIgnore: true */ JOBS_DIR, id);
  const full = path.resolve(/* turbopackIgnore: true */ base, ...rel);
  if (!full.startsWith(base)) throw new Error("path escapes job folder");
  return full;
}

export async function readJson<T = unknown>(file: string): Promise<T | null> {
  try {
    return JSON.parse(await fs.readFile(file, "utf8")) as T;
  } catch {
    return null;
  }
}

export async function readText(file: string): Promise<string | null> {
  try {
    return await fs.readFile(file, "utf8");
  } catch {
    return null;
  }
}

export function newJobId() {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  const rand = Math.random().toString(16).slice(2, 8);
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(
    d.getMinutes(),
  )}${p(d.getSeconds())}-${rand}`;
}

export function safeName(name: string) {
  const ext = path.extname(name).toLowerCase().replace(/[^.\w]/g, "");
  const stem = path.basename(name, path.extname(name)).replace(/[^\w-]+/g, "_").slice(0, 60) || "file";
  return stem + ext;
}

const STAGES = ["download", "audio", "transcribe", "flipbook", "mastermind"] as const;
const LABELS: Record<string, string> = {
  download: "Download reel",
  audio: "Separate audio",
  transcribe: "Transcribe speech",
  flipbook: "Flipbook visuals",
  mastermind: "Opus mastermind",
};

export function freshStatus() {
  return {
    state: "queued",
    error: null as string | null,
    updated_at: Date.now() / 1000,
    stages: Object.fromEntries(STAGES.map((s) => [s, { state: "pending", message: "", label: LABELS[s] }])),
  };
}

/** Is a runner already working on this job? (status touched in the last 15 min) */
export async function isRunning(id: string) {
  const st = await readJson<{ state: string; updated_at: number }>(jobPath(id, "status.json"));
  return !!st && st.state === "running" && Date.now() / 1000 - st.updated_at < 900;
}

export async function startRun(id: string, redo: string[] = []) {
  const st = (await readJson<ReturnType<typeof freshStatus>>(jobPath(id, "status.json"))) ?? freshStatus();
  st.state = "queued";
  st.error = null;
  st.updated_at = Date.now() / 1000;
  await fs.writeFile(jobPath(id, "status.json"), JSON.stringify(st, null, 2));
  const args = ["-m", "ugc_system.reel_lab", "run", id];
  if (redo.length) args.push("--redo", redo.join(","));
  const child = spawn(/* turbopackIgnore: true */ PYTHON, args, {
    cwd: UGC_ROOT,
    detached: true,
    stdio: ["ignore", "ignore", "ignore"],
    windowsHide: true,
  });
  child.on("error", async (e) => {
    st.state = "error";
    st.error = `could not start ${PYTHON}: ${e.message} (set PYC env var to your python)`;
    await fs.writeFile(jobPath(id, "status.json"), JSON.stringify(st, null, 2)).catch(() => {});
  });
  child.unref();
}

export function health(): Promise<Record<string, unknown>> {
  return new Promise((resolve) => {
    execFile(
      /* turbopackIgnore: true */ PYTHON,
      ["-m", "ugc_system.reel_lab", "health"],
      { cwd: UGC_ROOT, timeout: 30_000, windowsHide: true },
      (err, stdout) => {
        try {
          resolve(JSON.parse(stdout));
        } catch {
          resolve({ error: `python not reachable (${PYTHON}): ${err?.message ?? "no output"}` });
        }
      },
    );
  });
}
