/** Field rules: `set_field_rules` (backend `_apply_set_field_rules`, `_field_rule`). */
import { validateExpression } from '@app/lib/expressions/validator';
import { FIELD_RULES_MAX } from '@app/lib/field-rules';

import { fieldRuleChecker } from '../field-rule-checks';
import { type FieldLocation, OpError, childrenOf, locateField, pyLen, pyStrip, titleText } from '../model';
import type { FieldRuleSpec, FormDoc, FormField, SetFieldRulesOp } from '../types';
import { type Handler, draftField, ensureProperties, setKey } from './context';
import { validatedConditions } from './fields';

export const RULE_ID = /^[A-Za-z0-9_-]{1,64}$/;
export const RULE_CONDITIONS_MAX = 20;
export const RULE_TITLE_MAX_LENGTH = 300;
export const RULE_DESCRIPTION_MAX_LENGTH = 1000;
export const RULE_CONST_MAX_LENGTH = 1000;
export const RULE_EFFECT_KEYS = ['required', 'readOnly', 'title', 'description', 'setValue'] as const;

const given = (value: unknown): boolean => value !== undefined && value !== null;

function expressionProblem(ast: unknown): string | null {
    const problems = validateExpression(ast);
    if (!problems.length) return null;
    return `${problems[0].message}${problems[0].path ? ` (at '${problems[0].path}')` : ''}`;
}

/** The checks the models make while a rule is read (spec and stored model): shape, caps, effects. */
function checkRuleSpec(spec: FieldRuleSpec): void {
    if (!spec || typeof spec !== 'object' || Array.isArray(spec)) throw new OpError('Input should be a valid dictionary');
    if (typeof spec.id !== 'string' || !RULE_ID.test(spec.id)) throw new OpError(`id: String should match pattern '${RULE_ID.source}'`);
    const when = spec.when;
    if (!when || typeof when !== 'object') throw new OpError("A rule's 'when' needs either conditions or an expression (not both).");
    const hasConditions = given(when.conditions);
    const hasExpression = given(when.expression);
    if (hasConditions === hasExpression) throw new OpError("A rule's 'when' needs either conditions or an expression (not both).");
    if (hasConditions) {
        if (!Array.isArray(when.conditions) || !when.conditions.length) throw new OpError("A rule's 'when' needs at least one condition.");
        if (when.conditions.length > RULE_CONDITIONS_MAX) throw new OpError(`List should have at most ${RULE_CONDITIONS_MAX} items after validation, not ${when.conditions.length}`);
        if (when.operator != null && when.operator !== 'AND' && when.operator !== 'OR') throw new OpError("operator: Input should be 'AND' or 'OR'");
    } else {
        if (given(when.operator)) throw new OpError("A rule's 'operator' only combines conditions, not an expression.");
        const problem = expressionProblem(when.expression);
        if (problem) throw new OpError(`A rule's 'when' expression: ${problem}`);
    }
    const then = spec.then;
    if (!then || typeof then !== 'object' || !RULE_EFFECT_KEYS.some((key) => given((then as Record<string, unknown>)[key]))) {
        throw new OpError(`A rule's 'then' needs at least one of: ${RULE_EFFECT_KEYS.join(', ')}.`);
    }
    if (given(then.required) && typeof then.required !== 'boolean') throw new OpError('required: Input should be a valid boolean');
    if (given(then.readOnly) && then.readOnly !== true) throw new OpError('readOnly: Input should be True');
    for (const [key, max] of [
        ['title', RULE_TITLE_MAX_LENGTH],
        ['description', RULE_DESCRIPTION_MAX_LENGTH]
    ] as const) {
        const text = then[key];
        if (!given(text)) continue;
        if (typeof text !== 'string') throw new OpError(`${key}: Input should be a valid string`);
        if (pyLen(text) > max) throw new OpError(`${key}: String should have at most ${max} characters`);
    }
    if (typeof then.title === 'string' && !pyStrip(then.title)) throw new OpError("A rule's title cannot be empty.");
    const value = then.setValue;
    if (given(value)) {
        if (typeof value !== 'object' || Array.isArray(value)) throw new OpError('Input should be a valid dictionary');
        if (given(value!.const) === given(value!.expression)) throw new OpError("'setValue' needs either 'const' or 'expression'.");
        const constant = value!.const;
        if (given(constant)) {
            if (typeof constant === 'number' && !Number.isFinite(constant)) throw new OpError(Number.isNaN(constant) ? "'setValue' cannot be NaN." : "'setValue' must be a finite number.");
            if (typeof constant === 'string' && pyLen(constant) > RULE_CONST_MAX_LENGTH) throw new OpError(`A 'setValue' text can be at most ${RULE_CONST_MAX_LENGTH} characters.`);
            if (!['string', 'number', 'boolean'].includes(typeof constant)) throw new OpError('setValue.const: Input should be a valid string, number or boolean');
        } else {
            const problem = expressionProblem(value!.expression);
            if (problem) throw new OpError(`A 'setValue' expression: ${problem}`);
        }
    }
}

