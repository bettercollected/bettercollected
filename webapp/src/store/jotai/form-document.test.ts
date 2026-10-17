import { createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { jsonEqual } from '@app/lib/form-ops/model';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import form200 from '@app/test/fixtures/form-200.json';

import { activeFieldAtom, activeSlideAtom } from './active-builder-component';
import { formStateAtom } from './form';
import {
    SET_FIELDS,
    SET_FORM_KEYS,
    UNDO_COALESCE_MS,
    applyRemoteAtom,
    builderFieldsAtom,
    canRedoAtom,
    canUndoAtom,
    commitBuilderFieldsAtom,
    dispatchAtom,
    docHistoryAtom,
    formDocAtom,
    latestStep,
    redoAtom,
    resetFromServerAtom,
    undoAtom,
    undoIfLatestAtom
} from './form-document';
import { fieldAtom, fieldIdsOfPageAtom, locationIndexAtom, pageAtom, pageIdsAtom } from './form-document-selectors';

type Store = ReturnType<typeof createStore>;

const title = (text: string) => ({ type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text }] }] });

let store: Store;
const doc = () => store.get(formDocAtom);
const field = (pageIdx: number, fieldIdx: number) => doc().fields[pageIdx].properties!.fields![fieldIdx];
const steps = () => store.get(docHistoryAtom).steps;

function load() {
    store = createStore();
    store.set(resetFromServerAtom, structuredClone(form200) as any);
}

/** The pages without `index` (which the engine renumbers itself). */
const withoutIndex = (fields: StandardFormFieldDto[]) => JSON.parse(JSON.stringify(fields, (key, value) => (key === 'index' ? undefined : value)));

