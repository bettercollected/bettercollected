// Focus on a page change with the real page transition: while the old page
// slides out, both pages are mounted, and focus must land in the new one.
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

import Form from './form';

vi.mock('next/navigation', () => ({ usePathname: () => '/acme/forms/f1', useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ RenderImage: () => null, default: () => null }));
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


describe('focus on a page change, with the page transition', () => {
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
        // the old page is still on screen, sliding out
        expect(screen.queryByRole('textbox', { name: 'Your name' })).toBeInTheDocument();
        await waitFor(() => expect(document.activeElement).not.toBe(document.body), { timeout: 3000 });
        expect(document.activeElement).toHaveTextContent('Page 2 of 2');
        expect(document.activeElement).toHaveAttribute('tabindex', '-1');

        await act(async () => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));
        await screen.findByRole('heading', { level: 1, name: 'Thank you' }, { timeout: 5000 });
        await waitFor(() => expect(document.activeElement).not.toBe(document.body), { timeout: 3000 });
        expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1, name: 'Thank you' }));
    });
});
