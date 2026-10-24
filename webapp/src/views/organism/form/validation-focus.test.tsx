// After a page fails validation, focus lands on the first question with a
// problem, whatever its type, so keyboard and screen reader users reach it
// and hear its error (WCAG 3.3.1, 2.4.3). Before, only text fields took
// focus; a choice question left focus on the page itself.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
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
import { firstControlIn, scrollToDivById } from '@app/utils/scroll-utils';

import Form from './form';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const choices = (...values: string[]) => values.map((value, i) => ({ id: `choice-${i}`, value }));
const question = (id: string, index: number, type: FieldTypes, title: string, properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({
    id,
    index,
    type,
    title,
    properties: { fields: [], ...properties },
    validations: { required: true }
});

function Page() {
    const { responderState, setResponderState } = useResponderState();
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(ThemeColors.find((theme) => theme.title === 'Default')!, { undoable: false });
        setResponderState({ ...responderState, currentSlide: 0, prevActiveSlide: 0 });
    }, []);
    return <Form isPreviewMode />;
}

const open = (fields: StandardFormFieldDto[]) => {
    store.dispatch(setForm({ formId: `focus-${Math.random()}`, title: 'Survey', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, title: '', properties: { fields } }] } as any));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page />
            </Provider>
        </ReduxProvider>
    );
};

const submit = () => act(() => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));

describe('focus after a page fails validation', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('lands on the first option of a choice question', async () => {
        open([question('colour', 0, FieldTypes.MULTIPLE_CHOICE, 'Favourite colour?', { choices: choices('Red', 'Green') }), question('name', 1, FieldTypes.SHORT_TEXT, 'Your name')]);
        await screen.findByRole('radio', { name: 'Red' });
        submit();
        expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Red' }));
        expect(screen.getByRole('radiogroup', { name: /Favourite colour/ })).toHaveAttribute('aria-invalid', 'true');
    });

    it('lands on the first box of a several-answers question', async () => {
        open([question('fruit', 0, FieldTypes.MULTIPLE_CHOICE, 'Which fruits?', { choices: choices('Apple', 'Pear'), allowMultipleSelection: true })]);
        await screen.findByRole('checkbox', { name: 'Apple' });
        submit();
        expect(document.activeElement).toBe(screen.getByRole('checkbox', { name: 'Apple' }));
    });

    it('lands on yes/no', async () => {
        open([question('agree', 0, FieldTypes.YES_NO, 'Do you agree?', { choices: choices('Yes', 'No') }), question('name', 1, FieldTypes.SHORT_TEXT, 'Your name')]);
        await screen.findByRole('radio', { name: 'Yes' });
        submit();
        expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Yes' }));
    });

    it('lands on a text field, as before', async () => {
        open([question('name', 0, FieldTypes.SHORT_TEXT, 'Your name'), question('agree', 1, FieldTypes.YES_NO, 'Do you agree?', { choices: choices('Yes', 'No') })]);
        await screen.findByRole('textbox', { name: 'Your name' });
        submit();
        expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Your name' }));
    });
});

describe('scrollToDivById', () => {
    afterEach(() => {
        document.body.innerHTML = '';
    });

    it('moves on to a question without a text field and keeps focus where it was', () => {
        document.body.innerHTML = '<button id="here">Red</button><div id="next"><button role="radio" tabindex="0">Yes</button></div>';
        const here = document.getElementById('here')!;
        here.focus();
        scrollToDivById('next');
        expect(document.activeElement).toBe(here);
    });

    it("finds a radio group's tab stop, skipping options out of the tab order", () => {
        document.body.innerHTML = '<div id="q"><button role="radio" tabindex="-1">A</button><button role="radio" tabindex="0">B</button></div>';
        expect(firstControlIn(document.getElementById('q'))?.textContent).toBe('B');
        document.body.innerHTML = '<div id="q"><span tabindex="-1">x</span><button disabled>no</button><button>Pick a date</button></div>';
        expect(firstControlIn(document.getElementById('q'))?.textContent).toBe('Pick a date');
    });
});
