/**
 * The switch for the newer question types (backend `NEW_QUESTION_TYPES_ENABLED`,
 * services/new_question_types.py): while it is off, an op that leaves a time,
 * day or currency question new, or changes the type or the settings of one the
 * form already had, is refused. Questions a form already holds keep working.
 *
 * Pass `newQuestionTypes: false` in the apply options to apply the switch (the
 * webapp learns it from the workspace permissions). The server checks every
 * save either way.
 */
import { childrenOf, pagesOf } from './model';
import type { FormDoc, FormField } from './types';

// Types behind the switch. Keep in step with GATED_TYPES in the backend module.
export const GATED_TYPES = new Set<string>(['time', 'day', 'currency']);

/** Ops that can give a form such a question or change one (backend GATED_OPS). */
export const GATED_OPS = new Set<string>(['add_field', 'add_group', 'add_page', 'duplicate_page', 'update_field', 'set_field_validation', 'insert_field', 'insert_page', 'replace_field']);

export const NEW_QUESTION_TYPES_DISABLED_MESSAGE =
    'These question types (time, day and currency) cannot be added or changed on this server yet (NEW_QUESTION_TYPES_ENABLED is off). Questions of these types that a form already has are kept.';

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

/** What makes a gated question the same one: its type and the settings that belong to it (backend `signature`). */
export function signature(field: FormField): string {
    const props = (field.properties ?? {}) as Record<string, unknown>;
    const validations = (field.validations ?? {}) as Record<string, unknown>;
    return JSON.stringify(
        stable({
            type: field.type,
            minTime: props.minTime,
            maxTime: props.maxTime,
            currencies: props.currencies,
            dateRules: props.dateRules,
            minValue: validations.minValue,
            maxValue: validations.maxValue
        })
    );
}

function* walk(fields: FormField[]): Generator<FormField> {
    for (const field of fields) {
        yield field;
        yield* walk(childrenOf(field));
    }
}

/** `{question id: signature}` of the gated questions of `doc`. */
export function gatedSignatures(doc: FormDoc): Map<string, string> {
    const out = new Map<string, string>();
    for (const field of walk(pagesOf(doc))) if (GATED_TYPES.has(String(field.type))) out.set(String(field.id), signature(field));
    return out;
}

/** Ids of the gated questions of `doc` that are new or changed against `stored`. */
export function newOrChangedQuestions(doc: FormDoc, stored: Map<string, string>): string[] {
    const ids: string[] = [];
    for (const field of walk(pagesOf(doc))) if (GATED_TYPES.has(String(field.type)) && stored.get(String(field.id)) !== signature(field)) ids.push(String(field.id));
    return ids;
}

/** The refusal an op earns when it left `doc` with a gated question new or changed against `stored`, or null (backend `question_type_problem`). */
export function questionTypeProblem(doc: FormDoc, stored: Map<string, string>, opName: string): string | null {
    if (!GATED_OPS.has(opName)) return null;
    return newOrChangedQuestions(doc, stored).length ? NEW_QUESTION_TYPES_DISABLED_MESSAGE : null;
}
