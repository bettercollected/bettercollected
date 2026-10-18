/**
 * Compaction: fold an op log into fewer ops with the same effect — typing in
 * a title makes one `update_field` per keystroke, and an undo step that
 * coalesces them needs only the last.
 *
 * Only consecutive ops on the same target fold, and only when the later one
 * sets everything the earlier one did (so the earlier one leaves no trace):
 *  - `update_field` on the same question whose patch keys are covered by the
 *    later patch's keys;
 *  - `replace_field` on the same question, `update_page` on the same page
 *    with covered keys, `set_field_logic` / `set_page_jumps` on the same
 *    target, and the whole-value form ops (`update_theme`,
 *    `set_hidden_fields`, `set_form_language`): the later one wins.
 */
import type { FormOp } from './types';

const keysCovered = (earlier: object, later: object) => Object.keys(earlier).every((key) => key in later);

function folds(earlier: FormOp, later: FormOp): boolean {
    if (earlier.op !== later.op) return false;
    switch (earlier.op) {
        case 'update_field': {
            const next = later as typeof earlier;
            return earlier.fieldId === next.fieldId && keysCovered(earlier.patch ?? {}, next.patch ?? {});
        }
        case 'replace_field':
            return earlier.field?.id === (later as typeof earlier).field?.id;
        case 'update_page': {
            const next = later as typeof earlier;
            return earlier.pageId === next.pageId && keysCovered(earlier.patch ?? {}, next.patch ?? {});
        }
        case 'update_welcome_page':
            return keysCovered(earlier.patch ?? {}, (later as typeof earlier).patch ?? {});
        case 'update_logo':
            return keysCovered(earlier, later);
        case 'set_field_logic':
            return earlier.fieldId === (later as typeof earlier).fieldId;
        case 'set_page_jumps':
            return earlier.pageId === (later as typeof earlier).pageId;
        case 'update_theme':
        case 'set_hidden_fields':
        case 'set_form_language':
            return true;
        default:
            return false;
    }
}

/** `ops` with consecutive ops that the next one overrides left out. */
export function compactOps(ops: FormOp[]): FormOp[] {
    const out: FormOp[] = [];
    for (const op of ops) {
        while (out.length && folds(out[out.length - 1], op)) out.pop();
        out.push(op);
    }
    return out;
}
