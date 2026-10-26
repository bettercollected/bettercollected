// Ratings and number scales: one answer as a radio group, chosen by pointer,
// arrows, Home, End or a digit; the chosen value shows in a mark as well as
// in colour; the keys never act outside the group.
import React from 'react';

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import axe from 'axe-core';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';
import { scaleIndexForKey } from '@app/views/atoms/scale-radio-group';
import { FormFieldComponent } from '@app/views/organism/form/form-slide';

vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const scale = (type: FieldTypes, properties: Partial<StandardFormFieldDto['properties']> = {}): StandardFormFieldDto => ({
    id: 'q',
    index: 0,
    type,
    title: 'How was it?',
    properties: { fields: [], ...properties }
});

const renderField = (f: StandardFormFieldDto) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <FormFieldComponent field={f} slideIndex={0} />
            </Provider>
        </ReduxProvider>
    );

describe('scaleIndexForKey', () => {
    const values = [1, 2, 3, 4, 5];
    const key = (k: string, mods: Partial<{ ctrlKey: boolean; altKey: boolean; metaKey: boolean }> = {}) => ({ key: k, ctrlKey: false, altKey: false, metaKey: false, ...mods });

    it('maps arrows (wrapping), Home, End and digits to an index', () => {
        expect(scaleIndexForKey(key('ArrowRight'), values, 4)).toBe(0);
        expect(scaleIndexForKey(key('ArrowLeft'), values, 0)).toBe(4);
        expect(scaleIndexForKey(key('ArrowDown'), values, 1)).toBe(2);
        expect(scaleIndexForKey(key('ArrowUp'), values, 1)).toBe(0);
        expect(scaleIndexForKey(key('Home'), values, 3)).toBe(0);
        expect(scaleIndexForKey(key('End'), values, 1)).toBe(4);
        expect(scaleIndexForKey(key('3'), values, 0)).toBe(2);
    });

    it('follows the reading direction for the horizontal arrows', () => {
        expect(scaleIndexForKey(key('ArrowLeft'), values, 1, true)).toBe(2);
        expect(scaleIndexForKey(key('ArrowRight'), values, 1, true)).toBe(0);
    });

    it('ignores a digit outside the scale, other keys and any modifier', () => {
        expect(scaleIndexForKey(key('9'), values, 0)).toBe(-1);
        expect(scaleIndexForKey(key('a'), values, 0)).toBe(-1);
        expect(scaleIndexForKey(key('ArrowRight', { ctrlKey: true }), values, 0)).toBe(-1);
        expect(scaleIndexForKey(key('2', { metaKey: true }), values, 0)).toBe(-1);
        expect(scaleIndexForKey(key('2', { altKey: true }), values, 0)).toBe(-1);
    });

    it('reads a scale that starts at 0', () => {
        expect(scaleIndexForKey(key('0'), [0, 1, 2, 3], 2)).toBe(0);
    });
});

