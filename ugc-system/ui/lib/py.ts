// Run a ugc_system CLI module and parse its JSON stdout.
import { execFile } from "node:child_process";
import { PYTHON, UGC_ROOT } from "./reel-server";

export function runPy(module: string, args: string[], stdin?: unknown, timeoutMs = 600_000): Promise<{ ok: boolean; data: any }> {
  return new Promise((resolve) => {
    const child = execFile(
      /* turbopackIgnore: true */ PYTHON,
      ["-m", module, ...args],
      { cwd: UGC_ROOT, timeout: timeoutMs, maxBuffer: 64 * 1024 * 1024, windowsHide: true },
      (err, stdout, stderr) => {
        const last = stdout.trim().split("\n").pop() ?? "";
        try {
          const data = JSON.parse(last);
          resolve({ ok: !data?.error, data });
        } catch {
          resolve({ ok: false, data: { error: (stderr || err?.message || "no output").slice(-800) } });
        }
      },
    );
    if (stdin !== undefined) child.stdin?.end(JSON.stringify(stdin));
    else child.stdin?.end();
  });
}
