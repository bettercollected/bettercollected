/// <reference types="cypress" />
import { equal } from 'assert';

describe('example to-do app', () => {
    beforeEach(() => {
        cy.visit('https://admin.bettercollected.com/login');
    });

    it('displays two login buttons by default', () => {
        cy.get('[role="button"]').should('have.length', 2);
    });
});
