/**
 * The Open Formulieren export download (backend GET
 * /workspaces/{id}/forms/{form_id}/open-formulieren-export, behind
 * OPEN_FORMULIEREN_EXPORT): a zip, its file name in Content-Disposition and the
 * number of things that did not make the trip in X-Open-Formulieren-Unmapped
 * (both exposed through CORS). The file name is only ever used as a download
 * name: reduced to the characters the backend writes.
 */
export interface OpenFormulierenExport {
    blob: Blob;
    fileName: string;
    unmapped: number;
}

export const FALLBACK_EXPORT_FILE_NAME = 'form-open-formulieren.zip';

/** The file name from a Content-Disposition header, or the fallback. */
export function exportFileName(disposition: string | null | undefined): string {
    const found = /filename="([a-z0-9-]{1,80}\.zip)"/.exec(disposition ?? '');
    return found ? found[1] : FALLBACK_EXPORT_FILE_NAME;
}

/** The count of the unmapped header: a whole number, 0 when absent or not one. */
export function unmappedCount(value: string | null | undefined): number {
    return /^\d{1,6}$/.test(value ?? '') ? Number(value) : 0;
}

export function openFormulierenExportOf(blob: Blob, response?: Response): OpenFormulierenExport {
    return {
        blob,
        fileName: exportFileName(response?.headers.get('Content-Disposition')),
        unmapped: unmappedCount(response?.headers.get('X-Open-Formulieren-Unmapped'))
    };
}

/** Save the archive through a temporary link (the way the CSV download does). */
export function saveExport({ blob, fileName }: OpenFormulierenExport): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
