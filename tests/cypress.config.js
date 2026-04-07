export default {
  allowCypressEnv: false,

  e2e: {
    specPattern: "**/*.cy.{js,jsx,ts,tsx}",
    setupNodeEvents(on, config) {
    },
  },
};
