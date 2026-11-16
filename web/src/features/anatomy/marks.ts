// Splits a requirement sentence into the parts a bid engineer underlines: who, how much, under which condition.
export type Kind = "subject" | "value" | "condition" | "defect" | "plain";
export interface Segment { text: string; kind: Kind }

const VALUE = /((?:at least|not less than|no less than|no more than|not more than|at most|minimum(?: of)?|maximum(?: of)?|min\.|max\.|>=|<=|≥|≤|greater than or equal to|less than or equal to|must not exceed|limited to|between|from)\s[^,]*?-?\d[\d.,]*\s?(?:[A-Za-z°%/()]+)?(?:\s(?:and|to)\s-?\d[\d.,]*\s?[A-Za-z°%/()]*)?)(?=[\s,.]|$)/i;
const LEAD = /^((?:When|While|If|Where|During)\b[^,]+,\s*)/;
const TRAIL = /(\s(?:at a|at an|in|under)\s[^,]*?-?\d[\d.,]*\s?°?[A-Za-z%]*)(?=,|$)/;
const SUBJECT = /^((?:the|a|an)\s[\w -]+?)(?=\s(?:shall|must)\b)/i;

export function marks(text: string): Segment[] {
  const out: Segment[] = [];
  let rest = text;
  const lead = LEAD.exec(rest);
  if (lead) {
    out.push({ text: lead[1], kind: "condition" });
    rest = rest.slice(lead[1].length);
  }
  const tail: Segment[] = [];
  const trail = TRAIL.exec(rest);
  if (trail && VALUE.exec(rest.slice(0, trail.index))) {
    tail.push({ text: trail[1], kind: "condition" }, { text: rest.slice(trail.index + trail[1].length), kind: "plain" });
    rest = rest.slice(0, trail.index);
  }
  const subj = SUBJECT.exec(rest);
  if (subj) {
    out.push({ text: subj[1], kind: "subject" });
    rest = rest.slice(subj[1].length);
  }
  const v = VALUE.exec(rest);
  if (v) {
    out.push({ text: rest.slice(0, v.index), kind: "plain" });
    out.push({ text: v[1], kind: "value" });
    rest = rest.slice(v.index + v[1].length);
  }
  out.push({ text: rest, kind: "plain" }, ...tail);
  return out.flatMap(splitDefects).filter((s) => s.text.length > 0);
}

const DEFECT = /(if technically feasible|where possible|as far as practicable|under all operating conditions|including but not limited to [^,.]+|and\/or|sufficiently|adequately|as possible|quickly|minimal)/i;

function splitDefects(s: Segment): Segment[] {
  if (s.kind !== "plain") return [s];
  const m = DEFECT.exec(s.text);
  if (!m) return [s];
  return [{ text: s.text.slice(0, m.index), kind: "plain" }, { text: m[1], kind: "defect" },
    ...splitDefects({ text: s.text.slice(m.index + m[1].length), kind: "plain" })];
}
