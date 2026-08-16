import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { TaskLauncher } from "@/components/TaskLauncher"

jest.mock("@/lib/api", () => ({
  submitTask: jest.fn(async () => ({ run_id: "abc-123" })),
  TASK_TYPES: ["research_and_email", "inbox_summarize", "data_lookup_report"],
}))

describe("TaskLauncher", () => {
  it("submits a task and shows run_id", async () => {
    const onRun = jest.fn()
    render(<TaskLauncher onRun={onRun} />)

    fireEvent.change(screen.getByTestId("task-input"), {
      target: { value: "research python" },
    })
    fireEvent.click(screen.getByTestId("run-button"))

    await waitFor(() => expect(screen.getByTestId("run-id")).toHaveTextContent("abc-123"))
    expect(onRun).toHaveBeenCalledWith("abc-123")
  })

  it("shows an error when submit fails", async () => {
    const { submitTask } = require("@/lib/api")
    submitTask.mockRejectedValueOnce(new Error("submit failed: 400"))
    render(<TaskLauncher />)

    fireEvent.change(screen.getByTestId("task-input"), { target: { value: "x" } })
    fireEvent.click(screen.getByTestId("run-button"))

    await waitFor(() =>
      expect(screen.getByTestId("launch-error")).toHaveTextContent("submit failed"),
    )
  })
})