describe('form document: dispatch, undo and redo', () => {
    beforeEach(load);

    it('loading starts with no history', () => {
        expect(doc().fields).toHaveLength(20);
        expect(store.get(canUndoAtom)).toBe(false);
        expect(store.get(canRedoAtom)).toBe(false);
        // The builder's copy is a separate copy of the pages.
        expect(store.get(builderFieldsAtom)).toEqual(doc().fields);
        expect(store.get(builderFieldsAtom)[0]).not.toBe(doc().fields[0]);
    });

    it('undoes and redoes question edits and form-level edits alike', () => {
        const before = doc();
        expect(store.set(dispatchAtom, { ops: [{ op: 'update_field', fieldId: 'p01-q01', patch: { title: 'Your name' } }] })).toBe(true);
        expect(store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'Renamed' }] })).toBe(true);
        expect(store.set(dispatchAtom, { ops: [{ op: 'update_theme', theme: { title: 'Ocean', primary: '#111827', secondary: '#1D4ED8', tertiary: '#2563EB', accent: '#DBEAFE' } }] })).toBe(true);
        expect(store.set(dispatchAtom, { ops: [{ op: 'set_hidden_fields', names: ['utm_source'] }] })).toBe(true);
        expect(steps()).toHaveLength(4);
        expect(doc().title).toBe('Renamed');
        expect(store.get(formStateAtom).theme?.title).toBe('Ocean');

        store.set(undoAtom);
        expect(doc().hiddenFields).toEqual(form200.hiddenFields);
        store.set(undoAtom);
        expect(doc().theme).toBeUndefined();
        store.set(undoAtom);
        expect(doc().title).toBe(form200.title);
        store.set(undoAtom);
        expect(jsonEqual(doc(), before)).toBe(true);
        expect(store.get(canUndoAtom)).toBe(false);

        store.set(redoAtom);
        expect(field(0, 0).title).toBe('Your name');
        // The builder's copy follows the document.
        expect(store.get(builderFieldsAtom)[0].properties!.fields![0].title).toBe('Your name');
        store.set(redoAtom);
        store.set(redoAtom);
        store.set(redoAtom);
        expect(doc().hiddenFields).toEqual(['utm_source']);
        expect(store.get(canRedoAtom)).toBe(false);
    });

    it('a refused batch changes nothing and makes no step', () => {
        const before = doc();
        expect(store.set(dispatchAtom, { ops: [{ op: 'update_field', fieldId: 'p01-q01', patch: { title: 'ok' } }, { op: 'remove_field', fieldId: 'no-such-field' }] })).toBe(false);
        expect(doc()).toBe(before);
        expect(steps()).toHaveLength(0);
    });

    it('a new edit after an undo drops the redo steps', () => {
        store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'One' }] });
        store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'Two' }] });
        store.set(undoAtom);
        store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'Three' }] });
        expect(store.get(canRedoAtom)).toBe(false);
        store.set(undoAtom);
        expect(doc().title).toBe('One');
    });

    it('endings are changed, undone and redone through ending ops', () => {
        const loaded = doc().thankyouPage!;
        const endings = [
            { id: 'ending-1', title: 'Eligible', message: 'You qualify.' },
            { id: 'ending-2', name: 'Not eligible', title: 'Sorry', message: 'You do not qualify.' }
        ];
        store.set(formStateAtom, { ...store.get(formStateAtom), thankyouPage: endings });
        const [step] = steps();
        expect(step.forward.map((op) => op.op)).toEqual(['set_endings']);
        expect(step.inverse.map((op) => op.op)).toEqual(['set_endings']);
        expect(doc().thankyouPage).toEqual(endings);
        expect(doc().thankyouPage).not.toBe(endings);
        store.set(undoAtom);
        expect(doc().thankyouPage).toHaveLength(1);
        expect(doc().thankyouPage![0]).toMatchObject(loaded[0]);
        store.set(redoAtom);
        expect(doc().thankyouPage).toEqual(endings);
    });

    it('editing one ending keeps the ids page jumps name', () => {
        store.set(formStateAtom, { ...store.get(formStateAtom), thankyouPage: [{ id: 'ok', title: 'A' }, { id: 'no', title: 'B' }] });
        store.set(formStateAtom, (prev) => ({ ...prev, thankyouPage: prev.thankyouPage!.map((e, i) => (i === 1 ? { ...e, title: 'B2' } : e)) }));
        expect(doc().thankyouPage!.map((e) => e.id)).toEqual(['ok', 'no']);
        expect(doc().thankyouPage![1].title).toBe('B2');
        expect(steps().flatMap((s) => s.forward.map((op) => op.op))).not.toContain(SET_FORM_KEYS);
    });
});

describe('form document: typing is one step', () => {
    beforeEach(() => {
        vi.useFakeTimers();
        load();
    });
    afterEach(() => vi.useRealTimers());

    const typeTitle = (text: string, key = 'title:p01-q01') => store.set(dispatchAtom, { ops: [{ op: 'update_field', fieldId: 'p01-q01', patch: { title: text } }], coalesceKey: key });

    it('keystrokes with the same key within the window merge: first inverse, last forward', () => {
        for (const text of ['Y', 'Yo', 'You', 'Your']) {
            typeTitle(text);
            vi.advanceTimersByTime(200);
        }
        expect(steps()).toHaveLength(1);
        expect(steps()[0].forward).toEqual([{ op: 'update_field', fieldId: 'p01-q01', patch: { title: 'Your' } }]);
        store.set(undoAtom);
        expect(field(0, 0).title).toEqual(form200.fields[0].properties.fields[0].title);
        store.set(redoAtom);
        expect(field(0, 0).title).toBe('Your');
    });

    it('a pause, another key or an undo starts a new step', () => {
        typeTitle('a');
        vi.advanceTimersByTime(UNDO_COALESCE_MS);
        typeTitle('ab');
        expect(steps()).toHaveLength(2);
        typeTitle('abc', 'description:p01-q01');
        expect(steps()).toHaveLength(3);
        store.set(undoAtom);
        store.set(redoAtom);
        typeTitle('abcd', 'description:p01-q01');
        expect(steps()).toHaveLength(4);
    });

    it('steps without a key never merge', () => {
        store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'A' }] });
        store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'B' }] });
        expect(steps()).toHaveLength(2);
    });
});

