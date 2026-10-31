import React from 'react';

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { Comparison, JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';
import { ANONYMOUS_RESPONSE, ANSWERS, COLOUR_CHOICES, FORM, RESPONSE } from '@app/test/response-fixtures';

import ReadOnlyForm from './read-only-form';

const NOT_SHOWN = 'Not shown to the respondent';

const toast = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast }) }));

const download = vi.fn();
vi.mock('@app/utils/file-utils', async (importOriginal) => ({ ...(await importOriginal<typeof import('@app/utils/file-utils')>()), downloadFile: (...args: any[]) => download(...args) }));

const renderForm = (response: any = RESPONSE, form: any = FORM) =>
    render(
        <ReduxProvider store={store}>
            <ReadOnlyForm form={form} response={response} />
        </ReduxProvider>
    );

/** The question's group, found by its title. */
// (a multi-select's own options group carries the same name: the outer one comes first)
const question = (title: string | RegExp) => screen.getAllByRole('group', { name: title })[0];

/** The chosen options of a choice question, by their names. */
const chosen = (group: HTMLElement) =>
    Array.from(group.querySelectorAll('[role=radio], [role=checkbox]'))
        .filter((option) => option.getAttribute('aria-checked') === 'true')
        .map((option) => option.textContent);

// p1 jumps straight to p3 for someone who agreed: p2 is skipped
const JUMPING = {
    ...FORM,
    fields: FORM.fields.map((slide) =>
        slide.id === 'p1'
            ? { ...slide, properties: { ...slide.properties, jumps: [{ operator: LogicalOperator.AND, target: 'p3', conditions: [{ fieldId: 'agree', fieldType: FieldTypes.YES_NO, comparison: Comparison.IS_EQUAL, value: 'Yes' }] }] } }
            : slide
    )
};
// The server computes and stores every calculated field on every submission,
// whatever the path: the calculation ('total') keeps its value on a skipped page.
const PAGE_TWO_IDS = ['rating', 'scale', 'm1', 'm2', 'table', 'cv', 'guests', 'why'];
const WITHOUT_PAGE_TWO = Object.fromEntries(Object.entries(ANSWERS).filter(([id]) => !PAGE_TWO_IDS.includes(id)));

beforeEach(() => {
    toast.mockReset();
    download.mockReset();
    store.dispatch(setWorkspace({ id: 'workspace-1', workspaceName: 'acme' } as any));
});

describe('the response, drawn like the form', () => {
    it('is the form title as the page heading, then a section with a heading for every page of the form', () => {
        renderForm();
        expect(screen.getByRole('heading', { level: 1, name: 'Summer meeting registration' })).toBeInTheDocument();
        // these pages have no name of their own: the heading does not repeat the first question right above it
        expect(screen.getByRole('heading', { level: 2, name: 'Page 1 of 3' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 2, name: 'Page 2 of 3' })).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 2, name: 'Page 3 of 3' })).toBeInTheDocument();
        expect(screen.getAllByRole('region').length).toBeGreaterThanOrEqual(3);
        expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('wears the form theme: its face, ground and corner variables', () => {
        const { container } = renderForm();
        const root = container.querySelector('[data-response-form]') as HTMLElement;
        // Kantlijn: Atkinson Hyperlegible Next body, Besley titles, soft corners, a margin-rule page on the blush ground
        expect(root.getAttribute('data-form-body-font')).toBe('atkinson-next');
        expect(root.getAttribute('data-form-title-font')).toBe('besley');
        expect(root.style.getPropertyValue('--form-radius-field')).toBe('6px');
        expect(root.style.backgroundColor).not.toBe('');
        expect(root.style.color).not.toBe('');
    });

    it('numbers the questions of a page the form numbers', () => {
        renderForm();
        // single-choice, multi-select, ... the page has several questions: 1.1, 1.2, ...
        expect(screen.getAllByTestId('question-number').map((node) => node.textContent)).toContain('1.1');
        expect(screen.getAllByTestId('question-number').map((node) => node.textContent)).toContain('2.1');
    });

    it('draws no editable input anywhere: nothing to type in, nothing to tab to but the contents, the download and the scrolling tables', () => {
        const { container } = renderForm();
        expect(container.querySelectorAll('input, textarea, select')).toHaveLength(0);
        const tabStops = Array.from(container.querySelectorAll<HTMLElement>('[tabindex="0"], button, a[href]'))
            .filter((node) => !node.closest('[data-contents]')).map((node) => node.getAttribute('role') ?? node.tagName.toLowerCase());
        expect(tabStops.every((stop) => ['button', 'region'].includes(stop))).toBe(true);
    });

    it('does not write to the respondent answer state', () => {
        const before = JSON.stringify(store.getState());
        renderForm();
        fireEvent.click(screen.getByText('Red'));
        expect(JSON.stringify(store.getState())).toBe(before);
    });
});

