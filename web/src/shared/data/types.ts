export interface Metrics {
  extraction: { truth: number; found: number; precision: number | null; recall: number | null; phantom: number };
  values: { accuracy: number | null; n: number; correct: number };
  trace: { precision: number | null; coverage: number | null; correct: number; wrong: number; invented: number; abstained: number };
  compliance: { false_compliant: number; accuracy_decided: number | null; noncompliant_recall: number | null; review: number };
  conflicts: { recall: number | null; precision: number | null; n: number; correct: number };
  injections: { n: number; held: number; held_share: number | null; obeyed_specs: number };
  impact: { precision: number | null; recall: number | null; false_alarms: number; truth: number };
  effort: { manual_hours: number; left_hours: number; review_items: number; questions: number; wrong_outputs: number };
  model: { calls: number; usd_per_spec: number };
}

export interface Row {
  uid: string;
  text: string;
  sub: string | null;
  sub_by: string;
  kind: string;
  lo: number | null;
  hi: number | null;
  unit: string | null;
  defects: string[];
  link: string | null;
  compliance: string;
  review: string[];
  questions: string[];
  table: boolean;
}

export interface GateLine {
  name: string;
  metric: string;
  op: string;
  value: number | null;
  target: number | null;
  against: string;
  pass: boolean;
}

export interface Report {
  world: string;
  system: string;
  specs: number;
  formats: { pdf: number; docx: number };
  baseline: { requirements: number; tests: number; subsystems: string[] };
  designs: Record<string, Metrics>;
  gate: GateLine[];
  example: {
    spec: string;
    customer: string;
    format: string;
    locale: string;
    requirements: Row[];
    quarantined: [string, string][];
    conflicts: [string, string][];
    impact: {
      changed: [string, string][];
      reworded: [string, string][];
      deleted: string[];
      added: string[];
      touched: string[];
      flips: [string, string, string][];
      truth: string[];
    };
  };
  reqif_roundtrip: { requirements: number; identical: number };
}
