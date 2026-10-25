// When the respondent moves to another page, focus moves with them: to
// "Page x of y" on a question page and to the title on the ending, so a
// keyboard user continues from the new page and a screen reader announces it
// (WCAG 2.4.3). Before, focus fell to the document when the old page left.
import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { moveOnFrom } from '@app/utils/scroll-utils';

import Form, { focusPageStart } from './form';

vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const text = (id: string, title: string): StandardFormFieldDto => ({ id, index: 0, type: FieldTypes.SHORT_TEXT, title, properties: { fields: [] }, validations: { required: false } });
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


describe('focus on a page change', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('lands on "Page 2 of 2" after Continue, and on the ending title after submitting', async () => {
        store.dispatch(setForm({ formId: `pages-${Math.random()}`, title: 'Survey', fields: [page('s1', 0, text('a', 'Your name')), page('s2', 1, text('b', 'Your town'))], thankyouPage: [{ id: 'end', title: 'Thank you', isDefault: true }] } as any));
        render(
            <ReduxProvider store={store}>
                <Provider>
                    <Respondent />
                </Provider>
            </ReduxProvider>
        );
        await screen.findByRole('textbox', { name: 'Your name' }, { timeout: 5000 });
        const next = screen.getByRole('button', { name: 'Continue' });
        next.focus();
        await act(async () => void fireEvent.click(next));
        await screen.findByRole('textbox', { name: 'Your town' }, { timeout: 5000 });
        await waitFor(() => expect(document.activeElement).not.toBe(document.body), { timeout: 3000 });
        expect(document.activeElement).toHaveTextContent('Page 2 of 2');
        expect(document.activeElement).toHaveAttribute('tabindex', '-1');

        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        await screen.findByRole('heading', { level: 1, name: 'Thank you' }, { timeout: 5000 });
        await waitFor(() => expect(document.activeElement).not.toBe(document.body), { timeout: 3000 });
        expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1, name: 'Thank you' }));
    });
});

describe('focusPageStart', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('leaves focus that is already inside the new page', () => {
        document.body.innerHTML = '<div id="p"><span data-page-start tabindex="-1">Page 1 of 2</span><input id="q" /></div>';
        document.getElementById('q')!.focus();
        focusPageStart(document.getElementById('p'));
        expect(document.activeElement?.id).toBe('q');
    });

    it('falls back to the page title, out of the tab order and without a ring', () => {
        document.body.innerHTML = '<button id="old">Continue</button><div id="p"><h1>Thank you</h1></div>';
        document.getElementById('old')!.focus();
        focusPageStart(document.getElementById('p'));
        const title = document.querySelector('h1')!;
        expect(document.activeElement).toBe(title);
        expect(title).toHaveAttribute('tabindex', '-1');
        expect(title.classList.contains('outline-none')).toBe(true);
    });
});

describe('moving on after a choice', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    const page = () => {
        document.body.innerHTML = '<div id="q1"><button id="opt" role="radio">Yes</button></div><div id="q2"><textarea id="input-field-q2"></textarea></div><span id="start" tabindex="-1">Page 2 of 2</span>';
    };

    it('goes to the next question while the respondent is still at the answered one', () => {
        page();
        document.getElementById('opt')!.focus();
        moveOnFrom('q1', 'q2');
        expect(document.activeElement?.id).toBe('input-field-q2');
    });

    it('also when nothing has focus (a click in a browser that does not focus buttons)', () => {
        page();
        moveOnFrom('q1', 'q2');
        expect(document.activeElement?.id).toBe('input-field-q2');
    });

    it('stays put once focus has moved on, e.g. to the next page', () => {
        page();
        document.getElementById('start')!.focus();
        moveOnFrom('q1', 'q2');
        expect(document.activeElement?.id).toBe('start');
    });
});
