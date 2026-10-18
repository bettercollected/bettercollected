// Every respondent control is named by its question, not by its placeholder,
// and described by the question's description (WCAG 1.3.1, 2.5.3, 4.1.2).
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import axe from 'axe-core';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { setForm } from '@app/store/forms/slice';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

import FormSlide from './form-slide';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const choices = (...values: string[]) => values.map((value, i) => ({ id: `choice-${i}`, value }));
const question = (id: string, type: FieldTypes, title: string, properties: StandardFormFieldDto['properties'] = {}, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({
    id,
    index: 0,
    type,
    title,
    description: `About ${title.toLowerCase()}`,
    properties: { fields: [], ...properties },
    ...extra
});

const FIELDS: StandardFormFieldDto[] = [
    question('short', FieldTypes.SHORT_TEXT, 'What is your name?', {}, { validations: { required: true } }),
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
    question('calc', FieldTypes.CALCULATED, 'Total', { expression: { '+': [1, 2] } }),
    question('children', FieldTypes.GROUP, 'Your children', {
        repeat: { minItems: 2, maxItems: 3, itemLabel: 'Child' },
        fields: [{ id: 'child-name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Child name', properties: { placeholder: 'Full name' } }]
    })
];

/** The form's only page, open (so it is the last page: Submit and the consent show). */
function Page() {
    const { responderState, setResponderState } = useResponderState();
    React.useEffect(() => {
        setResponderState({ ...responderState, currentSlide: 0 });
    }, []);
    return <FormSlide index={0} isPreviewMode />;
}

const open = (fields: StandardFormFieldDto[] = FIELDS, settings?: Record<string, unknown>) => {
    store.dispatch(setForm({ formId: `labels-${Math.random()}`, title: 'Labels', settings, fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }] } as any));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page />
            </Provider>
        </ReduxProvider>
    );
};

const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const describedBy = (title: string) => new RegExp(`About ${escapeRegExp(title.toLowerCase())}`);

describe('respondent controls are named by their question', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it.each([
        ['short text', 'textbox', 'What is your name?'],
        ['long text', 'textbox', 'Tell us more'],
        ['email', 'textbox', 'What is your email address?'],
        ['number', 'spinbutton', 'How many people?'],
        ['link', 'textbox', 'Your website'],
        ['phone', 'textbox', 'Your phone number'],
        ['date', 'button', 'When were you born?'],
        ['dropdown', 'button', 'Which country?'],
        ['multiple choice', 'radiogroup', 'Favourite colour?'],
        ['checkboxes', 'group', 'Which fruits?'],
        ['yes/no', 'radiogroup', 'Do you agree?'],
        ['rating', 'group', 'Rate the service'],
        ['linear scale', 'group', 'How likely are you to return?'],
        ['matrix', 'group', 'Rate each part'],
        ['table input', 'table', 'Your expenses'],
        ['calculated value', 'status', 'Total'],
        ['repeating group', 'group', 'Your children']
    ] as const)('%s: named by the title, described by the description', async (_kind, role, title) => {
        open();
        const control = await screen.findByRole(role, { name: title });
        expect(control).toHaveAccessibleDescription(describedBy(title));
    });

    it('the placeholder is not the name', async () => {
        open();
        expect(await screen.findByRole('textbox', { name: 'What is your email address?' })).toHaveAttribute('placeholder', 'name@example.com');
        expect(screen.queryByRole('textbox', { name: 'name@example.com' })).toBeNull();
        expect(screen.queryByRole('textbox', { name: 'Answer' })).toBeNull();
    });

    it('a required question says so without changing the name', async () => {
        open();
        expect(await screen.findByRole('textbox', { name: 'What is your name?' })).toBeRequired();
    });

    it('the file input is focusable and named by the question', async () => {
        open();
        const input = (await screen.findByLabelText('Upload your CV')) as HTMLInputElement;
        expect(input.type).toBe('file');
        expect(input).toHaveAccessibleName('Upload your CV');
        expect(input).toHaveAccessibleDescription(/About upload your cv.*Max size limit: 25 MB/);
        expect(input.className).not.toMatch(/(^|\s)hidden(\s|$)/);
    });

    it('the dropdown and date buttons describe their current value', async () => {
        open();
        expect(await screen.findByRole('button', { name: 'Which country?' })).toHaveAccessibleDescription('About which country? Select an option');
        expect(screen.getByRole('button', { name: 'When were you born?' })).toHaveAccessibleDescription('About when were you born? Pick a date');
    });

    it('matrix rows are groups named by the row, cells by the column', async () => {
        open();
        const matrix = await screen.findByRole('group', { name: 'Rate each part' });
        const quality = within(matrix).getByRole('radiogroup', { name: 'Quality' });
        expect(within(quality).getByRole('radio', { name: 'Great' })).toBeInTheDocument();
        expect(within(matrix).getByRole('radiogroup', { name: 'Speed' })).toBeInTheDocument();
    });

    it('table cells are named by their row and column', async () => {
        open();
        const table = await screen.findByRole('table', { name: 'Your expenses' });
        expect(within(table).getByRole('textbox', { name: 'Food Amount' })).toBeInTheDocument();
    });

    it('questions in a repeating group are named with the item number', async () => {
        open();
        expect(await screen.findByRole('textbox', { name: 'Child name Child 1' })).toBeInTheDocument();
        expect(screen.getByRole('textbox', { name: 'Child name Child 2' })).toBeInTheDocument();
    });

    it('an error marks the control invalid and describes it', async () => {
        open();
        const name = await screen.findByRole('textbox', { name: 'What is your name?' });
        const submit = await screen.findByRole('button', { name: 'Submit response' });
        act(() => void fireEvent.click(submit));
        expect(await screen.findByText('Please answer this question to continue.')).toBeInTheDocument();
        expect(name).toHaveAttribute('aria-invalid', 'true');
        expect(name).toHaveAccessibleDescription(/About what is your name\? Please answer this question to continue\./);
    });

    it('the consent checkbox is named by its statement and described by its hint', async () => {
        store.dispatch(setAuth({ id: 'user-1', email: 'someone@example.com' }));
        open();
        const consent = await screen.findByRole('checkbox', { name: 'Share my email with the form collector' });
        expect(consent).toHaveAccessibleDescription(/someone@example\.com/);
    });

    it('a page with every field type passes axe', async () => {
        const { container } = open();
        await screen.findByRole('textbox', { name: 'What is your name?' });
        // Colour contrast needs layout jsdom does not have; the theme presets are checked elsewhere.
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
    });
});

