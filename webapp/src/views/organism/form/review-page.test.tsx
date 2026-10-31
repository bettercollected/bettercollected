// The review page: an optional page after the last one where respondents read
// their answers before sending them. These tests run the real respondent
// form (pages, logic jumps, field rules, repeating groups) through the review,
// "Edit" and "Back to review", and the submit with its refusals.
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import useFormFileAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';
import { REVIEW_SLIDE } from '@app/utils/review-page';

import Form from './form';
import RespondentPageShell from './respondent-page-shell';

const submit = vi.fn();
vi.mock('@app/store/redux/form-api', async (original) => ({
    ...((await original()) as object),
    useSubmitResponseMutation: () => [submit, { isLoading: false }],
    useSendFlowEventMutation: () => [() => ({ catch: () => {} })]
}));
vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
// Page transitions never finish in jsdom: the page being left would stay next to the new one.
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const choices = (...values: string[]) => values.map((value, i) => ({ id: `c-${value.toLowerCase()}`, value, index: i }));
const q = (id: string, type: FieldTypes, title: string, extra: Partial<StandardFormFieldDto> = {}, properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({
    id,
    index: 0,
    type,
    title,
    properties: { fields: [], ...properties },
    validations: { required: false },
    ...extra
});
const page = (id: string, index: number, fields: StandardFormFieldDto[], properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, title: '', properties: { fields, ...properties } });
const when = (fieldId: string, fieldType: string, value: string) => ({ operator: LogicalOperator.AND, conditions: [{ fieldId, fieldType, comparison: 'IS_EQUAL', value }] });

/** Three pages. A "Plus" plan jumps from page 1 to page 3, skipping page 2. */
const FORM = () => ({
    formId: `review-${Math.random()}`,
    title: 'Membership',
    settings: { showReviewPage: true },
    thankyouPage: [{ id: 'end', title: 'Thank you', isDefault: true }],
    fields: [
        page(
            's1',
            0,
            [
                q('name', FieldTypes.SHORT_TEXT, 'Your name', { validations: { required: true } }),
                q('plan', FieldTypes.MULTIPLE_CHOICE, 'Your plan', { validations: { required: true } }, { choices: choices('Basic', 'Plus') }),
                q('secret', FieldTypes.SHORT_TEXT, 'Plus code', {}, { logic: { action: 'SHOW', ...when('plan', 'multiple_choice', 'Plus') } as any }),
                q('note', FieldTypes.SHORT_TEXT, 'Staff note', { internal: true })
            ],
            { sectionTitle: 'About you', jumps: [{ ...when('plan', 'multiple_choice', 'Plus'), target: 's3' }] }
        ),
        page('s2', 1, [
            q(
                'extra',
                FieldTypes.LONG_TEXT,
                'Anything else?',
                {},
                // becomes required when the name is "Grace"
                { rules: [{ id: 'r-extra', when: { conditions: [{ fieldId: 'name', fieldType: 'short_text', comparison: 'IS_EQUAL', value: 'Grace' }] }, then: { required: true } }] as any }
            )
        ]),
        page('s3', 2, [
            q('code', FieldTypes.SHORT_TEXT, 'Customer code', {}, { rules: [{ id: 'r-code', when: { conditions: [{ fieldId: 'name', fieldType: 'short_text', comparison: 'IS_NOT_EMPTY' }] }, then: { setValue: { const: 'CUST-1' } } }] as any }),
            q('cv', FieldTypes.FILE_UPLOAD, 'Your CV'),
            q('children', FieldTypes.GROUP, 'Your children', {}, { repeat: { minItems: 1, maxItems: 3, itemLabel: 'Child' }, fields: [q('child-name', FieldTypes.SHORT_TEXT, 'Child name', { validations: { required: true } })] }),
            q('agree', FieldTypes.YES_NO, 'Do you agree?', { validations: { required: true } })
        ])
    ]
});

