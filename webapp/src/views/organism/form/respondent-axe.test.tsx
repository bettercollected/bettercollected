// Automated accessibility check of what a respondent sees: the welcome page,
// a page with every field type (with and without validation errors) and the
// ending page, in every form style. Fails on any WCAG 2.0/2.1 A or AA rule.
//
// jsdom has no layout, so axe cannot compute colour contrast here; it reports
// those checks as incomplete rather than passing them. Contrast of the theme
// presets is checked from their colour values in utils/theme-contrast.test.ts.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import axe from 'axe-core';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FormTheme, ThemeColors, ThemeStyle } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';
import TrustLayer from '@app/views/molecules/form/trust-layer';

import Form from './form';
import RespondentPageShell from './respondent-page-shell';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));
// Page transitions never finish in jsdom, so the page being left would stay
// in the document next to the one being checked.
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const choices = (...values: string[]) => values.map((value, i) => ({ id: `choice-${i}`, value }));
const question = (id: string, type: FieldTypes, title: string, properties: StandardFormFieldDto['properties'] = {}, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({
    id,
    index: 0,
    type,
    title,
    description: `About ${title.toLowerCase()}`,
    properties: { fields: [], ...properties },
    validations: { required: true },
    ...extra
});

/** One question of every type a respondent can answer, all required so each shows an error. */
const FIELDS: StandardFormFieldDto[] = [
    question('short', FieldTypes.SHORT_TEXT, 'What is your name?'),
    question('long', FieldTypes.LONG_TEXT, 'Tell us more'),
    question('email', FieldTypes.EMAIL, 'What is your email address?'),
    question('number', FieldTypes.NUMBER, 'How many people?'),
    question('link', FieldTypes.LINK, 'Your website'),
    question('phone', FieldTypes.PHONE_NUMBER, 'Your phone number'),
    question('date', FieldTypes.DATE, 'When were you born?'),
    question('dropdown', FieldTypes.DROP_DOWN, 'Which country?', { choices: choices('Netherlands', 'Belgium') }),
    question('single', FieldTypes.MULTIPLE_CHOICE, 'Favourite colour?', { choices: choices('Red', 'Green') }),
    question('multi', FieldTypes.MULTIPLE_CHOICE, 'Which fruits?', { choices: choices('Apple', 'Pear'), allowMultipleSelection: true }),
    question('yesno', FieldTypes.YES_NO, 'Do you agree?', { choices: choices('Yes', 'No') }),
    question('rating', FieldTypes.RATING, 'Rate the service', { steps: 5 }),
    question('scale', FieldTypes.LINEAR_RATING, 'How likely are you to return?', { steps: 5 }),
    question('matrix', FieldTypes.MATRIX, 'Rate each part', {
        fields: [
            { id: 'row-1', index: 0, type: FieldTypes.MATRIX_ROW_INPUT, title: 'Quality', properties: { fields: [], choices: choices('Poor', 'Great') } },
            { id: 'row-2', index: 1, type: FieldTypes.MATRIX_ROW_INPUT, title: 'Speed', properties: { fields: [], choices: choices('Poor', 'Great') } }
        ]
    }),
    question('table', FieldTypes.TABULAR_INPUT, 'Your expenses', { rowTitles: ['Travel', 'Food'], columnTitles: ['Amount', 'Note'] }),
    question('file', FieldTypes.FILE_UPLOAD, 'Upload your CV'),
    question('statement', FieldTypes.TEXT, 'Before you start', {}, { validations: {} }),
    question('calc', FieldTypes.CALCULATED, 'Total', { expression: { '+': [1, 2] } }, { validations: {} }),
    question('children', FieldTypes.GROUP, 'Your children', {
        repeat: { minItems: 1, maxItems: 3, itemLabel: 'Child' },
        fields: [{ id: 'child-name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Child name', properties: { placeholder: 'Full name' }, validations: { required: true } }]
    })
];

const STYLES: ThemeStyle[] = ['classic', 'sheet', 'studio', 'leaflet'];
const DEFAULT_THEME = ThemeColors.find((theme) => theme.title === 'Default')!;

const loadForm = (style: ThemeStyle) => {
    const theme: FormTheme = { ...DEFAULT_THEME, style };
    store.dispatch(
        setForm({
            formId: `axe-${style}-${Math.random()}`,
            title: 'Neighbourhood survey',
            theme,
            hiddenFields: ['source'],
            welcomePage: { title: 'Neighbourhood survey', description: 'Takes about five minutes.' },
            thankyouPage: [{ title: 'Thank you', message: 'Your answers have been sent.', buttonText: 'Back to the website', buttonLink: 'https://example.com' }],
            fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, title: 'About you', properties: { fields: FIELDS } }]
        } as any)
    );
    return theme;
};