describe('every question type shows its answer, read-only', () => {
    it('short text, email, phone, number (0 is an answer), link and date as read-only boxes', () => {
        renderForm();
        for (const [title, text] of [
            ['What is your name?', 'Anna Example'],
            ['What is your email address?', 'anna@example.com'],
            ['Your phone number', '+31612345678'],
            ['How many people?', '0'],
            ['Your website', 'https://example.com/anna'],
            ['When do you arrive?', '4 July 2026']
        ] as const) {
            const box = within(question(new RegExp(title.replace('?', '\\?')))).getByRole('textbox');
            expect(box).toHaveAttribute('aria-readonly', 'true');
            expect(box).toHaveTextContent(text);
        }
        // the link is text, never something to follow
        expect(screen.queryByRole('link', { name: /example.com\/anna/ })).toBeNull();
    });

    it('long text keeps its line breaks and is marked multiline', () => {
        renderForm();
        const box = within(question('Tell us more')).getByRole('textbox');
        expect(box).toHaveAttribute('aria-multiline', 'true');
        expect(box.textContent).toBe('First line\nSecond line');
    });

    it('a description sits under the title and describes the question', () => {
        renderForm();
        expect(question('What is your name?')).toHaveAccessibleDescription('As on your badge');
    });

    it('dropdown shows the chosen option', () => {
        renderForm();
        expect(within(question('Which country?')).getByRole('textbox')).toHaveTextContent('Belgium');
    });

    it('single choice lists every option and marks the chosen one, including "Other" with the respondent words', () => {
        renderForm();
        const group = within(question('Favourite colour?')).getByRole('radiogroup');
        expect(group).toHaveAttribute('aria-readonly', 'true');
        const options = within(group).getAllByRole('radio');
        expect(options.map((option) => option.textContent)).toEqual(['Red', 'Green', 'Blue', 'Teal']);
        expect(chosen(group)).toEqual(['Teal']);
    });

    it('single choice with an id answer marks that option, and an unused "Other" row is listed unmarked', () => {
        renderForm({ ...RESPONSE, answers: { ...ANSWERS, colour: { field: { id: 'colour' }, type: 'multiple_choice', choice: { value: COLOUR_CHOICES[1].id } } } });
        const group = within(question('Favourite colour?')).getByRole('radiogroup');
        expect(
            within(group)
                .getAllByRole('radio')
                .map((option) => option.textContent)
        ).toEqual(['Red', 'Green', 'Blue', 'Other']);
        expect(chosen(group)).toEqual(['Green']);
    });

    it('multi-select lists every option as a checkbox with the chosen ones checked', () => {
        renderForm();
        const group = within(question('Which fruits?')).getByRole('group');
        expect(within(group).getAllByRole('checkbox')).toHaveLength(3);
        expect(chosen(group)).toEqual(['Apple', 'Plum']);
    });

    it('yes/no marks the answer', () => {
        renderForm();
        const group = within(question('Do you agree?')).getByRole('radiogroup');
        expect(
            within(group)
                .getAllByRole('radio')
                .map((option) => option.textContent)
        ).toEqual(['Yes', 'No']);
        expect(chosen(group)).toEqual(['Yes']);
    });

    it('rating and linear scale mark the picked value', () => {
        renderForm();
        const stars = within(question('Rate the service')).getAllByRole('radio');
        expect(stars).toHaveLength(5);
        expect(stars.filter((star) => star.getAttribute('aria-checked') === 'true').map((star) => star.getAttribute('aria-label'))).toEqual(['4 of 5']);
        expect(within(question('Rate the service')).getByText('Rated 4 of 5')).toBeInTheDocument();
        expect(chosen(within(question('How likely are you to return?')).getByRole('radiogroup'))).toEqual(['3']);
    });

    it('a matrix says the chosen cell of every row in words', () => {
        renderForm();
        const table = within(question('Rate each part')).getByRole('table');
        const rows = within(table).getAllByRole('row').slice(1);
        expect(within(rows[0]).getByRole('rowheader')).toHaveTextContent('Quality');
        expect(
            within(rows[0])
                .getAllByRole('cell')
                .map((cell) => cell.textContent)
        ).toEqual(['Not selected', 'Selected']);
        expect(
            within(rows[1])
                .getAllByRole('cell')
                .map((cell) => cell.textContent)
        ).toEqual(['Selected', 'Not selected']);
    });

    it('a table field shows its rows and columns, with a dash for an empty cell', () => {
        renderForm();
        const table = within(question('Your expenses')).getByRole('table');
        expect(within(table).getByRole('columnheader', { name: 'Amount' })).toBeInTheDocument();
        expect(within(table).getByRole('rowheader', { name: 'Travel' })).toBeInTheDocument();
        expect(within(table).getByText('train')).toBeInTheDocument();
        expect(within(table).getAllByText('-')).toHaveLength(1);
    });

    it('a file upload is a download button that uses the server signed link', () => {
        renderForm();
        const button = within(question('Upload your CV')).getByRole('button', { name: /Download cv.pdf/ });
        fireEvent.click(button);
        expect(download).toHaveBeenCalledWith('https://files.example.com/signed/cv.pdf?sig=abc', 'cv.pdf');
    });

    it('a repeating group is one card per item, with that item answers', () => {
        renderForm();
        const items = within(question('Your guests')).getAllByRole('listitem');
        expect(items.map((item) => item.getAttribute('aria-label'))).toEqual(['Guest 1', 'Guest 2']);
        expect(within(items[0]).getByRole('textbox')).toHaveTextContent('Bram');
        expect(chosen(within(items[0]).getByRole('radiogroup'))).toEqual(['Vegan']);
        expect(within(items[1]).getByRole('textbox')).toHaveTextContent('Cato');
        // the second guest did not answer the diet question
        expect(within(items[1]).getByText('No answer')).toBeInTheDocument();
    });

    it('a calculated value is shown formatted', () => {
        renderForm();
        expect(within(question('Total')).getByRole('textbox')).toHaveTextContent('€42.50');
    });

    it('a text block is content, not a question: no group, no "No answer"', () => {
        renderForm();
        expect(screen.getByText('Welcome to the summer meeting')).toBeInTheDocument();
        expect(screen.queryByRole('group', { name: 'Welcome to the summer meeting' })).toBeNull();
    });

    it('a group that does not repeat is a heading, as on the form: no "No answer"', () => {
        const withGroup = { ...FORM, fields: [{ ...FORM.fields[0], properties: { ...FORM.fields[0].properties, fields: [{ id: 'gr', index: 0, type: FieldTypes.GROUP, title: 'About you', description: 'A few details', properties: { fields: [] } }] } }, ...FORM.fields.slice(1)] };
        const { container } = renderForm(RESPONSE, withGroup);
        const heading = container.querySelector('#rp-gr') as HTMLElement;
        expect(heading).toHaveAttribute('data-content');
        expect(heading).toHaveTextContent('About youA few details');
        expect(screen.queryByRole('group', { name: 'About you' })).toBeNull();
        expect(within(container.querySelector('[data-page="1"]') as HTMLElement).queryAllByText('No answer')).toHaveLength(0);
    });

    it('a file upload prints as its name and size (the button is screen-only)', () => {
        renderForm();
        const upload = question('Upload your CV');
        expect(within(upload).getByRole('button', { name: /Download cv.pdf/ }).className).toContain('print:hidden');
        const line = upload.querySelector('[data-print-file]') as HTMLElement;
        expect(line).toHaveTextContent('File: cv.pdf (205 KB)');
        expect(line.className).toContain('hidden');
        expect(line.className).toContain('print:block');
    });

    it('says so when a file cannot be downloaded (an expired link), and saves nothing', async () => {
        download.mockRejectedValue(new Error('Download failed (403)'));
        renderForm();
        fireEvent.click(within(question('Upload your CV')).getByRole('button', { name: /Download cv.pdf/ }));
        await vi.waitFor(() => expect(toast).toHaveBeenCalledWith({ description: 'Error downloading file', variant: 'destructive' }));
    });

    it('writes dates and calculated values in the form language', () => {
        const dutch = { ...FORM, settings: { ...FORM.settings, language: 'nl' } };
        renderForm(RESPONSE, dutch);
        expect(within(question('When do you arrive?')).getByRole('textbox')).toHaveTextContent('4 juli 2026');
        expect(within(question('Total')).getByRole('textbox').textContent?.replace(/\s/g, ' ')).toBe('€ 42,50');
    });

    it('writes them in English for a form in English or with no language', () => {
        renderForm();
        expect(within(question('When do you arrive?')).getByRole('textbox')).toHaveTextContent('4 July 2026');
    });

    it('hidden fields from the share link are listed with their values', () => {
        renderForm();
        const section = screen.getByRole('region', { name: 'Hidden fields (from the share link)' });
        expect(within(section).getByText('source')).toBeInTheDocument();
        expect(within(section).getByText('newsletter')).toBeInTheDocument();
    });
});

