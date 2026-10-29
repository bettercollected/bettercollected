import { atom } from 'jotai';

import { PATTERN_HAZARDS, PatternHazard } from '@app/utils/pattern-safety';

/** A pattern the server refused when the form was saved (422 `unsafe_pattern`), as the builder sent it. */
export interface PatternSaveError {
    hazard: PatternHazard;
    regex: string;
}

/**
 * The server's answer to a save that carried a pattern the builder let
 * through (an older client, an API caller's form opened here): question id
 * to what was refused. The pattern box shows it with its usual message until
 * the pattern changes or a save goes through.
 */
export const patternSaveErrorsAtom = atom<Record<string, PatternSaveError>>({});

function regexOfField(fields: any[] | undefined, id: string): string | undefined {
    for (const field of fields ?? []) {
        if (field?.id === id && typeof field?.validations?.regex === 'string') return field.validations.regex;
        const found = regexOfField(field?.properties?.fields, id);
        if (found !== undefined) return found;
    }
    return undefined;
}

/**
 * Read a failed save's response: the refused patterns by question id, or null
 * when it is not an `unsafe_pattern` refusal. `body` is the JSON that was sent.
 */
export function patternSaveErrorsOf(response: any, body: string): Record<string, PatternSaveError> | null {
    const error = response?.error;
    if (error?.status !== 422 || error?.data?.code !== 'unsafe_pattern' || !Array.isArray(error.data.errors)) return null;
    let sent: any;
    try {
        sent = JSON.parse(body);
    } catch {
        return null;
    }
    const found: Record<string, PatternSaveError> = {};
    for (const item of error.data.errors) {
        const regex = regexOfField(sent?.fields, String(item?.fieldId));
        if (regex !== undefined && (PATTERN_HAZARDS as ReadonlyArray<string>).includes(item?.hazard)) found[String(item.fieldId)] = { hazard: item.hazard, regex };
    }
    return found;
}