describe('form document: remote changes', () => {
    beforeEach(load);

    it('a whole form from elsewhere is one undo step, form-level parts included', () => {
        const before = doc();
        const server = structuredClone(form200) as any;
        server.fields[3].properties.fields[2].title = 'Changed by the assistant';
        server.fields.splice(5, 1);
        server.title = 'Assistant title';
        server.theme = { title: 'Ocean', primary: '#111827', secondary: '#1D4ED8', tertiary: '#2563EB', accent: '#DBEAFE' };
        server.thankyouPage = [{ title: 'All done', message: 'Bye' }];
        expect(store.set(applyRemoteAtom, server, { label: 'AI edit' })).toBe(true);
        expect(steps()).toHaveLength(1);
        expect(steps()[0].label).toBe('AI edit');
        expect(doc().fields).toHaveLength(19);
        expect(doc().title).toBe('Assistant title');
        expect(doc().thankyouPage).toEqual([{ title: 'All done', message: 'Bye' }]);
        // Pages the change did not touch keep their reference.
        expect(doc().fields[0]).toBe(before.fields[0]);

        store.set(undoAtom);
        expect(jsonEqual(withoutIndex(doc().fields), withoutIndex(before.fields))).toBe(true);
        expect(doc().title).toBe(form200.title);
        expect(doc().theme).toBeUndefined();
        expect(doc().thankyouPage).toEqual(form200.thankyouPage);
    });

    it('can be taken in without an undo step', () => {
        store.set(applyRemoteAtom, { title: 'Server title' }, { undoable: false });
        expect(doc().title).toBe('Server title');
        expect(steps()).toHaveLength(0);
    });

    it('the same form again changes nothing', () => {
        expect(store.set(applyRemoteAtom, structuredClone(form200) as any)).toBe(false);
        expect(steps()).toHaveLength(0);
    });
});

describe('form document: per-entity atoms', () => {
    beforeEach(load);

    it('indexes pages, questions and group questions', () => {
        store.set(dispatchAtom, { ops: [{ op: 'add_group', pageId: 'page-02', title: 'People', fields: [{ type: 'short_text', title: 'Name' }] }] });
        const index = store.get(locationIndexAtom);
        expect(index.get('page-01')).toEqual({ pageIdx: 0 });
        expect(index.get('p03-q04')).toEqual({ pageIdx: 2, fieldIdx: 3 });
        const group = doc().fields[1].properties!.fields!.at(-1)!;
        const child = group.properties!.fields![0];
        expect(index.get(group.id)).toEqual({ pageIdx: 1, fieldIdx: 10 });
        expect(index.get(child.id)).toEqual({ pageIdx: 1, fieldIdx: 10, childIdx: 0 });
        expect(store.get(fieldAtom(child.id))).toBe(child);
    });

    it('keep their reference while their entity is unchanged', () => {
        const other = store.get(fieldAtom('p05-q01'));
        const edited = store.get(fieldAtom('p01-q01'));
        const page5 = store.get(pageAtom('page-05'));
        const page1 = store.get(pageAtom('page-01'));
        const pageIds = store.get(pageIdsAtom);
        const page1Ids = store.get(fieldIdsOfPageAtom('page-01'));
        expect(edited?.id).toBe('p01-q01');
        expect(page5?.id).toBe('page-05');

        store.set(dispatchAtom, { ops: [{ op: 'update_field', fieldId: 'p01-q01', patch: { title: 'Changed' } }] });
        expect(store.get(fieldAtom('p05-q01'))).toBe(other);
        expect(store.get(pageAtom('page-05'))).toBe(page5);
        expect(store.get(pageIdsAtom)).toBe(pageIds);
        expect(store.get(fieldIdsOfPageAtom('page-01'))).toBe(page1Ids);
        expect(store.get(fieldAtom('p01-q01'))).not.toBe(edited);
        expect(store.get(pageAtom('page-01'))).not.toBe(page1);

        store.set(dispatchAtom, { ops: [{ op: 'move_field', fieldId: 'p01-q01', index: 2 }] });
        expect(store.get(fieldIdsOfPageAtom('page-01'))).not.toBe(page1Ids);
        expect(store.get(fieldIdsOfPageAtom('page-01')).slice(0, 3)).toEqual(['p01-q02', 'p01-q03', 'p01-q01']);
        expect(store.get(pageIdsAtom)).toBe(pageIds);
        expect(store.get(fieldAtom('p05-q01'))).toBe(other);
    });

    it('the same atom for the same id; unknown ids read undefined', () => {
        expect(fieldAtom('p01-q01')).toBe(fieldAtom('p01-q01'));
        expect(store.get(fieldAtom('nope'))).toBeUndefined();
        expect(store.get(pageAtom('p01-q01'))).toBeUndefined();
    });
});