describe('what has no answer', () => {
    it('says "No answer" quietly for an unanswered question, and lists the options of an unanswered choice with none marked', () => {
        renderForm({ ...RESPONSE, answers: {} });
        expect(within(question('What is your name?')).getByText('No answer')).toBeInTheDocument();
        const group = within(question('Which fruits?')).getByRole('group');
        expect(within(group).getAllByRole('checkbox')).toHaveLength(3);
        expect(chosen(group)).toEqual([]);
        expect(within(question('Which fruits?')).getByText('No answer')).toBeInTheDocument();
        expect(screen.queryByText('Could not be decrypted')).toBeNull();
    });

    it('says "Could not be decrypted" for each question, never "No answer", when the answers are unreadable', () => {
        renderForm({ ...RESPONSE, answers: {}, unreadableFields: ['answers'] });
        expect(screen.queryByText('No answer')).toBeNull();
        expect(within(question('What is your name?')).getByText('Could not be decrypted')).toBeInTheDocument();
        // no option list pretending nothing was chosen
        expect(within(question('Which fruits?')).queryByRole('checkbox')).toBeNull();
    });

    it('does not guess what logic hid or skipped when the answers are unreadable', () => {
        const jumping = {
            ...FORM,
            fields: FORM.fields.map((slide) =>
                slide.id === 'p1'
                    ? { ...slide, properties: { ...slide.properties, jumps: [{ operator: LogicalOperator.AND, target: 'p3', conditions: [{ fieldId: 'agree', fieldType: FieldTypes.YES_NO, comparison: Comparison.IS_EQUAL, value: 'Yes' }] }] } }
                    : slide
            )
        };
        const { container } = renderForm({ ...RESPONSE, answers: {}, unreadableFields: ['answers'] }, jumping);
        expect(screen.queryByText(NOT_SHOWN)).toBeNull();
        expect(container.querySelectorAll('[data-page-skipped]')).toHaveLength(0);
        expect(within(screen.getByRole('group', { name: 'Why not?' })).getByText('Could not be decrypted')).toBeInTheDocument();
    });

    it('shows a question a logic rule hid, with why there is no answer', () => {
        // "Why not?" shows only for "No": this respondent said yes
        renderForm();
        const hidden = screen.getByRole('group', { name: 'Why not?' });
        expect(hidden).toHaveTextContent('Not shown to the respondent');
        expect(within(hidden).queryByRole('textbox')).toBeNull();
        expect(within(hidden).queryByText('No answer')).toBeNull();
    });

    it('shows that question normally for a respondent who got it', () => {
        renderForm({ ...RESPONSE, answers: { ...ANSWERS, agree: { field: { id: 'agree' }, type: 'yes_no', boolean: false }, why: { field: { id: 'why' }, type: 'short_text', text: 'Too far' } } });
        const group = screen.getByRole('group', { name: 'Why not?' });
        expect(within(group).getByRole('textbox')).toHaveTextContent('Too far');
        expect(group).not.toHaveTextContent('Not shown');
    });

    it('collapses a page the respondent was sent past, and says so', () => {
        const { container } = renderForm({ ...RESPONSE, answers: WITHOUT_PAGE_TWO }, JUMPING);
        const skipped = container.querySelector('[data-page="2"]') as HTMLElement;
        expect(within(skipped).getByText("Skipped: this respondent's answers sent them past this page.")).toBeInTheDocument();
        expect(within(skipped).queryByText(/still stored/)).toBeNull();
        const details = skipped.querySelector('details') as HTMLDetailsElement;
        expect(details.open).toBe(false);
        // the stored calculation is no answer of the respondent's: plain "Skipped", nothing counted
        expect(details.querySelector('summary')!.textContent).toBe('Show the 8 questions on this page');
        expect(details.querySelectorAll('[data-not-shown]')).toHaveLength(7);
        // it is still listed, with its value and why it is there
        const total = within(skipped).getByRole('group', { name: 'Total' });
        expect(within(total).getByText('Calculated, on a page the respondent skipped')).toBeInTheDocument();
        expect(within(total).queryByText('Answered, then skipped')).toBeNull();
        // the visited pages are drawn in full
        expect(container.querySelector('[data-page="1"] [data-page-skipped]')).toBeNull();
        expect(container.querySelector('[data-page="3"] [data-page-skipped]')).toBeNull();
    });

    it('shows answers given on a page before the respondent went back and changed course: marked, with the list open', () => {
        // page 1 said "yes" (jump past page 2) after page 2 had been filled in: the answers are stored, and in the table and the export
        const { container } = renderForm(RESPONSE, JUMPING);
        const skipped = container.querySelector('[data-page="2"]') as HTMLElement;
        const details = skipped.querySelector('details') as HTMLDetailsElement;
        expect(details.open).toBe(true);
        // the calculation is not counted: the server stores it whatever the path
        expect(details).toHaveTextContent('Show the 8 questions on this page (6 answered)');
        expect(within(skipped).getByText(/Answers given here before they changed course are still stored/)).toBeInTheDocument();
        const rating = within(skipped).getByRole('group', { name: 'Rate the service' });
        expect(within(rating).getByText('Answered, then skipped')).toBeInTheDocument();
        expect(within(rating).getByText('Rated 4 of 5')).toBeInTheDocument();
        // a matrix answers by row; a repeating group by item
        expect(within(within(skipped).getAllByRole('group', { name: 'Rate each part' })[0]).getByText('Answered, then skipped')).toBeInTheDocument();
        expect(within(within(skipped).getAllByRole('group', { name: 'Your guests' })[0]).getAllByRole('listitem')).toHaveLength(2);
        // the one question without an answer stays "not shown"
        expect(within(skipped).getByRole('group', { name: 'Why not?' })).toHaveTextContent('Not shown to the respondent');
    });

    it('opens the list for a single answer on a skipped page, and counts only that one', () => {
        const { container } = renderForm({ ...RESPONSE, answers: { ...WITHOUT_PAGE_TWO, scale: ANSWERS.scale } }, JUMPING);
        const details = container.querySelector('[data-page="2"] details') as HTMLDetailsElement;
        expect(details.open).toBe(true);
        expect(details).toHaveTextContent('Show the 8 questions on this page (1 answered)');
    });

    it('counts no statement, text or non-repeating group as a question of a skipped page', () => {
        const withContent = {
            ...JUMPING,
            fields: JUMPING.fields.map((slide) =>
                slide.id === 'p2'
                    ? {
                          ...slide,
                          properties: {
                              ...slide.properties,
                              fields: [
                                  { id: 'st', index: 20, type: FieldTypes.STATEMENT, title: 'A statement', properties: { fields: [] } },
                                  { id: 'tx', index: 21, type: FieldTypes.TEXT, title: 'Some text', properties: { fields: [] } },
                                  { id: 'gr', index: 22, type: FieldTypes.GROUP, title: 'About you', properties: { fields: [] } },
                                  ...slide.properties!.fields!
                              ]
                          }
                      }
                    : slide
            )
        };
        const { container } = renderForm({ ...RESPONSE, answers: WITHOUT_PAGE_TWO }, withContent);
        expect(container.querySelector('[data-page="2"] details')).toHaveTextContent('Show the 8 questions on this page');
    });

    it('a jump to "submit" skips the pages after it', () => {
        const ending = {
            ...FORM,
            fields: FORM.fields.map((slide) =>
                slide.id === 'p1'
                    ? { ...slide, properties: { ...slide.properties, jumps: [{ operator: LogicalOperator.AND, target: JUMP_TARGET_SUBMIT, conditions: [{ fieldId: 'agree', fieldType: FieldTypes.YES_NO, comparison: Comparison.IS_EQUAL, value: 'Yes' }] }] } }
                    : slide
            )
        };
        const { container } = renderForm(RESPONSE, ending);
        expect(container.querySelectorAll('[data-page-skipped]')).toHaveLength(2);
    });
});

