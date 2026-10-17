import React, { Suspense } from 'react';

import { act, render } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import FormEditPage from '@app/app/(admin-portal)/(no-layout)/[workspace_name]/dashboard/forms/[form_id]/edit/_components/form-edit-page';
import { setForm } from '@app/store/forms/slice';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { formDocAtom } from '@app/store/jotai/form-document';
import { store as reduxStore } from '@app/store/store';
import form200 from '@app/test/fixtures/form-200.json';
import { ComponentRenderTracker, ComponentRenders, trackComponentRenders } from '@app/test/render-counter';

/**
 * Typing in one question title on the whole builder (navbar, outline,
 * canvas, inspector, autosave) with a 200-question form
 * (test/fixtures/form-200.json): which components render per keystroke and
 * how long a keystroke takes. Each keystroke goes through the title editor
 * and its save (the editor writes the title 300 ms after the last change).
 *
 * Rendered components are grouped into units: a canvas question with
 * everything inside it, an outline question row, and the inspector. Typing
 * may render the question typed in, its outline row and, when the
 * inspector shows that question, the inspector; nothing else.
 */

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/form-200/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));

const PAGE_ID = 'page-03';
const FIELD_ID = 'p03-q05';
const OTHER_FIELD_ID = 'p03-q02';
const KEYSTROKES = 30;
/** The title editor writes the title this long after the last change. */
const TITLE_DEBOUNCE_MS = 300;

const UNITS = {
    CanvasField: (props: { fieldId?: string }) => `field:${props.fieldId}`,
    OutlineQuestionRow: (props: { fieldId?: string }) => `row:${props.fieldId}`,
    PropertiesDrawer: () => 'inspector'
};

// jsdom has no layout; ProseMirror and the outline measure.
beforeAll(() => {
    const rects = () => ({ length: 0, item: () => null, [Symbol.iterator]: [][Symbol.iterator] }) as unknown as DOMRectList;
    const rect = () => ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) }) as DOMRect;
    Range.prototype.getClientRects = rects;
    Range.prototype.getBoundingClientRect = rect;
    if (!Element.prototype.getClientRects) Element.prototype.getClientRects = rects;
    if (!document.elementFromPoint) document.elementFromPoint = () => null;
    if (!(globalThis as any).ResizeObserver) {
        (globalThis as any).ResizeObserver = class {
            observe() {}
            unobserve() {}
            disconnect() {}
        };
    }
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
});

afterAll(() => {
    vi.useRealTimers();
});

afterEach(() => {
    reduxStore.dispatch(setForm({} as any));
});

type EditorElement = HTMLElement & { editor?: any };

async function mountBuilder(select: { field?: string } = {}) {
    const jotai = createStore();
    // The form has logic, so the builder would open on the Flow view: this
    // creator chose the page view.
    localStorage.setItem(`bc-default-view-${form200.formId}`, 'page');
    reduxStore.dispatch(setForm(structuredClone(form200) as any));
    const container = document.body.appendChild(document.createElement('div'));
    const tracker = trackComponentRenders(container, UNITS);
    const params = Promise.resolve({ form_id: form200.formId });
    await act(async () => {
        render(
            <ReduxProvider store={reduxStore}>
                <Provider store={jotai}>
                    <ComponentRenderTracker tracker={tracker}>
                        <Suspense fallback={null}>
                            <FormEditPage params={params} />
                        </Suspense>
                    </ComponentRenderTracker>
                </Provider>
            </ReduxProvider>,
            { container }
        );
    });
    for (let i = 0; i < 5; i++) {
        await act(async () => {
            await vi.advanceTimersByTimeAsync(10);
        });
    }
    await act(async () => {
        jotai.set(activeSlideAtom, { id: PAGE_ID, index: 2 });
        jotai.set(activeFieldAtom, select.field ? { id: select.field, index: 0 } : null);
        await vi.advanceTimersByTimeAsync(50);
    });
    const editor = container.querySelector<EditorElement>(`#title-editor-${FIELD_ID}`);
    if (!editor) console.info(container.innerHTML.slice(0, 3000));
    expect(editor?.editor).toBeTruthy();
    return { jotai, tracker, editor: editor! };
}

interface KeystrokeStats {
    msMedian: number;
    msP95: number;
    componentsPerKeystrokeMedian: number;
    unitsPerKeystrokeMax: number;
    units: string[];
}

const percentile = (values: number[], p: number) => {
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * p) - 1))];
};

/** Type `KEYSTROKES` characters at the end of the title, each followed by its save. */
function typeIntoTitle(editor: EditorElement, tracker: ComponentRenders): KeystrokeStats {
    const times: number[] = [];
    const components: number[] = [];
    const unitCounts: number[] = [];
    const units = new Set<string>();
    // The first keystroke opens the undo step; measure the ones after it.
    for (let i = 0; i <= KEYSTROKES; i++) {
        tracker.reset();
        const start = performance.now();
        act(() => {
            editor.editor
                .chain()
                .insertContentAt(editor.editor.state.doc.content.size - 1, 'x')
                .run();
        });
        act(() => {
            vi.advanceTimersByTime(TITLE_DEBOUNCE_MS);
        });
        const elapsed = performance.now() - start;
        if (i === 0) continue;
        times.push(elapsed);
        components.push(tracker.rendered.length);
        unitCounts.push(tracker.units().length);
        tracker.units().forEach((unit) => units.add(unit));
    }
    return {
        msMedian: Number(percentile(times, 0.5).toFixed(2)),
        msP95: Number(percentile(times, 0.95).toFixed(2)),
        componentsPerKeystrokeMedian: percentile(components, 0.5),
        unitsPerKeystrokeMax: Math.max(...unitCounts),
        units: Array.from(units).sort()
    };
}

const storedTitleText = (jotai: ReturnType<typeof createStore>) => {
    const page = jotai.get(formDocAtom).fields?.find((entry) => entry.id === PAGE_ID);
    return JSON.stringify(page?.properties?.fields?.find((field) => field.id === FIELD_ID)?.title);
};

describe('typing in a question title on the whole builder (form-200)', () => {
    it('renders only the question, its outline row and the inspector showing it', async () => {
        const { jotai, tracker, editor } = await mountBuilder({ field: FIELD_ID });
        const stats = typeIntoTitle(editor, tracker);
        console.info('[builder-typing] question selected', JSON.stringify(stats));

        expect(storedTitleText(jotai)).toContain('Start date' + 'x'.repeat(KEYSTROKES + 1));
        expect(stats.units).toEqual([`field:${FIELD_ID}`, 'inspector', `row:${FIELD_ID}`]);
        expect(stats.unitsPerKeystrokeMax).toBeLessThanOrEqual(3);
    });

    it('leaves the inspector alone when it shows another question', async () => {
        const { jotai, tracker, editor } = await mountBuilder({ field: OTHER_FIELD_ID });
        const stats = typeIntoTitle(editor, tracker);
        console.info('[builder-typing] other question selected', JSON.stringify(stats));

        expect(storedTitleText(jotai)).toContain('Start date' + 'x'.repeat(KEYSTROKES + 1));
        expect(stats.units).toEqual([`field:${FIELD_ID}`, `row:${FIELD_ID}`]);
    });
});
