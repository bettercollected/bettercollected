import { v4 } from 'uuid';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { JUMP_TARGET_SUBMIT, PageJump } from '@app/models/types/form-builder-shared';

/**
 * Endings: the pages shown after submitting. A form has one or more; a page
 * jump to "submit" may name one (`jump.endingId`), otherwise respondents see
 * the default ending (the one marked `isDefault`, else the first).
 *
 * Twin of the backend's `common/models/standard_form.py` helpers
 * (`with_ending_ids`, `default_ending`, `ending_by_id`): keep them in step.
 */
export interface Ending {
    id?: string;
    name?: string;
    isDefault?: boolean;
    title?: string;
    message?: string;
    buttonText?: string;
    buttonLink?: string;
    layout?: FormSlideLayout;
    imageUrl?: string;
}

/** Longest internal name of an ending (the backend's ENDING_NAME_MAX_LENGTH). */
export const ENDING_NAME_MAX_LENGTH = 60;

/**
 * Every ending with an id: ones stored before endings had ids get
 * `ending-<n>` from their position (1-based; the next free number when that
 * one is taken), exactly as the server derives them on read. Returns a new
 * array (and new objects for the endings it gives an id).
 */
export function withEndingIds<T extends Ending>(endings: T[] | null | undefined): T[] {
    const list = Array.isArray(endings) ? endings : [];
    const used = new Set(list.map((ending) => ending?.id).filter(Boolean) as string[]);
    return list.map((ending, position) => {
        if (ending?.id) return ending;
        let number = position + 1;
        while (used.has(`ending-${number}`)) number += 1;
        const id = `ending-${number}`;
        used.add(id);
        return { ...(ending ?? {}), id } as T;
    });
}

/** The ending a plain submit shows: the one marked default, else the first. */
export function defaultEnding<T extends Ending>(endings: T[] | null | undefined): T | undefined {
    if (!endings?.length) return undefined;
    return endings.find((ending) => ending?.isDefault) ?? endings[0];
}

export function defaultEndingIndex(endings: Ending[] | null | undefined): number {
    if (!endings?.length) return -1;
    const marked = endings.findIndex((ending) => ending?.isDefault);
    return marked >= 0 ? marked : 0;
}

export function endingById<T extends Ending>(endings: T[] | null | undefined, id: string | undefined): T | undefined {
    if (!id) return undefined;
    return endings?.find((ending) => ending?.id === id);
}

/**
 * The ending a respondent sees after submitting, given the ending the
 * deciding jump named (if any): that one when the form has it, else the
 * default ending.
 */
export function endingToShow<T extends Ending>(endings: T[] | null | undefined, endingId: string | undefined): T | undefined {
    const list = withEndingIds(endings);
    return endingById(list, endingId) ?? defaultEnding(list);
}

/**
 * How the builder names an ending: its internal name, else its place
 * ("Ending 2"), or "Thank you" when it is the form's only ending.
 */
export function endingLabel(ending: Ending | undefined, index: number, total: number): string {
    return ending?.name?.trim() || (total > 1 ? `Ending ${index + 1}` : 'Thank you');
}

export function newEndingId(): string {
    return v4();
}

function slideJumps(slide: StandardFormFieldDto | undefined): PageJump[] {
    return (slide?.properties?.jumps as PageJump[] | undefined) ?? [];
}

/** Does this jump show a specific ending (rather than the default one)? */
export function jumpEndingId(jump: PageJump | undefined): string | undefined {
    return jump?.target === JUMP_TARGET_SUBMIT && jump.endingId ? jump.endingId : undefined;
}

/** How many page jumps name this ending. */
export function countJumpsToEnding(slides: StandardFormFieldDto[] | undefined, endingId: string | undefined): number {
    if (!endingId) return 0;
    return (slides ?? []).reduce((count, slide) => count + slideJumps(slide).filter((jump) => jumpEndingId(jump) === endingId).length, 0);
}

/**
 * Can respondents reach this ending? The default ending always (a plain
 * submit shows it); any other only when a jump names it.
 */
export function isEndingReachable(slides: StandardFormFieldDto[] | undefined, endings: Ending[] | undefined, index: number): boolean {
    if (index === defaultEndingIndex(endings)) return true;
    return countJumpsToEnding(slides, endings?.[index]?.id) > 0;
}

/** Does this jump name an ending the form no longer has? */
export function isJumpEndingMissing(jump: PageJump | undefined, endings: Ending[] | undefined): boolean {
    const id = jumpEndingId(jump);
    return !!id && !endingById(endings, id);
}

/**
 * The slides with every jump that names `endingId` showing the default
 * ending instead (they still submit). Returns null when no jump names it.
 * New slide/jump objects; the input is not changed.
 */
export function jumpsFallBackToDefault(slides: StandardFormFieldDto[], endingId: string): { slides: StandardFormFieldDto[]; count: number } | null {
    const count = countJumpsToEnding(slides, endingId);
    if (!count) return null;
    const next = slides.map((slide) => {
        const jumps = slideJumps(slide);
        if (!jumps.some((jump) => jumpEndingId(jump) === endingId)) return slide;
        return {
            ...slide,
            properties: {
                ...slide.properties,
                jumps: jumps.map((jump) => {
                    if (jumpEndingId(jump) !== endingId) return jump;
                    const { endingId: _dropped, ...rest } = jump;
                    return rest;
                })
            }
        } as StandardFormFieldDto;
    });
    return { slides: next, count };
}

/**
 * Jump destinations in the builder's selects are one string: a page id,
 * JUMP_TARGET_SUBMIT (default ending), or `__ENDING__:<id>` for a specific
 * ending. Only the editors use this encoding; jumps are stored as
 * `{ target: JUMP_TARGET_SUBMIT, endingId }`.
 */
export const ENDING_CHOICE_PREFIX = '__ENDING__:';

export function jumpChoiceValue(jump: Pick<PageJump, 'target' | 'endingId'>): string {
    const id = jumpEndingId(jump as PageJump);
    return id ? `${ENDING_CHOICE_PREFIX}${id}` : jump.target;
}

export function jumpFromChoice(value: string): Pick<PageJump, 'target' | 'endingId'> {
    if (value.startsWith(ENDING_CHOICE_PREFIX)) return { target: JUMP_TARGET_SUBMIT, endingId: value.slice(ENDING_CHOICE_PREFIX.length) };
    return { target: value, endingId: undefined };
}
