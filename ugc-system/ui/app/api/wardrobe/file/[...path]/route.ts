import { promises as fs } from "node:fs";
import path from "node:path";
import { UGC_ROOT } from "../../../../../lib/reel-server";

export const runtime = "nodejs";
const ROOTS: Record<string, string> = { wardrobe: "wardrobe", demo: path.join("assets", "seed") };
const TYPES: Record<string, string> = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };

// GET /api/wardrobe/file/<wardrobe|demo>/<rel path>
export async function GET(_req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const [root, ...rest] = (await params).path;
  if (!ROOTS[root] || !rest.length) return new Response("not found", { status: 404 });
  const base = path.join(/* turbopackIgnore: true */ UGC_ROOT, ROOTS[root]);
  const file = path.resolve(/* turbopackIgnore: true */ base, ...rest);
  const type = TYPES[path.extname(file).toLowerCase()];
  if (!file.startsWith(base + path.sep) || !type) return new Response("not found", { status: 404 });
  const buf = await fs.readFile(file).catch(() => null);
  if (!buf) return new Response("not found", { status: 404 });
  return new Response(buf, { headers: { "Content-Type": type, "Cache-Control": "no-cache" } });
}
