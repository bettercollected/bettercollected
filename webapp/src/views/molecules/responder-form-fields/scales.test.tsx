// Ratings and number scales: one answer as a radio group, chosen by pointer,
// arrows, Home, End or a digit; the chosen value shows in a mark as well as
// in colour; the keys never act outside the group.
import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
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
        expect(document.querySelector('[data-rating-readout]')).toBeNull();
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

    it('does not move on to the next question after a key press', () => {
        vi.useFakeTimers();
        try {
            const next = document.createElement('input');
            renderField(scale(FieldTypes.RATING, { steps: 5 }));
            document.body.appendChild(next);
            const first = screen.getByRole('radio', { name: 'Rate 1 of 5' });
            first.focus();
            act(() => {
                fireEvent.keyDown(first, { key: '3' });
                vi.advanceTimersByTime(500);
            });
            expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Rate 3 of 5' }));
            next.remove();
        } finally {
            vi.useRealTimers();
        }
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
