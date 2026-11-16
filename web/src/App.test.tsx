import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { marks } from "./features/anatomy/marks";
import report from "../public/dev.json";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function serve(dev: unknown, held: unknown = null, status = 200) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
    String(url).includes("heldout")
      ? new Response(held ? JSON.stringify(held) : "", { status: held ? 200 : 404 })
      : new Response(JSON.stringify(dev), { status }),
  );
}

describe("App", () => {
  it("shows a skeleton while loading, then every section", async () => {
    serve(report);
    render(<App />);
    expect(screen.getByLabelText("Loading the results")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Four ways to read the same specs")).toBeTruthy());
    expect(screen.getByText("What revision B touches")).toBeTruthy();
    expect(screen.getByText(/The held-out world has not been run yet/)).toBeTruthy();
  });

  it("says plainly when the report fails, and loads again", async () => {
    serve(report, null, 500);
    render(<App />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    serve(report);
    fireEvent.click(screen.getByText("Load again"));
    await waitFor(() => expect(screen.getByText("Four ways to read the same specs")).toBeTruthy());
  });

  it("shows how to make a report when there is none", async () => {
    serve({ world: "D1" });
    render(<App />);
    await waitFor(() => expect(screen.getByText("No results yet.")).toBeTruthy());
  });

  it("filters requirements by verdict and explains an empty filter", async () => {
    const ex = { ...report.example, requirements: report.example.requirements.filter((r: { compliance: string }) => r.compliance !== "partial") };
    serve({ ...report, example: ex });
    render(<App />);
    await waitFor(() => expect(screen.getByRole("group", { name: "Show requirements by verdict" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /^Partly compliant/ }));
    expect(screen.getByText(/has this verdict/)).toBeTruthy();
  });
});

describe("marks", () => {
  it("underlines the condition, the subject and the value", () => {
    const s = marks("When the coolant inlet temperature exceeds 65 °C, the inverter shall limit a phase current of at most 406 A");
    expect(s.find((x) => x.kind === "condition")?.text).toContain("65 °C");
    expect(s.find((x) => x.kind === "subject")?.text).toBe("the inverter");
    expect(s.find((x) => x.kind === "value")?.text).toBe("at most 406 A");
    const t = marks("The electric motor shall provide a minimum peak torque of 364 Nm at a coolant temperature of -30 °C");
    expect(t.map((x) => x.kind)).toEqual(["subject", "plain", "value", "condition"]);
  });
});
