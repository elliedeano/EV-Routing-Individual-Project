export default {
  allowCypressEnv: false,

  e2e: {
    supportFile: "../frontend/cypress/support/e2e.js",
    // Match any spec under the tests folder (including ui_test_plan.cy.js at repo/tests)
    specPattern: "**/*.cy.{js,jsx,ts,tsx}",
    setupNodeEvents(on, config) {
      // No-op: avoid importing 'cypress' at runtime so Cypress can load this file
    },
  },
};