const text = (value: string) => ({ type: 'text', text: value });
const ANSWERS = {
    name: text('Ada'),
    plan: { type: 'choice', choice: { value: 'c-basic' } },
    secret: text('PLUS-123'),
    note: text('staff only'),
    extra: text('Line one\nLine two'),
    cv: { type: 'file_upload', file_metadata: { id: 'f1', name: 'cv.pdf', url: 'https://files.example/secret-link' } },
    children: { type: 'group', items: [{ 'child-name': text('Kim') }] },
    agree: { type: 'boolean', boolean: true }
};

let responder: ReturnType<typeof useResponderState>;
let response: ReturnType<typeof useFormResponse>;
let fileStore: ReturnType<typeof useFormFileAtom>;
let preview = false;
function Respondent() {
    responder = useResponderState();
    response = useFormResponse();
    fileStore = useFormFileAtom();
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(ThemeColors[0], { undoable: false });
    }, []);
    return (
        <RespondentPageShell>
            <Form isPreviewMode={preview} />
        </RespondentPageShell>
    );
}

const start = (data: any = FORM(), answers: Record<string, any> = ANSWERS) => {
    store.dispatch(setForm(data));
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Respondent />
            </Provider>
        </ReduxProvider>
    );
    act(() => response.setFormResponse({ ...response.formResponse, answers: { ...answers } as any }));
    act(() => responder.setResponderState({ ...responder.responderState, currentSlide: 0, prevActiveSlide: 0, history: [] }));
};

const click = async (name: string | RegExp) => {
    await act(async () => void fireEvent.click(await screen.findByRole('button', { name })));
};
/** The submitted answers (the body of the request). */
const sentAnswers = () => JSON.parse((submit.mock.calls.at(-1)![0].body as FormData).get('response') as string).answers;
/** The page headings of the review, without the block of what is also sent. */
const pageHeadings = () => screen.getAllByRole('heading', { level: 2 }).filter((heading) => heading.textContent !== 'Also sent');
const reviewHeading = () => screen.findByRole('heading', { level: 1, name: /Review your answers|Controleer je antwoorden/ });
const section = (slide: number) => screen.getByTestId(`review-section-${slide}`);
/** The row of a question (its term), and what it answers (the definition after it). */
const termOf = (within_: HTMLElement, title: string | RegExp) =>
    within(within_)
        .getAllByText(title)
        .map((node) => node.closest('dt'))
        .find(Boolean) as HTMLElement;
const valueOf = (within_: HTMLElement, title: string | RegExp) => termOf(within_, title).nextElementSibling as HTMLElement;

/** Through the pages of the default path (Basic plan: 1, 2, 3) to the review. */
const toReview = async () => {
    await click('Continue');
    await screen.findByText('Page 2 of 3');
    await click('Continue');
    await screen.findByText('Page 3 of 3');
    await click('Review your answers');
    return reviewHeading();
};