// Described in the order things show on screen: the question's description,
// "Why we ask this", the field's own hints, then the error.
describe('respondent controls are described in reading order', () => {
    const WHY = { whyWeAsk: 'To plan the menu.' };
    const ORDERED: StandardFormFieldDto[] = [
        question('multi', FieldTypes.MULTIPLE_CHOICE, 'Which fruits?', { choices: choices('Apple', 'Pear'), allowMultipleSelection: true, ...WHY }, { validations: { required: true } }),
        question('dropdown', FieldTypes.DROP_DOWN, 'Which country?', { choices: choices('Netherlands', 'Belgium'), ...WHY }),
        question('date', FieldTypes.DATE, 'When were you born?', WHY),
        question('file', FieldTypes.FILE_UPLOAD, 'Upload your CV', WHY)
    ];

    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('checkboxes: description, why we ask, then the "choose many" hint', async () => {
        open(ORDERED);
        const group = await screen.findByRole('group', { name: 'Which fruits?' });
        expect(group).toHaveAccessibleDescription('(required) About which fruits? Why we ask this: To plan the menu. Choose as many as you like.');
    });

    it('the hint comes before the error', async () => {
        open(ORDERED);
        const group = await screen.findByRole('group', { name: 'Which fruits?' });
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        expect(await screen.findByText('Please answer this question to continue.')).toBeInTheDocument();
        expect(group).toHaveAccessibleDescription('(required) About which fruits? Why we ask this: To plan the menu. Choose as many as you like. Please answer this question to continue.');
    });

    it('dropdown, date and file: their own hint after why we ask', async () => {
        open(ORDERED);
        expect(await screen.findByRole('button', { name: 'Which country?' })).toHaveAccessibleDescription('About which country? Why we ask this: To plan the menu. Select an option');
        expect(screen.getByRole('button', { name: 'When were you born?' })).toHaveAccessibleDescription('About when were you born? Why we ask this: To plan the menu. Pick a date');
        expect(screen.getByLabelText('Upload your CV')).toHaveAccessibleDescription(/^About upload your cv Why we ask this: To plan the menu\. Choose your file or drag file ?Max size limit: 25 MB$/);
    });
});

