import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import { isRunning, jobPath, readJson, readText, startRun, validId } from "../../../../lib/reel-server";

export const runtime = "nodejs";
type Ctx = { params: Promise<{ id: string }> };

// GET /api/reel/:id -> everything the job page renders
export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params;
  if (!validId(id)) return NextResponse.json({ error: "bad id" }, { status: 400 });
  const spec = await readJson(jobPath(id, "job.json"));
  if (!spec) return NextResponse.json({ error: "job not found" }, { status: 404 });
  const [status, info, transcript, flipbook, usage, flow, prompts, partial, blueprint] = await Promise.all([
    readJson(jobPath(id, "status.json")),
    readJson(jobPath(id, "media", "info.json")),
    readJson(jobPath(id, "transcript.json")),
    readJson(jobPath(id, "flipbook", "index.json")),
    readJson(jobPath(id, "out", "usage.json")),
    readText(jobPath(id, "out", "reel_flow.md")),
    readText(jobPath(id, "out", "generation_prompts.md")),
    readText(jobPath(id, "out", "partial.md")),
    readJson(jobPath(id, "out", "blueprint.json")),
  ]);
  let video: string | null = null;
  try {
    video = (await fs.readdir(jobPath(id, "media"))).find((f) => /^source\.(mp4|mov|m4v|webm|mkv)$/i.test(f)) ?? null;
  } catch {}
  return NextResponse.json({
    id, spec, status, info, transcript, flipbook, usage, blueprint,
    video: video ? `media/${video}` : null,
    docs: { reel_flow: flow, generation_prompts: prompts, partial },
  });
}

// POST /api/reel/:id {action: "retry" | "rewrite"}
//   retry   -> resume from the failed stage (cached stages are skipped)
//   rewrite -> keep the analysis, ask Opus to write both documents again
export async function POST(req: Request, { params }: Ctx) {
  const { id } = await params;
  if (!validId(id)) return NextResponse.json({ error: "bad id" }, { status: 400 });
  const body = (await req.json().catch(() => ({}))) as { action?: string };
  if (await isRunning(id)) return NextResponse.json({ error: "This job is already running." }, { status: 409 });
  if (body.action === "retry") await startRun(id);
  else if (body.action === "rewrite") await startRun(id, ["mastermind"]);
  else return NextResponse.json({ error: "unknown action" }, { status: 400 });
  return NextResponse.json({ ok: true });
}
