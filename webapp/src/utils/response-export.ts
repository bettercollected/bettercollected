import { StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';

/**
 * The export of a form's responses is built on the server (docs/response-export.md,
 * backend services/response_export): streamed for a small set, a background job
 * for a large one. What stays here is what the screens share with it.
 */

export type ExportCell = string | number;

/** Joins the options of a multi-select answer inside one cell (a comma would read as a column break). */
export const LIST_SEPARATOR = '; ';

const cell = (value: any): ExportCell => (value === undefined || value === null ? '' : typeof value === 'number' ? value : String(value));

/** Answer of one child question in one item of a repeating group, formatted like any other answer (multi-select joined with the export's '; ' unless the screen passes its own). */
export function getItemAnswer(item: Record<string, any> | undefined, child: StandardFormFieldDto, listSeparator: string = LIST_SEPARATOR): ExportCell {
    return cell(getAnswerForField({ answers: item ?? {} } as StandardFormResponseDto, child, listSeparator));
}

/** The formats the Export control offers (the server's `format`). */
export type ExportFormat = 'csv' | 'xlsx' | 'json';
export const EXPORT_FORMATS: ExportFormat[] = ['csv', 'xlsx', 'json'];
export type ExportExtension = 'csv' | 'zip' | 'xlsx' | 'json' | 'pdf';

export function isExportFormat(value: unknown): value is ExportFormat {
    return typeof value === 'string' && (EXPORT_FORMATS as string[]).includes(value);
}

/** A file-name-safe name made from the form's title (and a table's name); the extension follows the file the server sent. */
export function exportFileName(formTitle: string, extension: ExportExtension = 'csv'): string {
    const safe = (text: string) => text.replace(/[\\/:*?"<>|\u0000-\u001f]+/g, ' ').trim() || 'export';
    return `${safe(formTitle)}.${extension}`;
}

/** The extension of what the server sent: a ZIP when a repeating group is a table of its own, a workbook, JSON, else a CSV. */
export function exportExtension(mediaType: string | null | undefined): ExportExtension {
    const type = (mediaType ?? '').toLowerCase();
    if (type.startsWith('application/zip')) return 'zip';
    if (type.startsWith('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')) return 'xlsx';
    if (type.startsWith('application/json')) return 'json';
    if (type.startsWith('application/pdf')) return 'pdf';
    return 'csv';
}

/** Hands a file to the browser's download. */
export function downloadBlob(blob: Blob, fileName: string) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
