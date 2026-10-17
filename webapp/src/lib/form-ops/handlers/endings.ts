/**
 * Ending ops: add, update and remove an ending, and (editor only) set them
 * all. Backend twin: the "Endings" block of ops.py, word for word.
 *
 * An ending is a page shown after submitting. A form keeps at least one; a
 * page jump to `__SUBMIT__` may name one (`endingId`), otherwise respondents
 * see the default ending (the one marked `isDefault`, else the first).
 * Endings stored before they had ids get `ending-<n>` (utils/endings.ts);
 * an op that changes the endings writes the whole list back with its ids.
 */
import { FormSlideLayout } from '@app/models/enums/form';
import { endingById, withEndingIds } from '@app/utils/endings';

import { formImageUrls } from '../images';
import { ENDING_BUTTON_TEXT_MAX_LENGTH, ENDING_ID_PATTERN, ENDING_MESSAGE_MAX_LENGTH, ENDING_NAME_MAX_LENGTH, ENDING_TITLE_MAX_LENGTH, JUMP_TARGET_SUBMIT, MAX_ENDINGS, OpError, hasOwn, pyLen } from '../model';
import type { AddEndingOp, EndingPatch, FormDoc, PageJumpSpec, RemoveEndingOp, SetEndingsOp, UpdateEndingOp } from '../types';
import { type Handler, type OpContext, ensureProperties } from './context';
import { editorImage } from './editor';
import { checkedPolicyUrl } from './form';

type Ending = NonNullable<FormDoc['thankyouPage']>[number];

const NEW_ENDING_LAYOUT = FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND;
const LAYOUTS = new Set<string>(Object.values(FormSlideLayout));
const BUTTON_LINK_ERROR = "The ending button's link must be an http(s) URL.";
/** What each text key is called in messages, and its limit (backend `_ENDING_TEXTS`). */
const ENDING_TEXTS: Array<[keyof EndingPatch & keyof Ending, string, number]> = [
    ['title', 'title', ENDING_TITLE_MAX_LENGTH],
    ['message', 'message', ENDING_MESSAGE_MAX_LENGTH],
    ['buttonText', 'button text', ENDING_BUTTON_TEXT_MAX_LENGTH]
];
/** The keys an ending has (others are dropped, as the backend model drops them). */
const ENDING_KEYS = ['id', 'name', 'isDefault', 'title', 'message', 'buttonText', 'buttonLink', 'layout', 'imageUrl'] as const;

/** The form's endings with their ids, as plain objects (no draft). */
function endingsOf(state: FormDoc): Ending[] {
    return withEndingIds(state.thankyouPage ?? []);
}

function findEnding(state: FormDoc, endingId: string): Ending {
    const ending = endingById(endingsOf(state), endingId);
    if (!ending) throw new OpError(`Ending '${endingId}' not found.`);
    return ending;
}

const endingLabel = (ending: Ending) => ending.name || ending.title || ending.id || '';

/** A copy without unset keys (the backend never stores null). */
function compact(ending: Record<string, any>): Ending {
    const out: Record<string, any> = {};
    for (const key of ENDING_KEYS) if (ending[key] !== undefined && ending[key] !== null) out[key] = ending[key];
    return out as Ending;
}

function checkLayout(layout: unknown): void {
    if (layout != null && !LAYOUTS.has(String(layout))) throw new OpError(`layout: Input should be ${[...LAYOUTS].map((l) => `'${l}'`).join(', ')}`);
}

/** The text limits of an ending (backend `_check_ending_texts`). */
function checkTexts(values: Partial<Record<'name' | 'title' | 'message' | 'buttonText', string | null | undefined>>): void {
    if (values.name != null && pyLen(values.name.trim()) > ENDING_NAME_MAX_LENGTH) throw new OpError(`An ending's name can be at most ${ENDING_NAME_MAX_LENGTH} characters.`);
    for (const [key, label, limit] of ENDING_TEXTS) {
        const value = values[key as 'title'];
        if (value != null && pyLen(value) > limit) throw new OpError(`An ending's ${label} can be at most ${limit} characters.`);
    }
}

const checkedLink = (link: string) => checkedPolicyUrl(link, BUTTON_LINK_ERROR);

/**
 * `ending` with `patch` applied, and what changed in words; checked as a
 * whole first, so a refused patch changes nothing (backend `_patch_ending`).
 * `others` are unmarked when the patch makes this ending the default.
 */
function patched(ending: Ending, patch: EndingPatch): { ending: Ending; changed: string[]; takesDefault: boolean } {
    checkTexts(patch);
    checkLayout(patch.layout);
    const link = patch.buttonLink != null ? checkedLink(patch.buttonLink) : undefined;
    const next: Record<string, any> = { ...ending };
    const changed: string[] = [];
    if (patch.name != null) {
        next.name = patch.name.trim() || undefined;
        changed.push('name');
    }
    for (const [key, label] of ENDING_TEXTS) {
        const value = patch[key];
        if (value != null) {
            next[key] = value || undefined;
            changed.push(label);
        }
    }
    if (patch.buttonLink != null) {
        next.buttonLink = link || undefined;
        changed.push('button link');
    }
    if (patch.layout != null) {
        next.layout = patch.layout;
        changed.push('layout');
    }
    let takesDefault = false;
    if (patch.isDefault) {
        next.isDefault = true;
        takesDefault = true;
        changed.push('default');
    } else if (patch.isDefault === false) {
        delete next.isDefault;
        changed.push('default');
    }
    return { ending: compact(next), changed, takesDefault };
}

