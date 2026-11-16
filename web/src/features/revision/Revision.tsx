import type { Report } from "../../shared/data/types";
import { Section } from "../../shared/ui/Section";
import { VERDICT_WORDS, type Verdict } from "../../shared/tokens";
import styles from "./revision.module.css";

export function Revision({ report }: { report: Report }) {
  const imp = report.example.impact;
  const text = new Map(report.example.requirements.map((r) => [r.uid, r.text]));
  const truth = new Set(imp.truth);
  const flips = new Map(imp.flips.map(([u, a, b]) => [u, [a, b]]));
  const columns: { title: string; note: string; items: string[] }[] = [
    { title: "Changed", note: "the value moved after unit conversion", items: imp.changed.map(([a]) => a) },
    { title: "Reworded", note: "same value, new words or units: touches nothing", items: imp.reworded.map(([a]) => a) },
    { title: "Deleted", note: "the supplier items behind it are revisited", items: imp.deleted },
    { title: "Added", note: "needs a new trace", items: imp.added },
  ];
  const nothing = columns.every((c) => c.items.length === 0);
  return (
    <Section
      title="What revision B touches"
      lede={`Revision B of ${report.example.spec} against revision A. Requirements are paired by the customer's IDs when the spec has them, by trace link and label when it does not.`}
    >
      {nothing ? (
        <p className={styles.empty}>Revision B changes nothing in this spec.</p>
      ) : (
        <div className={styles.columns}>
          {columns.map((c) => (
            <div key={c.title}>
              <h3>{c.title} <span className="tabular">{c.items.length}</span></h3>
              <p className={styles.note}>{c.note}</p>
              <ul>
                {c.items.map((u) => (
                  <li key={u}>
                    <span className="tabular">{u}</span> {text.get(u) ?? ""}
                    {flips.has(u) && (
                      <em> Verdict {VERDICT_WORDS[flips.get(u)![0] as Verdict]} becomes {VERDICT_WORDS[flips.get(u)![1] as Verdict]}.</em>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <h3 className={styles.touchedTitle}>Supplier requirements and tests to revisit</h3>
      {imp.touched.length === 0 ? (
        <p className={styles.empty}>None: no change reaches the supplier's baseline.</p>
      ) : (
        <ul className={styles.touched}>
          {imp.touched.map((t) => (
            <li key={t} data-right={truth.has(t)} className="tabular">
              {t} <span>{truth.has(t) ? "engineers agree" : "not in the engineers' list"}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
