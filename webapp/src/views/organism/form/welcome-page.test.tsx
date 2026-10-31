// Respondent text resolves through the app's i18n instance.
import '@app/shared/hocs/i18n-provider';
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

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

const renderStub = (formId: string, unavailable: string, settings: Record<string, unknown> = {}) => {
    // The server's stub of a form that takes no responses: the welcome page, no questions.
    store.dispatch(setForm({ formId, builderVersion: 'v2', title: 'Visit feedback', welcomePage: { description: 'Three minutes.' }, settings, unavailable } as any));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <WelcomePage isPreviewMode={false} />
            </Provider>
        </ReduxProvider>
    );
};

describe('WelcomePage of a form that is not open yet', () => {
    it('says when it opens, in the respondent\'s time zone, and offers no Start', () => {
        renderStub('not-open', 'not_yet_open', { formOpenDate: '2099-11-02T08:00:00+00:00' });
        expect(screen.getByRole('heading', { level: 1, name: 'Visit feedback' })).toBeDefined();
        const notice = screen.getByRole('status').textContent ?? '';
        expect(notice).toMatch(/^This form is not open yet\. It opens on 2 November 2099, \d{2}:\d{2} [A-Z+\-0-9]+\.$/);
        expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
    });

    it('says only that it is not open when the stub carries no date', () => {
        renderStub('not-open-nodate', 'not_yet_open');
        expect(screen.getByRole('status').textContent).toBe('This form is not open yet.');
        expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
    });
});

describe('WelcomePage of a form that is full', () => {
    it('says it is no longer accepting responses, names no number and offers no Start', () => {
        renderStub('full', 'full', { responseLimit: 40 });
        expect(screen.getByRole('status').textContent).toBe('This form is no longer accepting responses.');
        expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
        expect(document.body.textContent).not.toContain('40');
    });
});

describe('WelcomePage of a closed form with its date', () => {
    it('adds when it closed', () => {
        renderStub('closed-dated', 'closed', { formCloseDate: '2020-01-01T10:00:00+00:00' });
        expect(screen.getByRole('status').textContent).toMatch(/^This form is closed and no longer accepts responses\. It closed on 1 January 2020, \d{2}:\d{2} [A-Z+\-0-9]+\.$/);
        expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
    });
});

describe('WelcomePage of a form not open yet for a member', () => {
    it('keeps Start and says respondents cannot answer yet', () => {
        store.dispatch(setForm({ formId: 'not-open-staff', title: 'Visit feedback', fields: [], welcomePage: {}, settings: { formOpenDate: '2099-11-02T08:00:00+00:00' } } as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <WelcomePage isPreviewMode />
                </Provider>
            </ReduxProvider>
        );
        expect(screen.getByRole('status').textContent).toMatch(/^This form is not open yet: respondents can start on 2 November 2099/);
        expect(screen.getByRole('button', { name: 'Start' })).toBeDefined();
    });

    it('says nothing once the open date has passed', () => {
        store.dispatch(setForm({ formId: 'opened-staff', title: 'Visit feedback', fields: [], welcomePage: {}, settings: { formOpenDate: '2020-01-01T00:00:00+00:00' } } as any));
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

describe('WelcomePage notices in Dutch', () => {
    afterEach(() => window.history.replaceState(null, '', '/'));

    it.each([
        ['not_yet_open', { formOpenDate: '2099-11-02T08:00:00+00:00' }, /^Dit formulier is nog niet open\. Het opent op 2 november 2099, \d{2}:\d{2} [A-Z+\-0-9]+\.$/],
        ['full', {}, /^Dit formulier neemt geen antwoorden meer aan\.$/],
        ['closed', {}, /^Dit formulier is gesloten en neemt geen antwoorden meer aan\.$/]
    ] as const)('%s', (reason, settings, expected) => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=nl');
        renderStub(`nl-${reason}`, reason, settings);
        expect(screen.getByRole('status').textContent).toMatch(expected);
        expect(screen.queryByRole('button', { name: 'Start' })).toBeNull();
        expect(screen.queryByRole('button', { name: 'Starten' })).toBeNull();
    });
});