describe('staff-only fields', () => {
    it('are left out of the form look (they have their own panel for the team)', () => {
        const withInternal = {
            ...FORM,
            fields: FORM.fields.map((slide, index) =>
                index === 0 ? { ...slide, properties: { ...slide.properties, fields: [...slide.properties!.fields!, { id: 'note', index: 50, type: FieldTypes.SHORT_TEXT, title: 'Office note', internal: true, properties: { fields: [] } }] } } : slide
            )
        };
        renderForm(RESPONSE, withInternal);
        expect(screen.queryByText('Office note')).toBeNull();
    });
});

describe('pipes and a form without a theme', () => {
    it('resolves an answer pipe in a question title with this response answers', () => {
        const piped = {
            ...FORM,
            fields: [
                {
                    ...FORM.fields[0],
                    properties: {
                        ...FORM.fields[0].properties,
                        fields: [
                            ...FORM.fields[0].properties!.fields!,
                            {
                                id: 'followup',
                                index: 99,
                                type: FieldTypes.SHORT_TEXT,
                                title: {
                                    type: 'doc',
                                    content: [
                                        {
                                            type: 'paragraph',
                                            content: [
                                                { type: 'text', text: 'Hello ' },
                                                { type: 'answerPipe', attrs: { pipeKey: 'name', kind: 'field', label: 'name' } },
                                                { type: 'text', text: ', how was it?' }
                                            ]
                                        }
                                    ]
                                },
                                properties: { fields: [] }
                            }
                        ]
                    }
                },
                ...FORM.fields.slice(1)
            ]
        };
        renderForm(RESPONSE, piped);
        expect(screen.getByRole('group', { name: /Hello Anna Example, how was it\?/ })).toBeInTheDocument();
    });

    it('draws an imported form (no pages, no theme) as one page with default colours', () => {
        const imported: any = {
            formId: 'g1',
            title: 'Imported survey',
            builderVersion: 'v1',
            settings: { provider: 'google' },
            fields: [{ id: 'q1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name' }]
        };
        const { container } = renderForm({ ...RESPONSE, hiddenFields: {}, answers: { q1: { field: { id: 'q1' }, type: 'short_text', text: 'Anna' } } }, imported);
        expect(within(screen.getByRole('group', { name: 'Your name' })).getByRole('textbox')).toHaveTextContent('Anna');
        expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(1);
        expect((container.querySelector('[data-response-form]') as HTMLElement).style.backgroundColor).not.toBe('');
    });
});

