import { motion, useReducedMotion } from "motion/react";
import type { Report, Row } from "../../shared/data/types";
import { DEFECT_WORDS, DURATION, EASE, VERDICT_WORDS, bound, verdictColour, type Verdict } from "../../shared/tokens";
import { marks, type Kind } from "./marks";
import styles from "./anatomy.module.css";

const ORDER: Kind[] = ["condition", "subject", "value", "defect"];

/** Picks the requirement that shows the most at once: a condition, a trace link and a decided verdict. */
export function pick(rows: Row[]): Row | null {
  const decided = rows.filter((r) => r.link && !["review", "clarify"].includes(r.compliance));
  const score = (r: Row) => (/^(When|If|While)\b/.test(r.text) ? 3 : 0) + (/ at a .*\d/.test(r.text) ? 2 : 0) - r.text.length / 400;
  return [...decided].sort((a, b) => score(b) - score(a))[0] ?? rows[0] ?? null;
}

export function Anatomy({ report }: { report: Report }) {
  const still = useReducedMotion();
  const row = pick(report.example.requirements);
  if (!row) return null;
  const segs = marks(row.text);
  const delay = (k: Kind) => DURATION.reveal + ORDER.indexOf(k) * DURATION.step;
  const verdict = row.compliance as Verdict;
  const condition = segs.find((s) => s.kind === "condition")?.text.trim().replace(/,$/, "");
  return (
    <section className={styles.hero} aria-label="One requirement, read">
      <p className={styles.source}>
        {report.example.customer}, Lastenheft {report.example.spec}, requirement {row.uid}
      </p>
      <motion.p
        className={styles.sentence}
        initial={still ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: DURATION.reveal, ease: EASE }}
      >
        {segs.map((s, i) =>
          s.kind === "plain" ? (
            <span key={i}>{s.text}</span>
          ) : (
            <motion.span
              key={i}
              className={styles.mark}
              data-kind={s.kind}
              initial={still ? false : { backgroundSize: "0% var(--underline)" }}
              animate={{ backgroundSize: "100% var(--underline)" }}
              transition={{ duration: DURATION.mark, ease: EASE, delay: still ? 0 : delay(s.kind) }}
            >
              {s.text}
            </motion.span>
          ),
        )}
      </motion.p>
      <motion.dl
        className={styles.reading}
        initial={still ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: DURATION.reveal, ease: EASE, delay: still ? 0 : delay("value") + DURATION.mark }}
      >
        <div data-kind="subject">
          <dt>Subsystem</dt>
          <dd>
            {row.sub ?? "unknown"} <small>{row.sub_by === "model" ? "named by the model, checked by code" : "named in the text"}</small>
          </dd>
        </div>
        <div data-kind="value">
          <dt>Requirement</dt>
          <dd className="tabular">{bound(row.kind, row.lo, row.hi, row.unit)}</dd>
        </div>
        <div data-kind="condition">
          <dt>Condition</dt>
          <dd>
            {condition ?? "none"}
            {condition && <small>kept with the requirement and matched when tracing</small>}
          </dd>
        </div>
        <div data-kind="defect">
          <dt>Writing, INCOSE GtWR</dt>
          <dd>
            {row.defects.length ? row.defects.map((d) => DEFECT_WORDS[d] ?? d).join(", ") : "no findings"}
            {row.defects.length > 0 && <small>sent back to the customer as a question</small>}
          </dd>
        </div>
        <div>
          <dt>Supplier requirement</dt>
          <dd className="tabular">{row.link}</dd>
        </div>
        <div>
          <dt>Verdict, computed</dt>
          <dd>
            <span className={styles.verdict} style={{ color: verdictColour(verdict) }}>{VERDICT_WORDS[verdict]}</span>
          </dd>
        </div>
      </motion.dl>
    </section>
  );
}
