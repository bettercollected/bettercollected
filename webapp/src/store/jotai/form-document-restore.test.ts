import { createStore } from 'jotai';
import { beforeEach, describe, expect, it } from 'vitest';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import form200 from '@app/test/fixtures/form-200.json';

import { activeFieldAtom, activeSlideAtom, followActiveFieldAtom } from './active-builder-component';
import { formStateAtom } from './form';
import {
    FormDocument,
    SET_FIELDS,
    SET_FORM_KEYS,
    builderFieldsAtom,
    canRedoAtom,
    canUndoAtom,
    commitBuilderFieldsAtom,
    dispatchAtom,
    docHistoryAtom,
    exactRestore,
    formDocAtom,
    latestStep,
    redoAtom,
    resetFromServerAtom,
    undoAtom
} from './form-document';

let store: ReturnType<typeof createStore>;
const doc = () => store.get(formDocAtom);
const field = (pageIdx: number, fieldIdx: number) => doc().fields[pageIdx].properties!.fields![fieldIdx];
/** The pages without `index` (which the engine renumbers itself). */
const withoutIndex = (fields: StandardFormFieldDto[]) => JSON.parse(JSON.stringify(fields, (key, value) => (key === 'index' ? undefined : value)));

/** What an older mutator does: edit the builder's copy in place, hand it over. */
const mutate = (edit: (fields: StandardFormFieldDto[]) => void) => {
    const fields = store.get(builderFieldsAtom);
    edit(fields);
    store.set(commitBuilderFieldsAtom, [...fields]);
};
/** As the builder's deleteField does: remove, then renumber. */
const deleteQuestion = (pageIdx: number, fieldIdx: number) =>
    mutate((fields) => {
        fields[pageIdx].properties!.fields = fields[pageIdx].properties!.fields!.filter((_, i) => i !== fieldIdx).map((f, index) => ({ ...f, index }));
    });
const deletePage = (pageIdx: number) =>
    mutate((fields) => {
        fields.splice(pageIdx, 1);
        fields.forEach((page, index) => (page.index = index));
    });
/** What autosave sends: the builder's pages and the form state. */
const saved = () => ({ fields: withoutIndex(store.get(builderFieldsAtom)), state: JSON.parse(JSON.stringify(store.get(formStateAtom))) });

