"use client";
import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function textOf(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (typeof node === "object" && "props" in node) return textOf((node as { props: { children?: ReactNode } }).props.children);
  return "";
}

export function CopyButton({ text, label = "Copy", className = "rl-btn" }: { text: string; label?: string; className?: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      type="button"
      className={`${className}${ok ? " ok" : ""}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setOk(true);
          setTimeout(() => setOk(false), 1400);
        } catch {
          /* clipboard blocked */
        }
      }}
    >
      {ok ? "Copied" : label}
    </button>
  );
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const child = Array.isArray(children) ? children[0] : children;
  const cls = (child as { props?: { className?: string } })?.props?.className ?? "";
  const lang = cls.replace("language-", "");
  const text = textOf(children).replace(/\n$/, "");
  return (
    <div className="rl-code">
      {lang && lang !== "text" ? <span className="tag">{lang}</span> : <span className="tag">prompt</span>}
      <CopyButton text={text} className="copy" />
      <pre>{children}</pre>
    </div>
  );
}

export default function Doc({ markdown }: { markdown: string }) {
  return (
    <div className="rl-doc">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre: CodeBlock,
          table: ({ children }) => (
            <div className="rl-table-wrap">
              <table>{children}</table>
            </div>
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
