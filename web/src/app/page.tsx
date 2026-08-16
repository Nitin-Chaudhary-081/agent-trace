"use client"

import { useState } from "react"
import { TaskLauncher } from "@/components/TaskLauncher"
import { MemoryViewer } from "@/components/MemoryViewer"
import { SecurityPanel } from "@/components/SecurityPanel"
import { TrajectoryViewer } from "@/components/TrajectoryViewer"
import { GoldenPathScore } from "@/components/GoldenPathScore"

export default function Home() {
  const [runId, setRunId] = useState("")

  return (
    <main style={{ padding: "1rem", fontFamily: "system-ui, sans-serif", maxWidth: 1100, margin: "0 auto" }}>
      <h1>AgentTrace Observer</h1>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <TaskLauncher onRun={setRunId} />
        <MemoryViewer />
        <TrajectoryViewer runId={runId} />
        <div style={{ display: "grid", gap: "1rem" }}>
          <GoldenPathScore runId={runId} />
          <SecurityPanel />
        </div>
      </div>
    </main>
  )
}