describe('star rating', () => {
    it('is a radio group named by the question, one tab stop, with the stars as radios', () => {
        renderField(scale(FieldTypes.RATING, { steps: 5 }));
        expect(screen.getByRole('radiogroup', { name: 'How was it?' })).toBeDefined();
        const radios = screen.getAllByRole('radio');
        expect(radios.map((r) => r.getAttribute('aria-label'))).toEqual(['Rate 1 of 5', 'Rate 2 of 5', 'Rate 3 of 5', 'Rate 4 of 5', 'Rate 5 of 5']);
        expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1, -1, -1]);
        expect(screen.queryByRole('button')).toBeNull();
    });

    it('chooses by click, shows the answer in words with a mark, and the chosen star is the tab stop', () => {
        renderField(scale(FieldTypes.RATING, { steps: 5 }));
        expect(document.querySelector('[data-rating-readout]')!.textContent).toBe('');
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: 'Rate 4 of 5' }));
        });
        expect(screen.getByRole('radio', { name: 'Rate 4 of 5' }).getAttribute('aria-checked')).toBe('true');
        expect(screen.getByRole('radio', { name: 'Rate 3 of 5' }).getAttribute('aria-checked')).toBe('false');
        expect(screen.getByRole('radio', { name: 'Rate 4 of 5' }).tabIndex).toBe(0);
        const readout = document.querySelector('[data-rating-readout]')!;
        expect(readout.textContent).toBe('4 of 5');
        expect(readout.getAttribute('aria-hidden')).toBe('true');
        expect(readout.querySelector('svg')).not.toBeNull();
    });

    it('chooses with arrows and digits and moves focus, and ignores a key with a modifier', () => {
        renderField(scale(FieldTypes.RATING, { steps: 5 }));
        const first = screen.getByRole('radio', { name: 'Rate 1 of 5' });
        first.focus();
        act(() => {
            fireEvent.keyDown(first, { key: 'ArrowRight' });
        });
        expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Rate 2 of 5' }));
        expect(screen.getByRole('radio', { name: 'Rate 2 of 5' }).getAttribute('aria-checked')).toBe('true');
        act(() => {
            fireEvent.keyDown(document.activeElement!, { key: '5' });
        });
        expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Rate 5 of 5' }));
        expect(screen.getByRole('radio', { name: 'Rate 5 of 5' }).getAttribute('aria-checked')).toBe('true');
        act(() => {
            fireEvent.keyDown(document.activeElement!, { key: '1', ctrlKey: true });
        });
        expect(screen.getByRole('radio', { name: 'Rate 5 of 5' }).getAttribute('aria-checked')).toBe('true');
    });

    it('names its digit key for assistive tech', () => {
        renderField(scale(FieldTypes.RATING, { steps: 5 }));
        expect(screen.getByRole('radio', { name: 'Rate 3 of 5' }).getAttribute('aria-keyshortcuts')).toBe('3');
    });
});

describe('number scale', () => {
    it('is a radio group of its numbers', () => {
        renderField(scale(FieldTypes.LINEAR_RATING, { steps: 5 }));
        expect(screen.getByRole('radiogroup', { name: 'How was it?' })).toBeDefined();
        expect(screen.getAllByRole('radio').map((r) => r.textContent)).toEqual(['1', '2', '3', '4', '5']);
    });

    it('marks the chosen number with a check as well as its fill', () => {
        renderField(scale(FieldTypes.LINEAR_RATING, { steps: 5 }));
        expect(document.querySelector('[data-scale-check]')).toBeNull();
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: '3' }));
        });
        const chosen = screen.getByRole('radio', { name: '3' });
        expect(chosen.getAttribute('aria-checked')).toBe('true');
        expect(chosen.querySelector('[data-scale-check]')).not.toBeNull();
        expect(document.querySelectorAll('[data-scale-check]')).toHaveLength(1);
        // The check is decorative: the name stays the number.
        expect(chosen.querySelector('[data-scale-check]')!.getAttribute('aria-hidden')).toBe('true');
    });

    it('chooses with Home, End and digits', () => {
        renderField(scale(FieldTypes.LINEAR_RATING, { steps: 10 }));
        const radios = screen.getAllByRole('radio');
        radios[0].focus();
        act(() => {
            fireEvent.keyDown(radios[0], { key: 'End' });
        });
        expect(screen.getByRole('radio', { name: '10' }).getAttribute('aria-checked')).toBe('true');
        act(() => {
            fireEvent.keyDown(document.activeElement!, { key: '7' });
        });
        expect(screen.getByRole('radio', { name: '7' }).getAttribute('aria-checked')).toBe('true');
        // 10 has no digit key and so no shortcut named.
        expect(screen.getByRole('radio', { name: '10' }).getAttribute('aria-keyshortcuts')).toBeNull();
    });
});

// A harness that opens page 0 of a form (so a choice can move on to the next
// question) and lets a test read and prefill the answers.
let response: ReturnType<typeof useFormResponse> | null = null;
function Page({ fields }: { fields: StandardFormFieldDto[] }) {
    const { responderState, setResponderState } = useResponderState();
    response = useFormResponse();
    React.useEffect(() => {
        setResponderState({ ...responderState, currentSlide: 0 });
    }, []);
    return (
        <>
            {fields.map((f) => (
                <FormFieldComponent key={f.id} field={f} slideIndex={0} />
            ))}
        </>
    );
}

