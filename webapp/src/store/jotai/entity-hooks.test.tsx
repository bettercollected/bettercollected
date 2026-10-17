import React from 'react';

import { act, render } from '@testing-library/react';
import { Provider, createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import form200 from '@app/test/fixtures/form-200.json';

import { useDocValue, useField, useFieldActions, usePage, usePageFieldIds, usePageIds, usePageShell } from './entity-hooks';
import useFormFieldsAtom, { UNDO_COALESCE_MS, builderActions, useBuilderActions } from './field-selectors';
import { builderFieldsAtom, canUndoAtom, docHistoryAtom, formDocAtom, resetFromServerAtom, undoAtom } from './form-document';

type Store = ReturnType<typeof createStore>;

const title = (text: string) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });

/** Renders `hook` in a component of its own; `seen` collects each render's value. */
function watch<T>(store: Store, hook: () => T) {
    const seen: T[] = [];
    function Probe() {
        seen.push(hook());
        return null;
    }
    render(
        <Provider store={store}>
            <Probe />
        </Provider>
    );
    return seen;
}

function loaded(): Store {
    const store = createStore();
    store.set(resetFromServerAtom, structuredClone(form200) as any);
    return store;
}

const builderField = (store: Store, pageIndex: number, fieldIndex: number) => store.get(builderFieldsAtom)[pageIndex].properties!.fields![fieldIndex];

describe('narrow hooks: unchanged entities keep their reference', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it('a title edit re-renders that question only', () => {
        const store = loaded();
        const edited = watch(store, () => useField('p03-q05'));
        const other = watch(store, () => useField('p03-q06'));
        const otherPage = watch(store, () => useField('p07-q01'));
        const before = { edited: edited.length, other: other.length, otherPage: otherPage.length };
        const otherValue = other.at(-1);
        const actions = actionsFromHook(store);

        act(() => void actions.updateTitle('p03-q05', title('Start date, please') as any));

        expect(edited.length).toBe(before.edited + 1);
        expect(edited.at(-1)?.title).toEqual(title('Start date, please'));
        expect(other.length).toBe(before.other);
        expect(otherPage.length).toBe(before.otherPage);
        expect(store.get(formDocAtom).fields![2].properties!.fields![5]).toBe(otherValue);
    });

    it('a page keeps its reference, its question ids and its shell while other pages change', () => {
        const store = loaded();
        const page = watch(store, () => usePage('page-07'));
        const ids = watch(store, () => usePageFieldIds('page-03'));
        const shell = watch(store, () => usePageShell('page-03'));
        const pageIds = watch(store, () => usePageIds());
        const counts = [page.length, ids.length, shell.length, pageIds.length];

        const actions = actionsFromHook(store);
        act(() => void actions.updateTitle('p03-q05', title('Start') as any));
        act(() => void actions.updateDescription('p03-q01', 'Why we ask'));

        // page 3 changed, but not the order of its questions nor its own settings
        expect([page.length, ids.length, shell.length, pageIds.length]).toEqual(counts);
        expect(shell.at(-1)?.properties?.fields).toBeUndefined();
        expect(shell.at(-1)?.properties?.layout).toBe(form200.fields[2].properties.layout);
    });

    it('the shell changes with the page settings, the ids with the order', () => {
        const store = loaded();
        const ids = watch(store, () => usePageFieldIds('page-03'));
        const shell = watch(store, () => usePageShell('page-03'));
        const [idCount, shellCount] = [ids.length, shell.length];

        act(() => void builderActions(store).updateSlideSectionTitle(2, 'Dates'));
        expect(shell.length).toBe(shellCount + 1);
        expect(shell.at(-1)?.properties?.sectionTitle).toBe('Dates');
        expect(ids.length).toBe(idCount);

        act(() => void builderActions(store).moveFieldToPage('p03-q01', 2, 1));
        expect(ids.length).toBe(idCount + 1);
        expect(ids.at(-1)?.slice(0, 2)).toEqual(['p03-q02', 'p03-q01']);
    });

    it('a derived value re-renders only when it changes', () => {
        const store = loaded();
        const count = watch(store, () => useDocValue((doc) => doc.fields?.length ?? 0, []));
        const renders = count.length;
        const actions = actionsFromHook(store);
        act(() => void actions.updateTitle('p03-q05', title('Start') as any));
        expect(count.length).toBe(renders);
        act(() => void builderActions(store).duplicateSlide(0));
        expect(count.at(-1)).toBe(form200.fields.length + 1);
    });
});