describe('the review page', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
        submit.mockReset();
        submit.mockResolvedValue({ data: 'response-1' });
        preview = false;
    });
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it('follows the last page instead of submitting, and sends nothing yet', async () => {
        start();
        expect(screen.queryByRole('button', { name: 'Submit response' })).not.toBeInTheDocument();
        const heading = await toReview();
        expect(responder.currentSlide).toBe(REVIEW_SLIDE);
        // the button on the last page said where it goes; nothing was sent
        expect(submit).not.toHaveBeenCalled();
        // focus moves to the heading, which says what the page is
        await vi.waitFor(() => expect(document.activeElement).toBe(heading));
        expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
        expect(screen.getByRole('main')).toContainElement(heading);
        expect(screen.getByText(/Nothing has been sent yet/)).toBeInTheDocument();
    });

    it('lists the answers of each page in a summary list under a heading per page', async () => {
        start();
        await toReview();
        expect(pageHeadings().map((h) => h.textContent)).toEqual(['Page 1: About you', 'Page 2', 'Page 3']);
        const one = section(0);
        expect(valueOf(one, 'Your name')).toHaveTextContent('Ada');
        // choices say the option's words, not its id
        expect(valueOf(one, 'Your plan')).toHaveTextContent('Basic');
        const three = section(2);
        expect(valueOf(three, 'Do you agree?')).toHaveTextContent('Yes');
        // a file shows its name, never its link
        expect(valueOf(three, 'Your CV')).toHaveTextContent('cv.pdf');
        // a summary list: terms and their definitions
        expect(within(one).getAllByRole('term').length).toBeGreaterThan(1);
        expect(within(one).getAllByRole('definition').length).toBeGreaterThan(1);
        expect(document.body.innerHTML).not.toContain('secret-link');
    });

    it('keeps the line breaks of a long text and lets it wrap', async () => {
        const data = FORM();
        data.fields[1].properties!.fields![0].type = FieldTypes.LONG_TEXT;
        start(data, { ...ANSWERS, extra: text(`${'word '.repeat(60)}\nsecond line ${'x'.repeat(200)}`) });
        await toReview();
        const value = valueOf(section(1), 'Anything else?').firstElementChild!;
        expect(value.className).toContain('whitespace-pre-wrap');
        expect(value.className).toContain('break-words');
        expect(value.textContent).toContain('second line');
    });

    it('leaves out questions hidden by logic, internal questions and hidden fields', async () => {
        const data = { ...FORM(), hiddenFields: ['utm_source'] };
        start(data, { ...ANSWERS });
        await toReview();
        // "Plus code" shows only for Plus: not a question of the review (it is sent, so it is named below)
        expect(within(section(0)).queryByText('Plus code')).not.toBeInTheDocument();
        expect(within(section(0)).queryByText('PLUS-123')).not.toBeInTheDocument();
        expect(screen.queryByText('Staff note')).not.toBeInTheDocument();
        expect(screen.queryByText('staff only')).not.toBeInTheDocument();
        expect(screen.queryByText('utm_source')).not.toBeInTheDocument();
    });

    describe('what is sent although the form no longer shows it', () => {
        it('names an earlier answer to a question the later answers hide, apart from the questions', async () => {
            start();
            await toReview();
            // the form keeps and sends it: "Plus code" was answered, then the plan changed to Basic
            const block = screen.getByTestId('review-also-sent');
            expect(within(block).getByRole('heading', { level: 2, name: 'Also sent' })).toBeInTheDocument();
            expect(within(block).getByText('Plus code')).toBeInTheDocument();
            expect(within(block).getByText('PLUS-123')).toBeInTheDocument();
            expect(within(block).getByText(/still sent/)).toBeInTheDocument();
            // staff-only answers are not the respondent's
            expect(screen.queryByText('staff only')).not.toBeInTheDocument();
            // and what the block names is what the submit sends
            await click('Submit response');
            expect(sentAnswers().secret.text).toBe('PLUS-123');
        });

        it('is not there when everything sent is listed above', async () => {
            const { secret, ...answers } = ANSWERS;
            start(FORM(), answers);
            await toReview();
            expect(screen.queryByTestId('review-also-sent')).not.toBeInTheDocument();
        });

        it('names a file whose question is hidden or on a skipped page, and sends it', async () => {
            start(FORM(), { ...ANSWERS, plan: { type: 'choice', choice: { value: 'c-plus' } } });
            const sent = new File(['x'], 'old-cv.pdf');
            // a file picked for the question of page 2, which a Plus plan skips
            act(() => fileStore.addFile('extra', 'file-1', 'old-cv.pdf', sent));
            await click('Continue');
            await screen.findByText('Page 3 of 3');
            await click('Review your answers');
            await reviewHeading();
            const block = screen.getByTestId('review-also-sent');
            expect(within(block).getByText('Anything else?')).toBeInTheDocument();
            expect(within(block).getByText('old-cv.pdf')).toBeInTheDocument();
            await click('Submit response');
            expect((submit.mock.calls[0][0].body as FormData).getAll('file_field_ids')).toEqual(['extra']);
        });
    });

    it('marks values a field rule filled in as read only', async () => {
        start();
        await toReview();
        expect(termOf(section(2), 'Customer code')).toHaveTextContent('Filled in by the form');
        expect(valueOf(section(2), 'Customer code')).toHaveTextContent('CUST-1');
    });

    it("shows a rule-changed title of a question inside a group item (the item's, not the form's)", async () => {
        const data = FORM();
        const children = data.fields[2].properties!.fields![2];
        children.properties!.fields!.push(q('cage', FieldTypes.NUMBER, 'Age'));
        children.properties!.fields![0].properties = { fields: [], rules: [{ id: 'rc', when: { conditions: [{ fieldId: 'cage', fieldType: 'number', comparison: 'IS_NOT_EMPTY' }] }, then: { title: 'Name of the child you described' } }] as any };
        start(data, { ...ANSWERS, children: { type: 'group', items: [{ 'child-name': text('Kim'), cage: { type: 'number', number: 7 } }] } });
        await toReview();
        const item = within(section(2)).getByTestId('review-item');
        expect(within(item).getByText('Name of the child you described')).toBeInTheDocument();
        expect(within(item).queryByText('Child name')).not.toBeInTheDocument();
    });

    it('lists a repeating group item by item', async () => {
        start(FORM(), { ...ANSWERS, children: { type: 'group', items: [{ 'child-name': text('Kim') }, { 'child-name': text('Noor') }] } });
        await toReview();
        const items = within(section(2)).getAllByTestId('review-item');
        expect(items.map((item) => item.getAttribute('aria-label'))).toEqual(['Child 1', 'Child 2']);
        expect(within(items[0]).getByText('Kim')).toBeInTheDocument();
        expect(within(items[1]).getByText('Noor')).toBeInTheDocument();
    });

    it('lists only the pages gone through: a jump past a page leaves its answer out of the review and the submit', async () => {
        start(FORM(), { ...ANSWERS, plan: { type: 'choice', choice: { value: 'c-plus' } } });
        // page 1 jumps to page 3 for a Plus plan
        await click('Continue');
        await screen.findByText('Page 3 of 3');
        await click('Review your answers');
        await reviewHeading();
        expect(screen.queryByText('Anything else?')).not.toBeInTheDocument();
        expect(pageHeadings().map((h) => h.textContent)).toEqual(['Page 1: About you', 'Page 3']);
        // the Plus-only question now shows
        expect(within(section(0)).getByText('PLUS-123')).toBeInTheDocument();
        await click('Submit response');
        expect(submit).toHaveBeenCalledTimes(1);
        const sent = sentAnswers();
        // page 2 was skipped: its answer is not sent even though it is in the browser
        expect(sent.extra).toBeUndefined();
        expect(sent.name.text).toBe('Ada');
    });

    it('sends from the review, shows the ending, and offers the email choice there', async () => {
        store.dispatch(setAuth({ id: 'user-1', email: 'someone@example.com' }));
        start();
        await click('Continue');
        await screen.findByText('Page 2 of 3');
        await click('Continue');
        await screen.findByText('Page 3 of 3');
        // the choice belongs to where they send from
        expect(screen.queryByTestId('share-email-consent')).not.toBeInTheDocument();
        await click('Review your answers');
        await reviewHeading();
        expect(screen.getByTestId('share-email-consent')).toBeInTheDocument();
        await click('Submit response');
        expect(submit).toHaveBeenCalledTimes(1);
        const body = JSON.parse((submit.mock.calls[0][0].body as FormData).get('response') as string);
        expect(body.anonymize).toBe(true);
        await screen.findByRole('heading', { level: 1, name: 'Thank you' });
    });

    it('Back returns to the last page', async () => {
        start();
        await toReview();
        await click('Back');
        await screen.findByText('Page 3 of 3');
        expect(screen.getByRole('button', { name: 'Review your answers' })).toBeInTheDocument();
        expect(submit).not.toHaveBeenCalled();
    });

    describe('Edit and Back to review', () => {
        it('goes to the page, and back to the review with the changed answer', async () => {
            start();
            await toReview();
            await click(/^Edit Page 1: About you/);
            await screen.findByText('Page 1 of 3');
            // the way back is the main button, the way on stays
            expect(screen.getByRole('button', { name: 'Back to review' })).toBeInTheDocument();
            expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
            act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, name: text('Ada Lovelace') } as any }));
            await click('Back to review');
            await reviewHeading();
            expect(valueOf(section(0), 'Your name')).toHaveTextContent('Ada Lovelace');
            // the same three pages, nothing was sent
            expect(pageHeadings()).toHaveLength(3);
            expect(submit).not.toHaveBeenCalled();
            await vi.waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1 })));
        });

        it('offers no way back on pages that were not reviewed, and none after a normal pass', async () => {
            start();
            await toReview();
            await click('Back');
            await screen.findByText('Page 3 of 3');
            expect(screen.queryByRole('button', { name: 'Back to review' })).not.toBeInTheDocument();
        });

        it('goes back to the review over the new route when the edit changes a jump to a page already gone through', async () => {
            start();
            await toReview();
            expect(pageHeadings()).toHaveLength(3);
            await click(/^Edit Page 1: About you/);
            await screen.findByText('Page 1 of 3');
            // a Plus plan now jumps past page 2
            act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, plan: { type: 'choice', choice: { value: 'c-plus' } } } as any }));
            await click('Back to review');
            await reviewHeading();
            expect(pageHeadings().map((h) => h.textContent)).toEqual(['Page 1: About you', 'Page 3']);
            await click('Submit response');
            expect(sentAnswers().extra).toBeUndefined();
        });

        it('replays from the first page of the path: Edit, Continue past a skipped page, then Back to review lists and sends no stale page', async () => {
            start();
            await toReview();
            await click(/^Edit Page 1: About you/);
            await screen.findByText('Page 1 of 3');
            // the edit makes page 1 jump past page 2; Continue (not Back to review) follows it
            act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, plan: { type: 'choice', choice: { value: 'c-plus' } } } as any }));
            await click('Continue');
            await screen.findByText('Page 3 of 3');
            // the way back is still offered on a page of the reviewed path
            await click('Back to review');
            await reviewHeading();
            expect(pageHeadings().map((h) => h.textContent)).toEqual(['Page 1: About you', 'Page 3']);
            expect(screen.queryByText('Anything else?')).not.toBeInTheDocument();
            await click('Submit response');
            expect(sentAnswers().extra).toBeUndefined();
        });

        it('continues at a page the respondent has not been through when the edit leads there', async () => {
            const data = FORM();
            // a fourth page; page 3 ends the form for "Yes", so it was never reached
            data.fields.push(page('s4', 3, [q('last', FieldTypes.SHORT_TEXT, 'One more thing')]));
            (data.fields[2].properties as any).jumps = [{ operator: LogicalOperator.AND, conditions: [{ fieldId: 'agree', fieldType: 'yes_no', comparison: 'IS_EQUAL', value: 'Yes' }], target: JUMP_TARGET_SUBMIT }];
            (data.fields[0].properties as any).jumps = [{ ...when('plan', 'multiple_choice', 'Plus'), target: 's4' }];
            start(data);
            await click('Continue');
            await screen.findByText('Page 2 of 4');
            await click('Continue');
            await screen.findByText('Last page');
            await click('Review your answers');
            await reviewHeading();
            await click(/^Edit Page 1: About you/);
            await screen.findByText('Page 1 of 4');
            act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, plan: { type: 'choice', choice: { value: 'c-plus' } } } as any }));
            await click('Back to review');
            await screen.findByText('Page 4 of 4');
            expect(screen.queryByRole('button', { name: 'Back to review' })).not.toBeInTheDocument();
        });

        it('shortens the path when the edit makes a page end the form', async () => {
            const data = FORM();
            (data.fields[0].properties!.jumps as any)[0].target = JUMP_TARGET_SUBMIT;
            start(data);
            await toReview();
            await click(/^Edit Page 1: About you/);
            await screen.findByText('Page 1 of 3');
            act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, plan: { type: 'choice', choice: { value: 'c-plus' } } } as any }));
            await click('Back to review');
            await reviewHeading();
            expect(pageHeadings().map((h) => h.textContent)).toEqual(['Page 1: About you']);
        });

        it('goes to a later page that the edit made incomplete', async () => {
            start();
            await toReview();
            await click(/^Edit Page 1: About you/);
            await screen.findByText('Page 1 of 3');
            // the name "Grace" makes page 2's question required
            act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, name: text('Grace'), extra: undefined } as any }));
            await click('Back to review');
            await screen.findByText('Page 2 of 3');
            expect(await screen.findByText('Please answer this question to continue.')).toBeInTheDocument();
        });

        it('checks the edited page before leaving it', async () => {
            start();
            await toReview();
            await click(/^Edit Page 1: About you/);
            await screen.findByText('Page 1 of 3');
            act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, name: undefined } as any }));
            await click('Back to review');
            expect(await screen.findByText('Please answer this question to continue.')).toBeInTheDocument();
            expect(responder.currentSlide).toBe(0);
        });
    });

    it('works out calculations again for the path as it now stands, after an edit shortened it', async () => {
        const data = FORM();
        data.fields[1].properties!.fields!.push(q('n', FieldTypes.NUMBER, 'How many?'));
        data.fields[2].properties!.fields!.push(q('total', FieldTypes.CALCULATED, 'Doubled', {}, { expression: { '*': [{ var: 'n' }, 2] } }));
        start(data, { ...ANSWERS, n: { type: 'number', number: 5 }, total: { type: 'number', number: 10 } });
        await toReview();
        expect(valueOf(section(2), 'Doubled')).toHaveTextContent('10');
        await click(/^Edit Page 1: About you/);
        await screen.findByText('Page 1 of 3');
        // a Plus plan skips page 2, where "How many?" is: the 5 no longer counts
        act(() => response.setFormResponse({ ...response.formResponse, answers: { ...response.formResponse.answers, plan: { type: 'choice', choice: { value: 'c-plus' } } } as any }));
        await click('Back to review');
        await reviewHeading();
        await vi.waitFor(() => expect(valueOf(section(2), 'Doubled')).not.toHaveTextContent('10'));
        expect(screen.queryByText('How many?')).not.toBeInTheDocument();
    });

    describe('a required question that is unanswered', () => {
        it('says so and links to its page', async () => {
            start(FORM(), { ...ANSWERS, name: undefined as any });
            await toReview().catch(() => undefined);
            // the first page does not let them pass without it: put them on the review directly
            act(() => responder.setResponderState({ ...responder.responderState, currentSlide: REVIEW_SLIDE, history: [0, 1, 2] }));
            await reviewHeading();
            expect(valueOf(section(0), 'Your name')).toHaveTextContent('Needs an answer');
            expect(screen.getByRole('status')).toHaveTextContent('1 answer needs your attention before you can submit.');
            // submitting goes to the page that needs it, not to the server
            await click('Submit response');
            expect(submit).not.toHaveBeenCalled();
            await screen.findByText('Page 1 of 3');
            expect(await screen.findByText('Please answer this question to continue.')).toBeInTheDocument();
            expect(screen.getByRole('button', { name: 'Back to review' })).toBeInTheDocument();
        });
    });

    describe('when the server says no', () => {
        it.each([
            ['form_closed', 'This form closed before your response was sent. Your answers were not sent.'],
            ['form_not_open', 'This form is not open yet, so your response was not sent. Your answers were not sent.'],
            ['form_full', 'This form received all the responses it accepts before yours was sent. Your answers were not sent.']
        ])('%s: says so by the button, keeps the answers and the page', async (code, message) => {
            submit.mockResolvedValue({ error: { status: 409, data: { code } } });
            start();
            await toReview();
            await click('Submit response');
            expect(await screen.findByRole('alert')).toHaveTextContent(message);
            expect(responder.currentSlide).toBe(REVIEW_SLIDE);
            expect(within(section(0)).getByText('Ada')).toBeInTheDocument();
            // the next attempt clears it and sends the same answers again
            submit.mockResolvedValue({ data: 'response-2' });
            await click('Submit response');
            expect(submit).toHaveBeenCalledTimes(2);
            await screen.findByRole('heading', { level: 1, name: 'Thank you' });
            expect(sentAnswers().name.text).toBe('Ada');
        });

        it('invalid answers: back to the first page with a problem, the way back to the review kept', async () => {
            submit.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_answers', errors: [{ fieldId: 'extra', rule: 'required' }] } } });
            start();
            await toReview();
            await click('Submit response');
            await screen.findByText('Page 2 of 3');
            expect(screen.getByRole('button', { name: 'Back to review' })).toBeInTheDocument();
            // pages and answers are as they were
            expect(responder.responderState.history).toEqual([0]);
            expect(response.formResponse.answers.name.text).toBe('Ada');
        });

        it('answers that map to no page: the message stays by the button, not only in a toast', async () => {
            submit.mockResolvedValue({ error: { status: 422, data: { code: 'invalid_answers', errors: [{ fieldId: 'a-question-this-form-has-no-page-for', rule: 'required' }] } } });
            start();
            await toReview();
            await click('Submit response');
            expect(await screen.findByRole('alert')).toHaveTextContent('Your answers could not be accepted, and we could not tell which one needs another look.');
            expect(responder.currentSlide).toBe(REVIEW_SLIDE);
            // the next attempt clears it
            submit.mockReturnValue(new Promise(() => {}));
            await click('Submit response');
            expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        });

        it('a failed request keeps the answers and says so', async () => {
            submit.mockResolvedValue({ error: { status: 500 } });
            start();
            await toReview();
            await click('Submit response');
            expect(await screen.findByRole('alert')).toHaveTextContent('Your response could not be sent. Please try again.');
            expect(responder.currentSlide).toBe(REVIEW_SLIDE);
        });
    });

    it('in a preview the submit shows the ending and sends nothing', async () => {
        preview = true;
        start();
        await toReview();
        await click('Submit response');
        await screen.findByRole('heading', { level: 1, name: 'Thank you' });
        expect(submit).not.toHaveBeenCalled();
    });

    it('is not there when the form does not ask for it: the last page submits', async () => {
        start({ ...FORM(), settings: {} });
        await click('Continue');
        await screen.findByText('Page 2 of 3');
        await click('Continue');
        await screen.findByText('Page 3 of 3');
        expect(screen.queryByRole('button', { name: 'Review your answers' })).not.toBeInTheDocument();
        await click('Submit response');
        expect(submit).toHaveBeenCalledTimes(1);
    });

    it('a one-page form has its review too', async () => {
        const data = FORM();
        data.fields = [data.fields[1]];
        start(data);
        expect(screen.getByRole('button', { name: 'Review your answers' })).toBeInTheDocument();
        await click('Review your answers');
        await reviewHeading();
        expect(within(section(0)).getByText(/Line one/)).toBeInTheDocument();
    });
});