const open = (fields: StandardFormFieldDto[]) => {
    const placed = fields.map((f, index) => ({ ...f, index }));
    store.dispatch(setForm({ formId: `scales-${Math.random()}`, title: 'Scales', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: placed } }] } as any));
    const tree = (key: string) => (
        <ReduxProvider store={store}>
            <Provider>
                <Page key={key} fields={placed} />
            </Provider>
        </ReduxProvider>
    );
    const result = render(tree('first'));
    // The same page shown again with the answers kept: as when a respondent comes back to it.
    return { ...result, remount: () => result.rerender(tree('again')) };
};

const next = (): StandardFormFieldDto => ({ id: 'next', index: 1, type: FieldTypes.SHORT_TEXT, title: 'Anything else?' });
const rating = (type: FieldTypes, properties: Partial<StandardFormFieldDto['properties']> = {}, extra: Partial<StandardFormFieldDto> = {}) => ({ ...scale(type, properties), ...extra });
const prefill = (id: string, answer: object) => act(() => response!.setFormResponse({ ...response!.formResponse, answers: { ...(response!.formResponse.answers || {}), [id]: answer as any } }));

describe.each([
    ['star rating', FieldTypes.RATING, { steps: 5 }, 'Rate 3 of 5'],
    ['number scale', FieldTypes.LINEAR_RATING, { steps: 5 }, '3']
] as const)('%s moving on', (_name, type, properties, third) => {
    it('moves on to the next question after a click, and not after a key press', async () => {
        open([rating(type, properties), next()]);
        // A click: the next question's text field takes focus once the delay has passed.
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: third }));
        });
        await waitFor(() => expect(document.activeElement).toBe(document.getElementById('input-field-next')), { timeout: 2000 });
    });

    it('stays at the scale after a key press', async () => {
        open([rating(type, properties), next()]);
        const first = screen.getAllByRole('radio')[0];
        first.focus();
        act(() => {
            fireEvent.keyDown(first, { key: '3' });
        });
        await act(() => new Promise((resolve) => setTimeout(resolve, 450)));
        expect(document.activeElement).toBe(screen.getByRole('radio', { name: third }));
        expect(document.activeElement).not.toBe(document.getElementById('input-field-next'));
    });
});

