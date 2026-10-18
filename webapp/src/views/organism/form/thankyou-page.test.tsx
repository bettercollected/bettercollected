// Respondent text resolves through the app's i18n instance.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it } from 'vitest';

import { FormSlideLayout } from '@app/models/enums/form';
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
        expect(screen.getByRole('heading', { level: 1, name: 'Thank you' })).toBeDefined();
        expect(screen.getByText('Your answers have been sent.')).toBeDefined();
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

    it('opens only an http(s) button link and leaves out any other', () => {
        const page = (buttonLink: string) =>
            render(
                <ReduxProvider store={store}>
                    <Provider>
                        <ThankyouPage isPreviewMode={false} />
                    </Provider>
                </ReduxProvider>
            );
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        store.dispatch(setForm({ formId: 'form-typ-l', title: 'Links', fields: [], thankyouPage: [{ buttonText: 'Visit us', buttonLink: 'https://example.com/next' }] }));
        const { unmount } = page('');
        expect(screen.getByRole('link', { name: 'Visit us (opens in a new tab)' }).getAttribute('href')).toBe('https://example.com/next');
        unmount();
        store.dispatch(setForm({ formId: 'form-typ-x', title: 'Links', fields: [], thankyouPage: [{ buttonText: 'Visit us', buttonLink: 'javascript:alert(1)' }] }));
        page('');
        expect(screen.queryByText('Visit us')).toBeNull();
    });

    it('honours the page layout: "Centered" centres the content, "Left aligned" does not', () => {
        store.dispatch(setForm({ formId: 'form-typ-c', title: 'Centered', fields: [], thankyouPage: [{ title: 'Done', layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }] }));
        const { unmount } = renderPage();
        expect(screen.getByTestId('thankyou-column').className).toContain('text-center');
        expect(screen.getByRole('heading', { level: 1, name: 'Done' })).toBeDefined();
        unmount();

        store.dispatch(setForm({ formId: 'form-typ-l', title: 'Left', fields: [], thankyouPage: [{ title: 'Done', layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN }] }));
        renderPage();
        const column = screen.getByTestId('thankyou-column').className;
        expect(column).not.toContain('text-center');
        expect(column).toContain('mr-auto');
    });
});
