/**
 * Undo: the ops that take a batch back.
 *
 * The engine never changes a document in place, so the state before the
 * batch is the untouched input: the entities a batch touched are found by
 * reference (unchanged pages and questions keep theirs), and the inverse is
 * the entity diff from the result back to that input — side effects included
 * (date rules a removal dropped on other questions, the welcome page title an
 * info update changed, ...).
 */
import { entityDiff } from './entity-diff';
import { childrenOf, isRepeatingGroup, isSlide, jsonEqual } from './model';
import type { FormDoc, FormField, FormOp, Touched } from './types';

export function buildInverse(prev: FormDoc, next: FormDoc): FormOp[] {
    return entityDiff(next, prev);
}

function questions(pages: FormField[]): Map<string, FormField> {
    const out = new Map<string, FormField>();
    for (const page of pages) {
        for (const field of childrenOf(page)) {
            out.set(field.id, field);
            if (isRepeatingGroup(field)) for (const child of childrenOf(field)) out.set(child.id, child);
        }
    }
    return out;
}

const pageOwn = (page: FormField) => ({ ...page, index: undefined, properties: { ...page.properties, fields: undefined } });

/** The pages, questions and form-level keys that differ between two documents (by reference). */
export function touchedEntities(prev: FormDoc, next: FormDoc): Touched {
    const touched: Touched = { pages: new Set(), fields: new Set(), form: new Set() };
    for (const key of new Set([...Object.keys(prev), ...Object.keys(next)])) {
        if (key !== 'fields' && (prev as Record<string, any>)[key] !== (next as Record<string, any>)[key]) touched.form.add(key);
    }
    if (prev.fields === next.fields) return touched;
    const prevPages = (prev.fields ?? []).filter(isSlide);
    const nextPages = (next.fields ?? []).filter(isSlide);
    const prevById = new Map(prevPages.map((p) => [p.id, p]));
    const nextById = new Map(nextPages.map((p) => [p.id, p]));
    const changedPrev = prevPages.filter((p) => nextById.get(p.id) !== p);
    const changedNext = nextPages.filter((p) => prevById.get(p.id) !== p);
    for (const page of changedPrev) {
        const after = nextById.get(page.id);
        if (!after || !jsonEqual(pageOwn(page), pageOwn(after))) touched.pages.add(page.id);
    }
    for (const page of changedNext) if (!prevById.has(page.id)) touched.pages.add(page.id);
    // pages whose order changed
    const kept = prevPages.filter((p) => nextById.has(p.id)).map((p) => p.id);
    const keptNext = nextPages.filter((p) => prevById.has(p.id)).map((p) => p.id);
    kept.forEach((id, k) => {
        if (keptNext[k] !== id) touched.pages.add(id);
    });
    const before = questions(changedPrev);
    const after = questions(changedNext);
    for (const [id, field] of before) if (after.get(id) !== field) touched.fields.add(id);
    for (const id of after.keys()) if (!before.has(id)) touched.fields.add(id);
    return touched;
}
