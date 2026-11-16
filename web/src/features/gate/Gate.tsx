import type { GateLine, Report } from "../../shared/data/types";
import { Section } from "../../shared/ui/Section";
import { pct } from "../../shared/tokens";
import styles from "./gate.module.css";

const COUNTS = new Set(["compliance.false_compliant"]);
const show = (v: number | null, metric: string) =>
  v === null ? "n/a" : COUNTS.has(metric) ? String(v) : pct(v);

export function Gate({ dev, held }: { dev: Report; held: Report | null }) {
  const byName = new Map<string, GateLine>((held?.gate ?? []).map((g) => [g.name, g]));
  const passedHeld = held ? held.gate.filter((g) => g.pass).length : 0;
  return (
    <Section
      title="The gate, on dev and on the held-out product"
      lede={held
        ? `Written before the first held-out result. The held-out world, ${held.system}, ran once: ${passedHeld} of ${held.gate.length} lines passed. The failures are written up in docs/heldout.md and were fixed on dev; the held-out world is not run again.`
        : "Written before the first held-out result. The held-out world has not been run yet."}
    >
      <table className={styles.table}>
        <thead>
          <tr><th scope="col">Line</th><th scope="col">Target</th><th scope="col">Dev</th><th scope="col">Held-out</th></tr>
        </thead>
        <tbody>
          {dev.gate.map((g) => {
            const h = byName.get(g.name);
            return (
              <tr key={g.name}>
                <th scope="row">{g.name}</th>
                <td className="tabular">{g.op} {g.against === "fixed" ? show(g.target, g.metric) : g.against.replace("_", " ")}</td>
                <td className="tabular" data-pass={g.pass}>{show(g.value, g.metric)} {g.pass ? "pass" : "fail"}</td>
                <td className="tabular" data-pass={h ? h.pass : undefined}>{h ? `${show(h.value, h.metric)} ${h.pass ? "pass" : "fail"}` : "not run"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Section>
  );
}
