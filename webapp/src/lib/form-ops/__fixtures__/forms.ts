/** Test documents and helpers for the ops engine tests. */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import { finishDoc } from '../apply';
import type { FormDoc, FormField, FormOp } from '../types';

/** Deterministic ids: `${prefix}1`, `${prefix}2`, ... */
export function idMaker(prefix = 'new-'): () => string {
    let n = 0;
    return () => `${prefix}${++n}`;
}

/** Seeded random numbers (mulberry32). */
export function rng(seed: number): () => number {
    let a = seed >>> 0;
    return () => {
        a = (a + 0x6d2b79f5) >>> 0;
        let t = a;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

const q = (id: string, type: string, title: any, extra: Partial<FormField> = {}): FormField => {
    const { properties, ...rest } = extra;
    return { id, index: 0, type, title, validations: {}, ...rest, properties: { fields: [], ...(properties ?? {}) } };
};
const page = (id: string, fields: FormField[], properties: Record<string, any> = {}): FormField => ({ id, index: 0, type: 'slide', properties: { fields, layout: 'SINGLE_COLUMN_NO_BACKGROUND' as any, ...properties }, validations: {} });

/** A small form with every kind of reference: logic, jumps, date rules, a repeating group. */
export function smallForm(): FormDoc {
    const doc: FormDoc = {
        formId: 'form-1',
        title: 'Intake',
        description: 'About you',
        welcomePage: { title: 'Intake', description: 'Welcome' },
        hiddenFields: ['utm_source'],
        thankyouPage: [{ id: 'thanks', title: 'Thanks', layout: 'SINGLE_COLUMN_NO_BACKGROUND' as any }, { id: 'sorry', name: 'Not eligible', title: 'Sorry', isDefault: true }],
        theme: { title: 'Default', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB' },
        settings: { purpose: 'Research', requireVerifiedIdentity: false, allowEditingResponse: false, showSubmissionNumber: false } as any,
        fields: [
            page(
                'p1',
                [
                    q('name', 'short_text', 'Your name', { validations: { required: true } }),
                    q('color', 'multiple_choice', 'Favourite colour', {
                        properties: {
                            choices: [
                                { id: 'c-red', value: 'Red' },
                                { id: 'c-blue', value: 'Blue' },
                                { id: 'c-green', value: 'Green' }
                            ],
                            allowMultipleSelection: true
                        }
                    }),
                    q('start', 'date', 'Start date'),
                    q('end', 'date', 'End date', { properties: { dateRules: [{ comparison: 'after', target: 'field', fieldId: 'start' }] } }),
                    q('kids', 'group', 'Children', {
                        properties: {
                            repeat: { minItems: 0, maxItems: 4, itemLabel: 'Child' },
                            fields: [
                                q('kid-name', 'short_text', 'Name'),
                                q('kid-born', 'date', 'Born'),
                                q('kid-yes', 'yes_no', 'At school', {
                                    properties: {
                                        choices: [
                                            { id: 'y1', value: 'Yes' },
                                            { id: 'y2', value: 'No' }
                                        ]
                                    }
                                })
                            ]
                        }
                    })
                ],
                { jumps: [{ operator: 'AND', target: 'p3', conditions: [{ fieldId: 'name', fieldType: 'short_text', comparison: 'IS_EMPTY' }] }] }
            ),
            page('p2', [
                q('age', 'number', 'Age', { properties: { logic: { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'color', fieldType: 'multiple_choice', comparison: 'IS_EQUAL', value: 'Red' }] } as any } }),
                q('bio', 'long_text', 'About you')
            ]),
            page('p3', [q('note', 'text', 'Thanks for your answers')], { sectionTitle: 'The end' })
        ]
    };
    return finishDoc(doc);
}

/**
 * The shared 200-question fixture (src/test/fixtures/form-200.json), with
 * a theme and the settings switches, as the server sends a form (ops can
 * change a theme or turn a switch off, not remove either).
 */
export function form200(): FormDoc {
    const doc = JSON.parse(readFileSync(resolve(__dirname, '../../../test/fixtures/form-200.json'), 'utf8')) as FormDoc;
    const theme = { title: 'Default', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB' };
    return finishDoc({ ...doc, theme, settings: { requireVerifiedIdentity: false, allowEditingResponse: false, showSubmissionNumber: false } as any });
}

const TYPES = ['short_text', 'long_text', 'number', 'email', 'date', 'multiple_choice', 'dropdown', 'yes_no', 'rating', 'url'];

/** A form of `pages` pages with `perPage` questions each (200 questions by default). */
export function largeForm(pages = 10, perPage = 20): FormDoc {
    const fields: FormField[] = [];
    for (let p = 0; p < pages; p++) {
        const questions: FormField[] = [];
        for (let i = 0; i < perPage; i++) {
            const type = TYPES[(p * perPage + i) % TYPES.length];
            const id = `f${p}-${i}`;
            const properties: Record<string, any> = {};
            if (type === 'multiple_choice' || type === 'dropdown') properties.choices = [0, 1, 2, 3].map((c) => ({ id: `${id}-c${c}`, value: `Option ${c}` }));
            if (type === 'yes_no')
                properties.choices = [
                    { id: `${id}-y`, value: 'Yes' },
                    { id: `${id}-n`, value: 'No' }
                ];
            if (type === 'rating') properties.steps = 5;
            questions.push(q(id, type, { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: `Question ${p}.${i}` }] }] } as any, { properties }));
        }
        fields.push(page(`page-${p}`, questions));
    }
    // switches as the server sends them: always present (ops cannot unset a switch, only turn it off)
    const settings = { requireVerifiedIdentity: false, allowEditingResponse: false, showSubmissionNumber: false } as any;
    return finishDoc({ formId: 'large', title: 'Large form', description: '', settings, fields, theme: { title: 'Default', primary: '#101828', secondary: '#1649E2', tertiary: '#818CA0', accent: '#F5F7FB' } });
}

