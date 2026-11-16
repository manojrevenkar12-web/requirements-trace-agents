// Values the components need in TypeScript; colours and sizes live in theme.css as custom properties.
export const DURATION = { reveal: 0.6, mark: 0.5, step: 0.35, meter: 0.6, list: 0.25 } as const;
export const EASE = [0.2, 0.7, 0.2, 1] as const;

export const DESIGNS = ["keyword", "model_only", "agents_no_model", "trace_agents"] as const;
export type Design = (typeof DESIGNS)[number];
export const DESIGN_WORDS: Record<Design, string> = {
  keyword: "Keyword script",
  model_only: "Model alone",
  agents_no_model: "Agents, no model",
  trace_agents: "Trace agents",
};
export const designColour = (d: Design): string => `var(--design-${d.replaceAll("_", "-")})`;

export const VERDICTS = ["compliant", "partial", "not_compliant", "open", "clarify", "review"] as const;
export type Verdict = (typeof VERDICTS)[number];
export const VERDICT_WORDS: Record<Verdict, string> = {
  compliant: "Compliant",
  partial: "Partly compliant",
  not_compliant: "Not compliant",
  open: "New to the supplier",
  clarify: "Question to the customer",
  review: "Engineer decides",
};
export const verdictColour = (v: Verdict): string => `var(--verdict-${v.replaceAll("_", "-")})`;

export const DEFECT_WORDS: Record<string, string> = {
  passive: "R2 passive voice",
  vague: "R7 vague term",
  escape: "R8 escape clause",
  open_ended: "R9 open-ended",
  oblique: "R17 and/or",
  combinator: "R19 two in one",
  universal: "R32 universal",
  missing_unit: "R34 no unit",
};

export const pct = (x: number | null | undefined, digits = 1): string =>
  x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${(100 * x).toFixed(digits)}%`;

const UNIT_SHOW: Record<string, string> = { s: "s", "°C": "°C" };
export function bound(kind: string, lo: number | null, hi: number | null, unit: string | null): string {
  if (unit === "s" && Math.max(Math.abs(lo ?? 0), Math.abs(hi ?? 0)) < 1) {
    return bound(kind, lo === null ? null : lo * 1000, hi === null ? null : hi * 1000, "ms");
  }
  const u = unit ? ` ${UNIT_SHOW[unit] ?? unit}` : "";
  const n = (x: number) => (Math.abs(x) < 1 && x !== 0 ? x.toPrecision(3) : x.toLocaleString("en-US", { maximumFractionDigits: 3 }));
  if (kind === "min" && lo !== null) return `≥ ${n(lo)}${u}`;
  if (kind === "max" && hi !== null) return `≤ ${n(hi)}${u}`;
  if (kind === "range" && lo !== null && hi !== null) return `${n(lo)} to ${n(hi)}${u}`;
  if (kind === "eq" && lo !== null) return `= ${n(lo)}${u}`;
  return "no measurable value";
}
