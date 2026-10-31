import React from 'react';

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NO_RULES } from '@app/lib/field-rules';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';

import { DERIVED_WRITES_MAX, useDerivedAnswers } from './use-derived-answers';

const derive = vi.hoisted(() => vi.fn());

// A form whose derived values never settle (no such form can be saved any more:
// the guard is for whatever else could), by an evaluator that swaps two answers.
vi.mock('@app/lib/field-rules', async (importOriginal) => ({ ...(await importOriginal<typeof import('@app/lib/field-rules')>()), withDerivedAnswers: derive }));

const slides = [
    {
        id: 'p1',
        index: 0,
        type: FieldTypes.SLIDE,
        properties: { fields: [{ id: 't1', index: 0, type: FieldTypes.SHORT_TEXT, title: 't1', properties: { rules: [{ id: 'r', when: { expression: true }, then: { readOnly: true } }] } }] }
    }
] as StandardFormFieldDto[];

const text = (value: string) => ({ type: 'text', text: value });
let seen: string[] = [];

function Page() {
    useDerivedAnswers(slides);
    const { addFieldTextAnswer, setFormResponse, formResponse } = useFormResponse();
    const answers = formResponse.answers;
    React.useEffect(() => {
        seen.push(JSON.stringify(answers ?? {}));
    }, [answers]);
    return (
        <>
            <button onClick={() => setFormResponse({ formId: '', answers: { ping: text('a'), pong: text('b') } as any })}>seed</button>
            <button onClick={() => addFieldTextAnswer('mine', 'typed')}>type</button>
        </>
    );
}

describe('useDerivedAnswers', () => {
    beforeEach(() => {
        seen = [];
        derive.mockReset();
        derive.mockImplementation((_slides, answers) => ({ answers: { ...answers, ping: answers.pong, pong: answers.ping }, states: NO_RULES }));
    });
    afterEach(cleanup);

    const start = async () => {
        render(
            <Provider>
                <Page />
            </Provider>
        );
        await act(async () => fireEvent.click(screen.getByText('seed')));
        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 50));
        });
    };

    it('stops after a bounded number of writes that no answer of the respondent caused', async () => {
        await start();
        // the first state, the seed, and DERIVED_WRITES_MAX swaps at most (without the guard it never stops)
        expect(seen.length).toBeGreaterThan(DERIVED_WRITES_MAX / 2);
        expect(seen.length).toBeLessThanOrEqual(DERIVED_WRITES_MAX + 3);
        const settled = seen.length;
        await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 50));
        });
        expect(seen.length).toBe(settled);
    });

    it('starts again when the respondent answers something', async () => {
        await start();
        const before = seen.length;
        await act(async () => fireEvent.click(screen.getByText('type')));
        expect(seen.length).toBeGreaterThan(before + DERIVED_WRITES_MAX / 2);
        expect(seen.length).toBeLessThanOrEqual(before + DERIVED_WRITES_MAX + 3);
    });
});
