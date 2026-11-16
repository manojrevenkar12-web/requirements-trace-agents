import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import type { Report } from "../../shared/data/types";
import { Section } from "../../shared/ui/Section";
import { DEFECT_WORDS, DURATION, EASE, VERDICTS, VERDICT_WORDS, bound, verdictColour, type Verdict } from "../../shared/tokens";
import styles from "./requirements.module.css";

export function Requirements({ report }: { report: Report }) {
  const still = useReducedMotion();
  const ex = report.example;
  const [only, setOnly] = useState<Verdict | "all">("all");
  const counts = Object.fromEntries(VERDICTS.map((v) => [v, ex.requirements.filter((r) => r.compliance === v).length]));
  const rows = ex.requirements.filter((r) => only === "all" || r.compliance === only);
  return (
    <Section
      title={`${ex.spec}, requirement by requirement`}
      lede={`A ${ex.format.toUpperCase()} from ${ex.customer}, read as ${ex.locale === "de" ? "German number format (91,5 %)" : "English number format (91.5 %)"}. Every verdict below is computed from the customer's value and the supplier's own requirement; the model only names subsystems the text calls by another word.`}
    >
      <div className={styles.filters} role="group" aria-label="Show requirements by verdict">
        <button aria-pressed={only === "all"} onClick={() => setOnly("all")}>All {ex.requirements.length}</button>
        {VERDICTS.map((v) => (
          <button key={v} aria-pressed={only === v} onClick={() => setOnly(v)} style={{ ["--chip" as string]: verdictColour(v) }}>
            {VERDICT_WORDS[v]} {counts[v]}
          </button>
        ))}
      </div>
      {rows.length === 0 ? (
        <p className={styles.empty}>No requirement in {ex.spec} has this verdict. Pick another, or show all.</p>
      ) : (
        <ol className={styles.list}>
          <AnimatePresence initial={false}>
            {rows.map((r) => (
              <motion.li
                key={r.uid}
                layout={!still}
                initial={still ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={still ? undefined : { opacity: 0 }}
                transition={{ duration: DURATION.list, ease: EASE }}
                className={styles.row}
              >
                <span className={`${styles.uid} tabular`}>{r.uid}</span>
                <div>
                  <p className={styles.text}>{r.text}</p>
                  {r.defects.length > 0 && (
                    <ul className={styles.defects} aria-label="Writing defects">
                      {r.defects.map((d) => <li key={d}>{DEFECT_WORDS[d] ?? d}</li>)}
                    </ul>
                  )}
                  {[...r.questions, ...r.review].map((q) => <p key={q} className={styles.why}>{q}</p>)}
                </div>
                <span className="tabular">{bound(r.kind, r.lo, r.hi, r.unit)}</span>
                <span className="tabular">{r.link ?? "no link"}</span>
                <span className={styles.verdict} style={{ color: verdictColour(r.compliance as Verdict) }}>
                  {VERDICT_WORDS[r.compliance as Verdict] ?? r.compliance}
                </span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ol>
      )}
      {ex.quarantined.length > 0 && (
        <div className={styles.held}>
          <h3>Held for a person, never parsed or sent to a model</h3>
          {ex.quarantined.map(([t]) => <blockquote key={t}>{t}</blockquote>)}
        </div>
      )}
    </Section>
  );
}
