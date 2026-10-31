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
import { useFormResponse } from '@app/store/jotai/responder-form-response';
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

describe('date range and tags answers on the respondent page', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    function Seeded({ answers }: { answers: Record<string, any> }) {
        const { setFormResponse, formResponse } = useFormResponse();
        const [ready, setReady] = React.useState(false);
        React.useEffect(() => {
            setFormResponse({ ...formResponse, answers });
            setReady(true);
            // eslint-disable-next-line react-hooks/exhaustive-deps
        }, []);
        return ready ? <Page /> : null;
    }
    const openWith = (fields: StandardFormFieldDto[], answers: Record<string, any>) => {
        store.dispatch(setForm({ formId: `range-${Math.random()}`, title: 'Rules', fields: [slide('s1', 0, fields), slide('s2', 1, [])] }));
        return render(
            <ReduxProvider store={store}>
                <Provider>
                    <Seeded answers={answers} />
                </Provider>
            </ReduxProvider>
        );
    };
    const stay = (start: string, end: string) => ({ s: { type: 'date_range', date_range: { start, end } } });

    it('a range with only its start blocks Continue and asks for the end, in English and Dutch', async () => {
        withLang('en');
        const first = openWith([field('s', FieldTypes.DATE_RANGE, {})], stay('2026-11-03', ''));
        const next = await screen.findByRole('button', { name: 'Continue' });
        const start = responder!.responderState.currentSlide;
        act(() => void fireEvent.click(next));
        expect(await screen.findByRole('alert')).toHaveTextContent('Choose both the start and the end.');
        expect(responder!.responderState.currentSlide).toBe(start);
        first.unmount();
        withLang('nl');
        openWith([field('s', FieldTypes.DATE_RANGE, {})], stay('2026-11-03', ''));
        const volgende = await screen.findByRole('button', { name: 'Volgende' });
        act(() => void fireEvent.click(volgende));
        expect(await screen.findByRole('alert')).toHaveTextContent('Kies zowel het begin als het einde.');
    });

    it('a range whose end is before its start blocks Continue', async () => {
        withLang('en');
        openWith([field('s', FieldTypes.DATE_RANGE, {})], stay('2026-11-07', '2026-11-03'));
        expect(await screen.findByRole('alert')).toHaveTextContent('The end is before the start.');
        const start = responder!.responderState.currentSlide;
        act(() => void fireEvent.click(screen.getByRole('button', { name: 'Continue' })));
        expect(responder!.responderState.currentSlide).toBe(start);
    });

    it('a finished range lets the respondent go on', async () => {
        withLang('en');
        openWith([field('s', FieldTypes.DATE_RANGE, {})], stay('2026-11-03', '2026-11-07'));
        const next = await screen.findByRole('button', { name: 'Continue' });
        const start = responder!.responderState.currentSlide;
        act(() => void fireEvent.click(next));
        expect(responder!.responderState.currentSlide).toBe(start + 1);
    });

    it('a required range left empty says so with the page’s own message', async () => {
        withLang('en');
        openWith([field('s', FieldTypes.DATE_RANGE, { required: true })], {});
        const next = await screen.findByRole('button', { name: 'Continue' });
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Please answer this question to continue.')).toBeInTheDocument();
    });

    it('too few tags block Continue, in English and Dutch, and adding one takes the message away', async () => {
        withLang('en');
        const first = openWith([field('t', FieldTypes.TAGS, { minChoices: 2 })], { t: { type: 'tags', tags: ['one'] } });
        const next = await screen.findByRole('button', { name: 'Continue' });
        const start = responder!.responderState.currentSlide;
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Enter at least 2 tags.', { selector: 'span' })).toBeInTheDocument();
        expect(responder!.responderState.currentSlide).toBe(start);
        const input = document.getElementById('tags-input-t')!;
        act(() => void fireEvent.change(input, { target: { value: 'two' } }));
        act(() => void fireEvent.keyDown(input, { key: 'Enter' }));
        expect(screen.queryByText('Enter at least 2 tags.', { selector: 'span' })).toBeNull();
        first.unmount();
        withLang('nl');
        openWith([field('t', FieldTypes.TAGS, { maxChoices: 1 })], { t: { type: 'tags', tags: ['a', 'b'] } });
        const volgende = await screen.findByRole('button', { name: 'Volgende' });
        act(() => void fireEvent.click(volgende));
        expect(await screen.findByText('Vul hooguit 1 tag in.', { selector: 'span' })).toBeInTheDocument();
    });

    it('a tag repeated in another case blocks Continue (the browser and the server differing, or an answer from a prefilled link)', async () => {
        withLang('en');
        openWith([field('t', FieldTypes.TAGS, {})], { t: { type: 'tags', tags: ['Vegan', 'vegan'] } });
        const next = await screen.findByRole('button', { name: 'Continue' });
        act(() => void fireEvent.click(next));
        expect(await screen.findByText('Each tag can be used once, whether written in capitals or not.', { selector: 'span' })).toBeInTheDocument();
    });
});