describe('form document: the older mutators (compatibility path)', () => {
    beforeEach(load);

    /** What an older mutator does: edit the builder's copy in place, hand it over. */
    const mutate = (edit: (fields: StandardFormFieldDto[]) => void, key?: string) => {
        const fields = store.get(builderFieldsAtom);
        edit(fields);
        store.set(commitBuilderFieldsAtom, [...fields], key);
    };

    it('turns an in-place edit into entity ops, and keeps the document apart from the copy', () => {
        const before = doc();
        mutate((fields) => {
            fields[2].properties!.fields![4] = { ...fields[2].properties!.fields![4], title: title('Edited') };
        }, 'title:p03-q05');
        const [step] = steps();
        expect(step.forward.map((op) => op.op)).toEqual(['replace_field']);
        expect(field(2, 4).title).toEqual(title('Edited'));
        expect(doc().fields[0]).toBe(before.fields[0]);
        expect(doc().fields[2].properties!.fields![4]).not.toBe(store.get(builderFieldsAtom)[2].properties!.fields![4]);
        store.set(undoAtom);
        expect(field(2, 4).title).toEqual(form200.fields[2].properties.fields[4].title);
        expect(store.get(builderFieldsAtom)[2].properties!.fields![4].title).toEqual(form200.fields[2].properties.fields[4].title);
    });

    it('structural edits (delete, move, insert, page settings) round-trip', () => {
        mutate((fields) => {
            fields[0].properties!.fields!.splice(1, 1);
        });
        mutate((fields) => {
            const [page] = fields.splice(4, 1);
            fields.splice(0, 0, page);
        });
        mutate((fields) => {
            fields[1].properties = { ...fields[1].properties, layout: 'TWO_COLUMN_IMAGE_RIGHT' as any, sectionTitle: 'Intro' };
            fields[1].properties!.fields!.push({ id: 'new-q', index: 9, type: 'short_text' as any, title: 'New' });
        });
        const ops = steps().flatMap((step) => step.forward.map((op) => op.op));
        expect(ops).not.toContain(SET_FIELDS);
        expect(withoutIndex(doc().fields)).toEqual(withoutIndex(store.get(builderFieldsAtom)));
        store.set(undoAtom);
        store.set(undoAtom);
        store.set(undoAtom);
        expect(withoutIndex(doc().fields)).toEqual(withoutIndex(form200.fields as any));
        expect(withoutIndex(store.get(builderFieldsAtom))).toEqual(withoutIndex(form200.fields as any));
    });

    it('a change the engine refuses still lands, as one local step', () => {
        mutate((fields) => {
            (fields[0] as any).imageUrl = 'https://example.org/not-first-party.png';
        });
        expect(steps()[0].forward.map((op) => op.op)).toEqual([SET_FIELDS]);
        expect((doc().fields[0] as any).imageUrl).toBe('https://example.org/not-first-party.png');
        store.set(undoAtom);
        expect((doc().fields[0] as any).imageUrl).toBeUndefined();
        expect((store.get(builderFieldsAtom)[0] as any).imageUrl).toBeUndefined();
    });

    it('an unchanged hand-over makes no step', () => {
        mutate(() => undefined);
        expect(steps()).toHaveLength(0);
    });

    it('form state writes become ops and are undone like the rest', () => {
        store.set(formStateAtom, (prev) => ({ ...prev, title: 'New title' }));
        store.set(formStateAtom, (prev) => ({ ...prev, hiddenFields: ['ref'] }));
        expect(steps().map((step) => step.forward.map((op) => op.op))).toEqual([['update_form_info', 'update_welcome_page'], ['set_hidden_fields']]);
        expect(store.get(formStateAtom).title).toBe('New title');
        // The welcome page title is not renamed with the form.
        expect(doc().welcomePage?.title).toBe(form200.welcomePage.title);
        store.set(undoAtom);
        store.set(undoAtom);
        expect(store.get(formStateAtom).title).toBe(form200.title);
        expect(store.get(formStateAtom).hiddenFields).toEqual(form200.hiddenFields);
    });

    it('the form state keeps its reference while only pages change', () => {
        const state = store.get(formStateAtom);
        mutate((fields) => {
            fields[0].properties!.fields![0] = { ...fields[0].properties!.fields![0], description: 'x' };
        });
        expect(store.get(formStateAtom)).toBe(state);
    });

    it("the delete toast's undo only undoes while its step is the latest", () => {
        // As the builder's deleteField does: remove, then renumber.
        mutate((fields) => {
            fields[0].properties!.fields = fields[0].properties!.fields!.filter((_, i) => i > 0).map((f, index) => ({ ...f, index }));
        });
        const after = latestStep(store.get(docHistoryAtom));
        const afterJson = JSON.stringify(store.get(builderFieldsAtom));
        expect(after?.forward.map((op) => op.op)).toEqual(['remove_field']);
        mutate((fields) => {
            fields[1].properties!.fields = fields[1].properties!.fields!.filter((_, i) => i > 0).map((f, index) => ({ ...f, index }));
        });
        expect(store.set(undoIfLatestAtom, after)).toBe(false);
        expect(store.set(undoIfLatestAtom, afterJson)).toBe(false);
        // Nor while a later edit can be redone (as before).
        store.set(undoAtom);
        expect(store.set(undoIfLatestAtom, after)).toBe(false);
        // A new edit replaces the redo; its own toast undoes it.
        mutate((fields) => {
            fields[2].properties!.fields = fields[2].properties!.fields!.filter((_, i) => i > 0).map((f, index) => ({ ...f, index }));
        });
        const third = latestStep(store.get(docHistoryAtom));
        expect(store.set(undoIfLatestAtom, third)).toBe(true);
        expect(field(2, 0).id).toBe('p03-q01');
    });
});

