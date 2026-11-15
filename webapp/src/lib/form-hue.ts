/**
 * A stable identity colour for a form, from its id alone.
 *
 * The hue is a hash of the form id, so the same form has the same colour on a
 * card, in an outline and in a report header, in every workspace and on every
 * device. Nothing is stored and nothing is read besides the id: no title, no
 * list position, no workspace, no randomness. Changing `fnv1a32`, the
 * normalisation or the number or order of `PIGMENTS` recolours every form, so
 * form-hue.test.ts pins both the hash and a table of ids.
 */

/** The five pigment keys, in hue order. The index `formHueIndex` returns points into this list. */
export const PIGMENTS = ['tomato', 'sun', 'mint', 'sky', 'orchid'] as const;

export type Pigment = (typeof PIGMENTS)[number];

const FNV_OFFSET_BASIS = 2166136261;
const FNV_PRIME = 16777619;

/** 32-bit FNV-1a over the UTF-8 bytes of `text`, as an unsigned integer. */
export function fnv1a32(text: string): number {
    let hash = FNV_OFFSET_BASIS;
    for (const byte of new TextEncoder().encode(text)) {
        hash = Math.imul(hash ^ byte, FNV_PRIME) >>> 0;
    }
    return hash;
}

/** The hue index, 0 to 4, of a form id (surrounding spaces and letter case do not matter). */
export function formHueIndex(formId: string): number {
    return fnv1a32(formId.trim().toLowerCase()) % PIGMENTS.length;
}

/** The pigment key of a form id. */
export function formPigment(formId: string): Pigment {
    return PIGMENTS[formHueIndex(formId)];
}
