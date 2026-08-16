"use client"

import { useEffect, useState } from "react"
import { fetchSecurity, type AttackResult } from "@/lib/api"

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#cf222e",
  high: "#bc4c00",
  medium: "#9a6700",
  low: "#1a7f37",
}

export function SecurityPanel() {
  const [results, setResults] = useState<AttackResult[]>([])

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const data = await fetchSecurity()
        if (!cancelled) setResults(data.results)
      } catch {
        // backend not up yet
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
    <section data-testid="security-panel" style={{ border: "1px solid #ccc", padding: "1rem" }}>
      <h2>Security</h2>
      {results.length === 0 && <p>No attack results yet.</p>}
      <ul data-testid="attack-list">
        {results.map((r) => (
          <li key={r.attack_type} data-testid={`attack-${r.attack_type}`}>
            <span style={{ color: SEVERITY_COLOR[r.severity] || "#333" }}>
              <strong>{r.attack_type}</strong> ({r.severity})
            </span>{" "}
            detected: {r.detected ? "✅" : "—"} remediated: {r.remediated ? "✅" : "—"}
          </li>
        ))}
      </ul>
    </section>
  )
}