describe('scales as answered controls', () => {
    it('the radio group of a required question is required, and invalid with the error', async () => {
        for (const [type, name] of [
            [FieldTypes.RATING, 'How was it?'],
            [FieldTypes.LINEAR_RATING, 'How was it?']
        ] as const) {
            const { unmount } = open([rating(type, { steps: 5 }, { validations: { required: true } }), next()]);
            const group = screen.getByRole('radiogroup', { name });
            expect(group).toBeRequired();
            expect(group).not.toHaveAttribute('aria-invalid');
            act(() => response!.setInvalidFields({ q: ['REQUIRED'] }));
            await waitFor(() => expect(screen.getByRole('radiogroup', { name })).toHaveAttribute('aria-invalid', 'true'));
            expect(screen.getByRole('radiogroup', { name }).getAttribute('aria-describedby')).toBeTruthy();
            unmount();
        }
    });

    it('stores a star rating as 1 to n and a scale as its own number', () => {
        open([rating(FieldTypes.RATING, { steps: 5 }), { ...scale(FieldTypes.LINEAR_RATING, { startFrom: 0, steps: 10 }), id: 'nps' }]);
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: 'Rate 1 of 5' }));
        });
        expect(response!.formResponse.answers!.q.number).toBe(1);
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: 'Rate 5 of 5' }));
        });
        expect(response!.formResponse.answers!.q.number).toBe(5);
        const zero = screen.getByRole('radio', { name: '0' });
        act(() => {
            fireEvent.click(zero);
        });
        expect(response!.formResponse.answers!.nps.number).toBe(0);
        expect(screen.getByRole('radio', { name: '0' }).getAttribute('aria-checked')).toBe('true');
        // 0 is a value: the first radio is the chosen one and the tab stop.
        expect(screen.getByRole('radio', { name: '0' }).tabIndex).toBe(0);
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: '10' }));
        });
        expect(response!.formResponse.answers!.nps.number).toBe(10);
    });

    it('shows a prefilled answer chosen, and editing it by keyboard replaces it', () => {
        open([rating(FieldTypes.RATING, { steps: 5 }), { ...scale(FieldTypes.LINEAR_RATING, { startFrom: 0, steps: 10 }), id: 'nps' }]);
        prefill('q', { type: 'RATING', number: 4 });
        prefill('nps', { type: 'LINEAR_RATING', number: 0 });
        expect(screen.getByRole('radio', { name: 'Rate 4 of 5' }).getAttribute('aria-checked')).toBe('true');
        expect(screen.getByRole('radio', { name: 'Rate 4 of 5' }).tabIndex).toBe(0);
        expect(document.querySelector('[data-rating-readout]')!.textContent).toBe('4 of 5');
        expect(screen.getByRole('radio', { name: '0' }).getAttribute('aria-checked')).toBe('true');
        const four = screen.getByRole('radio', { name: 'Rate 4 of 5' });
        four.focus();
        act(() => {
            fireEvent.keyDown(four, { key: 'ArrowLeft' });
        });
        expect(response!.formResponse.answers!.q.number).toBe(3);
        expect(screen.getByRole('radio', { name: 'Rate 3 of 5' }).getAttribute('aria-checked')).toBe('true');
        expect(screen.getByRole('radio', { name: 'Rate 4 of 5' }).getAttribute('aria-checked')).toBe('false');
    });

    it('the preview under a resting pointer follows a key choice, not the old rating', () => {
        open([rating(FieldTypes.RATING, { steps: 5 })]);
        const fills = () =>
            [1, 2, 3, 4, 5].map(
                (n) =>
                    screen
                        .getByRole('radio', { name: `Rate ${n} of 5` })
                        .querySelector('[fill]')
                        ?.getAttribute('fill') !== 'transparent'
            );
        const three = screen.getByRole('radio', { name: 'Rate 3 of 5' });
        act(() => {
            fireEvent.mouseOver(three);
            fireEvent.click(three);
        });
        expect(fills()).toEqual([true, true, true, false, false]);
        act(() => {
            fireEvent.keyDown(three, { key: 'End' });
        });
        expect(fills()).toEqual([true, true, true, true, true]);
    });

    it('does not play the selection motion for an answer that is already there, only for a change', () => {
        const view = open([rating(FieldTypes.RATING, { steps: 5 }), { ...scale(FieldTypes.LINEAR_RATING, { steps: 5 }), id: 'nps' }]);
        prefill('q', { type: 'RATING', number: 4 });
        prefill('nps', { type: 'LINEAR_RATING', number: 2 });
        view.remount();
        // Shown from a stored answer: no animation classes on the star, readout or check.
        expect(document.querySelector('.form-star-settle')).toBeNull();
        expect(document.querySelector('.form-choice-pop')).toBeNull();
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: 'Rate 5 of 5' }));
        });
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: '4' }));
        });
        // A respondent's own change does play it.
        expect(screen.getByRole('radio', { name: 'Rate 5 of 5' }).querySelector('.form-star-settle')).not.toBeNull();
        expect(screen.getByRole('radio', { name: '4' }).querySelector('.form-choice-pop')).not.toBeNull();
    });

    it('keeps the line under the stars even before an answer, so answering shifts nothing', () => {
        open([rating(FieldTypes.RATING, { steps: 5 })]);
        const line = document.querySelector('[data-rating-readout]')!;
        expect(line).not.toBeNull();
        expect(line.textContent).toBe('');
        expect(line.getAttribute('aria-hidden')).toBe('true');
        expect(line.className).toContain('h-[18px]');
    });

    it('passes axe with an answer chosen in each', async () => {
        const { container } = open([rating(FieldTypes.RATING, { steps: 5 }), { ...scale(FieldTypes.LINEAR_RATING, { steps: 5 }), id: 'nps', title: 'And the scale?' }]);
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: 'Rate 4 of 5' }));
        });
        act(() => {
            fireEvent.click(screen.getByRole('radio', { name: '2' }));
        });
        const results = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } });
        expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
    });
});
