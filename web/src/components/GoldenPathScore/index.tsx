"use client"

import { useEffect, useState } from "react"
import { fetchRun, type Deviation, type Run } from "@/lib/api"

export function GoldenPathScore({ runId }: { runId: string }) {
  const [run, setRun] = useState<Run | null>(null)
  const [deviations, setDeviations] = useState<Deviation[]>([])

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    async function poll() {
      try {
        const data = await fetchRun(runId)
        if (cancelled) return
        setRun(data.run)
      } catch {
        // backend not up yet
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

  const score = run?.golden_path_score

  return (
    <section data-testid="golden-path-score" style={{ border: "1px solid #ccc", padding: "1rem" }}>
      <h2>Golden Path Score</h2>
      <p data-testid="score-value">
        {score === null || score === undefined ? "—" : `${Math.round(score)}/100`}
      </p>
      <ul data-testid="deviation-list">
        {deviations.map((d, i) => (
          <li key={i} data-testid={`deviation-${i}`}>
            [{d.severity}] {d.kind}: {d.tool} — {d.detail}
          </li>
        ))}
      </ul>
      {deviations.length === 0 && <p>No deviations from golden path.</p>}
    </section>
  )
}