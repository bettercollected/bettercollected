/// <reference types="cypress" />

describe('BetterCollected', () => {
    beforeEach(() => {
        cy.visit(Cypress.env('baseUrl'));
    });

    it('displays two login buttons by default', () => {
        cy.get('[role="button"]').should('have.length', 2);
    });
});
