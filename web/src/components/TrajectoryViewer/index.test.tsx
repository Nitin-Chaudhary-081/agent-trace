import { render, screen, waitFor } from "@testing-library/react"
import { TrajectoryViewer } from "@/components/TrajectoryViewer"

jest.mock("@/lib/api", () => ({
  fetchRun: jest.fn(async () => ({
    run: { run_id: "r1", status: "COMPLETED", golden_path_score: 100 },
    steps: [
      { step_number: 1, tool_called: "web_search", tool_input: {}, success: true, duration_ms: 5 },
      { step_number: 2, tool_called: "gmail_send", tool_input: {}, success: false, duration_ms: 9 },
    ],
  })),
}))

describe("TrajectoryViewer", () => {
  it("renders live steps with success/error status", async () => {
    render(<TrajectoryViewer runId="r1" />)

    await waitFor(() => expect(screen.getByTestId("run-status")).toHaveTextContent("COMPLETED"))
    expect(screen.getByTestId("step-1")).toHaveTextContent("web_search")
    expect(screen.getByTestId("step-1")).toHaveTextContent("5ms")
    expect(screen.getByTestId("step-2")).toHaveTextContent("gmail_send")
  })

  it("renders nothing without a run id", () => {
    const { container } = render(<TrajectoryViewer runId="" />)
    expect(container).toBeEmptyDOMElement()
  })
})