/** The actions a component would get from useFieldActions on this store. */
function actionsFromHook(store: Store) {
    let actions: ReturnType<typeof useFieldActions> | undefined;
    function Probe() {
        actions = useFieldActions();
        return null;
    }
    render(
        <Provider store={store}>
            <Probe />
        </Provider>
    );
    return actions!;
}

describe('useFieldActions and useBuilderActions', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it('have a stable identity and never re-render their component', () => {
        const store = loaded();
        const seen = watch(store, () => ({ field: useFieldActions(), builder: useBuilderActions() }));
        const renders = seen.length;
        act(() => void seen[0].field.updateTitle('p01-q01', title('Your full name') as any));
        act(() => void seen[0].builder.addChoiceField(1, 0));
        expect(seen.length).toBe(renders);
        const again = watch(store, () => ({ field: useFieldActions(), builder: useBuilderActions() }));
        expect(again[0].field).toBe(seen[0].field);
        expect(again[0].builder).toBe(seen[0].builder);
        expect(again[0].field.updateTitle).toBe(seen[0].field.updateTitle);
    });

    it('typing in one title is one undo step, and undo puts the title back', () => {
        const store = loaded();
        const actions = actionsFromHook(store);
        const before = store.get(formDocAtom).fields![2].properties!.fields![4].title;
        act(() => void actions.updateTitle('p03-q05', title('Start d') as any));
        act(() => void vi.advanceTimersByTime(UNDO_COALESCE_MS / 4));
        act(() => void actions.updateTitle('p03-q05', title('Start da') as any));
        act(() => void vi.advanceTimersByTime(UNDO_COALESCE_MS / 4));
        act(() => void actions.updateTitle('p03-q05', title('Start dat') as any));
        expect(store.get(docHistoryAtom).steps).toHaveLength(1);
        expect(store.get(docHistoryAtom).steps[0].coalesceKey).toBe('title:p03-q05');

        act(() => void store.set(undoAtom));
        expect(store.get(formDocAtom).fields![2].properties!.fields![4].title).toEqual(before);
        expect(builderField(store, 2, 4).title).toEqual(before);
        expect(store.get(canUndoAtom)).toBe(false);
    });

    it('keep the builder copy in step for the components that read it', () => {
        const store = loaded();
        const actions = actionsFromHook(store);
        let legacy: ReturnType<typeof useFormFieldsAtom> | undefined;
        function Legacy() {
            legacy = useFormFieldsAtom();
            return null;
        }
        render(
            <Provider store={store}>
                <Legacy />
            </Provider>
        );
        act(() => void actions.updateFieldPlaceholder('p01-q01', 'Jane Doe'));
        act(() => void actions.updateChoiceFieldValue('p01-q02', form200.fields[0].properties.fields[1].properties!.choices![0].id, 'Morning'));
        expect(legacy!.formFields[0].properties!.fields![0].properties!.placeholder).toBe('Jane Doe');
        expect(legacy!.formFields[0].properties!.fields![1].properties!.choices![0].value).toBe('Morning');
        // The copy is the builder's own: never the document's objects.
        expect(legacy!.formFields[0]).not.toBe(store.get(formDocAtom).fields![0]);
        // An older mutator still works on top.
        act(() => legacy!.updateFieldPlaceholder(0, 0, 'Jane'));
        expect(store.get(formDocAtom).fields![0].properties!.fields![0].properties!.placeholder).toBe('Jane');
    });

    it('use the coalesce keys of the builder mutators', () => {
        const store = loaded();
        const actions = actionsFromHook(store);
        const keys = () => store.get(docHistoryAtom).steps.map((step) => step.coalesceKey);
        const choiceId = form200.fields[0].properties.fields[1].properties!.choices![0].id;
        act(() => void actions.updateDescription('p01-q01', 'Shown on your receipt'));
        act(() => void actions.updateFieldPlaceholder('p01-q01', 'Jane Doe'));
        act(() => void actions.updateChoiceFieldValue('p01-q02', choiceId, 'Morning'));
        act(() => void actions.updateFieldProperty('p01-q01', 'whyWeAsk', 'To reply'));
        act(() => void actions.updateFieldValidations('p01-q01', { maxLength: 40, minLength: 2 }));
        act(() => void actions.updateFieldAttachment('p01-q01', { type: 'image', href: '' }));
        act(() => void actions.updateFieldLogic('p01-q04', undefined));
        expect(keys()).toEqual(['description:p01-q01', 'placeholder:p01-q01', `choice:p01-q02:${choiceId}`, 'property:p01-q01:whyWeAsk', 'validations:p01-q01:maxLength,minLength', 'attachment:p01-q01', 'logic:p01-q04']);
        expect(store.get(formDocAtom).fields![0].properties!.fields![3].properties?.logic).toBeUndefined();
    });

    it('make no undo step when nothing changes', () => {
        const store = loaded();
        const actions = actionsFromHook(store);
        const placeholder = form200.fields[0].properties.fields[0].properties?.placeholder ?? '';
        act(() => void actions.updateFieldPlaceholder('p01-q01', placeholder));
        act(() => void actions.updateTitle('p01-q01', structuredClone(store.get(formDocAtom).fields![0].properties!.fields![0].title)));
        act(() => void actions.updateTitle('missing', title('x') as any));
        expect(store.get(docHistoryAtom).steps).toHaveLength(0);
    });

    it('go through the builder copy when the ops engine refuses a change', () => {
        const store = loaded();
        const actions = actionsFromHook(store);
        // A node type the engine does not accept in a title.
        const odd = { type: 'doc', content: [{ type: 'mysteryNode', content: [{ type: 'text', text: 'Hi' }] }] };
        const copyBefore = store.get(builderFieldsAtom);
        const docBefore = store.get(formDocAtom);
        act(() => void actions.updateTitle('p01-q01', odd as any));

        // Refused by the engine: the step came from the builder copy being handed over.
        const step = store.get(docHistoryAtom).steps[0];
        expect(store.get(docHistoryAtom).steps).toHaveLength(1);
        expect(step.builderFields).toBeDefined();
        expect(store.get(formDocAtom).fields![0].properties!.fields![0].title).toEqual(odd);
        expect(builderField(store, 0, 0).title).toEqual(odd);
        // The copy was edited in place (its page objects kept) and handed over as a new array.
        const copyAfter = store.get(builderFieldsAtom);
        expect(copyAfter).not.toBe(copyBefore);
        copyAfter.forEach((page, i) => expect(page).toBe(copyBefore[i]));
        // The document was not: its earlier version is as it was, and the copy shares nothing with it.
        expect(docBefore.fields![0].properties!.fields![0].title).toEqual(form200.fields[0].properties.fields[0].title);
        expect(builderField(store, 0, 0)).not.toBe(store.get(formDocAtom).fields![0].properties!.fields![0]);
        expect(builderField(store, 0, 0).title).not.toBe(store.get(formDocAtom).fields![0].properties!.fields![0].title);

        act(() => void store.set(undoAtom));
        expect(store.get(formDocAtom).fields![0].properties!.fields![0].title).toEqual(form200.fields[0].properties.fields[0].title);
        expect(builderField(store, 0, 0).title).toEqual(form200.fields[0].properties.fields[0].title);
    });

    it('act on a repeating group question by id', () => {
        const store = loaded();
        const actions = actionsFromHook(store);
        const group = store
            .get(formDocAtom)
            .fields!.flatMap((page) => page.properties?.fields ?? [])
            .find((field) => field.type === FieldTypes.GROUP) as StandardFormFieldDto;
        const child = group.properties!.fields![0];
        act(() => void actions.updateTitle(child.id, title('Child name') as any));
        const seen = watch(store, () => useField(child.id));
        expect(seen.at(-1)?.title).toEqual(title('Child name'));
    });
});