/** Every question id of a document (group questions included). */
export function questionIds(doc: FormDoc): string[] {
    const ids: string[] = [];
    for (const p of doc.fields ?? []) {
        for (const f of p.properties?.fields ?? []) {
            ids.push(f.id);
            for (const c of f.properties?.repeat ? (f.properties.fields ?? []) : []) ids.push(c.id);
        }
    }
    return ids;
}

export const pageIds = (doc: FormDoc) => (doc.fields ?? []).filter((f) => f.type === 'slide').map((f) => f.id);

/** A random op against `doc` (valid or not — failures are part of the test). */
export function randomOp(doc: FormDoc, random: () => number, newId: () => string): FormOp {
    const pick = <T>(list: T[]): T => list[Math.floor(random() * list.length)];
    const pages = pageIds(doc);
    const questions = questionIds(doc);
    const pageId = pick(pages) ?? 'missing-page';
    const fieldId = pick(questions) ?? 'missing-field';
    const groups = (doc.fields ?? []).flatMap((p) => (p.properties?.fields ?? []).filter((f) => f.properties?.repeat)).map((f) => f.id);
    const choiceFields = (doc.fields ?? []).flatMap((p) => (p.properties?.fields ?? []).filter((f) => f.type === 'multiple_choice' || f.type === 'dropdown'));
    const endings = (doc.thankyouPage ?? []).map((e) => e.id).filter(Boolean) as string[];
    const endingId = pick(endings) ?? 'missing-ending';
    const kinds = [
        () => ({ op: 'update_field', fieldId, patch: { title: `T${Math.floor(random() * 100)}` } }),
        () => ({ op: 'update_field', fieldId, patch: { required: random() < 0.5, description: 'd' } }),
        () => ({ op: 'update_field', fieldId, patch: { internal: random() < 0.5 } }),
        () => ({ op: 'add_field', pageId, index: Math.floor(random() * 5), field: { title: 'New', type: pick(['short_text', 'date', 'dropdown', 'yes_no', 'rating']), choices: ['A', 'B'] } }),
        () => ({ op: 'remove_field', fieldId }),
        () => ({ op: 'move_field', fieldId, toPageId: random() < 0.5 ? pageId : undefined, index: Math.floor(random() * 6) }),
        () => ({ op: 'move_field', fieldId, toGroupId: pick(groups) ?? 'nope', index: 0 }),
        () => ({ op: 'add_page', index: Math.floor(random() * 4), fields: [{ title: 'P', type: 'email' }] }),
        () => ({ op: 'remove_page', pageId }),
        () => ({ op: 'move_page', pageId, index: Math.floor(random() * 4) }),
        () => ({ op: 'duplicate_page', pageId }),
        () => ({ op: 'set_field_logic', fieldId, logic: random() < 0.3 ? null : { action: 'HIDE', conditions: [{ fieldId: pick(questions), comparison: 'IS_NOT_EMPTY' }] } }),
        () => ({ op: 'set_page_jumps', pageId, jumps: random() < 0.3 ? null : [{ target: '__SUBMIT__', ...(random() < 0.5 ? { endingId } : {}), conditions: [{ fieldId: pick(questions), comparison: 'IS_EMPTY' }] }] }),
        () => ({ op: 'add_ending', name: random() < 0.5 ? 'Eligible' : undefined, title: 'Done', isDefault: random() < 0.3 ? true : random() < 0.5 ? false : undefined, index: random() < 0.5 ? 0 : undefined }),
        () => ({ op: 'update_ending', endingId, patch: { message: random() < 0.3 ? '' : 'See you', isDefault: random() < 0.5 ? random() < 0.5 : undefined, buttonLink: random() < 0.3 ? 'https://example.org' : undefined } }),
        () => ({ op: 'remove_ending', endingId }),
        // every ending kept (in another order): jumps never lose theirs here
        () => ({ op: 'set_endings', endings: [...(doc.thankyouPage ?? [])].reverse().map((e) => ({ ...e })) }),
        () => ({ op: 'set_section_title', pageId, title: random() < 0.3 ? '' : 'Section' }),
        () => ({ op: 'set_question_numbering', show: random() < 0.5 }),
        () => ({ op: 'set_field_validation', fieldId, validation: { minLength: 1, maxLength: 10 } }),
        () => ({ op: 'update_form_info', title: 'Renamed', description: random() < 0.5 ? 'x' : undefined }),
        () => ({ op: 'set_theme_preset', name: pick(['Ocean', 'leaflet', 'Blue', 'Nope']) }),
        () => ({ op: 'update_form_settings', patch: { purpose: random() < 0.5 ? '' : 'Care', requireVerifiedIdentity: true } }),
        () => ({ op: 'add_group', pageId, title: 'G', fields: [{ title: 'Child', type: 'short_text' }] }),
        () => ({ op: 'insert_field', pageId, index: Math.floor(random() * 4), field: { id: newId(), index: 0, type: 'short_text', title: 'Inserted', properties: { fields: [] }, validations: {} } }),
        () => ({ op: 'replace_field', field: { id: fieldId, index: 0, type: 'long_text', title: 'Replaced', properties: { fields: [] }, validations: { required: true } } }),
        () => ({ op: 'update_page', pageId, patch: { layout: 'TWO_COLUMN_IMAGE_LEFT', showQuestionNumbers: random() < 0.5 ? null : true } }),
        () => ({ op: 'update_welcome_page', patch: { title: 'Hello', buttonText: random() < 0.5 ? null : 'Start' } }),
        () => ({ op: 'set_hidden_fields', names: random() < 0.5 ? [] : ['utm_source', 'ref'] }),
        () => ({ op: 'update_logo', alt: 'Logo', position: random() < 0.3 ? null : 'left' }),
        () => {
            const field = pick(choiceFields);
            const choice = field?.properties?.choices?.[0];
            return pick([
                { op: 'set_choice', fieldId: field?.id ?? fieldId, choiceId: choice?.id ?? 'x', value: 'Renamed' },
                { op: 'add_choice', fieldId: field?.id ?? fieldId, choice: { id: newId(), value: 'Extra' }, index: 1 },
                { op: 'remove_choice', fieldId: field?.id ?? fieldId, choiceId: choice?.id ?? 'x' },
                { op: 'move_choice', fieldId: field?.id ?? fieldId, choiceId: choice?.id ?? 'x', index: 2 }
            ]);
        }
    ];
    return pick(kinds)() as FormOp;
}
