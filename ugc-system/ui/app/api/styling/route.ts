import { NextResponse } from "next/server";
import { runPy } from "../../../lib/py";

export const runtime = "nodejs";
const M = "ugc_system.styling";
const safe = (s: string | null) => (s && /^[\w-]{1,64}$/.test(s) ? s : null);

// GET ?cmd=scan | looks[&persona=] | show&look= | learning&persona=
export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  const cmd = q.get("cmd");
  let r;
  if (cmd === "scan") r = await runPy(M, ["scan"]);
  else if (cmd === "looks") r = await runPy(M, ["looks", ...(safe(q.get("persona")) ? ["--persona", q.get("persona")!] : [])]);
  else if (cmd === "show" && safe(q.get("look"))) r = await runPy(M, ["show", q.get("look")!]);
  else if (cmd === "learning" && safe(q.get("persona"))) r = await runPy(M, ["learning", "--persona", q.get("persona")!]);
  else return NextResponse.json({ error: "unknown command" }, { status: 400 });
  return NextResponse.json(r.data, { status: r.ok ? 200 : 500 });
}

// POST {cmd: "plan", persona, mood, place, ...} | {cmd: "feedback", look, verdict, alt?, rating?} | {cmd: "tag", force?}
export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as Record<string, any>;
  let r;
  if (body.cmd === "plan") {
    if (!safe(body.persona)) return NextResponse.json({ error: "Pick a persona." }, { status: 400 });
    if (!String(body.place || "").trim()) return NextResponse.json({ error: "Where is the photo taken? Fill in the place." }, { status: 400 });
    const { cmd: _c, ...inputs } = body;
    r = await runPy(M, ["plan", "--persona", body.persona, "--json"], inputs);
  } else if (body.cmd === "feedback" && safe(body.look) && ["approve", "reject", "swap", "posted"].includes(body.verdict)) {
    const args = ["feedback", body.look, body.verdict];
    if (Number.isInteger(body.alt)) args.push("--alt", String(body.alt));
    if (Number.isInteger(body.rating)) args.push("--rating", String(body.rating));
    if (typeof body.note === "string" && body.note) args.push("--note", body.note.slice(0, 500));
    r = await runPy(M, args);
  } else if (body.cmd === "tag") {
    r = await runPy(M, ["tag", ...(body.force ? ["--force"] : [])], undefined, 1_800_000);
  } else return NextResponse.json({ error: "unknown command" }, { status: 400 });
  return NextResponse.json(r.data, { status: r.ok ? 200 : 500 });
}
