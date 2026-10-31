/** Choice-level logic ops: an option's own logic, and filtering a question's options by an earlier answer. */
import { OPTION_CONDITIONS_MAX, OptionFilter, optionLogicProblems } from '@app/utils/option-logic';

import { CHOICE_FIELD_TYPES, OpError, locateField, titleText } from '../model';
import type { FormDoc, FormField, SetOptionFilterOp, SetOptionLogicOp } from '../types';
import { type Handler, draftField, ensureProperties } from './context';
import { validatedConditions } from './fields';

type Choice = { id?: string; value?: string; label?: string; logic?: any };

/** A page-level choice question: what option logic may sit on (backend `_option_question`). */
function optionQuestion(doc: FormDoc, fieldId: string): { field: FormField; location: ReturnType<typeof locateField> } {
    const location = locateField(doc, fieldId);
    const { parent, field } = location;
    if (parent !== null) throw new OpError(`'${titleText(field)}' is in a repeating group: option logic is not supported there yet.`);
    if (!CHOICE_FIELD_TYPES.has(field.type) || field.internal) throw new OpError(`'${titleText(field)}' is not a single or multiple choice or dropdown question (or is internal), so its options cannot have logic.`);
    return { field, location };
}

/** The option of `field` named by its id or its label (unique), backend `_option_of`. */
function optionOf(field: FormField, name: string): Choice & { id: string } {
    const choices: Choice[] = (field.properties?.choices as Choice[] | undefined) ?? [];
    const byId = choices.filter((c) => c.id === name);
    const found = byId.length ? byId : choices.filter((c) => c.value === name || c.label === name);
    if (!found.length) {
        const labels = choices.map((c) => c.value || c.label || c.id || '?').join(', ');
        throw new OpError(`'${name}' is not an option of '${titleText(field)}'. Options: ${labels}`);
    }
    if (found.length > 1) throw new OpError(`'${name}' names more than one option of '${titleText(field)}'; use the option's id.`);
    if (!found[0].id) throw new OpError(`An option of '${titleText(field)}' has no id, so logic cannot name it.`);
    return found[0] as Choice & { id: string };
}

/** `doc` with one question replaced (nothing is changed in place). */
function withQuestion(doc: FormDoc, location: ReturnType<typeof locateField>, replacement: FormField): FormDoc {
    const fields = (doc.fields ?? []).map((page, pos) => {
        if (pos !== location.pagePos) return page;
        const questions = (page.properties?.fields ?? []).map((question, at) => (at === location.position ? replacement : question));
        return { ...page, properties: { ...page.properties, fields: questions } } as FormField;
    });
    return { ...doc, fields };
}

/** The first problem option logic has after the change that it did not have before (for the question that changed), or null. */
function newProblem(before: FormDoc, after: FormDoc, fieldId: string): string | null {
    const known = new Set(optionLogicProblems(before.fields as any).map((p) => p.message));
    const found = optionLogicProblems(after.fields as any).find((p) => (p.fieldId === fieldId || p.fieldId === '') && !known.has(p.message));
    return found ? found.message : null;
}

export const setOptionLogic: Handler<SetOptionLogicOp> = (ctx, op) => {
    const { field, location } = optionQuestion(ctx.state, op.fieldId);
    const choice = optionOf(field, op.choice);
    const label = choice.value || choice.label || choice.id;
    const choices = (field.properties?.choices as Choice[] | undefined) ?? [];
    const write = (logic: any) => {
        const target = draftField(ctx.draft, location);
        const draftChoices = ensureProperties(target, false).choices as Choice[];
        const draftChoice = draftChoices.find((c) => c.id === choice.id)!;
        if (logic === undefined) delete draftChoice.logic;
        else draftChoice.logic = logic;
    };
    if (op.logic == null) {
        write(undefined);
        return `Cleared the logic of the option '${label}' of '${titleText(field)}'`;
    }
    if (!op.logic.conditions?.length) throw new OpError('List should have at least 1 item after validation, not 0');
    if (op.logic.conditions.length > OPTION_CONDITIONS_MAX) throw new OpError(`An option can have at most ${OPTION_CONDITIONS_MAX} conditions.`);
    const conditions = validatedConditions(ctx.state, op.logic.conditions, null);
    const logic = { action: op.logic.action, operator: op.logic.operator ?? 'AND', conditions };
    const candidate = withQuestion(ctx.state, location, { ...field, properties: { ...field.properties, choices: choices.map((c) => (c.id === choice.id ? { ...c, logic } : c)) } } as FormField);
    const problem = newProblem(ctx.state, candidate, field.id);
    if (problem) throw new OpError(problem);
    write(logic);
    const verb = op.logic.action === 'SHOW' ? 'Offer' : 'Hide';
    return `${verb} the option '${label}' of '${titleText(field)}' when ${conditions.length} condition(s) match`;
};

export const setOptionFilter: Handler<SetOptionFilterOp> = (ctx, op) => {
    const { field, location } = optionQuestion(ctx.state, op.fieldId);
    if (op.filter == null) {
        const properties = draftField(ctx.draft, location).properties;
        if (properties && 'optionFilter' in properties) delete (properties as any).optionFilter;
        return `Cleared the option filter of '${titleText(field)}'`;
    }
    if (!op.filter.mapping?.length) throw new OpError('List should have at least 1 item after validation, not 0');
    const { parent: sourceParent, field: source } = locateField(ctx.state, op.filter.fieldId);
    if (sourceParent !== null || !CHOICE_FIELD_TYPES.has(source.type)) throw new OpError(`'${titleText(source)}' is not a single or multiple choice or dropdown question of a page, so options cannot be filtered by it.`);
    const mapping = op.filter.mapping.map((row) => {
        const when = optionOf(source, row.when);
        const show: string[] = [];
        for (const name of row.show ?? []) {
            const option = optionOf(field, name);
            if (!show.includes(option.id)) show.push(option.id);
        }
        return { when: when.id, show };
    });
    const optionFilter: OptionFilter = { fieldId: source.id, mapping };
    const candidate = withQuestion(ctx.state, location, { ...field, properties: { ...field.properties, optionFilter } } as FormField);
    const problem = newProblem(ctx.state, candidate, field.id);
    if (problem) throw new OpError(problem);
    (ensureProperties(draftField(ctx.draft, location), false) as any).optionFilter = optionFilter;
    return `Filtered the options of '${titleText(field)}' by the answer to '${titleText(source)}' (${mapping.length} row(s))`;
};
