// The progress bar says what "Page x of y" says: page 1 of 3 is a third of the
// way, not the 40% it showed when the welcome and ending pages counted as steps.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { JUMP_TARGET_SUBMIT, LogicalOperator } from '@app/models/types/form-builder-shared';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { pageEndsForm, progressPercent } from '@app/utils/form-progress';

import Form from './form';

vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const text = (id: string, title: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: { fields: [] }, validations: { required: false } });
const jump = (target: string, value = 'no') => ({ operator: LogicalOperator.AND, conditions: [{ fieldId: 'a', fieldType: FieldTypes.SHORT_TEXT, comparison: 'IS_EQUAL', value }], target });
const page = (id: string, index: number, field: StandardFormFieldDto): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, title: '', properties: { fields: [field] } });

function Respondent() {
    const { responderState, setResponderState } = useResponderState();
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(ThemeColors[0], { undoable: false });
        setResponderState({ ...responderState, currentSlide: 0, prevActiveSlide: 0 });
    }, []);
    return <Form isPreviewMode />;
}

// The bar is decorative (aria-hidden), so it is found by its role among hidden elements.
const bar = () => screen.getByRole('progressbar', { hidden: true });

describe('progress bar', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('fills x/y on page x of y, and the whole bar on the ending', async () => {
        store.dispatch(
            setForm({
                formId: `progress-${Math.random()}`,
                title: 'Survey',
                fields: [page('s1', 0, text('a', 'Your name')), page('s2', 1, text('b', 'Your town')), page('s3', 2, text('c', 'Your street'))],
                thankyouPage: [{ id: 'end', title: 'Thank you', isDefault: true }]
            } as any)
        );
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Respondent />
                </Provider>
            </ReduxProvider>
        );
        await screen.findByRole('textbox', { name: 'Your name' }, { timeout: 5000 });
        expect(screen.getByText('Page 1 of 3')).toBeDefined();
        expect(Number(bar().getAttribute('aria-valuenow'))).toBeCloseTo(100 / 3, 5);

        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Continue' })));
        await screen.findByRole('textbox', { name: 'Your town' }, { timeout: 5000 });
        expect(screen.getByText('Page 2 of 3')).toBeDefined();
        expect(Number(bar().getAttribute('aria-valuenow'))).toBeCloseTo(200 / 3, 5);

        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Continue' })));
        await screen.findByRole('textbox', { name: 'Your street' }, { timeout: 5000 });
        expect(Number(bar().getAttribute('aria-valuenow'))).toBe(100);

        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        await screen.findByRole('heading', { level: 1, name: 'Thank you' }, { timeout: 5000 });
        expect(Number(bar().getAttribute('aria-valuenow'))).toBe(100);
    });

    const show = (fields: StandardFormFieldDto[]) => {
        store.dispatch(setForm({ formId: `progress-${Math.random()}`, title: 'Survey', fields, thankyouPage: [{ id: 'end', title: 'Thank you', isDefault: true }] } as any));
        return render(
            <ReduxProvider store={store}>
                <Provider>
                    <Respondent />
                </Provider>
            </ReduxProvider>
        );
    };

    it('a one-page form shows a full bar', async () => {
        show([page('s1', 0, text('a', 'Your name'))]);
        await screen.findByRole('textbox', { name: 'Your name' }, { timeout: 5000 });
        expect(screen.getByText('Page 1 of 1')).toBeDefined();
        expect(Number(bar().getAttribute('aria-valuenow'))).toBe(100);
    });

    it('a page that ends the form early fills the bar once its answer says so', async () => {
        const first = page('s1', 0, text('a', 'Your name'));
        first.properties!.jumps = [jump(JUMP_TARGET_SUBMIT) as any];
        show([first, page('s2', 1, text('b', 'Your town')), page('s3', 2, text('c', 'Your street'))]);
        const input = await screen.findByRole('textbox', { name: 'Your name' }, { timeout: 5000 });
        // Still the way to page 2: a third of the way.
        expect(Number(bar().getAttribute('aria-valuenow'))).toBeCloseTo(100 / 3, 5);
        await act(async () => void fireEvent.change(input, { target: { value: 'no' } }));
        // The answer is stored after a short delay.
        await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
        expect(screen.getByText('Last page')).toBeDefined();
        expect(Number(bar().getAttribute('aria-valuenow'))).toBe(100);
    });
});

describe('progressPercent', () => {
    const slide = (id: string, jumps?: unknown[]): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SLIDE, properties: { fields: [text('a', 'A')], ...(jumps ? { jumps } : {}) } as any });

    it('is x/y on page x of y, and full on the ending', () => {
        const fields = [slide('s1'), slide('s2'), slide('s3'), slide('s4')];
        expect([0, 1, 2, 3].map((i) => progressPercent(fields, i, {}))).toEqual([25, 50, 75, 100]);
        expect(progressPercent(fields, -2, {})).toBe(100);
    });

    it('does not count the welcome page and never goes past full or below the first page', () => {
        const fields = [slide('s1'), slide('s2')];
        expect(progressPercent(fields, -1, {})).toBe(50);
        expect(progressPercent(fields, 5, {})).toBe(100);
        expect(progressPercent(undefined, 0, {})).toBe(100);
    });

    it('follows the page shown after a jump to another page, not the pages skipped', () => {
        // Page 1 jumps to page 3 (slide index 2): the header then says "Page 3 of 3".
        const fields = [slide('s1', [jump('s3')]), slide('s2'), slide('s3')];
        expect(progressPercent(fields, 0, { a: { text: 'no' } })).toBeCloseTo(100 / 3, 5);
        expect(progressPercent(fields, 2, { a: { text: 'no' } })).toBe(100);
    });

    it('is full on a page whose answers make it submit the form, and only then', () => {
        const fields = [slide('s1', [jump(JUMP_TARGET_SUBMIT)]), slide('s2'), slide('s3')];
        expect(progressPercent(fields, 0, {})).toBeCloseTo(100 / 3, 5);
        expect(pageEndsForm(fields, 0, {})).toBe(false);
        expect(pageEndsForm(fields, 0, { a: { text: 'no' } })).toBe(true);
        expect(progressPercent(fields, 0, { a: { text: 'no' } })).toBe(100);
        expect(progressPercent(fields, 0, { a: { text: 'yes' } })).toBeCloseTo(100 / 3, 5);
        // The welcome page and the ending are not pages that end the form.
        expect(pageEndsForm(fields, -1, { a: { text: 'no' } })).toBe(false);
    });
});
