import i18n from 'i18next';
import { createStore } from 'jotai';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';

import { builderFieldsAtom, commitBuilderFieldsAtom, formDocAtom, resetFromServerAtom, undoAtom } from './form-document';

const toasts = vi.hoisted(() => [] as string[]);
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ toast: (props: { description?: string }) => void toasts.push(String(props.description)) }));

const q = (id: string, type: string, title: string, properties: Record<string, unknown> = {}) => ({ id, index: 0, type, title, properties: { fields: [], ...properties }, validations: {} }) as unknown as StandardFormFieldDto;
const page = (...fields: StandardFormFieldDto[]) => ({ id: 'p1', index: 0, type: 'slide', properties: { fields: fields.map((f, index) => ({ ...f, index })) } }) as unknown as StandardFormFieldDto;
const READ_A = { id: 'r_a', when: { conditions: [{ fieldId: 'a', fieldType: 'short_text', comparison: 'IS_NOT_EMPTY' }] }, then: { required: true } };
const SET_FROM = (id: string, from: string) => ({ id, when: { expression: true }, then: { setValue: { expression: { '+': [{ var: from }, 1] } } } });

function load(...fields: StandardFormFieldDto[]) {
    const store = createStore();
    store.set(resetFromServerAtom, { formId: 'f', title: 'T', builderVersion: 'v2', fields: [page(...fields)] } as any);
    return store;
}
const questions = (store: ReturnType<typeof createStore>) => store.get(formDocAtom).fields![0].properties!.fields as StandardFormFieldDto[];
const copyQuestions = (store: ReturnType<typeof createStore>) => store.get(builderFieldsAtom)[0].properties!.fields as StandardFormFieldDto[];
const toastText = () => toasts;

beforeEach(() => void (toasts.length = 0));
afterEach(() => i18n.changeLanguage('en'));

describe('the builder hands over pages with field rules', () => {
    it('makes a question internal: the rules that read it are dropped from the form and the builder copy, with a note, in one undoable step', () => {
        const store = load(q('a', 'short_text', 'A'), q('b', 'short_text', 'B', { rules: [READ_A] }));
        const fields = store.get(builderFieldsAtom);
        (fields[0].properties!.fields![0] as any).internal = true; // the older mutators edit the copy in place
        expect(store.set(commitBuilderFieldsAtom, [...fields])).toBe(true);
        expect(questions(store)[1].properties?.rules).toBeUndefined();
        expect(copyQuestions(store)[1].properties?.rules).toBeUndefined();
        expect(toastText().some((text) => /lost a rule/.test(text))).toBe(true);
        store.set(undoAtom);
        expect(questions(store)[1].properties?.rules).toEqual([READ_A]);
        expect(questions(store)[0].internal).toBeFalsy();
    });

    it('retypes a question to one that cannot carry rules: its rules go, and saving the rest goes on', () => {
        const store = load(q('a', 'short_text', 'A'), q('b', 'short_text', 'B', { rules: [READ_A] }));
        const fields = store.get(builderFieldsAtom);
        (fields[0].properties!.fields![1] as any).type = 'statement';
        expect(store.set(commitBuilderFieldsAtom, [...fields])).toBe(true);
        expect(questions(store)[1].properties?.rules).toBeUndefined();
        expect(questions(store)[1].type).toBe('statement');
    });

    it('refuses an edit that makes a circle of set values, says why, and puts the builder copy back', () => {
        const store = load(q('a', 'number', 'A', { rules: [SET_FROM('r1', 'b')] }), q('b', 'number', 'B'));
        const fields = store.get(builderFieldsAtom);
        (fields[0].properties!.fields![1].properties as any).rules = [SET_FROM('r2', 'a')];
        const before = store.get(formDocAtom);
        expect(store.set(commitBuilderFieldsAtom, [...fields])).toBe(false);
        expect(store.get(formDocAtom)).toBe(before);
        expect(copyQuestions(store)[1].properties?.rules).toBeUndefined();
        expect(toastText().some((text) => /Not changed/.test(text) && /in a circle/.test(text))).toBe(true);
    });

    it('refuses raising a group past what its rules can cost, and lets other edits through', () => {
        const wide = { '+': Array.from({ length: 100 }, () => ({ var: 'g.n' })) };
        const heavy = Array.from({ length: 10 }, (_, i) => q(`y${i}`, 'number', `Y${i}`, { rules: Array.from({ length: 8 }, (_, k) => ({ id: `y${i}r${k}`, when: { expression: { '>': [wide, 1] } }, then: { required: true } })) }));
        const group = q('g', 'group', 'G', { repeat: { minItems: 1, maxItems: 1 }, fields: [q('n', 'number', 'N')] });
        const store = load(group, ...heavy);
        const fields = store.get(builderFieldsAtom);
        (fields[0].properties!.fields![0].properties as any).repeat.maxItems = 50;
        expect(store.set(commitBuilderFieldsAtom, [...fields])).toBe(false);
        expect(toastText().some((text) => /too long to check/.test(text))).toBe(true);
        // the copy is back, and an ordinary edit is saved
        const again = store.get(builderFieldsAtom);
        (again[0].properties!.fields![1] as any).title = 'Renamed';
        expect(store.set(commitBuilderFieldsAtom, [...again])).toBe(true);
        expect(questions(store)[1].title).toBe('Renamed');
    });
});
