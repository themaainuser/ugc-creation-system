import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import {
  JOBS_DIR, freshStatus, health, jobPath, newJobId, readJson, safeName, startRun, validId,
} from "../../../lib/reel-server";

export const runtime = "nodejs";

type Spec = Record<string, unknown> & { assets?: { file: string; kind: string; label: string }[] };

// GET /api/reel            -> recent jobs
// GET /api/reel?health=1   -> tool / key readiness
export async function GET(req: Request) {
  if (new URL(req.url).searchParams.get("health")) return NextResponse.json(await health());
  let ids: string[] = [];
  try {
    ids = (await fs.readdir(/* turbopackIgnore: true */ JOBS_DIR)).filter(validId).sort().reverse().slice(0, 40);
  } catch {
    /* no jobs yet */
  }
  const jobs = await Promise.all(
    ids.map(async (id) => {
      const spec = (await readJson<Spec>(jobPath(id, "job.json"))) ?? {};
      const st = await readJson<{ state: string }>(jobPath(id, "status.json"));
      const bp = await readJson<{ title?: string }>(jobPath(id, "out", "blueprint.json"));
      return {
        id,
        state: st?.state ?? "unknown",
        persona: spec.persona ?? null,
        url: spec.url ?? null,
        mode: spec.mode ?? "remix",
        title: bp?.title ?? null,
        idea: typeof spec.idea === "string" ? spec.idea.slice(0, 120) : "",
        created_at: spec.created_at ?? null,
      };
    }),
  );
  return NextResponse.json({ jobs: jobs.filter((j) => j.state !== "unknown") });
}

// POST /api/reel (multipart) -> create a job and start the pipeline
export async function POST(req: Request) {
  let form: FormData;
  try {
    form = await req.formData();
  } catch {
    return NextResponse.json({ error: "expected multipart form data" }, { status: 400 });
  }
  const str = (k: string) => (typeof form.get(k) === "string" ? (form.get(k) as string).trim() : "");
  const url = str("url");
  const video = form.get("video");
  const sourceJob = str("source_job");
  const hasVideo = video instanceof File && video.size > 0;
  if (!url && !hasVideo && !sourceJob) {
    return NextResponse.json({ error: "Paste a reel URL or upload the video file." }, { status: 400 });
  }
  if (url && !/^https?:\/\//i.test(url)) {
    return NextResponse.json({ error: "That URL doesn't look right — it should start with https://" }, { status: 400 });
  }
  if (sourceJob && !validId(sourceJob)) {
    return NextResponse.json({ error: "bad source job" }, { status: 400 });
  }

  const id = newJobId();
  const dir = path.join(/* turbopackIgnore: true */ JOBS_DIR, id);
  for (const sub of ["media", "flipbook", "assets", "out"]) await fs.mkdir(path.join(/* turbopackIgnore: true */ dir, sub), { recursive: true });

  if (hasVideo) {
    const f = video as File;
    const ext = path.extname(f.name).toLowerCase() || ".mp4";
    await fs.writeFile(path.join(/* turbopackIgnore: true */ dir, "media", `source${ext}`), Buffer.from(await f.arrayBuffer()));
  }

  const files = form.getAll("assets").filter((x): x is File => x instanceof File && x.size > 0);
  const kinds = form.getAll("asset_kinds").map(String);
  const labels = form.getAll("asset_labels").map(String);
  const assets: Spec["assets"] = [];
  const used = new Set<string>();
  for (const [i, f] of files.entries()) {
    let name = safeName(f.name);
    while (used.has(name)) name = `${i}_${name}`;
    used.add(name);
    await fs.writeFile(path.join(/* turbopackIgnore: true */ dir, "assets", name), Buffer.from(await f.arrayBuffer()));
    assets.push({ file: `assets/${name}`, kind: kinds[i] || "other", label: labels[i] || "" });
  }

  let srcSpec: Spec | null = null;
  if (sourceJob) srcSpec = await readJson<Spec>(jobPath(sourceJob, "job.json"));

  const spec = {
    id,
    url: url || (srcSpec?.url as string) || null,
    persona: str("persona") || null,
    mode: str("mode") === "recreate" ? "recreate" : "remix",
    context: str("context"),
    idea: str("idea"),
    targets: { image: str("image_model"), video: str("video_model") },
    assets,
    source_job: sourceJob || null,
    created_at: new Date().toISOString(),
  };
  await fs.writeFile(path.join(/* turbopackIgnore: true */ dir, "job.json"), JSON.stringify(spec, null, 2));
  await fs.writeFile(path.join(/* turbopackIgnore: true */ dir, "status.json"), JSON.stringify(freshStatus(), null, 2));
  await startRun(id);
  return NextResponse.json({ id });
}
