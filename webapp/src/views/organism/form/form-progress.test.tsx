// The progress bar says what "Page x of y" says: page 1 of 3 is a third of the
// way, not the 40% it showed when the welcome and ending pages counted as steps.
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

import Form from './form';

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
});
