const { defineConfig } = require("@playwright/test")

module.exports = defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  use: {
    baseURL: "http://localhost:3001",
    headless: true,
  },
})
