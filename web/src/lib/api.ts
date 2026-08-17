/** API client for the observer UI. */

export type Step = {
  step_number: number
  tool_called: string
  tool_input: Record<string, unknown>
  success: boolean
  duration_ms: number
  timestamp: string
}

export type Run = {
  run_id: string
  task: string
  task_type: string
  status: string
  golden_path_score: number | null
  error: string | null
  started_at: string
  finished_at: string | null
}

export type Deviation = {
  kind: string
  tool: string
  detail: string
  severity: string
}

export type AttackResult = {
  attack_type: string
  severity: string
  detected: boolean
  remediated: boolean
  evidence: string
}

export type MemorySections = Record<string, string>

const BASE = (() => {
  if (typeof window === "undefined") return "http://localhost:8000"
  const env = process.env.NEXT_PUBLIC_API_BASE
  if (env) return env
  return `http://${window.location.hostname}:8000`
})()

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" })
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`)
  return res.json()
}

export async function submitTask(
  task: string,
  taskType: string,
): Promise<{ run_id: string }> {
  const res = await fetch(`${BASE}/api/v1/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, task_type: taskType }),
  })
  if (!res.ok) throw new Error(`submit failed: ${res.status}`)
  return res.json()
}

export async function fetchRun(
  runId: string,
): Promise<{ run: Run; steps: Step[]; deviations: Deviation[] }> {
  return getJSON(`/api/v1/runs/${runId}`)
}

export async function fetchMemory(): Promise<{ sections: MemorySections }> {
  return getJSON("/api/v1/memory")
}

export async function fetchSecurity(): Promise<{ results: AttackResult[] }> {
  return getJSON("/api/v1/security/attacks")
}

export const TASK_TYPES = [
  "research_and_email",
  "inbox_summarize",
  "data_lookup_report",
] as const
