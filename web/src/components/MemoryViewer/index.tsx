"use client"

import { useEffect, useState } from "react"
import { fetchMemory, type MemorySections } from "@/lib/api"

const SECTIONS = [
  "GOAL",
  "STATUS",
  "PROGRESS",
  "COMPLETED_STEPS",
  "NEXT_ACTIONS",
  "FAILURES",
  "SESSION_ID",
]

export function MemoryViewer() {
  const [sections, setSections] = useState<MemorySections>({})

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const data = await fetchMemory()
        if (!cancelled) setSections(data.sections)
      } catch {
        // backend not up yet — silent retry
      }
    }
    poll()
    const timer = setInterval(poll, 5000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [])

  return (
    <section data-testid="memory-viewer" style={{ border: "1px solid #ccc", padding: "1rem" }}>
      <h2>Memory</h2>
      {SECTIONS.map((s) => (
        <div key={s} data-testid={`memory-${s}`}>
          <strong>{s}</strong>
          <pre style={{ margin: "0.2rem 0 0.8rem", whiteSpace: "pre-wrap", background: "#f6f8fa" }}>
            {sections[s] || "—"}
          </pre>
        </div>
      ))}
    </section>
  )
}