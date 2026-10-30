// Respondent text resolves through the app's i18n instance.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FormSlideLayout } from '@app/models/enums/form';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';

import WelcomePage from './welcome-page';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));

const renderWith = (layout: FormSlideLayout) => {
    store.dispatch(setForm({ formId: `welcome-${layout}`, title: 'Visit feedback', fields: [], welcomePage: { description: 'Three minutes.', layout } }));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <WelcomePage isPreviewMode />
            </Provider>
        </ReduxProvider>
    );
};

describe('WelcomePage layout', () => {
    it('"Centered" centres the title, description, note and button', () => {
        renderWith(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
        const column = screen.getByTestId('welcome-column');
        expect(column.className).toContain('text-center');
        expect(column.className).toContain('items-center');
        expect(column.className).toContain('mx-auto');
        expect(screen.getByRole('heading', { level: 1, name: 'Visit feedback' })).toBeDefined();
        expect(screen.getByRole('button', { name: 'Start' })).toBeDefined();
    });

    it('"Left aligned" keeps one left edge', () => {
        renderWith(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN);
        const column = screen.getByTestId('welcome-column');
        expect(column.className).not.toContain('text-center');
        expect(column.className).toContain('items-start');
        expect(column.className).toContain('mr-auto');
    });
});

describe('WelcomePage as a preview of another form', () => {
    it('shows the given title and button text, not the form in the store', () => {
        store.dispatch(setForm({ formId: 'answered', title: 'Visit feedback', fields: [], welcomePage: { buttonText: 'Begin' } }));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <WelcomePage isPreviewMode formTitle="Support triage" welcomePageData={{ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, buttonText: 'Get help' }} />
                </Provider>
            </ReduxProvider>
        );
        expect(screen.getByRole('heading', { level: 1, name: 'Support triage' })).toBeDefined();
        expect(screen.queryByText('Visit feedback')).toBeNull();
        expect(screen.getByRole('button', { name: 'Get help' })).toBeDefined();
    });
});

describe('WelcomePage of a closed form', () => {
    it('says the form is closed and offers no Start', () => {
        // The server's stub of a closed form: the welcome page, no questions.
        store.dispatch(setForm({ formId: 'closed', builderVersion: 'v2', title: 'Visit feedback', welcomePage: { description: 'Three minutes.' }, settings: {}, unavailable: 'closed' } as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <WelcomePage isPreviewMode={false} />
                </Provider>
            </ReduxProvider>
        );
        expect(screen.getByRole('heading', { level: 1, name: 'Visit feedback' })).toBeDefined();
        expect(screen.getByRole('status').textContent).toBe('This form is closed and no longer accepts responses.');
        expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
    });
});

describe('WelcomePage of a closed form for a member', () => {
    it('keeps Start and says respondents can no longer answer', () => {
        // members get the whole form after the close date (no stub)
        store.dispatch(setForm({ formId: 'closed-staff', title: 'Visit feedback', fields: [], welcomePage: {}, settings: { formCloseDate: '2020-01-01T00:00:00+00:00' } } as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <WelcomePage isPreviewMode />
                </Provider>
            </ReduxProvider>
        );
        expect(screen.getByRole('status').textContent).toBe('This form is closed: respondents can no longer send answers.');
        expect(screen.getByRole('button', { name: 'Start' })).toBeDefined();
    });

    it('says nothing while the close date is ahead', () => {
        store.dispatch(setForm({ formId: 'open-staff', title: 'Visit feedback', fields: [], welcomePage: {}, settings: { formCloseDate: '2999-01-01T00:00:00+00:00' } } as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <WelcomePage isPreviewMode />
                </Provider>
            </ReduxProvider>
        );
        expect(screen.queryByRole('status')).toBeNull();
    });
});