describe('uploaded images survive undo', () => {
    // An uploaded image in our storage; the builder learns such addresses from the server.
    const STORED = 'https://storage.example.org/forms-bucket/public/form-images/photo.png';
    // An upload the store has not seen from the server, so the engine does not accept it.
    const unseen = (name: string) => `https://storage.example.org/forms-bucket/public/form-images/${name}-${Math.random().toString(36).slice(2)}.png`;

    function loadWithImages(): FormDocument {
        const form = structuredClone(form200) as any;
        form.fields[0].properties.fields[0].imageUrl = STORED;
        form.fields[1].imageUrl = STORED;
        form.welcomePage.imageUrl = STORED;
        form.theme = { title: 'Photo', primary: '#111827', secondary: '#1D4ED8', tertiary: '#2563EB', accent: '#DBEAFE', background: { type: 'image', imageUrl: STORED } };
        store = createStore();
        store.set(resetFromServerAtom, form);
        return store.get(formDocAtom);
    }

    it('a deleted question with an uploaded image comes back exactly', () => {
        const before = loadWithImages();
        const savedBefore = saved();
        deleteQuestion(0, 0);
        expect(field(0, 0).id).toBe('p01-q02');
        store.set(undoAtom);
        expect(withoutIndex(doc().fields)).toEqual(withoutIndex(before.fields));
        expect(saved()).toEqual(savedBefore);
        expect(store.get(canUndoAtom)).toBe(false);
        store.set(redoAtom);
        expect(field(0, 0).id).toBe('p01-q02');
    });

    it('so does one whose image the engine would refuse: the step records an exact restore', () => {
        loadWithImages();
        const url = unseen('question');
        mutate((fields) => {
            fields[2].properties!.fields![3] = { ...fields[2].properties!.fields![3], imageUrl: url };
        });
        const withImage = doc();
        const savedWith = saved();
        deleteQuestion(2, 3);
        expect(latestStep(store.get(docHistoryAtom))!.inverse.map((op) => op.op)).toEqual([SET_FIELDS]);
        store.set(undoAtom);
        expect(doc().fields).toBe(withImage.fields);
        expect(saved()).toEqual(savedWith);
        expect((field(2, 3) as any).imageUrl).toBe(url);
        store.set(redoAtom);
        expect(field(2, 3).id).toBe('p03-q05');
        store.set(undoAtom);
        store.set(undoAtom);
        expect((field(2, 3) as any).imageUrl).toBeUndefined();
        expect(store.get(canUndoAtom)).toBe(false);
    });

    it('a deleted page with an uploaded layout image comes back exactly', () => {
        const before = loadWithImages();
        const savedBefore = saved();
        deletePage(1);
        expect(doc().fields).toHaveLength(19);
        store.set(undoAtom);
        expect(withoutIndex(doc().fields)).toEqual(withoutIndex(before.fields));
        expect((doc().fields[1] as any).imageUrl).toBe(STORED);
        expect(saved()).toEqual(savedBefore);

        const url = unseen('page');
        mutate((fields) => {
            (fields[4] as any).imageUrl = url;
        });
        const savedWith = saved();
        deletePage(4);
        store.set(undoAtom);
        expect((doc().fields[4] as any).imageUrl).toBe(url);
        expect(saved()).toEqual(savedWith);
    });

    it('a replaced uploaded theme or welcome image is put back', () => {
        const before = loadWithImages();
        const savedBefore = saved();
        const replacement = unseen('welcome');
        store.set(formStateAtom, (prev) => ({ ...prev, welcomePage: { ...prev.welcomePage, imageUrl: replacement } }));
        store.set(formStateAtom, (prev) => ({ ...prev, theme: { ...prev.theme!, background: { type: 'image', imageUrl: replacement } as any } }));
        expect(doc().welcomePage?.imageUrl).toBe(replacement);
        store.set(undoAtom);
        expect(doc().theme).toEqual(before.theme);
        store.set(undoAtom);
        expect(doc().welcomePage).toEqual(before.welcomePage);
        expect(saved()).toEqual(savedBefore);
        store.set(redoAtom);
        store.set(redoAtom);
        expect(doc().welcomePage?.imageUrl).toBe(replacement);
        expect((doc().theme as any).background.imageUrl).toBe(replacement);
    });

    it('a step whose ops no longer apply falls back to its recorded documents', () => {
        loadWithImages();
        store.set(dispatchAtom, { ops: [{ op: 'update_form_info', title: 'Changed' }] });
        // Break the recorded ops: undo and redo must still land, never get stuck.
        const history = store.get(docHistoryAtom);
        const broken = { ...history.steps[0], inverse: [{ op: 'remove_field', fieldId: 'missing' } as any], forward: [{ op: 'remove_field', fieldId: 'missing' } as any] };
        store.set(docHistoryAtom, { ...history, steps: [broken] });
        expect(store.set(undoAtom)).toBe(true);
        expect(doc().title).toBe(form200.title);
        expect(store.get(canUndoAtom)).toBe(false);
        expect(store.set(redoAtom)).toBe(true);
        expect(doc().title).toBe('Changed');
        expect(store.get(canRedoAtom)).toBe(false);
    });

    it('exactRestore names the pages and the form-level keys that differ', () => {
        const a = loadWithImages();
        const b = { ...a, title: 'B', fields: a.fields.slice(1) };
        expect(exactRestore(b, a)).toEqual([
            { op: SET_FIELDS, fields: a.fields },
            { op: SET_FORM_KEYS, values: { title: a.title } }
        ]);
        expect(exactRestore(a, a)).toEqual([]);
    });
});

describe('selection after undo', () => {
    beforeEach(() => {
        store = createStore();
        store.set(resetFromServerAtom, structuredClone(form200) as any);
    });

    it('the selected page follows its question back after undoing a move to another page', () => {
        store.set(activeSlideAtom, { id: 'page-01', index: 0 });
        store.set(activeFieldAtom, { id: 'p01-q02', index: 1 });
        store.set(dispatchAtom, { ops: [{ op: 'move_field', fieldId: 'p01-q02', toPageId: 'page-04', index: 0 }] });
        store.set(activeSlideAtom, { id: 'page-04', index: 3 });
        store.set(undoAtom);
        store.set(followActiveFieldAtom);
        expect(store.get(activeSlideAtom)).toEqual({ id: 'page-01', index: 0 });
        expect(store.get(activeFieldAtom)).toEqual({ id: 'p01-q02', index: 1 });
    });
});

describe('top-level entries that are not pages', () => {
    beforeEach(() => {
        store = createStore();
        store.set(resetFromServerAtom, structuredClone(form200) as any);
    });

    it('are kept as handed over, at their position, and undone with the rest', () => {
        const fields = structuredClone(store.get(builderFieldsAtom));
        const loose = { id: 'loose-1', index: 2, type: 'short_text', title: 'Older top-level question' } as any;
        fields.splice(2, 0, loose);
        store.set(commitBuilderFieldsAtom, fields);
        expect(doc().fields).toHaveLength(21);
        expect(doc().fields[2]).toEqual(loose);

        // Edits next to it go through, and it stays where it is.
        const next = [...store.get(builderFieldsAtom)];
        next[0] = { ...next[0], properties: { ...next[0].properties, sectionTitle: 'Intro' } };
        store.set(commitBuilderFieldsAtom, next);
        expect(doc().fields[0].properties?.sectionTitle).toBe('Intro');
        expect(doc().fields[2]).toEqual(loose);

        store.set(undoAtom);
        expect(doc().fields[2]).toEqual(loose);
        store.set(undoAtom);
        expect(doc().fields.map((p) => p.id)).toEqual(form200.fields.map((p) => p.id));
    });
});