// The inputs sit in no form of their own (each unnamed form made screen
// readers say "end of form" after every question). Enter in a one-line input
// still moves on to the next question; short and long text are text areas,
// where Enter starts a new line, as it did inside the forms.
describe('respondent inputs outside forms', () => {
    const TEXT: StandardFormFieldDto[] = [
        question('email', FieldTypes.EMAIL, 'What is your email address?', {}, { index: 0 }),
        question('link', FieldTypes.LINK, 'Your website', {}, { index: 1 }),
        question('phone', FieldTypes.PHONE_NUMBER, 'Your phone number', {}, { index: 2 }),
        question('short', FieldTypes.SHORT_TEXT, 'What is your name?', {}, { index: 3 }),
        question('long', FieldTypes.LONG_TEXT, 'Tell us more', {}, { index: 4 })
    ];
    const enter = (element: Element) => fireEvent.keyDown(element, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13 });

    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('no question puts its input in a form', async () => {
        const { container } = open();
        await screen.findByRole('textbox', { name: 'What is your name?' });
        expect(container.querySelectorAll('form')).toHaveLength(0);
    });

    it('Enter moves from email to link to phone to short text', async () => {
        open(TEXT);
        const email = await screen.findByRole('textbox', { name: 'What is your email address?' });
        const link = screen.getByRole('textbox', { name: 'Your website' });
        const phone = screen.getByRole('textbox', { name: 'Your phone number' });
        const name = screen.getByRole('textbox', { name: 'What is your name?' });

        email.focus();
        expect(enter(email)).toBe(false); // handled: no default action
        expect(link).toHaveFocus();
        enter(link);
        expect(phone).toHaveFocus();
        enter(phone);
        expect(name).toHaveFocus();
    });

    it.each(['What is your name?', 'Tell us more'])('Enter in "%s" (a text area) is left to it: a new line', async (title) => {
        open(TEXT);
        const area = await screen.findByRole('textbox', { name: title });
        area.focus();
        expect(enter(area)).toBe(true); // not prevented
        expect(area).toHaveFocus();
    });

    it('Enter in the last question stays put', async () => {
        open([question('only', FieldTypes.EMAIL, 'What is your email address?', {}, { index: 0 })]);
        const email = await screen.findByRole('textbox', { name: 'What is your email address?' });
        email.focus();
        expect(enter(email)).toBe(false);
        expect(email).toHaveFocus();
    });
});

// The form's own text is marked with its declared language when that is
// not the respondent's interface language (the page's <html lang>).
describe('form content language', () => {
    const NL_FIELDS: StandardFormFieldDto[] = [question('single', FieldTypes.MULTIPLE_CHOICE, 'Lievelingskleur?', { choices: choices('Rood', 'Groen'), whyWeAsk: 'Voor de statistiek.' })];

    afterEach(() => window.history.replaceState(null, '', '/'));

    it('a Dutch form under an English interface marks its title, description, reason and options', async () => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        open(NL_FIELDS, { language: 'nl' });
        await screen.findByRole('radiogroup', { name: 'Lievelingskleur?' });
        expect(document.getElementById('q-title-single')).toHaveAttribute('lang', 'nl');
        expect(document.getElementById('q-desc-single')).toHaveAttribute('lang', 'nl');
        expect(screen.getByText('Voor de statistiek.')).toHaveAttribute('lang', 'nl');
        expect(screen.getByText('Rood')).toHaveAttribute('lang', 'nl');
        // The interface text around it stays in the page's language.
        expect(screen.getByText('Why we ask this:').closest('[lang="nl"]')).toBeNull();
        expect(screen.getByText('Optional').closest('[lang="nl"]')).toBeNull();
    });

    it('a Dutch form under a Dutch interface needs no marks', async () => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=nl');
        open(NL_FIELDS, { language: 'nl-NL' });
        await screen.findByRole('radiogroup', { name: 'Lievelingskleur?' });
        expect(document.querySelector('[lang="nl-NL"]')).toBeNull();
    });

    it('a form that declares no language is taken to be in the page language', async () => {
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        open(NL_FIELDS);
        await screen.findByRole('radiogroup', { name: 'Lievelingskleur?' });
        expect(document.getElementById('q-title-single')).not.toHaveAttribute('lang');
    });
});
