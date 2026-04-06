describe('Authentication - Sad Path', () => {
  beforeEach(() => {
    cy.wait(1000); 
  });

  it('renders login form and validates input', () => {
    cy.visit('http://localhost:5173/');
    cy.contains('Sign in').click();
    cy.get('input[placeholder="Email"], input[type="email"]').should('be.visible').type('elliedeaner@hotmail.com');
    cy.get('input[placeholder="Password"], input[type="password"]').type('InvalidPassword');
    cy.contains('Log In').click();
    cy.contains("Invalid email or password.").should('exist');
  });
});

describe('Authentication - Happy Path', () => {
  beforeEach(() => {
    cy.wait(1000); 
  });

  it('renders login form and validates input', () => {
    cy.visit('http://localhost:5173/login');
    cy.contains('Sign in').click();
    cy.get('input[placeholder="Email"], input[type="email"]').should('be.visible').type('elliedeaner@hotmail.com');
    cy.get('input[placeholder="Password"], input[type="password"]').type('M0ntyd0g1!');
    cy.contains('Log In').click();
    cy.contains('Profile').click();
    cy.contains("Sign out").should('exist');
  });
});

describe('Charger Planning: Meal Mode - Happy Path', () => {
  beforeEach(() => {
    cy.wait(1000);
  });

  it('renders route planner form', () => {
    cy.visit('http://localhost:5173/');
    cy.get('input[name="journeyTime"]').then($el => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call($el[0], '09:30');
      $el[0].dispatchEvent(new Event('input', { bubbles: true }));
    });
    cy.get('input[name="start_postcode"]').should('be.visible').clear().type('BA2 7AY');
    cy.get('input[name="end_postcode"]').should('be.visible').clear().type('TR12 7NT');
    cy.get('input[name="soc"]').should('be.visible').clear().type('45');
    cy.get('select[name="car_model"]', { timeout: 10000 }).should('exist').should('not.be.disabled').select('Citroen C5');
    cy.contains('Meal-Based').click();
    cy.get('.priority-buttons button').eq(0).click();
    cy.get('.priority-buttons button').eq(1).click();
    cy.get('button[type="submit"]').contains('Get recommendations').click();
    cy.get('.charger-list li', { timeout: 60000 }).should('have.length.at.least', 1);
    cy.contains('EVC Bath Spa Hotel', { timeout: 60000 }).should('exist');
    cy.get('.charger-list li').first().within(() => {
      cy.get('details.nearby-places summary', { timeout: 60000 }).click();
      cy.contains('Holburne Museum Tea House', { timeout: 60000 }).should('exist');
    });
  });
});

describe('Charger Planning: Meal Mode - Sad (Low charge distance fallback) Path', () => {
  beforeEach(() => {
    cy.wait(1000);
  });

  it('renders route planner form', () => {
    cy.visit('http://localhost:5173/');
    cy.get('input[name="journeyTime"]').then($el => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call($el[0], '06:30');
      $el[0].dispatchEvent(new Event('input', { bubbles: true }));
    });
    cy.get('input[name="start_postcode"]').should('be.visible').clear().type('BA2 7AY');
    cy.get('input[name="end_postcode"]').should('be.visible').clear().type('TR12 7NT');
    cy.get('input[name="soc"]').should('be.visible').clear().type('10');
    cy.get('select[name="car_model"]', { timeout: 10000 }).should('exist').should('not.be.disabled').select('Citroen C5');
    cy.contains('Meal-Based').click();
    cy.get('.priority-buttons button').eq(0).click();
    cy.get('.priority-buttons button').eq(1).click();
    cy.get('button[type="submit"]').contains('Get recommendations').click();
    cy.get('.charger-list li', { timeout: 60000 }).should('have.length.at.least', 1);
    cy.contains('Meal-Based options were unavailable for this time, so distance-based chargers are shown instead.', { timeout: 60000 }).should('exist');
  });
});

