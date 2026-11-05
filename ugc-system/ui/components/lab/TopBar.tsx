import type { ReactNode } from "react";

const LINKS = [
  ["lab", "/", "Reel Lab"],
  ["looks", "/looks", "Daily Look"],
  ["wardrobe", "/wardrobe", "Wardrobe"],
  ["console", "/console", "Console"],
] as const;

export default function TopBar({ active, children }: { active: (typeof LINKS)[number][0]; children?: ReactNode }) {
  return (
    <header className="rl-top">
      <a className="rl-brand" href="/"><b>UGC Studio</b><span>{LINKS.find((l) => l[0] === active)?.[2]}</span></a>
      <nav className="rl-nav" aria-label="Sections">
        {LINKS.map(([k, href, label]) => (
          <a key={k} href={href} aria-current={k === active ? "page" : undefined}>{label}</a>
        ))}
      </nav>
      <div className="rl-health">{children}</div>
    </header>
  );
}
