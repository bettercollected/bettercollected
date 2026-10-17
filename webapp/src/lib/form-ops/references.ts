/**
 * What still refers to a question that is not there (backend
 * `_prune_references`, the editor's `pruneOrphanedConditions` and
 * `pruneOrphanedPipes`): logic and jump conditions on a missing or internal
 * question (a rule or jump left without conditions goes too) and answer
 * pipes in titles — with `hiddenNames`, also pipes of hidden fields not
 * among them. Jumps to a missing page stay, so the editor can show them as
 * broken.
 *
 * Only references to `gone` (what the op removed) and `hiddenGone` are
 * counted; older orphans are removed too but not counted.
 *
 * The builder's helpers write every rule and title back, changed or not;
 * here the sweep reads a plain document and returns only the changes, so
 * untouched questions keep their references.
 */
import { FieldTypes } from '@app/models/dtos/form';
import { ANSWER_PIPE_NODE } from '@app/utils/answer-piping';

import { childrenOf, isRepeatingGroup, isSlide } from './model';
import type { FormDoc, FormField } from './types';

export interface ReferenceFix {
    /** Indexes into the nested `fields` arrays from `doc.fields`. */
    path: number[];
    /** New values of the changed keys (`undefined` clears one). */
    title?: { value: any };
    logic?: { value: any };
    jumps?: { value: any };
}

export interface ReferenceScope {
    /** Ids of the questions and pages the op removed. */
    gone?: Set<string>;
    /** The declared hidden fields: pipes of other names are removed. */
    hiddenNames?: Set<string>;
    /** Hidden-field names the op removed. */
    hiddenGone?: Set<string>;
}

function liveQuestions(doc: FormDoc): Map<string, FormField> {
    const found = new Map<string, FormField>();
    for (const page of (doc.fields ?? []).filter(isSlide)) {
        for (const field of childrenOf(page)) {
            if (field.id && !field.internal) found.set(field.id, field);
            if (isRepeatingGroup(field)) for (const child of childrenOf(field)) if (child.id && !child.internal) found.set(child.id, child);
        }
    }
    return found;
}

/** The changes that drop dangling references, and how many references to what the op removed they drop. */
export function referenceFixes(doc: FormDoc, scope: ReferenceScope = {}): { fixes: ReferenceFix[]; removed: number } {
    const live = liveQuestions(doc);
    const gone = scope.gone ?? new Set<string>();
    const referredGone = new Set<string>([...gone, ...[...(scope.hiddenGone ?? [])].map((name) => `hidden:${name}`)]);
    let removed = 0;
    const fixes: ReferenceFix[] = [];

    const isLive = (c: any) => {
        if (!live.has(c?.fieldId)) return false;
        if (!c.groupMode || c.groupMode === 'COUNT') return true;
        return !!c.childFieldId && live.has(c.childFieldId);
    };
    /** `conditions` without the dead ones; the same array when all are live. */
    const liveConditions = (conditions: any[]): any[] => {
        if (conditions.every(isLive)) return conditions;
        return conditions.filter((c) => {
            if (isLive(c)) return true;
            if (gone.has(c?.fieldId) || gone.has(c?.childFieldId)) removed++;
            return false;
        });
    };
    /** null when `node` is not an orphaned pipe, else what it referred to. */
    const orphanPipe = (node: any): string[] | null => {
        if (!node || typeof node !== 'object' || node.type !== ANSWER_PIPE_NODE) return null;
        const attrs = node.attrs ?? {};
        const key = attrs.pipeKey;
        if (attrs.kind === 'hidden') return scope.hiddenNames !== undefined && !scope.hiddenNames.has(key) ? [`hidden:${key}`] : null;
        if (attrs.kind === 'group') {
            const parts = String(key ?? '').split(':');
            const group = live.get(parts[0]);
            const childId = parts.length > 2 ? parts[2] : null;
            if (!group || group.type !== FieldTypes.GROUP || (!!childId && !childrenOf(group).some((c) => c.id === childId))) return childId === null ? [parts[0]] : [parts[0], childId];
            return null;
        }
        return live.has(key) ? null : [key];
    };
    /** The node without orphan pipes: the same object when nothing changes. */
    const prunePipes = (node: any): any => {
        if (!node || typeof node !== 'object' || !Array.isArray(node.content)) return node;
        let changed = false;
        const kept: any[] = [];
        for (const child of node.content) {
            const refs = orphanPipe(child);
            if (refs) {
                if (refs.some((ref) => referredGone.has(ref))) removed++;
                changed = true;
                continue;
            }
            const pruned = prunePipes(child);
            if (pruned !== child) changed = true;
            kept.push(pruned);
        }
        return changed ? { ...node, content: kept } : node;
    };
    const pruneQuestion = (field: FormField, path: number[]) => {
        const fix: ReferenceFix = { path };
        if (field.title && typeof field.title === 'object') {
            const title = prunePipes(field.title);
            if (title !== field.title) fix.title = { value: title };
        }
        const logic = field.properties?.logic;
        if (logic != null) {
            const all = logic.conditions ?? [];
            const conditions = liveConditions(all);
            if (!conditions.length) fix.logic = { value: undefined };
            else if (conditions !== all) fix.logic = { value: { ...logic, conditions } };
        }
        if (fix.title || fix.logic) fixes.push(fix);
    };

    (doc.fields ?? []).forEach((page, pagePos) => {
        if (!isSlide(page) || page.properties == null) return;
        const jumps = page.properties.jumps;
        if (jumps != null) {
            let changed = false;
            const kept: any[] = [];
            for (const jump of jumps) {
                const all = jump.conditions ?? [];
                const conditions = liveConditions(all);
                if (!conditions.length) changed = true;
                else if (conditions !== all) {
                    changed = true;
                    kept.push({ ...jump, conditions });
                } else kept.push(jump);
            }
            if (changed || !kept.length) fixes.push({ path: [pagePos], jumps: { value: kept.length ? kept : undefined } });
        }
        childrenOf(page).forEach((field, fieldPos) => {
            pruneQuestion(field, [pagePos, fieldPos]);
            if (isRepeatingGroup(field)) childrenOf(field).forEach((child, childPos) => pruneQuestion(child, [pagePos, fieldPos, childPos]));
        });
    });
    return { fixes, removed };
}
