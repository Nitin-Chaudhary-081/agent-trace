"use client"

import { useState } from "react"
import { submitTask, TASK_TYPES } from "@/lib/api"

export function TaskLauncher({ onRun }: { onRun?: (runId: string) => void }) {
  const [task, setTask] = useState("")
  const [taskType, setTaskType] = useState<string>(TASK_TYPES[0])
  const [runId, setRunId] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!task.trim() || busy) return
    setBusy(true)
    setError("")
    setRunId("")
    try {
      const res = await submitTask(task.trim(), taskType)
      setRunId(res.run_id)
      onRun?.(res.run_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : "submit failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section data-testid="task-launcher" style={{ border: "1px solid #ccc", padding: "1rem" }}>
      <h2>Launch Task</h2>
      <form onSubmit={onSubmit}>
        <input
          data-testid="task-input"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. research Python, store in supabase"
          style={{ width: "100%", marginBottom: "0.5rem" }}
        />
        <select
          data-testid="task-type-select"
          value={taskType}
          onChange={(e) => setTaskType(e.target.value)}
          style={{ marginBottom: "0.5rem" }}
        >
          {TASK_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button data-testid="run-button" type="submit" disabled={busy}>
          {busy ? "Running…" : "Run Agent"}
        </button>
      </form>
      {runId && <p data-testid="run-id">run_id: {runId}</p>}
      {error && <p data-testid="launch-error" style={{ color: "red" }}>{error}</p>}
    </section>
  )
}