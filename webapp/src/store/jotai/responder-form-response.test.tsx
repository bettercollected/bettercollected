import React from 'react';

import { act, renderHook } from '@testing-library/react';
import { Provider } from 'jotai';
import { describe, expect, it } from 'vitest';

import { useFormResponse } from './responder-form-response';

const setup = () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => <Provider>{children}</Provider>;
    return renderHook(() => useFormResponse(), { wrapper });
};

/**
 * The answer shapes below are load-bearing: the conditional-logic evaluator
 * (getComparableAnswerValue) and the submit payload both read these exact slots.
 */
describe('answer setters produce the shapes the evaluator reads', () => {
    it('text answers', () => {
        const { result } = setup();
        act(() => result.current.addFieldTextAnswer('f1', 'hello'));
        expect(result.current.formResponse.answers.f1).toEqual({ type: 'text', text: 'hello' });
    });

    it('boolean (Yes/No) answers', () => {
        const { result } = setup();
        act(() => result.current.addFieldBooleanAnswer('f1', true));
        expect(result.current.formResponse.answers.f1).toMatchObject({ boolean: true });
    });

    it('single-choice answers store choice.value', () => {
        const { result } = setup();
        act(() => result.current.addFieldChoiceAnswer('f1', 'Red'));
        expect(result.current.formResponse.answers.f1).toEqual({ type: 'choice', choice: { value: 'Red' } });
    });

    it('multi-select answers store choices.values', () => {
        const { result } = setup();
        act(() => result.current.addFieldChoicesAnswer('f1', ['Red', 'Blue']));
        expect(result.current.formResponse.answers.f1.choices?.values).toEqual(['Red', 'Blue']);
    });

    it('number answers', () => {
        const { result } = setup();
        act(() => result.current.addFieldNumberAnswer('f1', 42));
        expect(result.current.formResponse.answers.f1).toMatchObject({ number: 42 });
    });

    it('answers accumulate per field id without clobbering others', () => {
        const { result } = setup();
        act(() => result.current.addFieldTextAnswer('f1', 'a'));
        act(() => result.current.addFieldTextAnswer('f2', 'b'));
        act(() => result.current.addFieldTextAnswer('f1', 'c')); // overwrite same field
        expect(result.current.formResponse.answers.f1.text).toBe('c');
        expect(result.current.formResponse.answers.f2.text).toBe('b');
    });
});

describe('validation state', () => {
    it('setInvalidFields stores per-field invalidations for QuestionWrapper', () => {
        const { result } = setup();
        act(() => result.current.setInvalidFields({ f1: [0] } as any));
        expect(result.current.formResponse.invalidFields?.f1).toBeDefined();
    });
});
