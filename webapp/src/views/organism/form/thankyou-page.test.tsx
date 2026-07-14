import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it } from 'vitest';

import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import ThankyouPage from './thankyou-page';

const renderPage = () =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <ThankyouPage isPreviewMode />
            </Provider>
        </ReduxProvider>
    );

describe('ThankyouPage', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    });

    it('REGRESSION: survives a form with NO thank-you page (API/MCP-born forms)', () => {
        // create_form over MCP used to produce thankyouPage: null — the
        // non-null assertion + [0] here crashed the post-submit screen.
        store.dispatch(setForm({ formId: 'form-no-typ', title: 'No thankyou', thankyouPage: null, fields: [] }));
        renderPage();
        expect(screen.getByText('Thank You! 🎉')).toBeDefined();
        expect(screen.getByText(/successfully submitted/)).toBeDefined();
    });

    it('renders the custom title, message and button when set', () => {
        store.dispatch(
            setForm({
                formId: 'form-typ',
                title: 'With thankyou',
                fields: [],
                thankyouPage: [{ title: 'Cheers!', message: 'We got it.', buttonText: 'Visit us', buttonLink: 'https://example.com' }]
            })
        );
        renderPage();
        expect(screen.getByText('Cheers!')).toBeDefined();
        expect(screen.getByText('We got it.')).toBeDefined();
        expect(screen.getByText('Visit us')).toBeDefined();
    });
});