describe('Charger Planning: Distance Mode - Happy Path', () => {
  beforeEach(() => {
    cy.wait(1000);
  });

  it('renders route planner form', () => {
    cy.visit('http://localhost:5173/');
    cy.get('input[name="journeyTime"]').then($el => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call($el[0], '12:30');
      $el[0].dispatchEvent(new Event('input', { bubbles: true }));
    });
    cy.get('input[name="start_postcode"]').should('be.visible').clear().type('SW1A 0AA');
    cy.get('input[name="end_postcode"]').should('be.visible').clear().type('SP4 7DE');
    cy.get('input[name="soc"]').should('be.visible').clear().type('30');
    cy.get('select[name="car_model"]', { timeout: 10000 }).should('exist').should('not.be.disabled').select('Kia EV3');
    cy.contains('Distance-Based').click();
    cy.get('.priority-buttons button').eq(3).click();
    cy.get('.priority-buttons button').eq(4).click();
    cy.get('button[type="submit"]').contains('Get recommendations').click();
    cy.get('.charger-list li', { timeout: 60000 }).should('have.length.at.least', 1);
    cy.contains('White Hart Hotel', { timeout: 60000 }).should('exist');
  });
});

describe('Charger Planning: Invalid Input Path', () => {
  beforeEach(() => {
    cy.wait(1000);
  });

  it('renders route planner form', () => {
    cy.visit('http://localhost:5173/');
    cy.get('input[name="journeyTime"]').then($el => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call($el[0], '12:30');
      $el[0].dispatchEvent(new Event('input', { bubbles: true }));
    });
    cy.get('input[name="end_postcode"]').should('be.visible').clear().type('SP4 7DE');
    cy.get('input[name="soc"]').should('be.visible').clear().type('50');
    cy.get('select[name="car_model"]', { timeout: 10000 }).should('exist').should('not.be.disabled').select('Kia EV3');
    cy.contains('Distance-Based').click();
    cy.get('.priority-buttons button').eq(3).click();
    cy.get('.priority-buttons button').eq(4).click();
    cy.get('button[type="submit"]').contains('Get recommendations').click();
    cy.get('input[name="start_postcode"]').then($el => {
      expect($el[0].validity.valueMissing).to.be.true;
      expect($el[0].validationMessage).to.match(/fill|required|Please fill/i);
    });
    cy.get('form').then($form => {
      expect($form[0].checkValidity()).to.be.false;
    });
    cy.get('.charger-list', { timeout: 5000 }).should('not.exist');
  });
});

describe('Charger Planning: Save Defaults Path', () => {
  beforeEach(() => {
    cy.wait(1000);
  });

  it('renders route planner form', () => {
    cy.visit('http://localhost:5173/');
    cy.get('input[name="journeyTime"]').then($el => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call($el[0], '12:30');
      $el[0].dispatchEvent(new Event('input', { bubbles: true }));
    });
    cy.get('input[name="start_postcode"]').should('be.visible').clear().type('SW1A 0AA');
    cy.get('input[name="end_postcode"]').should('be.visible').clear().type('SP4 7DE');
    cy.get('input[name="soc"]').should('be.visible').clear().type('30');
    cy.get('select[name="car_model"]', { timeout: 10000 }).should('exist').should('not.be.disabled').select('Kia EV3');
    cy.contains('Distance-Based').click();
    cy.get('.priority-buttons button').eq(3).click();
    cy.get('.priority-buttons button').eq(4).click();
    cy.contains('Save as defaults').click();
    cy.contains('Defaults saved.', { timeout: 60000 }).should('exist');
  });
});

describe('Charger Planning: Load Defaults Path', () => {
  beforeEach(() => {
    cy.wait(1000);
  });

  it('renders route planner form', () => {
    cy.visit('http://localhost:5173/');
    cy.get('input[name="journeyTime"]').then($el => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call($el[0], '12:30');
      $el[0].dispatchEvent(new Event('input', { bubbles: true }));
    });
    cy.visit('http://localhost:5173/'); 
    cy.reload(true);
    cy.intercept('GET', '/api/v1/profile').as('getProfile');
    cy.contains('Load saved defaults').click();
    cy.wait('@getProfile');
    cy.get('input[name="end_postcode"]', { timeout: 60000 }).should('have.value', 'SP4 7DE');
    cy.get('select[name="car_model"]', { timeout: 60000 }).should('have.value', 'Kia EV3');
  });
});
