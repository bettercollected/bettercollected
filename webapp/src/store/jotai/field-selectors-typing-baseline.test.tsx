import React from 'react';

import { act, render } from '@testing-library/react';
import { JSONContent } from '@tiptap/react';
import { Provider } from 'jotai';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import form200 from '@app/test/fixtures/form-200.json';
import { RenderCounter, RenderCounts, createRenderCounts } from '@app/test/render-counter';

import useFormFieldsAtom from './field-selectors';

/**
 * Baseline of typing in a question title on a large form (20 pages x 10
 * questions, test/fixtures/form-200.json) through the current setters:
 * time per update, how many subscribers re-render, and whether the whole
 * form is serialised or cloned on each keystroke. It records today's
 * numbers (printed with the test output); the asserts only check that the
 * measurement itself works.
 */

const UPDATES = 40;
const slides = (): StandardFormFieldDto[] => structuredClone(form200.fields) as unknown as StandardFormFieldDto[];
const questions = (fields: StandardFormFieldDto[]) => fields.flatMap((slide, slideIndex) => (slide.properties?.fields ?? []).map((field, fieldIndex) => ({ id: field.id, slideIndex, fieldIndex })));

type Api = ReturnType<typeof useFormFieldsAtom>;

// A canvas question: subscribes to the fields like the builder's field views do.
function Question({ slideIndex, fieldIndex }: { slideIndex: number; fieldIndex: number }) {
    const { formFields } = useFormFieldsAtom();
    const field = formFields[slideIndex]?.properties?.fields?.[fieldIndex];
    return <span>{typeof field?.title === 'string' ? field.title : field?.id}</span>;
}

function Editor({ onApi }: { onApi: (api: Api) => void }) {
    const api = useFormFieldsAtom();
    onApi(api);
    return null;
}

function mount(counts: RenderCounts) {
    let api: Api | undefined;
    const all = questions(slides());
    render(
        <Provider>
            <Editor onApi={(a) => (api = a)} />
            {all.map((q) => (
                <RenderCounter key={q.id} id={q.id} counts={counts}>
                    <Question slideIndex={q.slideIndex} fieldIndex={q.fieldIndex} />
                </RenderCounter>
            ))}
        </Provider>
    );
    act(() => api!.initFormFields(slides()));
    return { api: () => api!, questionCount: all.length };
}

const title = (text: string): JSONContent => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });

const isWholeForm = (value: unknown) => Array.isArray(value) && value.length === form200.fields.length;

describe('typing baseline on form-200 (current field-selectors setters)', () => {
    afterEach(() => vi.restoreAllMocks());

    it('measures one title update', () => {
        const counts = createRenderCounts();
        const { api, questionCount } = mount(counts);
        expect(questionCount).toBe(200);

        const stringify = vi.spyOn(JSON, 'stringify');
        const clone = typeof globalThis.structuredClone === 'function' ? vi.spyOn(globalThis, 'structuredClone') : undefined;
        counts.reset();

        const times: number[] = [];
        let text = 'Section 3';
        for (let i = 0; i < UPDATES; i++) {
            text += 'x';
            const start = performance.now();
            act(() => api().updateTitle(4, 2, title(text)));
            times.push(performance.now() - start);
        }

        const wholeFormStringify = stringify.mock.calls.filter(([value]) => isWholeForm(value)).length;
        const wholeFormClone = clone ? clone.mock.calls.filter(([value]) => isWholeForm(value)).length : 0;
        const sorted = [...times].sort((a, b) => a - b);
        const baseline = {
            updates: UPDATES,
            msPerUpdateMedian: Number(sorted[Math.floor(sorted.length / 2)].toFixed(2)),
            msPerUpdateP95: Number(sorted[Math.floor(sorted.length * 0.95) - 1].toFixed(2)),
            subscribersRenderedPerUpdate: counts.total() / UPDATES,
            distinctSubscribersRendered: counts.rendered().length,
            wholeFormJsonStringifyPerUpdate: wholeFormStringify / UPDATES,
            wholeFormStructuredClonePerUpdate: wholeFormClone / UPDATES
        };
        console.info('[typing-baseline]', JSON.stringify(baseline));

        expect(api().formFields[2].properties!.fields![4].title).toEqual(title(text));
        expect(counts.total()).toBeGreaterThan(0);
    });
});
