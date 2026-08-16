"use client"

import { useEffect, useState } from "react"
import { fetchRun, type Run, type Step } from "@/lib/api"

const STATUS_COLOR: Record<string, string> = {
  COMPLETED: "#1a7f37",
  FAILED: "#cf222e",
  RUNNING: "#9a6700",
  STOPPED_MAX_STEPS: "#8250df",
}

export function TrajectoryViewer({ runId }: { runId: string }) {
  const [run, setRun] = useState<Run | null>(null)
  const [steps, setSteps] = useState<Step[]>([])
  const [error, setError] = useState("")

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    async function poll() {
      try {
        const data = await fetchRun(runId)
        if (cancelled) return
        setRun(data.run)
        setSteps(data.steps)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "poll failed")
      }
    }
    poll()
    const timer = setInterval(poll, 2000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [runId])

  if (!runId) return null

  return (
    <section data-testid="trajectory-viewer" style={{ border: "1px solid #ccc", padding: "1rem" }}>
      <h2>Trajectory</h2>
      {run && (
        <p style={{ color: STATUS_COLOR[run.status] || "#333" }}>
          status: <strong data-testid="run-status">{run.status}</strong>
        </p>
      )}
      {error && <p style={{ color: "red" }}>{error}</p>}
      <ol data-testid="step-list">
        {steps.map((s) => (
          <li key={s.step_number} data-testid={`step-${s.step_number}`}>
            <span style={{ color: s.success ? "#1a7f37" : "#cf222e" }}>
              {s.success ? "✅" : "❌"}
            </span>{" "}
            Step {s.step_number} {s.tool_called}({JSON.stringify(s.tool_input)}) — {s.duration_ms}ms
          </li>
        ))}
      </ol>
      {steps.length === 0 && <p>No steps yet…</p>}
    </section>
  )
}