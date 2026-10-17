// The respondent page enforces a question's answer rules (min/max length,
// format, number range, whole numbers, number of options) on Continue, in
// the respondent's language.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { FORMAT_PRESETS, INTEGER_PATTERN } from '@app/utils/answer-rules';

import FormSlide from './form-slide';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const POSTCODE = FORMAT_PRESETS.find((preset) => preset.id === 'postcode_nl')!.pattern;

const field = (id: string, type: FieldTypes, validations: StandardFormFieldDto['validations'], properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id, index: 0, type, title: `Question ${id}`, validations, properties });
const slide = (id: string, index: number, fields: StandardFormFieldDto[], properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields, ...properties } });

let responder: ReturnType<typeof useResponderState> | null = null;
function Page() {
    responder = useResponderState();
    return <FormSlide index={0} isPreviewMode />;
}

const open = (fields: StandardFormFieldDto[], pageProperties: StandardFormFieldDto['properties'] = {}, pages = 2) => {
    store.dispatch(
        setForm({
            formId: `rules-${Math.random()}`,
            title: 'Rules',
            fields: [slide('s1', 0, fields, pageProperties), ...Array.from({ length: pages - 1 }, (_, i) => slide(`s${i + 2}`, i + 1, []))]
        })
    );
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page />
            </Provider>
        </ReduxProvider>
    );
};

// The input reports its value after a 300 ms debounce (FieldInputWrapper).
const type = async (id: string, value: string) => {
    act(() => void fireEvent.change(document.getElementById(`input-field-${id}`)!, { target: { value } }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
};
const withLang = (lang: string) => window.history.replaceState(null, '', `/acme/forms/f1?lang=${lang}`);

describe('answer rules on the respondent page', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('a postcode in the wrong format blocks Continue with a message that says what to enter', async () => {
        withLang('en');
        open([field('pc', FieldTypes.SHORT_TEXT, { regex: POSTCODE })]);
        const next = await screen.findByRole('button', { name: 'Continue' });
        const start = responder!.responderState.currentSlide;

        await type('pc', 'not a postcode');
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Enter a Dutch postcode, for example 1234 AB.')).toBeInTheDocument();
        expect(responder!.responderState.currentSlide).toBe(start);

        // Fixing the answer takes the message away straight away.
        await type('pc', '1234 AB');
        expect(screen.queryByText('Enter a Dutch postcode, for example 1234 AB.')).toBeNull();
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Continue' })));
        expect(responder!.responderState.currentSlide).toBe(start + 1);
    });

    it('length limits, in Dutch with ?lang=nl', async () => {
        withLang('nl');
        open([field('name', FieldTypes.SHORT_TEXT, { minLength: 3, maxLength: 5 })]);
        const next = await screen.findByRole('button', { name: 'Volgende' });
        await type('name', 'ab');
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Gebruik minstens 3 tekens.')).toBeInTheDocument();
        await type('name', 'abcdefg');
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Gebruik hooguit 5 tekens.')).toBeInTheDocument();
    });

    it('number range and whole numbers', async () => {
        withLang('en');
        open([field('n', FieldTypes.NUMBER, { minValue: 1, maxValue: 10, regex: INTEGER_PATTERN })]);
        const next = await screen.findByRole('button', { name: 'Continue' });
        await type('n', '12');
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Enter a number of 10 or less.')).toBeInTheDocument();
        await type('n', '2.5');
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Enter a whole number, without decimals.')).toBeInTheDocument();
    });

    it('an empty optional answer is not checked; a missing required one still says so', async () => {
        withLang('en');
        open([field('opt', FieldTypes.SHORT_TEXT, { minLength: 3 }), { ...field('req', FieldTypes.SHORT_TEXT, { required: true, minLength: 3 }), index: 1 }]);
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Continue' })));
        expect(await screen.findByText('Please answer this question to continue.')).toBeInTheDocument();
        expect(screen.queryByText('Use at least 3 characters.')).toBeNull();
    });
});
