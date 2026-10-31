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

/** A file-name-safe name made from the form's title (and a table's name); the extension follows the file the server sent. */
export function exportFileName(formTitle: string, extension: 'csv' | 'zip' = 'csv'): string {
    const safe = (text: string) => text.replace(/[\\/:*?"<>|\u0000-\u001f]+/g, ' ').trim() || 'export';
    return `${safe(formTitle)}.${extension}`;
}

/** The extension of what the server sent: a ZIP when a repeating group is a table of its own, else a CSV. */
export function exportExtension(mediaType: string | null | undefined): 'csv' | 'zip' {
    return (mediaType ?? '').toLowerCase().startsWith('application/zip') ? 'zip' : 'csv';
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
