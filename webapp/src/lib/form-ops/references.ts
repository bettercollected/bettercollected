/**
 * What still refers to a question or page that is gone (backend
 * `_prune_references`, the editor's `pruneOrphanedConditions` and
 * `pruneOrphanedPipes`): logic and jump conditions on a missing or internal
 * question (a rule or jump left without conditions goes too), jumps to a
 * missing page, and answer pipes in titles — with `hiddenNames`, also pipes
 * of hidden fields not among them.
 *
 * The builder's helpers write every rule and title back, changed or not;
 * here the sweep reads a plain document and returns only the changes, so
 * untouched questions keep their references.
 */
import { FieldTypes } from '@app/models/dtos/form';
import { ANSWER_PIPE_NODE } from '@app/utils/answer-piping';

import { JUMP_TARGET_SUBMIT, childrenOf, isRepeatingGroup, isSlide } from './model';
import type { FormDoc, FormField } from './types';

export interface ReferenceFix {
    /** Indexes into the nested `fields` arrays from `doc.fields`. */
    path: number[];
    /** New values of the changed keys (`undefined` clears one). */
    title?: { value: any };
    logic?: { value: any };
    jumps?: { value: any };
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

/** The changes that drop dangling references, and how many references they drop. */
export function referenceFixes(doc: FormDoc, hiddenNames?: Set<string>): { fixes: ReferenceFix[]; removed: number } {
    const live = liveQuestions(doc);
    const pageIds = new Set((doc.fields ?? []).filter(isSlide).map((p) => p.id));
    let removed = 0;
    const fixes: ReferenceFix[] = [];

    const isLive = (c: any) => {
        if (!live.has(c?.fieldId)) return false;
        if (!c.groupMode || c.groupMode === 'COUNT') return true;
        return !!c.childFieldId && live.has(c.childFieldId);
    };
    const isOrphanPipe = (node: any): boolean => {
        if (!node || typeof node !== 'object' || node.type !== ANSWER_PIPE_NODE) return false;
        const attrs = node.attrs ?? {};
        const key = attrs.pipeKey;
        if (attrs.kind === 'hidden') return hiddenNames !== undefined && !hiddenNames.has(key);
        if (attrs.kind === 'group') {
            const parts = String(key ?? '').split(':');
            const group = live.get(parts[0]);
            const childId = parts.length > 2 ? parts[2] : null;
            return !group || group.type !== FieldTypes.GROUP || (!!childId && !childrenOf(group).some((c) => c.id === childId));
        }
        return !live.has(key);
    };
    /** The node without orphan pipes: the same object when nothing changes. */
    const prunePipes = (node: any): any => {
        if (!node || typeof node !== 'object' || !Array.isArray(node.content)) return node;
        let changed = false;
        const kept: any[] = [];
        for (const child of node.content) {
            if (isOrphanPipe(child)) {
                removed++;
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
            const conditions = all.filter(isLive);
            if (conditions.length !== all.length) {
                removed += all.length - conditions.length;
                fix.logic = { value: conditions.length ? { ...logic, conditions } : undefined };
            } else if (!conditions.length) {
                fix.logic = { value: undefined };
            }
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
                const conditions = all.filter(isLive);
                removed += all.length - conditions.length;
                if (!conditions.length) {
                    changed = true;
                    continue;
                }
                if (jump.target !== JUMP_TARGET_SUBMIT && !pageIds.has(jump.target)) {
                    removed++;
                    changed = true;
                    continue;
                }
                if (conditions.length !== all.length) {
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
