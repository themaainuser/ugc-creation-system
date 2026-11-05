import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import { UGC_ROOT, safeName } from "../../../lib/reel-server";
import { runPy } from "../../../lib/py";

export const runtime = "nodejs";

// POST multipart: files[] + folder (a hint like "gucci" or "handmade/gifts") -> saved into wardrobe/, then rescanned
export async function POST(req: Request) {
  const form = await req.formData().catch(() => null);
  if (!form) return NextResponse.json({ error: "expected multipart form data" }, { status: 400 });
  const folder = String(form.get("folder") ?? "")
    .toLowerCase().split("/").map((p) => p.replace(/[^\w-]+/g, "_")).filter(Boolean).slice(0, 3).join("/");
  const dir = path.join(/* turbopackIgnore: true */ UGC_ROOT, "wardrobe", folder);
  await fs.mkdir(dir, { recursive: true });
  let saved = 0;
  for (const f of form.getAll("files")) {
    if (!(f instanceof File) || !/^image\/(png|jpe?g|webp)$/.test(f.type)) continue;
    await fs.writeFile(path.join(/* turbopackIgnore: true */ dir, safeName(f.name)), Buffer.from(await f.arrayBuffer()));
    saved++;
  }
  const r = await runPy("ugc_system.styling", ["scan"]);
  return NextResponse.json({ saved, ...r.data }, { status: r.ok ? 200 : 500 });
}