describe('the contents list', () => {
    const contents = () => screen.getByRole('navigation', { name: 'Contents' });
    const entries = () => within(contents()).getAllByRole('link');

    it('lists every page with its number and the name its heading has, each a link to that page', () => {
        renderForm();
        expect(entries().map((link) => link.textContent)).toEqual(['Page 1 What is your name?', 'Page 2 Rate the service', 'Page 3 Anything else?']);
        expect(entries().map((link) => link.getAttribute('href'))).toEqual(['#page-1', '#page-2', '#page-3']);
        [1, 2, 3].forEach((n) => expect(document.getElementById(`page-${n}`)).toHaveAttribute('data-page', String(n)));
        // under the form title, before page 1
        const title = screen.getByRole('heading', { level: 1 });
        expect(title.compareDocumentPosition(contents()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(contents().compareDocumentPosition(document.getElementById('page-1')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    it("uses a page's own section title, in the list and in its heading", () => {
        const titled = { ...FORM, fields: FORM.fields.map((slide) => (slide.id === 'p2' ? { ...slide, properties: { ...slide.properties, sectionTitle: 'Your visit' } } : slide)) };
        renderForm(RESPONSE, titled);
        expect(entries()[1]).toHaveTextContent('Page 2 Your visit');
        expect(screen.getByRole('heading', { level: 2, name: 'Page 2 of 3 · Your visit' })).toBeInTheDocument();
    });

    it("names a page by its opening heading once: in the list and its heading, not again in the text block below", () => {
        const heading = (text: string) => ({ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text }] });
        const paragraph = (text: string) => ({ type: 'paragraph', content: [{ type: 'text', text }] });
        const opening = (id: string, ...content: any[]) => ({ id, index: -1, type: FieldTypes.TEXT, title: { type: 'doc', content }, properties: { fields: [] } });
        const withHeadings = {
            ...FORM,
            fields: FORM.fields.map((slide) =>
                slide.id === 'p2'
                    ? { ...slide, properties: { ...slide.properties, fields: [opening('open2', heading('Your visit'), paragraph('Tell us how it went.')), ...slide.properties!.fields!] } }
                    : slide.id === 'p3'
                      ? { ...slide, properties: { ...slide.properties, fields: [opening('open3', heading('Last words')), ...slide.properties!.fields!] } }
                      : slide
            )
        };
        const { container } = renderForm(RESPONSE, withHeadings);
        expect(entries()[1]).toHaveTextContent('Page 2 Your visit');
        expect(screen.getByRole('heading', { level: 2, name: 'Page 2 of 3 · Your visit' })).toBeInTheDocument();
        const two = container.querySelector('[data-page="2"]') as HTMLElement;
        // the heading's words once on the page; the rest of the text block still opens it
        expect(within(two).getAllByText(/Your visit/)).toHaveLength(1);
        expect(within(two).getByText('Tell us how it went.')).toBeInTheDocument();
        // a text block that was only the heading leaves nothing behind
        expect(entries()[2]).toHaveTextContent('Page 3 Last words');
        expect(screen.getByRole('heading', { level: 2, name: 'Page 3 of 3 · Last words' })).toBeInTheDocument();
        expect(within(container.querySelector('[data-page="3"]') as HTMLElement).getAllByText(/Last words/)).toHaveLength(1);
    });

    it("keeps the opening text whole under a page's own section title", () => {
        const opening = { id: 'open2', index: -1, type: FieldTypes.TEXT, title: { type: 'doc', content: [{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Before we start' }] }] }, properties: { fields: [] } };
        const titled = { ...FORM, fields: FORM.fields.map((slide) => (slide.id === 'p2' ? { ...slide, properties: { ...slide.properties, sectionTitle: 'Your visit', fields: [opening, ...slide.properties!.fields!] } } : slide)) };
        const { container } = renderForm(RESPONSE, titled);
        expect(screen.getByRole('heading', { level: 2, name: 'Page 2 of 3 · Your visit' })).toBeInTheDocument();
        expect(within(container.querySelector('[data-page="2"]') as HTMLElement).getByText('Before we start')).toBeInTheDocument();
    });

    it('puts only page numbers in the links, never a title or an answer', () => {
        renderForm();
        entries().forEach((link) => expect(link.getAttribute('href')).toMatch(/^#page-\d+$/));
    });

    it('moves focus to the heading of the page a link goes to, clear of the sticky toolbar', () => {
        renderForm();
        fireEvent.click(entries()[1]);
        expect(document.activeElement).toBe(screen.getByRole('heading', { level: 2, name: /^Page 2 of 3/ }));
        expect(document.getElementById('page-2')!.className).toContain('scroll-mt-28');
    });

    it('follows a link in place: no new Back step, the router state kept, the address given the page number', () => {
        const scroll = vi.fn();
        // jsdom has no scrolling
        (Element.prototype as any).scrollIntoView = scroll;
        try {
            window.history.replaceState({ __NA: true, router: 'state' }, '', '/acme/dashboard/forms/form-1/responses/resp-1');
            renderForm();
            const steps = window.history.length;
            // false: the browser's own jump (a history entry without the router's state) does not happen
            expect(fireEvent.click(entries()[1])).toBe(false);
            expect(window.history.length).toBe(steps);
            expect(window.history.state).toEqual({ __NA: true, router: 'state' });
            expect(window.location.pathname).toBe('/acme/dashboard/forms/form-1/responses/resp-1');
            expect(window.location.hash).toBe('#page-2');
            expect(scroll).toHaveBeenCalledTimes(1);
            expect(scroll.mock.instances[0]).toBe(document.getElementById('page-2'));
            expect(document.activeElement).toBe(screen.getByRole('heading', { level: 2, name: /^Page 2 of 3/ }));
            // again: still no new step
            fireEvent.click(entries()[2]);
            expect(window.history.length).toBe(steps);
            expect(window.location.hash).toBe('#page-3');
        } finally {
            delete (Element.prototype as any).scrollIntoView;
            window.history.replaceState(null, '', '/');
        }
    });

    it('leaves a click that opens a new tab or window to the browser', () => {
        renderForm();
        const before = document.activeElement;
        expect(fireEvent.click(entries()[1], { ctrlKey: true })).toBe(true);
        expect(fireEvent.click(entries()[1], { metaKey: true })).toBe(true);
        expect(fireEvent.click(entries()[1], { shiftKey: true })).toBe(true);
        expect(fireEvent.click(entries()[1], { button: 1 })).toBe(true);
        expect(document.activeElement).toBe(before);
    });

    it('marks a skipped page, and one that still holds answers differently', () => {
        renderForm({ ...RESPONSE, answers: WITHOUT_PAGE_TWO }, JUMPING);
        expect(entries()[1]).toHaveTextContent('Page 2 Rate the service Skipped');
        expect(entries()[1].querySelector('[data-skipped="empty"]')).not.toBeNull();
        // the calculation the server stored on it is no answer kept
        expect(entries()[1]).not.toHaveTextContent('answers kept');
        expect(entries()[0]).not.toHaveTextContent('Skipped');
        cleanup();
        renderForm(RESPONSE, JUMPING);
        expect(entries()[1]).toHaveTextContent('Skipped, answers kept');
        expect(entries()[1].querySelector('[data-skipped="with-answers"]')).not.toBeNull();
        // the link still lands on the (collapsed) section
        fireEvent.click(entries()[1]);
        expect(document.activeElement!.closest('section')).toBe(document.getElementById('page-2'));
    });

    it('is not there for a form of one page', () => {
        renderForm(RESPONSE, { ...FORM, fields: [FORM.fields[0]] });
        expect(screen.queryByRole('navigation', { name: 'Contents' })).toBeNull();
    });

    it('stays in print, as a table of contents', () => {
        renderForm();
        expect(contents().className).not.toContain('print:hidden');
        expect(contents().closest('.print\\:hidden')).toBeNull();
    });

    it('has no WCAG A/AA violation with a skipped page', async () => {
        renderForm(RESPONSE, JUMPING);
        expect(await axeViolations(document, {})).toEqual([]);
    });
});

describe('accessibility', () => {
    it.each([
        ['known response', RESPONSE],
        ['anonymous response', ANONYMOUS_RESPONSE],
        ['unreadable response', { ...RESPONSE, answers: {}, unreadableFields: ['answers'] }],
        ['empty response', { ...RESPONSE, answers: {}, hiddenFields: {} }]
    ])('has no WCAG A/AA violation: %s', async (_name, response) => {
        renderForm(response);
        expect(await axeViolations(document, {})).toEqual([]);
    });
});