describe('selection by id', () => {
    beforeEach(load);

    it('the index follows the page and question when others move', () => {
        store.set(activeSlideAtom, { id: 'page-03', index: 2 });
        store.set(activeFieldAtom, { id: 'p03-q05', index: 4 });
        const selected = store.get(activeSlideAtom);
        store.set(dispatchAtom, { ops: [{ op: 'move_page', pageId: 'page-03', index: 0 }] });
        store.set(dispatchAtom, { ops: [{ op: 'move_field', fieldId: 'p03-q05', index: 0 }] });
        expect(store.get(activeSlideAtom)).toEqual({ id: 'page-03', index: 0 });
        expect(store.get(activeFieldAtom)).toEqual({ id: 'p03-q05', index: 0 });
        // Unchanged selection: the same object.
        store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'x' }] });
        expect(store.get(activeSlideAtom)).toBe(store.get(activeSlideAtom));
        expect(selected.index).toBe(2);
    });

    it('ids the document does not hold keep their given index', () => {
        store.set(activeSlideAtom, { id: 'thank-you-page', index: 0 });
        expect(store.get(activeSlideAtom)).toEqual({ id: 'thank-you-page', index: 0 });
        expect(createStore().get(activeSlideAtom)).toEqual({ id: 'welcome-page', index: -10 });
    });
});
