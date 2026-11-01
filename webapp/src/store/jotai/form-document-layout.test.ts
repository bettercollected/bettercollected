import i18n from 'i18next';
import { createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LayoutContainer, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';

import { builderFieldsAtom, commitBuilderFieldsAtom, formDocAtom, resetFromServerAtom, undoAtom } from './form-document';

const toasts = vi.hoisted(() => [] as string[]);
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ toast: (props: { description?: string }) => void toasts.push(String(props.description)) }));

const q = (id: string) => ({ id, index: 0, type: 'short_text', title: id.toUpperCase(), properties: { fields: [] }, validations: {} }) as unknown as StandardFormFieldDto;
const RULE_ON_A = { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'a', fieldType: 'short_text', comparison: 'IS_EQUAL', value: 'x' }] };
const guarded: LayoutContainer = { id: 'c1', type: 'panel', title: 'Details', fields: ['c', 'd'], logic: RULE_ON_A as any };

/** A page `a b [c d] e`: the panel shows when `a` says so. */
function load() {
    const store = createStore();
    const fields = ['a', 'b', 'c', 'd', 'e'].map((id, index) => ({ ...q(id), index }));
    store.set(resetFromServerAtom, { formId: 'f', title: 'T', builderVersion: 'v2', fields: [{ id: 'p1', index: 0, type: 'slide', properties: { fields, containers: [guarded] } }] } as any);
    return store;
}
const order = (store: ReturnType<typeof createStore>) => (store.get(formDocAtom).fields![0].properties!.fields as StandardFormFieldDto[]).map((f) => f.id);
const copyOrder = (store: ReturnType<typeof createStore>) => (store.get(builderFieldsAtom)[0].properties!.fields as StandardFormFieldDto[]).map((f) => f.id);
/** What the older mutators do: reorder the builder's copy in place and hand the pages over. */
function reorder(store: ReturnType<typeof createStore>, from: number, to: number) {
    const fields = store.get(builderFieldsAtom);
    const list = fields[0].properties!.fields!;
    list.splice(to, 0, list.splice(from, 1)[0]);
    return store.set(commitBuilderFieldsAtom, [...fields]);
}

beforeEach(() => void (toasts.length = 0));
afterEach(() => i18n.changeLanguage('en'));

describe('the builder hands over pages with a container rule', () => {
    it('refuses a move that would leave the rule reading a later question, says why and puts the builder copy back', () => {
        const store = load();
        const before = store.get(formDocAtom);
        expect(reorder(store, 0, 4)).toBe(false);
        expect(store.get(formDocAtom)).toBe(before);
        expect(order(store)).toEqual(['a', 'b', 'c', 'd', 'e']);
        expect(copyOrder(store)).toEqual(['a', 'b', 'c', 'd', 'e']);
        expect(toasts.some((text) => /Not changed/.test(text) && /can only read questions before the container/.test(text))).toBe(true);
    });

    it('refuses a move that takes the question the rule reads into the container', () => {
        const store = load();
        expect(reorder(store, 0, 2)).toBe(false);
        expect(toasts.some((text) => /cannot read one of its own questions/.test(text))).toBe(true);
    });

    it('says it in Dutch too', async () => {
        await i18n.changeLanguage('nl');
        const store = load();
        expect(reorder(store, 0, 4)).toBe(false);
        expect(toasts.some((text) => /Niet aangepast/.test(text))).toBe(true);
    });

    it('lets other moves through, in one undoable step', () => {
        const store = load();
        expect(reorder(store, 1, 4)).toBe(true);
        expect(order(store)).toEqual(['a', 'c', 'd', 'e', 'b']);
        expect(toasts).toEqual([]);
        store.set(undoAtom);
        expect(order(store)).toEqual(['a', 'b', 'c', 'd', 'e']);
    });
});
