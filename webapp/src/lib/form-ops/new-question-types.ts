/**
 * The switch for the newer question types (backend `NEW_QUESTION_TYPES_ENABLED`,
 * services/new_question_types.py): while it is off, an op that leaves a time,
 * day, currency, date range or tags question new, or changes the type or the settings of one the
 * form already had, is refused. Questions a form already holds keep working.
 *
 * Pass `newQuestionTypes: false` in the apply options to apply the switch (the
 * webapp learns it from the workspace permissions). The server checks every
 * save either way.
 *
 * The signature and address questions have a switch of their own (`SIGNATURE_QUESTION_ENABLED`
 * and `ADDRESS_QUESTION_ENABLED`, `signatureQuestion: false` and `addressQuestion: false`
 * in the apply options): a `Gate` names a switch's
 * types and its refusal, and everything below looks at each gate that is off.
 */
import { childrenOf, pagesOf } from './model';
import type { FormDoc, FormField } from './types';

// Types behind the switch. Keep in step with GATED_TYPES in the backend module.
export const GATED_TYPES = new Set<string>(['time', 'day', 'currency', 'date_range', 'tags']);

// The address question's own switch (backend ADDRESS_TYPES).
export const ADDRESS_TYPES = new Set<string>(['address']);
// The signature question's own switch (backend SIGNATURE_TYPES).
export const SIGNATURE_TYPES = new Set<string>(['signature']);
const ALL_GATED_TYPES = new Set<string>([...GATED_TYPES, ...ADDRESS_TYPES, ...SIGNATURE_TYPES]);

/** Ops that can give a form such a question or change one (backend GATED_OPS). */
export const GATED_OPS = new Set<string>(['add_field', 'add_group', 'add_page', 'duplicate_page', 'update_field', 'set_field_validation', 'insert_field', 'insert_page', 'replace_field', 'splice_fields']);

export const NEW_QUESTION_TYPES_DISABLED_MESSAGE =
    'These question types (time, day, currency, date range and tags) cannot be added or changed on this server yet (NEW_QUESTION_TYPES_ENABLED is off). Questions of these types that a form already has are kept.';

export const ADDRESS_QUESTION_DISABLED_MESSAGE =
    'The address question cannot be added or changed on this server yet (ADDRESS_QUESTION_ENABLED is off). An address question that a form already has is kept.';
export const SIGNATURE_QUESTION_DISABLED_MESSAGE =
    'The signature question cannot be added or changed on this server yet (SIGNATURE_QUESTION_ENABLED is off). A signature question that a form already has is kept.';

/** A switch, the question types behind it and what a refused op says (backend `Gate`). */
export interface Gate {
    types: ReadonlySet<string>;
    message: string;
}
export const NEW_TYPES_GATE: Gate = { types: GATED_TYPES, message: NEW_QUESTION_TYPES_DISABLED_MESSAGE };
export const ADDRESS_GATE: Gate = { types: ADDRESS_TYPES, message: ADDRESS_QUESTION_DISABLED_MESSAGE };
export const SIGNATURE_GATE: Gate = { types: SIGNATURE_TYPES, message: SIGNATURE_QUESTION_DISABLED_MESSAGE };

/** The state of the switches (the workspace permissions tell them): default on. */
export interface TypeSwitches {
    newQuestionTypes?: boolean;
    addressQuestion?: boolean;
    signatureQuestion?: boolean;
}

/** The gates whose switch is off. */
export const gatesOff = (switches: TypeSwitches): Gate[] => [
    ...(switches.newQuestionTypes === false ? [NEW_TYPES_GATE] : []),
    ...(switches.addressQuestion === false ? [ADDRESS_GATE] : []),
    ...(switches.signatureQuestion === false ? [SIGNATURE_GATE] : [])
];

/** Is this type behind a switch that is off? */
export const typeIsOff = (type: unknown, switches: TypeSwitches): boolean => gatesOff(switches).some((gate) => gate.types.has(String(type)));

/** Keys sorted, null and undefined left out: what makes two settings the same. */
function stable(value: unknown): unknown {
    if (Array.isArray(value)) return value.map(stable);
    if (value && typeof value === 'object') {
        const out: Record<string, unknown> = {};
        for (const key of Object.keys(value as object).sort()) {
            const item = stable((value as Record<string, unknown>)[key]);
            if (item !== null && item !== undefined) out[key] = item;
        }
        return out;
    }
    return value;
}

