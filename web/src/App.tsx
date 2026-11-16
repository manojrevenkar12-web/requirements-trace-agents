import { Anatomy } from "./features/anatomy/Anatomy";
import { Designs } from "./features/designs/Designs";
import { Gate } from "./features/gate/Gate";
import { Requirements } from "./features/requirements/Requirements";
import { Revision } from "./features/revision/Revision";
import { useReport } from "./shared/data/useReport";
import { EmptyState, ErrorState, Skeleton } from "./shared/ui/States";
import styles from "./app.module.css";

export function App() {
  const { state, retry } = useReport("./dev.json");
  const held = useReport("./heldout.json");
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1>Requirements trace agents</h1>
        <p>Customer specifications in, traced and judged requirements out, measured against the engineers' answers.</p>
      </header>
      {state.status === "loading" && <Skeleton rows={6} />}
      {state.status === "error" && <ErrorState message={state.message} onRetry={retry} />}
      {state.status === "empty" && <EmptyState />}
      {state.status === "ready" && (
        <>
          <Anatomy report={state.report} />
          <Designs report={state.report} />
          <Requirements report={state.report} />
          <Revision report={state.report} />
          <Gate dev={state.report} held={held.state.status === "ready" ? held.state.report : null} />
          <footer className={styles.footer}>
            The specs, the baseline and the engineers' answers are simulated, and the model is a stand-in with fixed
            error rates. Engineer hours use the assumptions in config/pipeline.yaml.
          </footer>
        </>
      )}
    </main>
  );
}
