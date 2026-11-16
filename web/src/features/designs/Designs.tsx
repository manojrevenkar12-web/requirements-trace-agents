import type { Metrics, Report } from "../../shared/data/types";
import { Meter } from "../../shared/ui/Meter";
import { Section } from "../../shared/ui/Section";
import { DESIGNS, DESIGN_WORDS, designColour, pct, type Design } from "../../shared/tokens";
import styles from "./designs.module.css";

interface Measure {
  title: string;
  note: string;
  share: (m: Metrics, all: Metrics[]) => number;
  show: (m: Metrics) => string;
}

const MEASURES: Measure[] = [
  { title: "Values and units read right", note: "after unit conversion and decimal commas",
    share: (m) => m.values.accuracy ?? 0, show: (m) => pct(m.values.accuracy) },
  { title: "Trace links that are right", note: "of the links each design proposed",
    share: (m) => m.trace.precision ?? 0, show: (m) => pct(m.trace.precision) },
  { title: "False “compliant” verdicts", note: "a promise to the customer the product cannot keep",
    share: (m, all) => m.compliance.false_compliant / Math.max(1, ...all.map((x) => x.compliance.false_compliant)),
    show: (m) => String(m.compliance.false_compliant) },
  { title: "Injected instructions held for a person", note: "sentences in the spec addressed to an AI",
    share: (m) => m.injections.held_share ?? 0, show: (m) => `${m.injections.held} of ${m.injections.n}` },
  { title: "What revision B touches, flagged right", note: "precision of the supplier items and tests flagged",
    share: (m) => m.impact.precision ?? 0, show: (m) => pct(m.impact.precision) },
  { title: "Engineer hours left", note: "of the hours a full manual read takes, rework for wrong outputs included",
    share: (m) => Math.min(1.5, m.effort.left_hours / m.effort.manual_hours) / 1.5,
    show: (m) => `${m.effort.left_hours} of ${m.effort.manual_hours} h` },
];

export function Designs({ report }: { report: Report }) {
  const present = DESIGNS.filter((d) => report.designs[d]);
  if (present.length === 0) return null;
  const all = present.map((d) => report.designs[d]);
  return (
    <Section
      title="Four ways to read the same specs"
      lede={`Each design gets the same ${report.specs * 2} files (${report.formats.pdf} PDFs, ${report.formats.docx} Word) and the same supplier baseline of ${report.baseline.requirements} requirements and ${report.baseline.tests} tests. The model-alone numbers follow from the stand-in model's error rates in the world file.`}
    >
      <ul className={styles.legend} aria-label="Designs">
        {present.map((d) => (
          <li key={d}><span className={styles.swatch} style={{ background: designColour(d) }} />{DESIGN_WORDS[d]}</li>
        ))}
      </ul>
      <div className={styles.grid}>
        {MEASURES.map((ms) => (
          <figure key={ms.title} className={styles.measure}>
            <figcaption><strong>{ms.title}</strong><span>{ms.note}</span></figcaption>
            {present.map((d: Design) => (
              <div key={d} className={styles.bar}>
                <span className={styles.name}>{DESIGN_WORDS[d]}</span>
                <Meter value={ms.share(report.designs[d], all)} colour={designColour(d)} label={`${ms.title}, ${DESIGN_WORDS[d]}`} />
                <span className={`${styles.value} tabular`}>{ms.show(report.designs[d])}</span>
              </div>
            ))}
          </figure>
        ))}
      </div>
    </Section>
  );
}
