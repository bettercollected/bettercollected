// Importing responses from a CSV file (docs/response-import.md): the limits the
// screen states, and the small decisions the dialog makes from the server's answer.
import type { ResponseImportDto, ResponseImportProblem, ResponseImportTarget } from '@app/store/workspaces/api';

/** Stated beside the file chooser; the server enforces them (services/response_import/limits.py). */
export const IMPORT_MAX_MB = 5;
export const IMPORT_MAX_ROWS = 5000;
/** How often a running check or import is asked about. */
export const IMPORT_POLL_MS = 1500;

export function importFileTooLarge(file: { size: number }): boolean {
    return file.size > IMPORT_MAX_MB * 1024 * 1024;
}

/** The statuses in which a worker has (or is about to have) the import. */
export const BUSY = new Set(['checking', 'queued', 'running']);
/** The statuses in which the file waits for the importer. */
export const WAITING = new Set(['uploaded', 'checked']);

/** A message key (under RESPONSE_IMPORT) and its values for what the server refused with. */
export function refusalKey(error: any, fallback = 'ERROR_generic'): { key: string; values?: Record<string, unknown> } {
    const data = error?.data ?? {};
    const code: string | undefined = data.code;
    if (error?.status === 429 && (!code || code === 'rate_limited')) return { key: 'ERROR_rate_limited' };
    if (code) return { key: `ERROR_${code}`, values: { mb: IMPORT_MAX_MB, rows: IMPORT_MAX_ROWS, row: data.row ?? '' } };
    if (error?.status === 403) return { key: 'ERROR_forbidden' };
    if (error?.status === 413) return { key: 'ERROR_too_large', values: { mb: IMPORT_MAX_MB } };
    return { key: fallback };
}

/** Which targets are taken by another column: a target is chosen once. */
export function takenTargets(mapping: Record<string, string>, except: string): Set<string> {
    return new Set(
        Object.entries(mapping)
            .filter(([column, key]) => column !== except && key)
            .map(([, key]) => key)
    );
}

/** The mapping as the server takes it: only columns that go somewhere. */
export function cleanMapping(mapping: Record<string, string>): Record<string, string> {
    return Object.fromEntries(Object.entries(mapping).filter(([, key]) => !!key));
}

/** Does the mapping fill at least one question (the server refuses one that fills only the time)? */
export function mapsAQuestion(mapping: Record<string, string>, targets: ResponseImportTarget[]): boolean {
    const byKey = new Map(targets.map((t) => [t.key, t]));
    return Object.values(cleanMapping(mapping)).some((key) => {
        const kind = byKey.get(key)?.kind;
        return kind === 'question' || kind === 'internal' || kind === 'hidden';
    });
}

/** Where a problem is, from what the file and the form tell: its column heading, else its question. */
export function problemPlace(problem: ResponseImportProblem, imp: Pick<ResponseImportDto, 'headers' | 'targets'>): { column?: string; question?: string; columnNumber?: number } {
    const question = problem.field ? imp.targets?.find((t) => t.fieldId === problem.field && t.kind !== 'internal')?.label : undefined;
    if (problem.column === null || problem.column === undefined) return { question };
    return { column: imp.headers[problem.column] || undefined, columnNumber: problem.column + 1, question };
}

/** The name of the encoding the server read the file as, for the mapping step. */
export function encodingLabel(encoding: string): string {
    if (encoding === 'cp1252') return 'Windows-1252';
    return 'UTF-8';
}
