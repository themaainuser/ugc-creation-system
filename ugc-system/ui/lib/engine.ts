/* Typed, abortable client for POST /api/engine {cmd, payload}.
   Errors carry the command so stations can surface them in context. */

export type EngineErrorKind = "offline" | "timeout" | "invalid" | "engine";

export class EngineError extends Error {
  cmd: string;
  kind: EngineErrorKind;
  constructor(cmd: string, kind: EngineErrorKind, message: string) {
    super(message);
    this.name = "EngineError";
    this.cmd = cmd;
    this.kind = kind;
  }
}

export async function engine<T>(
  cmd: string,
  payload: unknown = {},
  opts: { signal?: AbortSignal } = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch("/api/engine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmd, payload }),
      signal: opts.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new EngineError(cmd, "offline", "engine unreachable — is the Next server running?");
  }

  let data: unknown;
  try {
    data = await res.json();
  } catch {
    throw new EngineError(cmd, "invalid", `HTTP ${res.status} — non-JSON response`);
  }
  const err = (data as { error?: string }).error;
  if (err) {
    const kind: EngineErrorKind =
      res.status >= 500 ? "engine" : res.status === 400 ? "invalid" : "engine";
    throw new EngineError(cmd, kind, err);
  }
  if (!res.ok) throw new EngineError(cmd, "engine", `HTTP ${res.status}`);
  return data as T;
}

export function isAbort(e: unknown): boolean {
  // Browsers differ: DOMException vs TypeError, both named "AbortError".
  return typeof e === "object" && e !== null && (e as { name?: unknown }).name === "AbortError";
}