/** The stored rule a spec describes: its conditions resolved against the form like logic's, nothing but what is given. */
function storedRule(doc: FormDoc, spec: FieldRuleSpec, scopeGroupId: string | null): Record<string, any> {
    // Conditions are resolved against the form before the rule's own shape is checked, as on the server,
    // so the same problem is named first.
    const listed = spec?.when?.conditions;
    const resolved = Array.isArray(listed) && listed.length && listed.every((c) => c && typeof c === 'object') ? validatedConditions(doc, listed, scopeGroupId) : undefined;
    checkRuleSpec(spec);
    const when: Record<string, any> = {};
    if (given(spec.when.conditions)) {
        if (given(spec.when.operator)) when.operator = spec.when.operator;
        when.conditions = resolved ?? validatedConditions(doc, spec.when.conditions!, scopeGroupId);
    } else {
        when.expression = spec.when.expression;
    }
    const then: Record<string, any> = {};
    for (const key of RULE_EFFECT_KEYS) {
        const value = (spec.then as Record<string, any>)[key];
        if (!given(value)) continue;
        then[key] = key === 'setValue' ? Object.fromEntries(Object.entries(value).filter(([, v]) => given(v))) : value;
    }
    return { id: spec.id, when, then };
}

/** `doc` with one located question replaced (a plain copy along the path, for checking before the op is made). */
export function docWithField(doc: FormDoc, location: FieldLocation, field: FormField): FormDoc {
    const fields = [...(doc.fields ?? [])];
    const page = fields[location.pagePos];
    const pageFields = [...childrenOf(page)];
    if (location.parent) {
        const group = pageFields[location.parentPos];
        const children = [...childrenOf(group)];
        children[location.position] = field;
        pageFields[location.parentPos] = { ...group, properties: { ...group.properties, fields: children } };
    } else {
        pageFields[location.position] = field;
    }
    fields[location.pagePos] = { ...page, properties: { ...page.properties, fields: pageFields } };
    return { ...doc, fields };
}

export const setFieldRules: Handler<SetFieldRulesOp> = (ctx, op) => {
    const location = locateField(ctx.state, op.fieldId);
    const { parent, field } = location;
    const target = draftField(ctx.draft, location);
    if (!op.rules || !op.rules.length) {
        setKey(ensureProperties(target, false), 'rules', undefined);
        return `Cleared the rules on '${titleText(field)}'`;
    }
    if (!Array.isArray(op.rules)) throw new OpError('Input should be a valid list');
    if (op.rules.length > FIELD_RULES_MAX) throw new OpError(`List should have at most ${FIELD_RULES_MAX} items after validation, not ${op.rules.length}`);
    const rules = op.rules.map((spec) => storedRule(ctx.state, spec, parent ? parent.id : null));
    // Only this question's rules changed: check them (and what spans the
    // form), and refuse what a save would refuse that was not already so.
    const next = docWithField(ctx.state, location, { ...field, properties: { ...field.properties, rules } as any });
    const known = new Set(
        fieldRuleChecker(ctx.state, { only: [field.id] })
            .run()
            .map((problem) => problem.message)
    );
    for (const problem of fieldRuleChecker(next, { only: [field.id] }).run()) if (!known.has(problem.message)) throw new OpError(problem.message);
    ensureProperties(target, false).rules = rules as any;
    return `Set ${rules.length} rule(s) on '${titleText(field)}'`;
};
