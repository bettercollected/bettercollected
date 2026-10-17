/**
 * Cross-question date-rule checks of the ops engine: the backend's
 * `date_rule_problems` and `prune_date_rules` (common/models/standard_form.py).
 *
 * The builder's twin, `utils/date-rules.ts` `pruneOrphanedDateRules`, applies
 * the same rule but writes every rule list back, changed or not; under immer
 * that would give every date question with rules a new reference on every
 * batch. Here the sweep reads a plain document and reports only the
 * questions whose rules actually change.
 */
import { FieldTypes } from '@app/models/dtos/form';
import { isIsoDate } from '@app/utils/date-rules';

import { DATE_RULES_MAX, OpError, isSlide } from './model';
import type { DateRuleSpec, FormField } from './types';

/** Path of a question: indexes into the nested `fields` arrays from `doc.fields`. */
export type FieldPath = number[];

interface ScopedQuestion {
    question: FormField;
    group: FormField | null;
    path: FieldPath;
}

/** Every question with its repeating group (backend `iter_questions_with_scope`). */
export function questionsWithScope(fields: FormField[] | undefined | null): ScopedQuestion[] {
    const out: ScopedQuestion[] = [];
    (fields ?? []).forEach((top, topPos) => {
        const questions: Array<[FormField, FieldPath]> = isSlide(top) ? ((top.properties?.fields as FormField[] | undefined) ?? []).map((q, i) => [q, [topPos, i]]) : [[top, [topPos]]];
        for (const [question, path] of questions) {
            out.push({ question, group: null, path });
            if (question?.properties?.repeat != null) {
                ((question.properties.fields as FormField[] | undefined) ?? []).forEach((child, childPos) => out.push({ question: child, group: question, path: [...path, childPos] }));
            }
        }
    });
    return out;
}

function questionTitle(field: FormField): string {
    if (typeof field.title === 'string' && field.title.trim()) return field.title.trim();
    return field.id || 'a question';
}

/** Validated, normalised date rules (backend `_date_rules` + DateRule). */
export function checkedDateRules(specs: DateRuleSpec[]): DateRuleSpec[] {
    if (specs.length > DATE_RULES_MAX) throw new OpError(`A date question can have at most ${DATE_RULES_MAX} date rules.`);
    return specs.map((spec) => {
        const rule: DateRuleSpec = { comparison: spec.comparison, target: spec.target };
        if (spec.target === 'date') {
            if (!isIsoDate(spec.date)) throw new OpError('A date rule needs a date written as YYYY-MM-DD.');
            rule.date = spec.date as string;
        } else if (spec.target === 'field') {
            if (typeof spec.fieldId !== 'string' || !spec.fieldId.trim()) throw new OpError('A date rule on another question needs its id.');
            rule.fieldId = spec.fieldId;
        }
        return rule;
    });
}

function findCycle(edges: Map<string, string[]>): string[] | null {
    const state = new Map<string, number>();
    for (const root of edges.keys()) {
        if (state.has(root)) continue;
        const path = [root];
        const pending: Array<{ list: string[]; i: number }> = [{ list: edges.get(root) ?? [], i: 0 }];
        state.set(root, 1);
        while (pending.length) {
            const top = pending[pending.length - 1];
            const target = top.i < top.list.length ? top.list[top.i++] : undefined;
            if (target === undefined) {
                pending.pop();
                state.set(path.pop()!, 2);
            } else if (state.get(target) === 1) {
                return path.slice(path.indexOf(target));
            } else if (!state.has(target)) {
                state.set(target, 1);
                path.push(target);
                pending.push({ list: edges.get(target) ?? [], i: 0 });
            }
        }
    }
    return null;
}

/**
 * Readable problems with the date rules of a form's questions. `override`
 * stands in other rules for one question (to check a patch before it is made).
 */
