import React from 'react';

import ShortText from './ShortText';

describe('<ShortText />', () => {
    it('renders', () => {
        // see: https://on.cypress.io/mounting-react
        cy.mount(<ShortText />);
    });
});
