import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider, useAtomValue, useSetAtom } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes } from '@app/models/dtos/form';
import { useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { docHistoryAtom, resetFromServerAtom } from '@app/store/jotai/form-document';
import { store } from '@app/store/store';

import ThankYouSlide from './thankyou-page';
import WelcomeSlide from './welcome-page';

const loadedForm = () => ({
    formId: 'form-1',
    title: 'Check-in',
    welcomePage: { title: 'Check-in', description: 'Hello there' },
    thankyouPage: [{ id: 'ending-1', title: 'Thanks', message: 'Done.' }],
    fields: [{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [] } }]
});

const seen: { builder?: ReturnType<typeof useFormFieldsAtom>; form?: ReturnType<typeof useFormState>; ending?: ReturnType<typeof useActiveThankYouPageComponent>; steps?: number } = {};

function Editor({ page }: { page: 'welcome' | 'ending' }) {
    const builder = useFormFieldsAtom();
    const form = useFormState();
    const ending = useActiveThankYouPageComponent();
    const steps = useAtomValue(docHistoryAtom).steps.length;
    const reset = useSetAtom(resetFromServerAtom);
    const [loaded, setLoaded] = React.useState(false);
    React.useEffect(() => {
        seen.builder = builder;
        seen.form = form;
        seen.ending = ending;
        seen.steps = steps;
    });
    React.useEffect(() => {
        reset(loadedForm() as any);
        setLoaded(true);
    }, []);
    if (!loaded) return null;
    return page === 'welcome' ? <WelcomeSlide /> : <ThankYouSlide />;
}

function renderPage(page: 'welcome' | 'ending') {
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Editor page={page} />
            </Provider>
        </ReduxProvider>
    );
}

describe('the welcome page in the builder', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it('showing it writes nothing: no undo step, the loaded text shown', async () => {
        renderPage('welcome');
        await act(async () => vi.advanceTimersByTimeAsync(1000));
        expect(seen.steps).toBe(0);
        expect(seen.builder!.canUndo).toBe(false);
        expect((screen.getByLabelText('Description') as HTMLTextAreaElement).value).toBe('Hello there');
    });

    it('typing in its description is one undo step, and undo shows the loaded text again', async () => {
        renderPage('welcome');
        for (const text of ['Hello there!', 'Hello there!!']) {
            fireEvent.change(screen.getByLabelText('Description'), { target: { value: text } });
            await act(async () => vi.advanceTimersByTimeAsync(100));
        }
        expect(seen.steps).toBe(1);
        await act(async () => seen.builder!.undo());
        expect(seen.form!.formState.welcomePage?.description).toBe('Hello there');
        expect((screen.getByLabelText('Description') as HTMLTextAreaElement).value).toBe('Hello there');
    });
});

describe('the ending page in the builder', () => {
    it('shows the default ending when the selected one is gone, without crashing', async () => {
        renderPage('ending');
        await act(async () => seen.ending!.setActiveThankYouPageComponent({ id: 'ending-5', index: 5 }));
        expect(screen.getByRole('textbox', { name: /title/i })).toBeInTheDocument();
    });
});