describe.each([
    ['en', 'Review your answers'],
    ['nl', 'Controleer je antwoorden']
])('the review page passes axe (WCAG 2.1 A/AA) in %s', (lang, title) => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);
        submit.mockReset();
        preview = false;
        store.dispatch(setAuth({ id: 'user-1', email: 'someone@example.com' }));
    });
    afterEach(() => {
        window.history.replaceState(null, '', '/');
        store.dispatch(setAuth({ id: '', email: '' }));
    });

    it.each(['classic', 'leaflet'])('in the %s style, with a group, a file, a rule value, a long text and a missing answer', async (style) => {
        const data: any = { ...FORM(), theme: { ...ThemeColors[0], style } };
        start(data, { ...ANSWERS, children: { type: 'group', items: [{ 'child-name': text('Kim') }, { 'child-name': text('Noor') }] }, extra: text('x'.repeat(300)), agree: undefined as any });
        act(() => responder.setResponderState({ ...responder.responderState, currentSlide: REVIEW_SLIDE, history: [0, 1, 2] }));
        const heading = await screen.findByRole('heading', { level: 1, name: title });
        expect(await axeViolations(document, { page: true })).toEqual([]);
        expect(screen.getAllByRole('main')).toHaveLength(1);
        expect(screen.getAllByRole('heading', { level: 1 })).toEqual([heading]);
        // the page's language is the respondent's
        expect(document.querySelector(`[lang="${lang}"]`)).not.toBeNull();
    });
});