export function dateRuleProblems(fields: FormField[] | undefined | null, override?: { field: FormField; rules: DateRuleSpec[] | undefined }): string[] {
    const questions = questionsWithScope(fields);
    const rulesOf = (q: FormField): DateRuleSpec[] => (override && q === override.field ? override.rules : (q?.properties?.dateRules as DateRuleSpec[] | undefined)) ?? [];
    const scopes = new Map<string, ScopedQuestion>();
    for (const entry of questions) if (entry.question?.id) scopes.set(String(entry.question.id), entry);
    const problems: string[] = [];
    const edges = new Map<string, string[]>();
    for (const { question, group } of questions) {
        const rules = rulesOf(question);
        if (!rules.length) continue;
        const title = questionTitle(question);
        if (question.type !== FieldTypes.DATE) {
            problems.push(`'${title}' is not a date question, so it cannot have date rules.`);
            continue;
        }
        for (const rule of rules) {
            if (rule.target !== 'field') continue;
            const refId = String(rule.fieldId ?? '');
            if (refId === String(question.id)) {
                problems.push(`A date rule of '${title}' cannot compare it with itself.`);
                continue;
            }
            const entry = scopes.get(refId);
            if (!entry) {
                problems.push(`A date rule of '${title}' uses a question that does not exist (any more).`);
                continue;
            }
            const refTitle = questionTitle(entry.question);
            if (entry.question.type !== FieldTypes.DATE) {
                problems.push(`A date rule of '${title}' uses '${refTitle}', which is not a date question.`);
                continue;
            }
            if (entry.question.internal) {
                problems.push(`A date rule of '${title}' uses the internal field '${refTitle}' — respondents never answer internal fields.`);
                continue;
            }
            const groupId = group?.id ?? null;
            const refGroupId = entry.group?.id ?? null;
            if (groupId !== refGroupId) {
                problems.push(
                    `A date rule of '${title}' uses '${refTitle}' from ` +
                        (groupId ? 'another part of the form' : 'a repeating group') +
                        ": inside a repeating group, rules can only use dates of the same group, and questions outside a group cannot use a group's dates."
                );
                continue;
            }
            const key = String(question.id);
            if (!edges.has(key)) edges.set(key, []);
            edges.get(key)!.push(refId);
        }
    }
    const cycle = findCycle(edges);
    if (cycle) {
        const names = cycle.filter((id) => scopes.has(id)).map((id) => questionTitle(scopes.get(id)!.question));
        problems.push('Date rules cannot depend on each other in a circle (' + [...names, ...names.slice(0, 1)].map((n) => `'${n}'`).join(' → ') + ').');
    }
    return problems;
}

export interface DateRuleFix {
    path: FieldPath;
    /** The rules to keep; undefined clears them. */
    rules: DateRuleSpec[] | undefined;
    dropped: number;
}

/** Does any question have date rules? (cheap: no lists built) */
export function hasDateRules(fields: FormField[] | undefined | null): boolean {
    for (const top of fields ?? []) {
        if (top?.properties?.dateRules?.length) return true;
        for (const question of (top?.properties?.fields as FormField[] | undefined) ?? []) {
            if (question?.properties?.dateRules?.length) return true;
            if (question?.properties?.repeat != null) for (const child of (question.properties.fields as FormField[] | undefined) ?? []) if (child?.properties?.dateRules?.length) return true;
        }
    }
    return false;
}

/**
 * Visit every question with its repeating group's id and where it is: the
 * position of its page (or of itself, for a question outside pages) in
 * `fields`, its position on the page (-1 outside pages) and in its group
 * (-1 outside groups). No lists are built.
 */
function eachQuestion(fields: FormField[] | undefined | null, visit: (question: FormField, groupId: string | null, top: number, position: number, child: number) => void): void {
    const all = fields ?? [];
    for (let top = 0; top < all.length; top++) {
        const item = all[top];
        const questions: FormField[] = isSlide(item) ? ((item.properties?.fields as FormField[] | undefined) ?? []) : [item];
        for (let position = 0; position < questions.length; position++) {
            const question = questions[position];
            const at = isSlide(item) ? position : -1;
            visit(question, null, top, at, -1);
            if (question?.properties?.repeat != null) {
                const children = (question.properties.fields as FormField[] | undefined) ?? [];
                for (let child = 0; child < children.length; child++) visit(children[child], question.id ?? null, top, at, child);
            }
        }
    }
}

const pathOf = (top: number, position: number, child: number): FieldPath => [top, ...(position >= 0 ? [position] : []), ...(child >= 0 ? [child] : [])];

/**
 * The date rules a structural edit left dangling, as fixes to make (backend
 * `prune_date_rules`, which drops them in place): rules of questions that are
 * no longer dates, and rules on a question that was removed, made internal,
 * is no longer a date or is in another scope.
 */
export function dateRuleFixes(fields: FormField[] | undefined | null): DateRuleFix[] {
    if (!hasDateRules(fields)) return [];
    const scopes = new Map<string, [FormField, string | null]>();
    eachQuestion(fields, (question, groupId) => {
        if (question?.id) scopes.set(String(question.id), [question, groupId]);
    });
    const fixes: DateRuleFix[] = [];
    eachQuestion(fields, (question, groupId, top, position, child) => {
        const rules = (question?.properties?.dateRules as DateRuleSpec[] | undefined) ?? [];
        if (!rules.length) return;
        const kept =
            question.type !== FieldTypes.DATE
                ? []
                : rules.filter((rule) => {
                      if (rule.target !== 'field') return true;
                      const entry = scopes.get(String(rule.fieldId));
                      if (!entry || entry[0] === question) return false;
                      if (entry[0].type !== FieldTypes.DATE || entry[0].internal) return false;
                      return groupId === entry[1];
                  });
        if (kept.length !== rules.length) fixes.push({ path: pathOf(top, position, child), rules: kept.length ? kept : undefined, dropped: rules.length - kept.length });
    });
    return fixes;
}

/** Ids of every question some date rule compares with. */
export function dateRuleSources(fields: FormField[] | undefined | null): Set<string> {
    const sources = new Set<string>();
    for (const { question } of questionsWithScope(fields)) {
        for (const rule of (question?.properties?.dateRules as DateRuleSpec[] | undefined) ?? []) if (rule.fieldId) sources.add(rule.fieldId);
    }
    return sources;
}
