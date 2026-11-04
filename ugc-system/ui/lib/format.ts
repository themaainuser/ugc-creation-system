/* Small pure formatters shared across stations. */

export const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

export const pretty = (s: string) => s.replace(/_/g, " ");

export const fileName = (p: string) => p.split(/[\\/]/).pop() ?? p;

/* One-line MDEP readout — glossary wording: Mood | Day | Environment → Place. */
export const mdepLine = (m: { mood: string; day: string; environment: string; place: string }) =>
  `${m.mood} | ${m.day} | ${m.environment} → ${m.place}`;
