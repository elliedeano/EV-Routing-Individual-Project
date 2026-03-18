module.exports = {
  allowCypressEnv: false,
  e2e: {
    baseUrl: 'http://localhost:5173', 
    chromeWebSecurity: false,
    setupNodeEvents(on, config) {
      
    },
  },
};