/** What makes a gated question the same one, in two parts (backend `signature_parts`): the settings that belong to its type as one text, and its date rules one text each. */
export interface SignatureParts {
    base: string;
    rules: string[];
}

export function signatureParts(field: FormField): SignatureParts {
    const props = (field.properties ?? {}) as Record<string, unknown>;
    const validations = (field.validations ?? {}) as Record<string, unknown>;
    const base = JSON.stringify(
        stable({
            type: field.type,
            minTime: props.minTime,
            maxTime: props.maxTime,
            currencies: props.currencies,
            // an address question: the countries and whether street and city are looked up
            countries: props.countries,
            addressLookup: props.addressLookup,
            minValue: validations.minValue,
            maxValue: validations.maxValue,
            // a tags question: the number of tags and the length of one
            minChoices: validations.minChoices,
            maxChoices: validations.maxChoices,
            maxLength: validations.maxLength
        })
    );
    const rules = (Array.isArray(props.dateRules) ? props.dateRules : []).map((rule) => JSON.stringify(stable(rule)));
    return { base, rules };
}

/** The two parts of `signatureParts` as one text. */
export function signature(field: FormField): string {
    const { base, rules } = signatureParts(field);
    return JSON.stringify([base, rules]);
}

/** Is a question as it is now what was stored, or less: the same settings and no date rule the stored one did not have (backend `_covers`)? */
const covers = (stored: SignatureParts, now: SignatureParts): boolean => stored.base === now.base && now.rules.every((rule) => stored.rules.includes(rule));

export type GatedSignatures = Map<string, SignatureParts[]>;

function* walk(fields: FormField[]): Generator<FormField> {
    for (const field of fields) {
        yield field;
        yield* walk(childrenOf(field));
    }
}

/** Is this question of a type behind a switch? */
export const isGatedQuestion = (field: FormField | undefined | null): boolean => !!field && ALL_GATED_TYPES.has(String(field.type));

/** Does this page, or the group in it, hold a question of a type behind a switch that is off? (`switches` default: every switch off.) */
export function pageHoldsGatedQuestion(page: FormField | undefined | null, switches: TypeSwitches = { newQuestionTypes: false, addressQuestion: false, signatureQuestion: false }): boolean {
    if (!page) return false;
    for (const field of walk(childrenOf(page))) if (typeIsOff(field.type, switches)) return true;
    return false;
}

/** `{question id: [parts, ...]}` of the gated questions of `doc` (a list: a document may carry one id twice, and each copy counts). */
export function gatedSignatures(doc: FormDoc): GatedSignatures {
    const out: GatedSignatures = new Map();
    for (const field of walk(pagesOf(doc))) {
        if (!ALL_GATED_TYPES.has(String(field.type))) continue;
        const key = String(field.id);
        out.set(key, [...(out.get(key) ?? []), signatureParts(field)]);
    }
    return out;
}

/**
 * Ids of the gated questions of `doc` that are new or changed against `stored`
 * (a date rule may be fewer, not more). A stored question covers one question
 * of `doc` only: a second one with the same id reads as new (backend
 * `new_or_changed_questions`).
 */
export function newOrChangedQuestions(doc: FormDoc, stored: GatedSignatures, gate: Gate = NEW_TYPES_GATE): string[] {
    const remaining = new Map([...stored].map(([key, values]) => [key, [...values]]));
    const ids: string[] = [];
    for (const field of walk(pagesOf(doc))) {
        if (!gate.types.has(String(field.type))) continue;
        const key = String(field.id);
        const parts = signatureParts(field);
        const left = remaining.get(key) ?? [];
        const at = left.findIndex((kept) => covers(kept, parts));
        if (at >= 0) left.splice(at, 1);
        else ids.push(key);
    }
    return ids;
}

/** The refusal an op earns when it left `doc` with a question new or changed against `stored` that is behind one of `gates` (the ones that are off; default the newer question types'), or null (backend `question_type_problem`). */
export function questionTypeProblem(doc: FormDoc, stored: GatedSignatures, opName: string, gates: Gate[] = [NEW_TYPES_GATE]): string | null {
    if (!GATED_OPS.has(opName)) return null;
    for (const gate of gates) if (newOrChangedQuestions(doc, stored, gate).length) return gate.message;
    return null;
}
