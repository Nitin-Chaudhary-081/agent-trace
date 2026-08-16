/** Jest configuration for the observer UI (jsdom). */
const nextJest = require("next/jest")

const createJestConfig = nextJest({ dir: "./" })

const customConfig = {
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  testMatch: ["**/*.test.tsx", "**/*.test.ts"],
  transform: {
    "^.+\\.(ts|tsx)$": ["ts-jest", { tsconfig: "tsconfig.json" }],
  },
}

module.exports = createJestConfig(customConfig)