/** The respondent page as the form route composes it: the form above, the privacy strip below. */
function RespondentPage({ slide, theme }: { slide: number; theme: FormTheme }) {
    const { responderState, setResponderState } = useResponderState();
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(theme, { undoable: false });
        setResponderState({ ...responderState, currentSlide: slide, prevActiveSlide: slide });
    }, []);
    return (
        <RespondentPageShell footer={<TrustLayer ownerName="Acme" settings={{ purpose: 'To plan the summer events.' } as any} portalUrl="http://localhost:3000/acme" />}>
            <Form isPreviewMode />
        </RespondentPageShell>
    );
}

const open = (style: ThemeStyle, slide: number) => {
    const theme = loadForm(style);
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <RespondentPage slide={slide} theme={theme} />
            </Provider>
        </ReduxProvider>
    );
};

/** axe's findings on the whole document: WCAG A/AA plus the page-structure rules. */
const violations = () => axeViolations(document, { page: true });

/**
 * axe leaves its page-level checks (one main, one h1) incomplete in jsdom,
 * so they are asserted here: one main landmark, one footer, one h1.
 */
function expectPageStructure() {
    expect(screen.getAllByRole('main')).toHaveLength(1);
    expect(screen.getAllByRole('contentinfo')).toHaveLength(1);
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
}

describe.each(STYLES)('respondent pages pass axe (WCAG 2.1 A/AA) in the %s style', (style) => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        // Signed in, so the last page also shows the share-my-email consent.
        store.dispatch(setAuth({ id: 'user-1', email: 'someone@example.com' }));
    });
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it('the welcome page', async () => {
        open(style, -1);
        await screen.findByRole('button', { name: 'Start' });
        expect(await violations()).toEqual([]);
        expectPageStructure();
    });

    it('a page with every field type', async () => {
        open(style, 0);
        await screen.findByRole('textbox', { name: 'What is your name?' });
        await screen.findByRole('checkbox', { name: 'Share my email with the form collector' });
        expect(await violations()).toEqual([]);
        expectPageStructure();
    });

    it('the same page with every validation error shown', async () => {
        open(style, 0);
        await screen.findByRole('textbox', { name: 'What is your name?' });
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        expect((await screen.findAllByText('Please answer this question to continue.')).length).toBeGreaterThan(5);
        expect(await violations()).toEqual([]);
        expectPageStructure();
    });

    it('the same page with the dropdown, the date picker and the privacy panel open', async () => {
        open(style, 0);
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Which country?' })));
        await screen.findByRole('button', { name: 'Belgium' });
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'When were you born?' })));
        await screen.findByRole('grid');
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Your privacy' })));
        expect(screen.getByRole('button', { name: 'Your privacy' })).toHaveAttribute('aria-expanded', 'true');
        expect(await violations()).toEqual([]);
        expectPageStructure();
    });

    it('the ending page', async () => {
        open(style, -2);
        await screen.findByRole('heading', { level: 1, name: 'Thank you' });
        expect(await violations()).toEqual([]);
        expectPageStructure();
    });
});

describe('colour contrast', () => {
    it('is left to the preset check: axe cannot measure it without layout', async () => {
        open('classic', -1);
        await screen.findByRole('button', { name: 'Start' });
        const results = await axe.run(document, { runOnly: { type: 'rule', values: ['color-contrast'] } });
        // If this fails, axe can measure contrast here: add the rule to the checks above.
        expect(results.passes).toEqual([]);
        expect(results.incomplete.map((rule) => rule.id)).toEqual(['color-contrast']);
    });
});
