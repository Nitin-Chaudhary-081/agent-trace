import { render, screen, waitFor } from "@testing-library/react"
import { MemoryViewer } from "@/components/MemoryViewer"
import { SecurityPanel } from "@/components/SecurityPanel"
import { GoldenPathScore } from "@/components/GoldenPathScore"

jest.mock("@/lib/api", () => ({
  fetchMemory: jest.fn(async () => ({
    sections: { GOAL: "research", STATUS: "RUNNING", PROGRESS: "started", FAILURES: "" },
  })),
  fetchSecurity: jest.fn(async () => ({
    results: [
      { attack_type: "prompt_injection", severity: "critical", detected: true, remediated: true, evidence: "x" },
    ],
  })),
  fetchRun: jest.fn(async () => ({
    run: { run_id: "r1", status: "COMPLETED", golden_path_score: 100 },
    steps: [],
    deviations: [
      { kind: "missing_step", tool: "gmail_send", detail: "never called", severity: "warning" },
    ],
  })),
}))

describe("MemoryViewer", () => {
  it("renders live memory sections", async () => {
    render(<MemoryViewer />)
    await waitFor(() => expect(screen.getByTestId("memory-GOAL")).toHaveTextContent("research"))
    expect(screen.getByTestId("memory-STATUS")).toHaveTextContent("RUNNING")
  })

  it("renders NEXT_ACTIONS section", async () => {
    render(<MemoryViewer />)
    await waitFor(() => expect(screen.getByTestId("memory-NEXT_ACTIONS")).toBeInTheDocument())
  })
})

describe("SecurityPanel", () => {
  it("renders attack results with severity", async () => {
    render(<SecurityPanel />)
    await waitFor(() =>
      expect(screen.getByTestId("attack-prompt_injection")).toHaveTextContent("prompt_injection"),
    )
    expect(screen.getByTestId("attack-prompt_injection")).toHaveTextContent("critical")
  })
})

describe("GoldenPathScore", () => {
  it("renders the score value", async () => {
    render(<GoldenPathScore runId="r1" />)
    await waitFor(() => expect(screen.getByTestId("score-value")).toHaveTextContent("100/100"))
  })

  it("renders deviations from the run", async () => {
    render(<GoldenPathScore runId="r1" />)
    await waitFor(() =>
      expect(screen.getByTestId("deviation-0")).toHaveTextContent("missing_step"),
    )
  })
})