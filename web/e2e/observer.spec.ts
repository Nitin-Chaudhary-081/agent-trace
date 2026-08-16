import { test, expect } from "@playwright/test"

// Requires the Flask API on :8000 and `yarn start` on :3001 (see CONTRIBUTING).
const UI = "http://localhost:3001"

test("flow 1: launch a task and see live trajectory + score", async ({ page }) => {
  await page.goto(UI)
  await expect(page.getByText("AgentTrace Observer")).toBeVisible()
  await expect(page.getByTestId("memory-viewer")).toBeVisible()

  await page.getByTestId("task-input").fill("lookup records from table")
  await page.getByTestId("run-button").click()
  await expect(page.getByTestId("run-id")).toBeVisible()

  await expect(page.getByTestId("trajectory-viewer")).toBeVisible()
  await expect(page.getByTestId("run-status")).toBeVisible()
  await expect(page.getByTestId("score-value")).toBeVisible()
})

test("flow 2: task-type selector drives rubric selection", async ({ page }) => {
  await page.goto(UI)
  const select = page.getByTestId("task-type-select")
  await select.selectOption("inbox_summarize")
  await expect(select).toHaveValue("inbox_summarize")
  await page.getByTestId("task-input").fill("summarize my inbox")
  await page.getByTestId("run-button").click()
  await expect(page.getByTestId("run-id")).toBeVisible()
})

test("flow 3: security panel surfaces attack results", async ({ page }) => {
  await page.goto(UI)
  await expect(page.getByTestId("security-panel")).toBeVisible()
  await expect(page.getByTestId("attack-prompt_injection")).toBeVisible()
  const item = page.getByTestId("attack-prompt_injection")
  await expect(item).toContainText("critical")
})

test("flow 4: memory viewer shows live agent state", async ({ page }) => {
  await page.goto(UI)
  const goal = page.getByTestId("memory-GOAL")
  await expect(goal).toBeVisible()
  await expect(page.getByTestId("memory-STATUS")).toBeVisible()
  await expect(page.getByTestId("memory-SESSION_ID")).toBeVisible()
})