/** Write `endings` as the form's endings, the default moved to `defaultId` when given. */
function writeEndings(ctx: OpContext, endings: Ending[], defaultId?: string): void {
    const list = defaultId === undefined ? endings : endings.map((e) => (e.id === defaultId ? e : e.isDefault ? compact({ ...e, isDefault: undefined }) : e));
    ctx.draft.thankyouPage = list as any;
}

export const addEnding: Handler<AddEndingOp> = (ctx, op) => {
    const endings = endingsOf(ctx.state);
    if (endings.length >= MAX_ENDINGS) throw new OpError(`A form can have at most ${MAX_ENDINGS} endings.`);
    const { ending, takesDefault } = patched({ id: ctx.newId(), layout: NEW_ENDING_LAYOUT }, op);
    const at = op.index == null ? endings.length : Math.max(0, Math.min(op.index, endings.length));
    writeEndings(ctx, [...endings.slice(0, at), ending, ...endings.slice(at)], takesDefault ? ending.id : undefined);
    ctx.noteCreated(ending.id!);
    return `Added the ending '${endingLabel(ending)}'`;
};

export const updateEnding: Handler<UpdateEndingOp> = (ctx, op) => {
    const current = findEnding(ctx.state, op.endingId);
    const { ending, changed, takesDefault } = patched(current, op.patch ?? {});
    if (!changed.length) return `Nothing to change on the ending '${endingLabel(current)}'`;
    writeEndings(
        ctx,
        endingsOf(ctx.state).map((e) => (e.id === current.id ? ending : e)),
        takesDefault ? ending.id : undefined
    );
    return `Updated the ending '${endingLabel(ending)}' (${changed.join(', ')})`;
};

export const removeEnding: Handler<RemoveEndingOp> = (ctx, op) => {
    const ending = findEnding(ctx.state, op.endingId);
    const endings = endingsOf(ctx.state);
    if (endings.length <= 1) throw new OpError('A form keeps at least one ending; change this one instead.');
    writeEndings(
        ctx,
        endings.filter((e) => e.id !== ending.id)
    );
    // Its jumps still submit; they lose the ending, so respondents see the default ending instead.
    let count = 0;
    (ctx.state.fields ?? []).forEach((page, pos) => {
        const jumps = (page.properties?.jumps as any[] | undefined) ?? [];
        if (!jumps.some((jump) => jump?.endingId === ending.id)) return;
        ensureProperties(ctx.draft.fields![pos], false).jumps = jumps.map((jump) => {
            if (jump?.endingId !== ending.id) return jump;
            count++;
            const { endingId: _dropped, ...rest } = jump;
            return rest;
        }) as any;
    });
    const note = count ? ` (and ${count} jump(s) to it now show the default ending)` : '';
    return `Removed the ending '${endingLabel(ending)}'${note}`;
};

/** Is this jump's ending one of the form's (backend `_check_jump_ending`)? */
export function checkJumpEnding(state: FormDoc, spec: PageJumpSpec): void {
    if (spec.endingId == null) return;
    if (spec.target !== JUMP_TARGET_SUBMIT) throw new OpError(`A jump chooses an ending only with target "${JUMP_TARGET_SUBMIT}".`);
    findEnding(state, spec.endingId);
}

/** The endings as a whole, ids kept; jumps are left as they are (backend `_apply_set_endings`). */
export const setEndings: Handler<SetEndingsOp> = (ctx, op) => {
    const raw = op.endings;
    if (!Array.isArray(raw)) throw new OpError('endings: Input should be a valid list');
    if (raw.length > MAX_ENDINGS) throw new OpError(`A form can have at most ${MAX_ENDINGS} endings.`);
    const keep = formImageUrls(ctx.state);
    const endings: Ending[] = raw.map((item) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) throw new OpError('Each ending must be an object.');
        const ending = compact(item);
        if (ending.id != null && (typeof ending.id !== 'string' || !ENDING_ID_PATTERN.test(ending.id))) throw new OpError(`String should match pattern '${ENDING_ID_PATTERN.source}'`);
        if (ending.name != null && pyLen(String(ending.name)) > ENDING_NAME_MAX_LENGTH) throw new OpError(`String should have at most ${ENDING_NAME_MAX_LENGTH} characters`);
        checkLayout(ending.layout);
        checkTexts({ title: ending.title, message: ending.message, buttonText: ending.buttonText });
        const out: Record<string, any> = { ...ending };
        if (hasOwn(out, 'buttonLink')) out.buttonLink = checkedLink(String(out.buttonLink)) || undefined;
        if (hasOwn(out, 'imageUrl')) out.imageUrl = editorImage(out.imageUrl, keep, ctx.options) || undefined;
        return compact(out);
    });
    const seen = new Set<string>();
    for (const ending of withEndingIds(endings)) {
        if (seen.has(ending.id!)) throw new OpError(`The ending id '${ending.id}' is used more than once.`);
        seen.add(ending.id!);
    }
    if (endings.filter((e) => e.isDefault).length > 1) throw new OpError('Only one ending can be the default.');
    if (endings.length) ctx.draft.thankyouPage = endings as any;
    else delete ctx.draft.thankyouPage;
    return `Set ${endings.length} ending(s)`;
};
